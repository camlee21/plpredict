import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import { FixtureRow } from "../components/FixtureRow";
import { gameweekScoreSummary, predictionFooter } from "../utils/scoring";

export default function GameweekScorePage() {
  const { number } = useParams();
  const [data, setData] = useState(undefined);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(undefined);
    setError("");
    apiRequest(`/api/predictions/gameweek/${number}/`)
      .then(setData)
      .catch((err) => {
        if (err.status === 404) {
          setData(null);
        } else {
          setError(err.message);
        }
      });
  }, [number]);

  const summary = useMemo(() => gameweekScoreSummary(data), [data]);

  return (
    <div className="page">
      <Link to="/" className="back-link">
        &larr; Back to home
      </Link>
      <h1>Gameweek {number} score</h1>
      {error && <div className="error-banner">{error}</div>}

      {data === undefined && !error && <p>Loading...</p>}
      {data === null && <p className="muted">Gameweek {number} doesn't exist.</p>}

      {data && !summary.hasPredictions && (
        <p className="muted">
          No predictions submitted for this week. <Link to="/predict">Make predictions</Link>.
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
