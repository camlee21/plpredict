import { Link, useParams } from "react-router-dom";
import { api, blockingError, useApi, usePrefetchOnIntent } from "../api/queries";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";
import ScoringInfo from "../components/ScoringInfo";

export default function LeaguePlayerPage() {
  const { publicId, userId } = useParams();
  const query = useApi(api.leagueMember(publicId, userId));
  const prefetchOnIntent = usePrefetchOnIntent();
  const player = query.data;
  const error =
    query.error?.status === 404 ? "That player isn't part of this league." : blockingError(query);

  if (error || !player) {
    return (
      <>
        <PageHeader
          title="Player"
          back={
            <Link to={`/leagues/${publicId}`} className="back-link">
              &larr; Back to the league
            </Link>
          }
        />
        <main className="page">
          {error ? <div className="error-banner">{error}</div> : <LoadingIndicator label="Loading player..." />}
        </main>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={
          <>
            {player.username}
            {player.is_you && <span className="title-aside"> (you)</span>}
          </>
        }
        back={
          <Link to={`/leagues/${publicId}`} className="back-link">
            &larr; {player.league.name}
          </Link>
        }
        meta={[
          player.rank_display,
          player.starting_gameweek && `Counting from Gameweek ${player.starting_gameweek}`,
        ]}
        actions={<ScoringInfo />}
      />

      <main className="page">
        <dl className="panel stat-row">
          <div className="stat">
            <dt>Points in this league</dt>
            <dd>{player.has_counted_gameweeks ? player.total_points : "-"}</dd>
          </div>
          <div className="stat">
            <dt>Career points</dt>
            <dd>{player.career_points}</dd>
          </div>
          <div className="stat">
            <dt>
              Average per gameweek
              {player.career_gameweeks > 0 && ` (${player.career_gameweeks} played)`}
            </dt>
            <dd>{player.average_points ?? "-"}</dd>
          </div>
        </dl>

        <div className="section-head">
          <h2>Gameweek by gameweek</h2>
        </div>
        {player.gameweeks.length === 0 && (
          <p className="muted">
            {player.starting_gameweek
              ? `Nothing to show yet. Scores start counting from Gameweek ${player.starting_gameweek}.`
              : "Nothing to show yet. No gameweeks have been played."}
          </p>
        )}

        {player.gameweeks.length > 0 && (
          <ul className="panel row-list">
            {player.gameweeks.map((row) => (
              <li className="league-row" key={row.gameweek}>
                <span className="league-row-name">Gameweek {row.gameweek}</span>
                <span className="league-row-detail league-row-points">
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
                    {...prefetchOnIntent(api.leagueMemberGameweek(publicId, userId, row.gameweek))}
                  >
                    View predictions
                  </Link>
                ) : (
                  <span className="league-row-note">
                    {row.has_predictions ? "Hidden until kickoff" : "No predictions"}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}
