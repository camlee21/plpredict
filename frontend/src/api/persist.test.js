import { CACHE_BUSTER, PERSIST_MAX_AGE, clearPersistedCache, restoreSavedCache } from "./persist";
import { createQueryClient } from "./queries";

const KEY = "plpredict-cache";

function save({ buster = CACHE_BUSTER, age = 0 } = {}) {
  const source = createQueryClient();
  source.setQueryData(["predictions", "history"], { overall_total: 21 });
  const clientState = {
    mutations: [],
    queries: source.getQueryCache().getAll().map((query) => ({
      queryKey: query.queryKey,
      queryHash: query.queryHash,
      state: query.state,
    })),
  };
  localStorage.setItem(KEY, JSON.stringify({ buster, timestamp: Date.now() - age, clientState }));
}

beforeEach(() => localStorage.clear());

describe("restoreSavedCache", () => {
  test("loads a current save before anything renders", () => {
    save();
    const client = createQueryClient();
    restoreSavedCache(client);
    expect(client.getQueryData(["predictions", "history"])).toEqual({ overall_total: 21 });
  });

  test("throws away a save from a different deploy", () => {
    save({ buster: "some-older-commit" });
    const client = createQueryClient();
    restoreSavedCache(client);
    expect(client.getQueryData(["predictions", "history"])).toBeUndefined();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  test("throws away a save that's too old", () => {
    save({ age: PERSIST_MAX_AGE + 1000 });
    const client = createQueryClient();
    restoreSavedCache(client);
    expect(client.getQueryData(["predictions", "history"])).toBeUndefined();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  test("survives a corrupted save", () => {
    localStorage.setItem(KEY, "{not json");
    const client = createQueryClient();
    expect(() => restoreSavedCache(client)).not.toThrow();
    expect(localStorage.getItem(KEY)).toBeNull();
  });

  test("does nothing when there's no save", () => {
    const client = createQueryClient();
    restoreSavedCache(client);
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });

  test("clearPersistedCache removes the save", () => {
    save();
    clearPersistedCache();
    expect(localStorage.getItem(KEY)).toBeNull();
  });
});
