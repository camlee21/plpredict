import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../api/client";

function useCountdown(deadline) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  if (!deadline) return null;
  const diffMs = new Date(deadline).getTime() - now;
  if (diffMs <= 0) return "Locked";

  const totalSeconds = Math.floor(diffMs / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  return `${hours}h ${minutes}m ${seconds}s`;
}

export default function PredictionsPage() {
  const [gameweeks, setGameweeks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [data, setData] = useState(null);
  const [scores, setScores] = useState({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiRequest("/api/fixtures/gameweeks/")
      .then(async (list) => {
        setGameweeks(list);
        try {
          const current = await apiRequest("/api/fixtures/gameweeks/current/");
          setSelected(current.number);
        } catch {
          if (list.length) setSelected(list[0].number);
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (selected == null) return;
    setError("");
    setMessage("");
    apiRequest(`/api/predictions/gameweek/${selected}/`)
      .then((gwData) => {
        setData(gwData);
        const initial = {};
        gwData.fixtures.forEach((f) => {
          initial[f.id] = {
            home: f.prediction?.predicted_home_score ?? "",
            away: f.prediction?.predicted_away_score ?? "",
          };
        });
        setScores(initial);
      })
      .catch((err) => setError(err.message));
  }, [selected]);

  const countdown = useCountdown(data?.deadline);

  const updateScore = (fixtureId, side, value) => {
    setScores((prev) => ({
      ...prev,
      [fixtureId]: { ...prev[fixtureId], [side]: value },
    }));
  };

  const canSubmit = useMemo(() => {
    if (!data || data.is_locked) return false;
    return data.fixtures.every((f) => {
      const s = scores[f.id];
      return s && s.home !== "" && s.away !== "" && !Number.isNaN(Number(s.home)) && !Number.isNaN(Number(s.away));
    });
  }, [data, scores]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);
    try {
      const payload = {
        predictions: data.fixtures.map((f) => ({
          fixture_id: f.id,
          home_score: Number(scores[f.id].home),
          away_score: Number(scores[f.id].away),
        })),
      };
      const updated = await apiRequest(`/api/predictions/gameweek/${selected}/`, {
        method: "POST",
        body: payload,
      });
      setData(updated);
      setMessage("Predictions saved!");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <h1>Predict</h1>

      <div className="gameweek-selector">
        <label>
          Gameweek
          <select value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))}>
            {gameweeks.map((gw) => (
              <option key={gw.number} value={gw.number}>
                Gameweek {gw.number} {gw.is_locked ? "(locked)" : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      {gameweeks.length === 0 && !error && (
        <p className="muted">
          No gameweeks are loaded yet. Run <code>python manage.py sync_fixtures</code> on the backend
          to pull fixtures from the Fantasy Premier League API.
        </p>
      )}

      {data && (
        <>
          <div className="deadline-banner card">
            {data.is_locked ? (
              <span>Predictions are locked for this gameweek.</span>
            ) : (
              <span>Time left to predict: <strong>{countdown}</strong></span>
            )}
          </div>

          <form onSubmit={handleSubmit}>
            <div className="fixture-list">
              {data.fixtures.map((fixture) => (
                <div className="card fixture-row" key={fixture.id}>
                  <span className="team home">{fixture.home_team.name}</span>
                  <input
                    type="number"
                    min="0"
                    max="20"
                    disabled={data.is_locked}
                    value={scores[fixture.id]?.home ?? ""}
                    onChange={(e) => updateScore(fixture.id, "home", e.target.value)}
                  />
                  <span className="score-sep">-</span>
                  <input
                    type="number"
                    min="0"
                    max="20"
                    disabled={data.is_locked}
                    value={scores[fixture.id]?.away ?? ""}
                    onChange={(e) => updateScore(fixture.id, "away", e.target.value)}
                  />
                  <span className="team away">{fixture.away_team.name}</span>

                  {fixture.status === "FINISHED" && (
                    <span className="final-score muted">
                      Final: {fixture.home_score}-{fixture.away_score}
                      {fixture.prediction?.points != null && ` • ${fixture.prediction.points} pt`}
                    </span>
                  )}
                </div>
              ))}
            </div>

            {!data.is_locked && (
              <button type="submit" className="primary" disabled={!canSubmit || saving}>
                {saving ? "Saving..." : "Save predictions"}
              </button>
            )}
          </form>
        </>
      )}
    </div>
  );
}
