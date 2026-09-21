import { blockingError, createQueryClient, forgetLeague, queryKeys } from "./queries";

describe("blockingError", () => {
  test("shows an error when there's nothing cached to fall back on", () => {
    expect(blockingError({ error: { message: "Server down", status: 500 }, data: undefined })).toBe("Server down");
  });

  test("stays quiet when older data is still on screen", () => {
    expect(blockingError({ error: { message: "Server down", status: 500 }, data: [] })).toBe("");
  });

  test("ignores statuses the page handles itself", () => {
    expect(blockingError({ error: { message: "Not found", status: 404 }, data: undefined }, { ignoreStatus: [404] })).toBe("");
  });
});

describe("forgetLeague", () => {
  test("removes the league from cached lists at once and drops its own pages", async () => {
    const client = createQueryClient();
    const mine = [{ public_id: "AAA", name: "Keep" }, { public_id: "BBB", name: "Gone" }];
    client.setQueryData(queryKeys.myLeagues, mine);
    client.setQueryData(queryKeys.homeSummary, mine);
    client.setQueryData(queryKeys.league("BBB"), { name: "Gone" });
    client.setQueryData(queryKeys.leagueMember("BBB", 3), { username: "x" });
    client.setQueryData(queryKeys.league("AAA"), { name: "Keep" });

    // Nothing is mounted, so invalidation just marks queries stale.
    await forgetLeague(client, "BBB");

    expect(client.getQueryData(queryKeys.myLeagues).map((l) => l.public_id)).toEqual(["AAA"]);
    expect(client.getQueryData(queryKeys.homeSummary).map((l) => l.public_id)).toEqual(["AAA"]);
    expect(client.getQueryData(queryKeys.league("BBB"))).toBeUndefined();
    expect(client.getQueryData(queryKeys.leagueMember("BBB", 3))).toBeUndefined();
    expect(client.getQueryData(queryKeys.league("AAA"))).toEqual({ name: "Keep" });
    expect(client.getQueryState(queryKeys.league("AAA")).isInvalidated).toBe(true);
  });
});
