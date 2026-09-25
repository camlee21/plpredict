import { useState } from "react";
import { api, blockingError, useApi, usePrefetch } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import GameweekPicker from "../components/GameweekPicker";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";

export default function FixturesPage() {
  const gameweeksQuery = useApi(api.gameweeks());
  const homeQuery = useApi(api.homeGameweek());
  // null until the gameweek list has loaded (or failed to).
  const gameweeks = gameweeksQuery.data ?? null;
  const listError = blockingError(gameweeksQuery);
  const loadError = listError
    ? `Couldn't load the gameweeks: ${listError}. Please refresh the page to try again.`
    : "";

  // What you've picked, else the gameweek the home page would show (the one
  // being played, or the next one up), else the last one.
  const [picked, setPicked] = useState(null);
  const fallback = homeQuery.isError ? gameweeks?.[gameweeks.length - 1]?.number ?? null : null;
  const selected = picked ?? homeQuery.data?.number ?? fallback;

  const detailQuery = useApi(api.gameweekDetail(selected), {
    gameweek: selected,
    enabled: selected != null,
  });
  const data = detailQuery.data ?? null;
  const error = blockingError(detailQuery);

  // The gameweeks either side, so stepping back or forward is instant.
  const numbers = new Set((gameweeks ?? []).map((gw) => gw.number));
  usePrefetch(
    selected == null
      ? []
      : [selected - 1, selected + 1].filter((n) => numbers.has(n)).map((n) => api.gameweekDetail(n))
  );

  return (
    <>
      <PageHeader title="Fixtures and results" />

      <main className="page">
        {gameweeks && gameweeks.length > 0 && (
          <div className="toolbar">
            <GameweekPicker gameweeks={gameweeks} selected={selected} onChange={setPicked} />
          </div>
        )}

        {loadError && <div className="error-banner">{loadError}</div>}
        {error && <div className="error-banner">{error}</div>}

        {gameweeks === null && !loadError && <LoadingIndicator label="Loading fixtures..." />}

        {gameweeks && gameweeks.length === 0 && (
          <p className="muted">
            Fixtures haven't been loaded yet. They're pulled in automatically from the Premier League,
            so check back shortly.
          </p>
        )}

        {gameweeks && gameweeks.length > 0 && !data && !error && (
          <LoadingIndicator label="Loading gameweek..." />
        )}

        {data && (
          <div className="fixture-list">
            {data.fixtures.map((fixture) => (
              <FixtureRow fixture={fixture} key={fixture.id} />
            ))}
          </div>
        )}
      </main>
    </>
  );
}
