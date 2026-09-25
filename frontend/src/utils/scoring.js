// Mirrors backend/predictions/scoring.py's calculate_points - used to show a
// live points estimate for fixtures that have finished but haven't gone
// through the official score_gameweeks batch yet (prediction.points, once
// set, is authoritative and takes precedence over this).
export function calculatePoints(predictedHome, predictedAway, actualHome, actualAway) {
  if (predictedHome === actualHome && predictedAway === actualAway) {
    return actualHome + actualAway >= 5 ? 4 : 3;
  }
  const result = (home, away) => (home > away ? "H" : home < away ? "A" : "D");
  return result(predictedHome, predictedAway) === result(actualHome, actualAway) ? 1 : 0;
}

// Named as in the "How scoring works" dialog.
export const POINTS_DESCRIPTIONS = {
  0: "Wrong result",
  1: "Correct result",
  3: "Exact score",
  4: "Exact score, 5+ goals",
};

export function isFixtureFinished(fixture) {
  return fixture.status === "FINISHED" && fixture.home_score != null && fixture.away_score != null;
}

export function fixturePoints(fixture) {
  const prediction = fixture.prediction;
  if (!prediction || !isFixtureFinished(fixture)) return null;
  return (
    prediction.points ??
    calculatePoints(prediction.predicted_home_score, prediction.predicted_away_score, fixture.home_score, fixture.away_score)
  );
}

// How a gameweek's predictions went, match by match: exact scores (3 or 4
// points), correct results (1), wrong results (0), and ones still to finish.
export function predictionTally(fixtures) {
  const tally = { exact: 0, result: 0, wrong: 0, pending: 0 };
  fixtures.forEach((fixture) => {
    if (!fixture.prediction) return;
    const points = fixturePoints(fixture);
    if (points == null) tally.pending += 1;
    else if (points >= 3) tally.exact += 1;
    else if (points === 1) tally.result += 1;
    else tally.wrong += 1;
  });
  return tally;
}

export function gameweekScoreSummary(gwScore) {
  if (!gwScore) return null;
  const predicted = gwScore.fixtures.filter((f) => f.prediction != null);
  const finished = predicted.filter(isFixtureFinished);
  const totalPoints = finished.reduce((sum, f) => sum + fixturePoints(f), 0);
  return {
    hasPredictions: predicted.length > 0,
    fullyPredicted: gwScore.fixtures.length > 0 && predicted.length === gwScore.fixtures.length,
    totalPoints,
    stillToPlay: predicted.length - finished.length,
  };
}
