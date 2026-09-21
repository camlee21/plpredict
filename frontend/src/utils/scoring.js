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

export const POINTS_DESCRIPTIONS = {
  0: "no correct result",
  1: "correct result",
  3: "exact score",
  4: "exact score, 5+ goals",
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

export function predictionFooter(fixture, label = "Your prediction") {
  const prediction = fixture.prediction;
  if (!prediction) return "No prediction submitted";
  const predictedLine = `${label}: ${prediction.predicted_home_score}-${prediction.predicted_away_score}`;
  if (!isFixtureFinished(fixture)) return `${predictedLine} · Awaiting result`;
  const points = fixturePoints(fixture);
  return `${predictedLine} · ${points} pt${points === 1 ? "" : "s"} (${POINTS_DESCRIPTIONS[points]})`;
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
