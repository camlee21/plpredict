import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "../api/client";
import { api, blockingError, queryKeys, useApi, usePrefetch, usePrefetchOnIntent } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import GameweekScoreStrip from "../components/GameweekScoreStrip";
import LoadingIndicator from "../components/LoadingIndicator";
import ScoringInfo from "../components/ScoringInfo";
import { formatDateTime } from "../utils/format";
import { predictionFooter } from "../utils/scoring";

function gameweekOptionLabel(gw) {
  return `Gameweek ${gw.number}${gw.lifecycle === "current" ? " (current)" : ""}`;
}

const LOCKED_MESSAGES = {
  previous: "This gameweek has already been played.",
  current: "This gameweek is in progress - predictions closed an hour before its first kickoff.",
  future: "Predictions for this gameweek aren't open yet - the current gameweek needs to finish first.",
};

// The form's starting values: whatever's already saved for each fixture.
function savedScores(gameweekData) {
  const initial = {};
  gameweekData.fixtures.forEach((f) => {
    initial[f.id] = {
      home: f.prediction?.predicted_home_score ?? "",
      away: f.prediction?.predicted_away_score ?? "",
    };
  });
  return initial;
}

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
  const queryClient = useQueryClient();
  const gameweeksQuery = useApi(api.gameweeks());
  const currentQuery = useApi(api.currentGameweek());
  // Only feeds the score strip, so a failure here leaves the rest of the
  // page working.
  const historyQuery = useApi(api.history());

  // null until the gameweek list has loaded (or failed to).
  const gameweeks = gameweeksQuery.data ?? null;
  const history = historyQuery.data ?? null;
  const historyError = historyQuery.isError && !history;
  const listError = blockingError(gameweeksQuery);
  const loadError = listError
    ? `Couldn't load the gameweeks: ${listError}. Please refresh the page to try again.`
    : "";

  // Played-and-scored gameweeks live in the strip above, not the picker. By
  // default the picker shows the current gameweek.
  const [picked, setPicked] = useState(null);
  const defaultSelection = useMemo(() => {
    const upcomingNumbers = (gameweeks ?? []).filter((gw) => gw.lifecycle !== "previous").map((gw) => gw.number);
    if (upcomingNumbers.length === 0) return null;
    if (currentQuery.data) {
      return upcomingNumbers.includes(currentQuery.data.number) ? currentQuery.data.number : upcomingNumbers[0];
    }
    return currentQuery.isError ? upcomingNumbers[0] : null;
  }, [gameweeks, currentQuery.data, currentQuery.isError]);
  const selected = picked ?? defaultSelection;

  const gameweekQuery = useApi(api.predictionsGameweek(selected), {
    gameweek: selected,
    enabled: selected != null,
  });
  const data = gameweekQuery.data ?? null;

  // The next gameweek in the picker, ready before you pick it.
  const upcomingNumbers = (gameweeks ?? []).filter((gw) => gw.lifecycle !== "previous").map((gw) => gw.number);
  const nextNumber = upcomingNumbers[upcomingNumbers.indexOf(selected) + 1];
  usePrefetch(selected != null && nextNumber != null ? [api.predictionsGameweek(nextNumber)] : []);
  const prefetchOnIntent = usePrefetchOnIntent();

  const [scores, setScores] = useState({});
  // Which gameweek the form was last filled in from. The boxes are only reset
  // from saved predictions when you move to a different gameweek - never when
  // a background refresh brings the same one back, which would wipe whatever
  // you were halfway through typing.
  const [formGameweek, setFormGameweek] = useState(null);
  if (data && data.gameweek !== formGameweek) {
    setFormGameweek(data.gameweek);
    setScores(savedScores(data));
  }

  const [actionError, setActionError] = useState("");
  const error = actionError || blockingError(gameweekQuery);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const justSavedTimeout = useRef(null);

  useEffect(() => () => clearTimeout(justSavedTimeout.current), []);

  const setSelected = (number) => {
    setPicked(number);
    setActionError("");
    setMessage("");
    setJustSaved(false);
    clearTimeout(justSavedTimeout.current);
  };

  const countdown = useCountdown(data?.deadline);

  // The gameweeks still to come: what the picker offers. Anything already
  // scored is reachable from the score strip instead.
  const upcoming = useMemo(
    () => (gameweeks ?? []).filter((gw) => gw.lifecycle !== "previous"),
    [gameweeks]
  );

  // Every scored gameweek in season order - including ones with no
  // predictions, so the run of gameweek numbers has no confusing gaps in it.
  const pastScores = useMemo(() => {
    if (!gameweeks || !history) return [];
    const pointsByGameweek = new Map(history.by_gameweek.map((row) => [row.gameweek, row.points]));
    return gameweeks
      .filter((gw) => gw.lifecycle === "previous")
      .map((gw) => ({
        gameweek: gw.number,
        points: pointsByGameweek.get(gw.number) ?? 0,
        hasPredictions: pointsByGameweek.has(gw.number),
      }));
  }, [gameweeks, history]);

  const updateScore = (fixtureId, side, value) => {
    setScores((prev) => ({
      ...prev,
      [fixtureId]: { ...prev[fixtureId], [side]: value },
    }));
  };

  // Fixtures with both boxes validly filled in. A save must cover every
  // fixture in the gameweek - a partial draft can no longer be submitted -
  // so this also drives how many are still missing a score.
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

  const missingCount = data ? data.fixtures.length - completePredictions.length : 0;
  const canSave = !data?.is_locked && missingCount === 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setActionError("");
    setMessage("");
    if (missingCount > 0) {
      setActionError(`Enter a score for every fixture before saving - ${missingCount} still need one.`);
      return;
    }
    setSaving(true);
    try {
      const updated = await apiRequest(`/api/predictions/gameweek/${selected}/`, {
        method: "POST",
        body: { predictions: completePredictions },
      });
      // The response is the gameweek as now saved: put it straight into the
      // cache, which the home page's "this gameweek" card also reads.
      queryClient.setQueryData(queryKeys.predictionsGameweek(selected), updated);
      setMessage("All predictions saved!");
      setJustSaved(true);
      clearTimeout(justSavedTimeout.current);
      justSavedTimeout.current = setTimeout(() => setJustSaved(false), 1000);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <div className="heading-row">
        <h1>Predict</h1>
        <ScoringInfo />
      </div>

      {historyError && <p className="muted">Couldn't load your recent scores.</p>}
      <GameweekScoreStrip
        items={pastScores}
        cardProps={(item) => prefetchOnIntent(api.predictionsGameweek(item.gameweek))}
      />

      {upcoming.length > 0 && (
        <div className="gameweek-selector">
          <label>
            Gameweek
            <select value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))}>
              {upcoming.map((gw) => (
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
      {message && <div className="success-banner">{message}</div>}

      {gameweeks === null && !loadError && <LoadingIndicator label="Loading fixtures..." />}

      {gameweeks && gameweeks.length === 0 && (
        <p className="muted">
          Fixtures haven't been loaded yet. They're pulled in automatically from the Premier League,
          so please check back shortly.
        </p>
      )}

      {gameweeks && gameweeks.length > 0 && upcoming.length === 0 && (
        <p className="muted">
          Every gameweek has been played and scored - there's nothing left to predict this season.
          Use the scores above to look back over how it went.
        </p>
      )}

      {upcoming.length > 0 && !data && !error && <LoadingIndicator label="Loading gameweek..." />}

      {data && data.is_locked && (
        <>
          <p className="muted">{LOCKED_MESSAGES[data.lifecycle]}</p>
          <div className="fixture-list">
            {data.fixtures.map((fixture) => (
              <FixtureRow
                fixture={fixture}
                key={fixture.id}
                // Once a gameweek is locked, what you predicted is the point of
                // the page - the bare result alone doesn't tell you how you did.
                // A future gameweek you couldn't predict yet keeps its kickoff time.
                footer={
                  fixture.prediction || data.lifecycle !== "future"
                    ? predictionFooter(fixture)
                    : undefined
                }
              />
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
                      {formatDateTime(fixture.kickoff_time)}
                      {fixture.prediction != null && <span className="saved-tag"> &middot; Saved</span>}
                    </>
                  }
                />
              ))}
            </div>

            <button type="submit" className="primary" disabled={!canSave || saving || justSaved}>
              {saving ? "Saving..." : justSaved ? "Saved!" : "Save predictions"}
            </button>
            {missingCount > 0 && (
              <p className="muted">
                Enter a score for every fixture to save - {missingCount} more still needed.
              </p>
            )}
          </form>
        </>
      )}
    </div>
  );
}
