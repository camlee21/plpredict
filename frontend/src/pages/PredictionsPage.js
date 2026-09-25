import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiRequest } from "../api/client";
import { api, blockingError, queryKeys, useApi, usePrefetch, usePrefetchOnIntent } from "../api/queries";
import { FixtureRow } from "../components/FixtureRow";
import GameweekPicker from "../components/GameweekPicker";
import GameweekScoreStrip from "../components/GameweekScoreStrip";
import LoadingIndicator from "../components/LoadingIndicator";
import PageHeader from "../components/PageHeader";
import PredictionResult from "../components/PredictionResult";
import ScoringInfo from "../components/ScoringInfo";
import { useCountdown } from "../utils/countdown";
import { formatDateTime } from "../utils/format";

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
  // Load problems show at the top; save problems show in the save bar.
  const queryError = blockingError(gameweekQuery);
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
    // "Saved" no longer holds once you've changed something.
    setMessage("");
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
      setMessage("Predictions saved");
      setJustSaved(true);
      clearTimeout(justSavedTimeout.current);
      justSavedTimeout.current = setTimeout(() => setJustSaved(false), 1000);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const predictedCount = data ? data.fixtures.length - missingCount : 0;

  return (
    <>
      <PageHeader title="Predict" actions={<ScoringInfo />} />

      <main className="page">
        {historyError && <p className="muted">Couldn't load your recent scores.</p>}
        <GameweekScoreStrip
          items={pastScores}
          cardProps={(item) => prefetchOnIntent(api.predictionsGameweek(item.gameweek))}
        />

        {upcoming.length > 0 && (
          <div className="toolbar">
            <GameweekPicker gameweeks={upcoming} selected={selected} onChange={setSelected} />
            {data && !data.is_locked && countdown && (
              <p className={`deadline${countdown.urgent ? " is-urgent" : ""}`}>
                Closes in <strong>{countdown.text}</strong>
              </p>
            )}
          </div>
        )}

        {loadError && <div className="error-banner">{loadError}</div>}
        {queryError && <div className="error-banner">{queryError}</div>}

        {gameweeks === null && !loadError && <LoadingIndicator label="Loading fixtures..." />}

        {gameweeks && gameweeks.length === 0 && (
          <p className="muted">
            Fixtures haven't been loaded yet. They're pulled in automatically from the Premier League,
            so check back shortly.
          </p>
        )}

        {gameweeks && gameweeks.length > 0 && upcoming.length === 0 && (
          <p className="muted">
            Every gameweek has been played and scored, so there's nothing left to predict this season.
            Your scores above show how it went.
          </p>
        )}

        {upcoming.length > 0 && !data && !queryError && <LoadingIndicator label="Loading gameweek..." />}

        {data && data.is_locked && (
          <>
            <p className="locked-note">{LOCKED_MESSAGES[data.lifecycle]}</p>
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
                      ? <PredictionResult fixture={fixture} />
                      : undefined
                  }
                />
              ))}
            </div>
          </>
        )}

        {data && !data.is_locked && (
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
                      {fixture.prediction != null && <span className="saved-tag">Saved</span>}
                    </>
                  }
                />
              ))}
            </div>

            {/* Stays in view at the bottom of the screen while you fill in scores. */}
            <div className="save-bar">
              <p className={`save-bar-status${actionError ? " is-error" : ""}`} role="status">
                {actionError ||
                  message ||
                  (missingCount > 0
                    ? `${predictedCount} of ${data.fixtures.length} matches predicted`
                    : "Every match predicted")}
              </p>
              <button type="submit" className="primary" disabled={!canSave || saving || justSaved}>
                {saving ? "Saving..." : justSaved ? "Saved" : "Save predictions"}
              </button>
            </div>
          </form>
        )}
      </main>
    </>
  );
}
