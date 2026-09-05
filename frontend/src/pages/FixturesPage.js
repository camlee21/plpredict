import { useEffect, useState } from "react";
import { apiRequest } from "../api/client";
import { FixtureRow } from "../components/FixtureRow";

const LIFECYCLE_LABELS = { previous: "Previous", current: "Current", future: "Upcoming" };

export default function FixturesPage() {
  const [gameweeks, setGameweeks] = useState([]);
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
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (selected == null) return;
    setError("");
    apiRequest(`/api/fixtures/gameweeks/${selected}/`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [selected]);

  return (
    <div className="page">
      <h1>Fixtures &amp; Results</h1>

      {gameweeks.length > 0 && (
        <div className="gameweek-selector">
          <label>
            Gameweek
            <select value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))}>
              {gameweeks.map((gw) => (
                <option key={gw.number} value={gw.number}>
                  Gameweek {gw.number} — {LIFECYCLE_LABELS[gw.lifecycle]}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      {gameweeks.length === 0 && !error && (
        <p className="muted">
          No gameweeks are loaded yet. Run <code>python manage.py sync_fixtures</code> on the backend
          to pull teams and fixtures from the Fantasy Premier League API.
        </p>
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
