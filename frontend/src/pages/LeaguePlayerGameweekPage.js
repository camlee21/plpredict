import { Link, useParams } from "react-router-dom";
import { api, blockingError, useApi } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import LoadingIndicator from "../components/LoadingIndicator";
import ScoringInfo from "../components/ScoringInfo";
import { predictionFooter } from "../utils/scoring";

export default function LeaguePlayerGameweekPage() {
  const { publicId, userId, number } = useParams();
  const query = useApi(api.leagueMemberGameweek(publicId, userId, number), { gameweek: number });
  const data = query.data;
  const error =
    query.error?.status === 404 ? "That gameweek isn't part of this league." : blockingError(query);

  const backToPlayer = (
    <Link to={`/leagues/${publicId}/players/${userId}`} className="back-link">
      &larr; Back to {data ? data.username : "the player"}
    </Link>
  );

  if (error) {
    return (
      <div className="page">
        {backToPlayer}
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <LoadingIndicator label="Loading predictions..." />
      </div>
    );
  }

  const label = data.is_you ? "Your prediction" : `${data.username}'s prediction`;

  return (
    <div className="page">
      {backToPlayer}

      <div className="heading-row">
        <h1>Gameweek {data.gameweek}</h1>
        <ScoringInfo />
      </div>
      <p className="muted">
        {data.username} in {data.league.name}
      </p>

      <div className="card home-last-score">
        <p className="score-highlight">{data.points} pts</p>
        <p className="muted">{data.is_scored ? "Final" : "Still being played"}</p>
      </div>

      <div className="fixture-list">
        {data.fixtures.map((fixture) => (
          <FixtureRow fixture={fixture} key={fixture.id} footer={predictionFooter(fixture, label)} />
        ))}
      </div>
    </div>
  );
}
