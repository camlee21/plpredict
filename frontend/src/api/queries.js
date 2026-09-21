import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "./client";
import {
  CACHE_TIME,
  LIVE_POLL_INTERVAL,
  LIVE_STALE_TIME,
  QUIET_STALE_TIME,
  liveGameweekNumbers,
  nextBoundary,
  shouldRetry,
} from "./freshness";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: QUIET_STALE_TIME,
        // Kept at least as long as the saved copy (see persist.js), or
        // entries would be dropped from memory before they could be saved.
        gcTime: CACHE_TIME,
        refetchOnWindowFocus: true,
        retry: shouldRetry,
      },
    },
  });
}

// --- Every GET endpoint, with its cache key ---------------------------------

const endpoint = (queryKey, path) => ({ queryKey, path });

// The one place each endpoint's URL and cache key are defined. Pages read
// through these and prefetching warms the same entries, so the two can never
// disagree about what a key holds. Keys are nested so e.g. ["leagues"] covers
// every league query when something invalidates them.
export const api = {
  gameweeks: () => endpoint(["gameweeks"], "/api/fixtures/gameweeks/"),
  currentGameweek: () => endpoint(["gameweeks", "current"], "/api/fixtures/gameweeks/current/"),
  homeGameweek: () => endpoint(["gameweeks", "home"], "/api/fixtures/gameweeks/home/"),
  gameweekDetail: (number) =>
    endpoint(["gameweeks", "detail", Number(number)], `/api/fixtures/gameweeks/${number}/`),
  predictionsGameweek: (number) =>
    endpoint(["predictions", "gameweek", Number(number)], `/api/predictions/gameweek/${number}/`),
  history: () => endpoint(["predictions", "history"], "/api/predictions/history/"),
  myLeagues: () => endpoint(["leagues", "mine"], "/api/leagues/"),
  homeSummary: () => endpoint(["leagues", "home-summary"], "/api/leagues/home-summary/"),
  browseLeagues: (search, filter) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    params.set("filter", filter);
    return endpoint(["leagues", "browse", search, filter], `/api/leagues/browse/?${params.toString()}`);
  },
  league: (publicId) => endpoint(["leagues", "detail", publicId], `/api/leagues/${publicId}/`),
  leagueMember: (publicId, userId) =>
    endpoint(
      ["leagues", "detail", publicId, "members", Number(userId)],
      `/api/leagues/${publicId}/members/${userId}/`
    ),
  leagueMemberGameweek: (publicId, userId, number) =>
    endpoint(
      ["leagues", "detail", publicId, "members", Number(userId), "gameweek", Number(number)],
      `/api/leagues/${publicId}/members/${userId}/gameweek/${number}/`
    ),
};

// Key prefixes for invalidating whole groups at once.
export const queryKeys = {
  gameweeks: api.gameweeks().queryKey,
  leagues: ["leagues"],
  myLeagues: api.myLeagues().queryKey,
  homeSummary: api.homeSummary().queryKey,
  predictionsGameweek: (number) => api.predictionsGameweek(number).queryKey,
  league: (publicId) => api.league(publicId).queryKey,
  leagueMember: (publicId, userId) => api.leagueMember(publicId, userId).queryKey,
};

// --- Live gameweek detection -------------------------------------------------

const FreshnessContext = createContext({ liveGameweeks: new Set() });

// A setTimeout longer than this overflows and fires immediately.
const MAX_TIMEOUT = 2 ** 31 - 1;

/**
 * Works out whether a gameweek is being played right now, from the gameweek
 * list's deadlines and finalise times, and shares that with every query via
 * useApi. It also wakes up at the next deadline or end of a live window and
 * re-checks what's on screen, so e.g. the Predict page flips to its locked
 * view the moment predictions close. Once you're logged in it also warms
 * the cache for the main pages (see warmCache).
 */
export function FreshnessProvider({ children }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [now, setNow] = useState(() => Date.now());
  const gameweeksEndpoint = api.gameweeks();

  // Read straight from the cache so this query's own polling can depend on
  // the answer it produces; useQuery below re-renders us when it changes.
  const cached = queryClient.getQueryData(gameweeksEndpoint.queryKey);
  const liveGameweeks = useMemo(() => liveGameweekNumbers(cached, now), [cached, now]);
  const live = liveGameweeks.size > 0;

  const { data: gameweeks } = useQuery({
    queryKey: gameweeksEndpoint.queryKey,
    queryFn: () => apiRequest(gameweeksEndpoint.path),
    enabled: Boolean(user),
    staleTime: live ? LIVE_STALE_TIME : QUIET_STALE_TIME,
    refetchInterval: live ? LIVE_POLL_INTERVAL : false,
  });

  useEffect(() => {
    const next = nextBoundary(gameweeks, now);
    if (next === null) return undefined;
    const timer = setTimeout(() => {
      const current = Date.now();
      setNow(current);
      // A deadline or live window just ended: locks, lifecycles and scores
      // may all have moved, so everything on screen is worth re-checking.
      if (current >= next) queryClient.invalidateQueries();
    }, Math.min(Math.max(next - Date.now() + 1000, 0), MAX_TIMEOUT));
    return () => clearTimeout(timer);
  }, [gameweeks, now, queryClient]);

  const userId = user?.id;
  useEffect(() => {
    if (userId != null) warmCache(queryClient);
  }, [userId, queryClient]);

  const value = useMemo(() => ({ liveGameweeks }), [liveGameweeks]);
  return <FreshnessContext.Provider value={value}>{children}</FreshnessContext.Provider>;
}

export function useFreshness() {
  return useContext(FreshnessContext);
}

// --- Reading and prefetching -----------------------------------------------

/**
 * useQuery for one of the `api` endpoints, with the refresh rules applied:
 * cached between gameweeks, polled while one is live. Pass `gameweek` for
 * data about one specific gameweek, so only the live one is polled - a
 * finished gameweek's results don't change just because another one is on.
 */
export function useApi({ queryKey, path }, { gameweek, enabled = true, staleTime, ...options } = {}) {
  const { liveGameweeks } = useFreshness();
  const live = gameweek == null ? liveGameweeks.size > 0 : liveGameweeks.has(Number(gameweek));
  return useQuery({
    queryKey,
    queryFn: () => apiRequest(path),
    enabled,
    staleTime: staleTime ?? (live ? LIVE_STALE_TIME : QUIET_STALE_TIME),
    refetchInterval: live ? LIVE_POLL_INTERVAL : false,
    ...options,
  });
}

/**
 * Loads an endpoint into the cache ahead of time, unless a fresh copy is
 * already there. Never throws - a failed prefetch just means the page loads
 * it itself when you get there.
 */
export function prefetch(queryClient, { queryKey, path }) {
  return queryClient
    .prefetchQuery({ queryKey, queryFn: () => apiRequest(path), staleTime: QUIET_STALE_TIME })
    .then(() => queryClient.getQueryData(queryKey));
}

/**
 * Fetches what the main pages open with, so the first visit to each is as
 * instant as a return visit: the gameweek list, your scores and leagues, the
 * current gameweek's fixtures and your predictions for it, and each of your
 * leagues' standings. Anything already cached and fresh is skipped, so on a
 * reload this usually costs nothing.
 */
export async function warmCache(queryClient) {
  const [current, home, leagues] = await Promise.all([
    prefetch(queryClient, api.currentGameweek()),
    prefetch(queryClient, api.homeGameweek()),
    prefetch(queryClient, api.myLeagues()),
    prefetch(queryClient, api.history()),
    prefetch(queryClient, api.homeSummary()),
    prefetch(queryClient, api.browseLeagues("", "recent")),
  ]);
  const follow = [];
  if (current) follow.push(prefetch(queryClient, api.predictionsGameweek(current.number)));
  if (home) follow.push(prefetch(queryClient, api.gameweekDetail(home.number)));
  for (const league of leagues ?? []) follow.push(prefetch(queryClient, api.league(league.public_id)));
  await Promise.all(follow);
}

/** Prefetches `targets` (endpoints) whenever the set of them changes - e.g.
 * the gameweeks either side of the one you're looking at, so stepping to the
 * next one is instant. */
export function usePrefetch(targets) {
  const queryClient = useQueryClient();
  const latest = useRef(targets);
  latest.current = targets;
  const signature = JSON.stringify(targets.map((target) => target.queryKey));
  useEffect(() => {
    latest.current.forEach((target) => prefetch(queryClient, target));
  }, [signature, queryClient]);
}

/** Event handlers that prefetch `target` the moment you show intent to open
 * it - hovering, focusing or touching - so by the time the click lands the
 * data is usually already there. */
export function usePrefetchOnIntent() {
  const queryClient = useQueryClient();
  return (target) => {
    const start = () => {
      if (target) prefetch(queryClient, target);
    };
    return { onPointerEnter: start, onFocus: start, onTouchStart: start };
  };
}

// --- Helpers for pages -------------------------------------------------------

/**
 * The message to show for a failed query - but only when there's nothing
 * cached to show instead. A background re-check failing while older data is
 * on screen stays quiet and is simply retried on the next check.
 */
export function blockingError(query, { ignoreStatus = [] } = {}) {
  if (!query.error || query.data !== undefined) return "";
  if (ignoreStatus.includes(query.error.status)) return "";
  return query.error.message;
}

/**
 * After leaving or deleting a league: drop it from the cached lists straight
 * away (so it never flashes back up while they re-fetch), forget its own
 * cached pages, then refresh every other league query in the background.
 */
export function forgetLeague(queryClient, publicId) {
  const withoutIt = (leagues) => leagues?.filter((league) => league.public_id !== publicId);
  queryClient.setQueryData(queryKeys.myLeagues, withoutIt);
  queryClient.setQueryData(queryKeys.homeSummary, withoutIt);
  queryClient.removeQueries({ queryKey: queryKeys.league(publicId) });
  return queryClient.invalidateQueries({ queryKey: queryKeys.leagues, refetchType: "all" });
}
