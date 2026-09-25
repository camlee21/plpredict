import { Link, useParams } from "react-router-dom";
import { api, blockingError, useApi } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";
import PredictionResult, { PredictionTally } from "../components/PredictionResult";
import ScoringInfo from "../components/ScoringInfo";

export default function LeaguePlayerGameweekPage() {
  const { publicId, userId, number } = useParams();
  const query = useApi(api.leagueMemberGameweek(publicId, userId, number), { gameweek: number });
  const data = query.data;
  const error =
    query.error?.status === 404 ? "That gameweek isn't part of this league." : blockingError(query);

  const backToPlayer = (
    <Link to={`/leagues/${publicId}/players/${userId}`} className="back-link">
      &larr; {data ? data.username : "Back to the player"}
    </Link>
  );

  if (error) {
    return (
      <>
        <PageHeader title={`Gameweek ${number}`} back={backToPlayer} />
        <main className="page">
          <div className="error-banner">{error}</div>
        </main>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <PageHeader title={`Gameweek ${number}`} back={backToPlayer} />
        <main className="page">
          <LoadingIndicator label="Loading predictions..." />
        </main>
      </>
    );
  }

  const who = data.is_you ? "You" : data.username;

  return (
    <>
      <PageHeader
        title={`Gameweek ${data.gameweek}`}
        back={backToPlayer}
        meta={[data.is_you ? "You" : data.username, data.league.name]}
        actions={<ScoringInfo />}
      >
        <div className="score-summary">
          <div className="scoreboard">
            <span className="scoreboard-figure">{data.points}</span>
            <span className="scoreboard-label">{data.is_scored ? "points, final" : "points so far"}</span>
          </div>
          <PredictionTally fixtures={data.fixtures} />
        </div>
      </PageHeader>

      <main className="page">
        <div className="fixture-list">
          {data.fixtures.map((fixture) => (
            <FixtureRow fixture={fixture} key={fixture.id} footer={<PredictionResult fixture={fixture} who={who} />} />
          ))}
        </div>
      </main>
    </>
  );
}
