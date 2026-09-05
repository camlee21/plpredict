import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../api/client";
import { FixtureRow } from "../components/FixtureRow";

function gameweekOptionLabel(gw) {
  return `Gameweek ${gw.number}${gw.lifecycle === "current" ? " (current)" : ""}`;
}

const LOCKED_MESSAGES = {
  previous: "This gameweek has already been played.",
  current: "This gameweek is in progress - predictions closed an hour before its first kickoff.",
  future: "Predictions for this gameweek aren't open yet - the current gameweek needs to finish first.",
};

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

  // Fixtures with both boxes validly filled in - the ones a save will
  // actually submit. Anything left blank is simply skipped, so a partial
  // draft can be saved and finished off later, right up to the deadline.
  const completePredictions = useMemo(() => {
    if (!data) return [];
    return data.fixtures
      .filter((f) => {
        const s = scores[f.id];
        return s && s.home !== "" && s.away !== "" && !Number.isNaN(Number(s.home)) && !Number.isNaN(Number(s.away));
      })
      .map((f) => ({
        fixture_id: f.id,
        home_score: Number(scores[f.id].home),
        away_score: Number(scores[f.id].away),
      }));
  }, [data, scores]);

  const canSave = !data?.is_locked && completePredictions.length > 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);
    try {
      const updated = await apiRequest(`/api/predictions/gameweek/${selected}/`, {
        method: "POST",
        body: { predictions: completePredictions },
      });
      setData(updated);
      setMessage(
        completePredictions.length === updated.fixtures.length
          ? "All predictions saved!"
          : `Saved ${completePredictions.length} of ${updated.fixtures.length} predictions. Come back any time before the deadline to fill in the rest.`
      );
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
                {gameweekOptionLabel(gw)}
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

      {data && data.is_locked && (
        <>
          <p className="muted">{LOCKED_MESSAGES[data.lifecycle]}</p>
          <div className="fixture-list">
            {data.fixtures.map((fixture) => (
              <FixtureRow fixture={fixture} key={fixture.id} />
            ))}
          </div>
        </>
      )}

      {data && !data.is_locked && (
        <>
          <div className="deadline-banner card">
            <span>
              Time left to predict: <strong>{countdown}</strong>
            </span>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="fixture-list">
              {data.fixtures.map((fixture) => (
                <FixtureRow
                  key={fixture.id}
                  fixture={fixture}
                  renderScore={() => (
                    <div className="score-box editable">
                      <input
                        type="number"
                        min="0"
                        max="10"
                        inputMode="numeric"
                        aria-label={`${fixture.home_team.name} predicted score`}
                        value={scores[fixture.id]?.home ?? ""}
                        onChange={(e) => updateScore(fixture.id, "home", e.target.value)}
                      />
                      <span className="score-box-sep">-</span>
                      <input
                        type="number"
                        min="0"
                        max="10"
                        inputMode="numeric"
                        aria-label={`${fixture.away_team.name} predicted score`}
                        value={scores[fixture.id]?.away ?? ""}
                        onChange={(e) => updateScore(fixture.id, "away", e.target.value)}
                      />
                    </div>
                  )}
                  footer={
                    <>
                      {new Date(fixture.kickoff_time).toLocaleString()}
                      {fixture.prediction != null && <span className="saved-tag"> &middot; Saved</span>}
                    </>
                  }
                />
              ))}
            </div>

            <button type="submit" className="primary" disabled={!canSave || saving}>
              {saving ? "Saving..." : "Save predictions"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
