import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { api, blockingError, useApi } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";
import PredictionResult, { PredictionTally } from "../components/PredictionResult";
import ScoringInfo from "../components/ScoringInfo";
import { gameweekScoreSummary } from "../utils/scoring";

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
    <>
      <PageHeader
        title={`Gameweek ${number}`}
        back={
          <Link to="/predict" className="back-link">
            &larr; Predict
          </Link>
        }
        actions={<ScoringInfo />}
      >
        {data && summary.hasPredictions && (
          <div className="score-summary">
            <div className="scoreboard">
              <span className="scoreboard-figure">{summary.totalPoints}</span>
              <span className="scoreboard-label">{summary.stillToPlay > 0 ? "points so far" : "points"}</span>
            </div>
            <PredictionTally fixtures={data.fixtures} />
          </div>
        )}
      </PageHeader>

      <main className="page">
        {error && <div className="error-banner">{error}</div>}

        {data === undefined && !error && <LoadingIndicator />}
        {data === null && <p className="muted">Gameweek {number} doesn't exist.</p>}

        {data && !summary.hasPredictions && (
          <p className="muted">You didn't submit any predictions for this gameweek.</p>
        )}

        {data && summary.hasPredictions && (
          <div className="fixture-list">
            {data.fixtures.map((fixture) => (
              <FixtureRow fixture={fixture} key={fixture.id} footer={<PredictionResult fixture={fixture} />} />
            ))}
          </div>
        )}
      </main>
    </>
  );
}
