import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { api, blockingError, useApi } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import ScoringInfo from "../components/ScoringInfo";
import { gameweekScoreSummary, predictionFooter } from "../utils/scoring";

export default function GameweekScorePage() {
  const { number } = useParams();
  const query = useApi(api.predictionsGameweek(number), {
    gameweek: number,
  });
  // undefined while loading, null for a gameweek that doesn't exist.
  const data = query.error?.status === 404 ? null : query.data;
  const error = blockingError(query, { ignoreStatus: [404] });

  const summary = useMemo(() => gameweekScoreSummary(data), [data]);

  return (
    <div className="page">
      <Link to="/predict" className="back-link">
        &larr; Back to predictions
      </Link>
      <div className="heading-row">
        <h1>Gameweek {number} score</h1>
        <ScoringInfo />
      </div>
      {error && <div className="error-banner">{error}</div>}

      {data === undefined && !error && <p>Loading...</p>}
      {data === null && <p className="muted">Gameweek {number} doesn't exist.</p>}

      {data && !summary.hasPredictions && (
        <p className="muted">
          No predictions submitted for this week.
        </p>
      )}

      {data && summary.hasPredictions && (
        <>
          <div className="card home-last-score">
            <p className="score-highlight">{summary.totalPoints} pts</p>
            <p className="muted">
              {summary.stillToPlay > 0
                ? `${summary.stillToPlay} fixture${summary.stillToPlay === 1 ? "" : "s"} still to play`
                : "All fixtures finished"}
            </p>
          </div>
          <div className="fixture-list">
            {data.fixtures.map((fixture) => (
              <FixtureRow fixture={fixture} key={fixture.id} footer={predictionFooter(fixture)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
