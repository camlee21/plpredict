import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../api/client";

export default function HomePage() {
  const [lastScore, setLastScore] = useState(undefined);
  const [leagueSummaries, setLeagueSummaries] = useState(null);
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

  return (
    <div className="page">
      <h1>Home</h1>
      {error && <div className="error-banner">{error}</div>}

      {lastScore && (
        <div className="card home-last-score">
          <h2>Your last score</h2>
          <p className="score-highlight">{lastScore.points} pts</p>
          <p className="muted">Gameweek {lastScore.gameweek}</p>
        </div>
      )}

      <h2>Your leagues</h2>
      {leagueSummaries === null && <p>Loading...</p>}
      {leagueSummaries && leagueSummaries.length === 0 && (
        <p className="muted">
          You're not in any leagues yet. <Link to="/leagues">Create or join one</Link>.
        </p>
      )}
      <div className="league-grid">
        {leagueSummaries?.map((league) => (
          <Link to={`/leagues/${league.public_id}`} key={league.public_id} className="card league-card">
            <h3>{league.name}</h3>
            <p className="muted">Position: {league.rank_display}</p>
            <p className="muted">{league.total_points} pts</p>
          </Link>
        ))}
      </div>

      <h2>
        {gameweek ? `${gameweek.phase === "upcoming" ? "Next gameweek" : "This gameweek"} — Gameweek ${gameweek.number}` : "Fixtures"}
      </h2>
      {gameweek === undefined && <p>Loading...</p>}
      {gameweek === null && (
        <p className="muted">
          No gameweeks are loaded yet. Run <code>python manage.py sync_fixtures</code> on the backend
          once a FOOTBALL_DATA_API_KEY is configured.
        </p>
      )}
      {gameweek && (
        <div className="fixture-list">
          {gameweek.fixtures.map((fixture) => (
            <div className="card fixture-row" key={fixture.id}>
              <span className="team home">{fixture.home_team.name}</span>
              <span className="score-sep">
                {fixture.status === "FINISHED" ? `${fixture.home_score} - ${fixture.away_score}` : "vs"}
              </span>
              <span className="team away">{fixture.away_team.name}</span>
              <span className="final-score muted">
                {fixture.status === "FINISHED"
                  ? "Full time"
                  : new Date(fixture.kickoff_time).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
