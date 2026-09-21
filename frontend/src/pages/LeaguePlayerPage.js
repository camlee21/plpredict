import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest } from "../api/client";
import LoadingIndicator from "../components/LoadingIndicator";
import ScoringInfo from "../components/ScoringInfo";

export default function LeaguePlayerPage() {
  const { publicId, userId } = useParams();
  const [player, setPlayer] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setPlayer(null);
    setError("");
    apiRequest(`/api/leagues/${publicId}/members/${userId}/`)
      .then(setPlayer)
      .catch((err) =>
        setError(err.status === 404 ? "That player isn't part of this league." : err.message)
      );
  }, [publicId, userId]);

  if (error) {
    return (
      <div className="page">
        <Link to={`/leagues/${publicId}`} className="back-link">
          &larr; Back to the league
        </Link>
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!player) {
    return (
      <div className="page">
        <LoadingIndicator label="Loading player..." />
      </div>
    );
  }

  return (
    <div className="page">
      <Link to={`/leagues/${publicId}`} className="back-link">
        &larr; {player.league.name}
      </Link>

      <div className="heading-row">
        <h1>
          {player.username}
          {player.is_you && <span className="muted"> (you)</span>}
        </h1>
        <ScoringInfo />
      </div>

      <p className="muted">
        In {player.league.name} &middot; {player.rank_display}
        {player.starting_gameweek ? ` · counting from Gameweek ${player.starting_gameweek}` : ""}
      </p>

      <div className="card">
        <div className="profile-stats-row">
          <div className="profile-stat">
            <div className="stat-value">
              {player.has_counted_gameweeks ? player.total_points : "-"}
            </div>
            <div className="muted small">Points in this league</div>
          </div>
          <div className="profile-stat">
            <div className="stat-value">{player.career_points}</div>
            <div className="muted small">Career points</div>
          </div>
          <div className="profile-stat">
            <div className="stat-value">{player.average_points ?? "-"}</div>
            <div className="muted small">
              Avg per gameweek
              {player.career_gameweeks > 0 && ` (${player.career_gameweeks} played)`}
            </div>
          </div>
        </div>
      </div>

      <h2>Gameweek by gameweek</h2>
      {player.gameweeks.length === 0 && (
        <p className="muted">
          {player.starting_gameweek
            ? `Nothing to show yet - scores start counting from Gameweek ${player.starting_gameweek}.`
            : "Nothing to show yet - no gameweeks have been played."}
        </p>
      )}

      {player.gameweeks.length > 0 && (
        <div className="league-row-list">
          {player.gameweeks.map((row) => (
            <div className="league-row" key={row.gameweek}>
              <span className="league-row-name">Gameweek {row.gameweek}</span>
              <span className="league-row-detail">
                {row.has_started ? `${row.points} pt${row.points === 1 ? "" : "s"}` : "-"}
              </span>
              {row.has_started && !row.is_scored && (
                <span className="league-row-detail muted">In progress</span>
              )}
              {!row.has_started && <span className="league-row-detail muted">Not started</span>}
              {row.predictions_visible && row.has_predictions ? (
                <Link
                  to={`/leagues/${publicId}/players/${userId}/gameweek/${row.gameweek}`}
                  className="league-row-action"
                >
                  View predictions
                </Link>
              ) : (
                <span className="league-row-note">
                  {row.has_predictions ? "Hidden until kickoff" : "No predictions"}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
