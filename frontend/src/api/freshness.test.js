import { SCORING_GRACE, liveGameweekNumbers, nextBoundary, shouldRetry } from "./freshness";

const HOUR = 60 * 60 * 1000;
const NOW = Date.parse("2026-10-10T15:00:00Z");
const at = (offsetMs) => new Date(NOW + offsetMs).toISOString();

// A gameweek that locks `lockIn` from now and is finalised `finaliseIn` from now.
const gw = (number, lockIn, finaliseIn, extra = {}) => ({
  number,
  deadline: at(lockIn),
  finalize_after: at(finaliseIn),
  is_scored: false,
  ...extra,
});

describe("liveGameweekNumbers", () => {
  test("nothing is live before a gameweek's deadline", () => {
    expect(liveGameweekNumbers([gw(6, 2 * HOUR, 50 * HOUR)], NOW).size).toBe(0);
  });

  test("a gameweek is live from its deadline until it's finalised", () => {
    const live = liveGameweekNumbers([gw(5, -30 * HOUR, -60 * HOUR, { is_scored: true }), gw(6, -1 * HOUR, 40 * HOUR)], NOW);
    expect([...live]).toEqual([6]);
  });

  test("it stays live for a grace period after finalising, until it's actually scored", () => {
    expect(liveGameweekNumbers([gw(6, -50 * HOUR, -SCORING_GRACE / 2)], NOW).has(6)).toBe(true);
    expect(liveGameweekNumbers([gw(6, -50 * HOUR, -SCORING_GRACE - 1000)], NOW).has(6)).toBe(false);
  });

  test("once scored, it's no longer live even inside the window", () => {
    expect(liveGameweekNumbers([gw(6, -1 * HOUR, 40 * HOUR, { is_scored: true })], NOW).size).toBe(0);
  });

  test("gameweeks without a schedule are ignored, as is a missing list", () => {
    expect(liveGameweekNumbers([{ number: 7, deadline: null, finalize_after: null, is_scored: false }], NOW).size).toBe(0);
    expect(liveGameweekNumbers(undefined, NOW).size).toBe(0);
  });
});

describe("nextBoundary", () => {
  test("between gameweeks, it's the next deadline", () => {
    expect(nextBoundary([gw(6, 5 * HOUR, 60 * HOUR), gw(7, 200 * HOUR, 260 * HOUR)], NOW)).toBe(NOW + 5 * HOUR);
  });

  test("during a live gameweek, it's the end of its window", () => {
    expect(nextBoundary([gw(6, -1 * HOUR, 40 * HOUR), gw(7, 200 * HOUR, 260 * HOUR)], NOW)).toBe(
      NOW + 40 * HOUR + SCORING_GRACE
    );
  });

  test("scored gameweeks don't count, and nothing ahead gives null", () => {
    expect(nextBoundary([gw(38, 5 * HOUR, 60 * HOUR, { is_scored: true })], NOW)).toBeNull();
    expect(nextBoundary([], NOW)).toBeNull();
  });
});

describe("shouldRetry", () => {
  test("retries network failures and server errors, twice at most", () => {
    expect(shouldRetry(0, new TypeError("Failed to fetch"))).toBe(true);
    expect(shouldRetry(1, { status: 503 })).toBe(true);
    expect(shouldRetry(2, { status: 503 })).toBe(false);
  });

  test("never retries an answer like 403 or 404", () => {
    expect(shouldRetry(0, { status: 404 })).toBe(false);
    expect(shouldRetry(0, { status: 403 })).toBe(false);
  });
});
