import { useEffect, useState } from "react";
import { apiRequest } from "../api/client";
import { FixtureRow } from "../components/FixtureRow";
import LoadingIndicator from "../components/LoadingIndicator";

function gameweekOptionLabel(gw) {
  return `Gameweek ${gw.number}${gw.lifecycle === "current" ? " (current)" : ""}`;
}

export default function FixturesPage() {
  // null until the gameweek list has loaded (or failed to).
  const [gameweeks, setGameweeks] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [selected, setSelected] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest("/api/fixtures/gameweeks/")
      .then(async (list) => {
        setGameweeks(list);
        try {
          const current = await apiRequest("/api/fixtures/gameweeks/home/");
          setSelected(current.number);
        } catch {
          if (list.length) setSelected(list[list.length - 1].number);
        }
      })
      .catch((err) =>
        setLoadError(`Couldn't load the gameweeks: ${err.message}. Please refresh the page to try again.`)
      );
  }, []);

  useEffect(() => {
    if (selected == null) return;
    setError("");
    setData(null);
    apiRequest(`/api/fixtures/gameweeks/${selected}/`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [selected]);

  return (
    <div className="page">
      <h1>Fixtures &amp; Results</h1>

      {gameweeks && gameweeks.length > 0 && (
        <div className="gameweek-selector">
          <label>
            Gameweek
            <select value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))}>
              {gameweeks.map((gw) => (
                <option key={gw.number} value={gw.number}>
                  {gameweekOptionLabel(gw)}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {loadError && <div className="error-banner">{loadError}</div>}
      {error && <div className="error-banner">{error}</div>}

      {gameweeks === null && !loadError && <LoadingIndicator label="Loading fixtures..." />}

      {gameweeks && gameweeks.length === 0 && (
        <p className="muted">
          Fixtures haven't been loaded yet. They're pulled in automatically from the Premier League,
          so please check back shortly.
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
    </div>
  );
}
