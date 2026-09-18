import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../api/client";
import { FixtureRow } from "../components/FixtureRow";
import { gameweekScoreSummary } from "../utils/scoring";

export default function HomePage() {
  const [lastScore, setLastScore] = useState(undefined);
  const [leagueSummaries, setLeagueSummaries] = useState(null);
  const [gwScore, setGwScore] = useState(undefined);
  const [gameweek, setGameweek] = useState(undefined);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest("/api/predictions/history/")
      .then((history) => {
        const entries = history.by_gameweek;
        setLastScore(entries.length ? entries[entries.length - 1] : null);
      })
      .catch((err) => setError(err.message));

    apiRequest("/api/leagues/home-summary/")
      .then(setLeagueSummaries)
      .catch((err) => setError(err.message));

    apiRequest("/api/fixtures/gameweeks/current/")
      .then((current) => apiRequest(`/api/predictions/gameweek/${current.number}/`).then(setGwScore))
      .catch((err) => {
        if (err.status === 404) {
          setGwScore(null);
        } else {
          setError(err.message);
        }
      });

    apiRequest("/api/fixtures/gameweeks/home/")
      .then(setGameweek)
      .catch((err) => {
        if (err.status === 404) {
          setGameweek(null);
        } else {
          setError(err.message);
        }
      });
  }, []);

  const gwScoreSummary = useMemo(() => gameweekScoreSummary(gwScore), [gwScore]);

  return (
    <div className="page">
      <h1>Home</h1>
      {error && <div className="error-banner">{error}</div>}

      {lastScore && (
        <Link to={`/scores/${lastScore.gameweek}`} className="card home-last-score home-last-score-link">
          <h2>Your last score</h2>
          <p className="score-highlight">{lastScore.points} pts</p>
          <p className="muted">Gameweek {lastScore.gameweek}</p>
        </Link>
      )}

      {gwScore !== null && (
        <>
          <h2>This gameweek's score</h2>
          {gwScore === undefined && <p>Loading...</p>}
          {gwScore && (
            <div className="league-row-list">
              <div className="league-row">
                <span className="league-row-name">Gameweek {gwScore.gameweek}</span>
                <span className="league-row-detail muted">
                  {gwScoreSummary.hasPredictions ? `${gwScoreSummary.totalPoints} pts` : "No predictions"}
                </span>
                <span className="league-row-detail muted">
                  {gwScoreSummary.hasPredictions
                    ? gwScoreSummary.stillToPlay > 0
                      ? `${gwScoreSummary.stillToPlay} to play`
                      : "All played"
                    : ""}
                </span>
                <Link to={`/scores/${gwScore.gameweek}`} className="league-row-action">
                  View breakdown
                </Link>
              </div>
            </div>
          )}
        </>
      )}

      <h2>Your leagues</h2>
      {leagueSummaries === null && <p>Loading...</p>}
      {leagueSummaries && leagueSummaries.length === 0 && (
        <p className="muted">
          You're not in any leagues yet. <Link to="/leagues">Create or join one</Link>.
        </p>
      )}
      {leagueSummaries && leagueSummaries.length > 0 && (
        <div className="league-row-list">
          {leagueSummaries.slice(0, 5).map((league) => (
            <div className="league-row" key={league.public_id}>
              <span className="league-row-name">{league.name}</span>
              <span className="league-row-detail muted">{league.rank_display}</span>
              <span className="league-row-detail muted">{league.total_points} pts</span>
              <Link to={`/leagues/${league.public_id}`} className="league-row-action">
                View league
              </Link>
            </div>
          ))}
        </div>
      )}
      {leagueSummaries && leagueSummaries.length > 5 && (
        <Link to="/leagues" className="back-link">
          View all {leagueSummaries.length} leagues &rarr;
        </Link>
      )}

      <h2>
        {gameweek ? `${gameweek.phase === "upcoming" ? "Next gameweek" : "This gameweek"}: Gameweek ${gameweek.number}` : "Fixtures"}
      </h2>
      {gameweek === undefined && <p>Loading...</p>}
      {gameweek === null && (
        <p className="muted">
          No gameweeks are loaded yet. Run <code>python manage.py sync_fixtures</code> on the backend
          to pull fixtures from the Fantasy Premier League API.
        </p>
      )}
      {gameweek && (
        <>
          <div className="fixture-list">
            {gameweek.fixtures.map((fixture) => (
              <FixtureRow fixture={fixture} key={fixture.id} />
            ))}
          </div>
          <Link to="/fixtures" className="back-link">
            See all gameweeks, scores &amp; form &rarr;
          </Link>
        </>
      )}
    </div>
  );
}
