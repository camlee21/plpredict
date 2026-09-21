import { apiRequest } from "./client";
import { api, createQueryClient, warmCache } from "./queries";

jest.mock("./client", () => ({ apiRequest: jest.fn() }));

const RESPONSES = {
  "/api/fixtures/gameweeks/current/": { number: 6 },
  "/api/fixtures/gameweeks/home/": { number: 6, fixtures: [] },
  "/api/leagues/": [{ public_id: "AAA" }, { public_id: "BBB" }],
  "/api/predictions/history/": { overall_total: 12, by_gameweek: [] },
  "/api/leagues/home-summary/": [],
  "/api/leagues/browse/?filter=recent": [],
  "/api/predictions/gameweek/6/": { gameweek: 6, fixtures: [] },
  "/api/fixtures/gameweeks/6/": { number: 6, fixtures: [] },
  "/api/leagues/AAA/": { name: "A" },
  "/api/leagues/BBB/": { name: "B" },
};

beforeEach(() => {
  apiRequest.mockReset();
  apiRequest.mockImplementation((path) =>
    path in RESPONSES ? Promise.resolve(RESPONSES[path]) : Promise.reject(Object.assign(new Error("nope"), { status: 404 }))
  );
});

describe("api", () => {
  test("a gameweek's key is the same whether its number came from a URL or the API", () => {
    expect(api.predictionsGameweek("6").queryKey).toEqual(api.predictionsGameweek(6).queryKey);
    expect(api.predictionsGameweek(6).path).toBe("/api/predictions/gameweek/6/");
  });

  test("browse only sends a search when there is one", () => {
    expect(api.browseLeagues("", "recent").path).toBe("/api/leagues/browse/?filter=recent");
    expect(api.browseLeagues("office", "capacity_desc").path).toBe(
      "/api/leagues/browse/?search=office&filter=capacity_desc"
    );
  });
});

describe("warmCache", () => {
  test("loads the main pages' data, then what depends on it", async () => {
    const client = createQueryClient();
    await warmCache(client);

    // The current gameweek's predictions and fixtures, and every league's standings.
    expect(client.getQueryData(api.predictionsGameweek(6).queryKey)).toEqual({ gameweek: 6, fixtures: [] });
    expect(client.getQueryData(api.gameweekDetail(6).queryKey)).toEqual({ number: 6, fixtures: [] });
    expect(client.getQueryData(api.league("AAA").queryKey)).toEqual({ name: "A" });
    expect(client.getQueryData(api.league("BBB").queryKey)).toEqual({ name: "B" });
    expect(client.getQueryData(api.history().queryKey)).toEqual({ overall_total: 12, by_gameweek: [] });
  });

  test("skips anything already cached and fresh", async () => {
    const client = createQueryClient();
    await warmCache(client);
    apiRequest.mockClear();

    await warmCache(client);
    expect(apiRequest).not.toHaveBeenCalled();
  });

  test("a failure (e.g. no gameweeks synced yet) doesn't stop the rest", async () => {
    apiRequest.mockImplementation((path) =>
      path.startsWith("/api/fixtures/")
        ? Promise.reject(Object.assign(new Error("No gameweeks"), { status: 404 }))
        : Promise.resolve(RESPONSES[path])
    );
    const client = createQueryClient();
    await expect(warmCache(client)).resolves.toBeUndefined();
    expect(client.getQueryData(api.league("AAA").queryKey)).toEqual({ name: "A" });
  });
});
