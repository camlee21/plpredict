import { POINTS_DESCRIPTIONS, fixturePoints, predictionTally } from "../utils/scoring";

// Sits under a fixture: what was predicted, and once the match is over, the
// points it earned and why. `who` names the predictor, e.g. "You" or "jess.w".
export default function PredictionResult({ fixture, who = "You" }) {
  const prediction = fixture.prediction;
  if (!prediction) {
    return <div className="prediction-result is-none">No prediction submitted</div>;
  }

  const points = fixturePoints(fixture);
  const scored = points != null;
  return (
    <div className={`prediction-result${scored ? ` points-${points}` : " is-pending"}`}>
      <span className="prediction-pick">
        <span className="prediction-who">{who} predicted</span>
        <span className="prediction-score">
          {prediction.predicted_home_score}
          <span className="score-box-sep">-</span>
          {prediction.predicted_away_score}
        </span>
      </span>
      {scored ? (
        <span className="prediction-outcome">
          <span className={`points-badge points-${points}`}>
            {points} {points === 1 ? "pt" : "pts"}
          </span>
          <span className="prediction-reason">{POINTS_DESCRIPTIONS[points]}</span>
        </span>
      ) : (
        <span className="prediction-reason">
          {fixture.status === "LIVE" ? (
            <span className="live-tag">
              <span className="live-dot" aria-hidden="true" />
              Live
            </span>
          ) : (
            "Awaiting result"
          )}
        </span>
      )}
    </div>
  );
}

// A one-line breakdown for the page header, e.g. "2 exact, 1 correct result".
export function PredictionTally({ fixtures }) {
  const tally = predictionTally(fixtures);
  const items = [
    [tally.exact, tally.exact === 1 ? "exact score" : "exact scores", "exact"],
    [tally.result, tally.result === 1 ? "correct result" : "correct results", "result"],
    [tally.wrong, "wrong", "wrong"],
    [tally.pending, "to play", "pending"],
  ].filter(([count, , kind]) => count > 0 || kind === "exact");

  return (
    <ul className="prediction-tally">
      {items.map(([count, label, kind]) => (
        <li key={kind} className={`tally-${kind}`}>
          <strong>{count}</strong> {label}
        </li>
      ))}
    </ul>
  );
}
