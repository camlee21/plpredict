import { useMemo } from "react";
import { Link } from "react-router-dom";
import { api, blockingError, useApi, usePrefetchOnIntent } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import ScoringInfo from "../components/ScoringInfo";
import { gameweekScoreSummary } from "../utils/scoring";

export default function HomePage() {
  const historyQuery = useApi(api.history());
  const summariesQuery = useApi(api.homeSummary());
  const currentQuery = useApi(api.currentGameweek());
  const currentNumber = currentQuery.data?.number;
  // Same cache entry as the Predict page's view of this gameweek, so saving
  // predictions there shows up here straight away.
  const gwScoreQuery = useApi(api.predictionsGameweek(currentNumber), {
    gameweek: currentNumber,
    enabled: currentNumber != null,
  });
  const homeQuery = useApi(api.homeGameweek());
  const prefetchOnIntent = usePrefetchOnIntent();

  // undefined = still loading, null = nothing to show.
  const entries = historyQuery.data?.by_gameweek;
  const lastScore = entries === undefined ? undefined : entries.length ? entries[entries.length - 1] : null;
  const leagueSummaries = summariesQuery.data ?? null;
  const gwScore = currentQuery.error?.status === 404 ? null : gwScoreQuery.data;
  const gameweek = homeQuery.error?.status === 404 ? null : homeQuery.data;
  const error =
    blockingError(historyQuery) ||
    blockingError(summariesQuery) ||
    blockingError(currentQuery, { ignoreStatus: [404] }) ||
    blockingError(gwScoreQuery) ||
    blockingError(homeQuery, { ignoreStatus: [404] });

  const gwScoreSummary = useMemo(() => gameweekScoreSummary(gwScore), [gwScore]);

  return (
    <div className="page">
      <h1>Home</h1>
      {error && <div className="error-banner">{error}</div>}

      {lastScore && (
        <Link
          to={`/scores/${lastScore.gameweek}`}
          className="card home-last-score home-last-score-link"
          {...prefetchOnIntent(api.predictionsGameweek(lastScore.gameweek))}
        >
          <h2>Your last score</h2>
          <p className="score-highlight">{lastScore.points} pts</p>
          <p className="muted">Gameweek {lastScore.gameweek}</p>
        </Link>
      )}

      {gwScore !== null && (
        <>
          <div className="heading-row">
            <h2>This gameweek's score</h2>
            <ScoringInfo />
          </div>
          {gwScore === undefined && <p>Loading...</p>}
          {gwScore && (
            <div className="league-row-list">
              <div className="league-row">
                <span className="league-row-name">Gameweek {gwScore.gameweek}</span>
                {gwScore.is_locked ? (
                  <>
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
                  </>
                ) : (
                  <>
                    <span className="league-row-detail muted">
                      {gwScoreSummary.fullyPredicted ? "Predictions saved" : "Predictions unsaved"}
                    </span>
                    <Link to="/predict" className="league-row-action">
                      {gwScoreSummary.fullyPredicted ? "Edit predictions" : "Make predictions"}
                    </Link>
                  </>
                )}
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
              <span className="league-row-detail muted">
                {league.has_counted_gameweeks ? `${league.total_points} pts` : "-"}
              </span>
              <Link
                to={`/leagues/${league.public_id}`}
                className="league-row-action"
                {...prefetchOnIntent(api.league(league.public_id))}
              >
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
          Fixtures haven't been loaded yet. They're pulled in automatically from the Premier League,
          so please check back shortly.
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
