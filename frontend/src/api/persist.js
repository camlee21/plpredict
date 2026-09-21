import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { hydrate } from "@tanstack/react-query";
import { persistQueryClientSubscribe } from "@tanstack/react-query-persist-client";
import { CACHE_TIME } from "./freshness";

const PERSIST_KEY = "plpredict-cache";

// Vercel exposes the deployed commit to Create React App builds under this
// name. A new deploy then starts from an empty cache, so a response whose
// shape changed can never be read back by code expecting the old one.
export const CACHE_BUSTER = process.env.REACT_APP_VERCEL_GIT_COMMIT_SHA || "local";

export const PERSIST_MAX_AGE = CACHE_TIME;

/** Saves the query cache to localStorage, so a reload or a new tab starts
 * with your last data on screen while it's re-checked in the background. */
export function createPersister() {
  return createSyncStoragePersister({
    storage: typeof window === "undefined" ? undefined : window.localStorage,
    key: PERSIST_KEY,
  });
}

/** Removes the saved copy straight away, rather than waiting for the
 * persister's next (throttled) save of the now-empty cache. */
export function clearPersistedCache() {
  try {
    window.localStorage.removeItem(PERSIST_KEY);
  } catch {
    // Storage can be unavailable (private windows, blocked site data).
  }
}

/**
 * Loads the saved cache into `queryClient` before the app first renders. The
 * library's own provider restores asynchronously, which shows every page's
 * loading state for a moment on each reload; reading localStorage directly
 * avoids that. A copy from an older deploy, or older than PERSIST_MAX_AGE,
 * is thrown away instead.
 */
export function restoreSavedCache(queryClient) {
  const persister = createPersister();
  try {
    const saved = persister.restoreClient();
    if (!saved) return;
    const usable = saved.buster === CACHE_BUSTER && Date.now() - saved.timestamp <= PERSIST_MAX_AGE;
    if (usable) hydrate(queryClient, saved.clientState);
    else clearPersistedCache();
  } catch {
    // Unreadable or from an incompatible version: start from nothing.
    clearPersistedCache();
  }
}

/** Saves the cache whenever it changes (at most once a second). Returns a
 * function that stops saving. */
export function saveCacheAsItChanges(queryClient) {
  return persistQueryClientSubscribe({ queryClient, persister: createPersister(), buster: CACHE_BUSTER });
}
