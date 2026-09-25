import { formatDate, formatTime } from "../utils/format";

export function FormBadges({ form }) {
  if (!form || form.length === 0) {
    return <span className="muted small form-badges">No form yet</span>;
  }
  return (
    <span className="form-badges">
      {form.map((result, index) => (
        <span
          key={index}
          className={`form-badge ${result.toLowerCase()}${index === form.length - 1 ? " form-badge-latest" : ""}`}
        >
          {result}
        </span>
      ))}
    </span>
  );
}

function formatGoals(goals) {
  if (!goals || goals.length === 0) return "";
  return goals
    .map((goal) => `${goal.player}${goal.count > 1 ? ` (${goal.count})` : ""}${goal.own_goal ? " (OG)" : ""}`)
    .join(", ");
}

function TeamColumn({ team, goals, align }) {
  const badge = team.crest_url && <img src={team.crest_url} alt="" className="team-badge" />;
  return (
    <div className={`team-col ${align}`}>
      <div className="team-name-row">
        {align === "away" && badge}
        {/* Only one of these shows at a time: the short name on narrow screens. */}
        <span className="team-name team-name-full">{team.name}</span>
        <span className="team-name team-name-short">{team.short_name || team.name}</span>
        {align === "home" && badge}
      </div>
      <FormBadges form={team.form} />
      {goals && goals.length > 0 && <div className="goalscorers">{formatGoals(goals)}</div>}
    </div>
  );
}

function defaultFooter(fixture) {
  if (fixture.status === "SCHEDULED") return formatDate(fixture.kickoff_time);
  if (fixture.status === "LIVE") {
    return (
      <span className="live-tag">
        <span className="live-dot" aria-hidden="true" />
        Live
      </span>
    );
  }
  return "Full time";
}

export function FixtureRow({ fixture, renderScore, footer }) {
  const isScheduled = fixture.status === "SCHEDULED";
  const isLive = fixture.status === "LIVE";
  const hasScore = fixture.home_score != null && fixture.away_score != null;
  return (
    <div className={`fixture-row${isLive ? " is-live" : ""}`}>
      <div className="fixture-main">
        <TeamColumn team={fixture.home_team} goals={fixture.home_goals} align="home" />
        {renderScore ? (
          renderScore()
        ) : (
          <div className={`score-box${isScheduled || !hasScore ? " pending" : ""}${isLive ? " live" : ""}`}>
            {isScheduled ? (
              // Kickoff time where the score will go; the date sits underneath.
              formatTime(fixture.kickoff_time)
            ) : hasScore ? (
              <>
                {fixture.home_score}
                <span className="score-box-sep">-</span>
                {fixture.away_score}
              </>
            ) : (
              "vs"
            )}
          </div>
        )}
        <TeamColumn team={fixture.away_team} goals={fixture.away_goals} align="away" />
      </div>
      <div className="fixture-footer">{footer ?? defaultFooter(fixture)}</div>
    </div>
  );
}
