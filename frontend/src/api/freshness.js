// How long fetched data is trusted before it's re-checked. The app's data
// only changes when the backend's sync job runs (every 5-10 minutes, from
// cron-job.org) and only really moves while a gameweek is being played, so
// the rules below lean on that: long-lived between gameweeks, polled while
// one is live. Tune them here - nothing else hard-codes a timing.

// Between gameweeks: re-check at most this often (on navigating back, or on
// returning to the tab). Kickoff times occasionally move, so not forever.
export const QUIET_STALE_TIME = 15 * 60 * 1000;

// While a gameweek is live, navigating back re-checks anything older than
// this, and on-screen data is polled every LIVE_POLL_INTERVAL. Polling faster
// than the sync job runs gains nothing, so keep this near the cron interval.
export const LIVE_STALE_TIME = 30 * 1000;
export const LIVE_POLL_INTERVAL = 60 * 1000;

// How long cached data is kept - in memory, and saved in the browser for
// reloads and new tabs. Older than this and a page loads from scratch.
// Anything kept is still re-checked by the rules above before being trusted.
export const CACHE_TIME = 24 * 60 * 60 * 1000;

// Other people join and leave public leagues at any time, regardless of the
// gameweek, so the browse list is re-checked more readily.
export const BROWSE_STALE_TIME = 60 * 1000;

// A gameweek is marked as scored by the same cron job, some time after its
// finalise time. Stay in live mode this long past it so that change (which
// moves it into the score strip) is picked up promptly.
export const SCORING_GRACE = 60 * 60 * 1000;

/**
 * The gameweeks "in play" at `now`: from their prediction deadline (when they
 * lock - an hour before kickoff) until they're scored, or SCORING_GRACE past
 * their finalise time, whichever comes first.
 */
export function liveGameweekNumbers(gameweeks, now) {
  const live = new Set();
  for (const gw of gameweeks ?? []) {
    if (gw.is_scored || !gw.deadline || !gw.finalize_after) continue;
    const start = Date.parse(gw.deadline);
    const end = Date.parse(gw.finalize_after) + SCORING_GRACE;
    if (now >= start && now <= end) live.add(gw.number);
  }
  return live;
}

/**
 * The next moment the rules above change their answer - a deadline passing
 * (a gameweek locks and goes live) or a live window closing. Null if nothing
 * is coming up.
 */
export function nextBoundary(gameweeks, now) {
  let next = null;
  for (const gw of gameweeks ?? []) {
    if (gw.is_scored) continue;
    const times = [
      gw.deadline && Date.parse(gw.deadline),
      gw.finalize_after && Date.parse(gw.finalize_after) + SCORING_GRACE,
    ];
    for (const t of times) {
      if (t && t > now && (next === null || t < next)) next = t;
    }
  }
  return next;
}

/** Retry network hiccups and server errors, but not a 403/404 - those are answers. */
export function shouldRetry(failureCount, error) {
  if (failureCount >= 2) return false;
  return !error?.status || error.status >= 500;
}
