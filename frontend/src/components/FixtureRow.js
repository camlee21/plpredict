export function FormBadges({ form }) {
  if (!form || form.length === 0) {
    return <span className="muted small form-badges">No form yet</span>;
  }
  return (
    <span className="form-badges">
      {form.map((result, index) => (
        <span key={index} className={`form-badge ${result.toLowerCase()}`}>
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
  return (
    <div className={`team-col ${align}`}>
      <div className="team-name-row">
        {team.crest_url && <img src={team.crest_url} alt="" className="team-badge" />}
        <span className="team-name">{team.name}</span>
      </div>
      <FormBadges form={team.form} />
      {goals && goals.length > 0 && <div className="goalscorers">{formatGoals(goals)}</div>}
    </div>
  );
}

export function FixtureRow({ fixture, renderScore, footer }) {
  const isScheduled = fixture.status === "SCHEDULED";
  const isLive = fixture.status === "LIVE";
  return (
    <div className="card fixture-row">
      <div className="fixture-main">
        <TeamColumn team={fixture.home_team} goals={fixture.home_goals} align="home" />
        {renderScore ? (
          renderScore()
        ) : (
          <div className={`score-box ${isScheduled ? "pending" : ""} ${isLive ? "live" : ""}`}>
            {isScheduled ? "vs" : `${fixture.home_score} - ${fixture.away_score}`}
          </div>
        )}
        <TeamColumn team={fixture.away_team} goals={fixture.away_goals} align="away" />
      </div>
      <div className="final-score muted">
        {footer ?? (isScheduled ? new Date(fixture.kickoff_time).toLocaleString() : isLive ? "In progress" : "Full time")}
      </div>
    </div>
  );
}
