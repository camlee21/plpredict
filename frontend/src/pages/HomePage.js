import { useMemo } from "react";
import { Link } from "react-router-dom";
import { api, blockingError, useApi, usePrefetchOnIntent } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";
import ScoringInfo from "../components/ScoringInfo";
import { useCountdown } from "../utils/countdown";
import { gameweekScoreSummary } from "../utils/scoring";

// The current gameweek at a glance, in the page header: your points once
// predictions have locked, or the time left to make them before that.
function GameweekStatus({ gwScore, summary, countdown }) {
  if (gwScore.is_locked) {
    return (
      <div className="gw-status">
        <div className="scoreboard">
          <span className="scoreboard-figure">{summary.hasPredictions ? summary.totalPoints : "-"}</span>
          <span className="scoreboard-label">
            {summary.hasPredictions && summary.stillToPlay > 0 ? "points so far" : "points"}
          </span>
        </div>
        <p className="gw-status-text">
          {!summary.hasPredictions
            ? "You didn't make any predictions for this gameweek."
            : summary.stillToPlay > 0
              ? `${summary.stillToPlay} of your predicted ${summary.stillToPlay === 1 ? "match is" : "matches are"} still to play.`
              : "All your predicted matches have been played."}
        </p>
        <Link to={`/scores/${gwScore.gameweek}`} className="button-green">
          View breakdown
        </Link>
      </div>
    );
  }

  return (
    <div className="gw-status">
      <div className={`scoreboard${countdown?.urgent ? " is-urgent" : ""}`}>
        <span className="scoreboard-figure">{countdown?.text}</span>
        <span className="scoreboard-label">until predictions close</span>
      </div>
      <p className="gw-status-text">
        {summary.fullyPredicted
          ? "Your predictions are saved. You can change them until the deadline."
          : "You haven't predicted every match yet."}
      </p>
      <Link to="/predict" className="button-green">
        {summary.fullyPredicted ? "Edit predictions" : "Make predictions"}
      </Link>
    </div>
  );
}

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
  const countdown = useCountdown(gwScore && !gwScore.is_locked ? gwScore.deadline : null);

  return (
    <>
      <PageHeader
        title={currentNumber != null ? `Gameweek ${currentNumber}` : "Home"}
        actions={<ScoringInfo />}
      >
        {gwScore && <GameweekStatus gwScore={gwScore} summary={gwScoreSummary} countdown={countdown} />}
        {gwScore === undefined && currentNumber != null && (
          <p className="gw-status-text">Loading your gameweek...</p>
        )}
      </PageHeader>

      <main className="page home-grid">
        {error && <div className="error-banner home-error">{error}</div>}

        <aside className="home-side">
          {lastScore && (
            <Link
              to={`/scores/${lastScore.gameweek}`}
              className="panel last-score"
              {...prefetchOnIntent(api.predictionsGameweek(lastScore.gameweek))}
            >
              <span className="last-score-points">{lastScore.points}</span>
              <span>
                <strong>Your last score</strong>
                <span className="muted small">Points in Gameweek {lastScore.gameweek}</span>
              </span>
            </Link>
          )}

          <section>
            <div className="section-head">
              <h2>Your leagues</h2>
              {leagueSummaries && leagueSummaries.length > 0 && (
                <Link to="/leagues" className="text-link">
                  {leagueSummaries.length > 5 ? `All ${leagueSummaries.length}` : "Manage"}
                </Link>
              )}
            </div>
            {leagueSummaries === null && <LoadingIndicator label="Loading leagues..." />}
            {leagueSummaries && leagueSummaries.length === 0 && (
              <div className="panel empty-panel">
                <p>You're not in any leagues yet.</p>
                <Link to="/leagues" className="primary-link">
                  Create or join a league
                </Link>
              </div>
            )}
            {leagueSummaries && leagueSummaries.length > 0 && (
              <ul className="panel link-list">
                {leagueSummaries.slice(0, 5).map((league) => (
                  <li key={league.public_id}>
                    <Link
                      to={`/leagues/${league.public_id}`}
                      className="league-mini-row"
                      {...prefetchOnIntent(api.league(league.public_id))}
                    >
                      <span className="league-mini-name">{league.name}</span>
                      <span className="league-mini-rank">{league.rank_display}</span>
                      <span className="league-mini-points">
                        {league.has_counted_gameweeks ? `${league.total_points} pts` : "-"}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

        </aside>

        <section className="home-fixtures">
          <div className="section-head">
            <h2>
              {gameweek
                ? `${gameweek.phase === "upcoming" ? "Next up" : "Fixtures"}: Gameweek ${gameweek.number}`
                : "Fixtures"}
            </h2>
            {gameweek && (
              <Link to="/fixtures" className="text-link">
                All fixtures
              </Link>
            )}
          </div>
          {gameweek === undefined && <LoadingIndicator label="Loading fixtures..." />}
          {gameweek === null && (
            <p className="muted">
              Fixtures haven't been loaded yet. They're pulled in automatically from the Premier League,
              so check back shortly.
            </p>
          )}
          {gameweek && (
            <div className="fixture-list">
              {gameweek.fixtures.map((fixture) => (
                <FixtureRow fixture={fixture} key={fixture.id} />
              ))}
            </div>
          )}
        </section>
      </main>
    </>
  );
}
