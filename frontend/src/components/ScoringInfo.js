import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Mirrors backend/predictions/scoring.py. ScoringInfo.test.js checks every
// example's points against calculatePoints, so these can't drift from the rules.
export const SCORING_RULES = [
  {
    points: 4,
    title: "Exact score in a high-scoring match",
    detail: "You got the score exactly right and the match had 5 or more goals in total.",
    predicted: [3, 2],
    actual: [3, 2],
  },
  {
    points: 3,
    title: "Exact score",
    detail: "You got the score exactly right.",
    predicted: [2, 1],
    actual: [2, 1],
  },
  {
    points: 1,
    title: "Correct result",
    detail: "You picked the right winner (or a draw), but not the exact score.",
    predicted: [2, 1],
    actual: [3, 0],
  },
  {
    points: 0,
    title: "Wrong result",
    detail: "You picked the wrong winner, or a draw when there was a winner.",
    predicted: [2, 1],
    actual: [0, 1],
  },
];

const EXAMPLE_MATCH = "Arsenal v Chelsea";

function ScoringDialog({ onClose }) {
  const titleId = useId();
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (e) => {
      if (e.key === "Escape") onClose();
      // The close button is the only focusable thing in here, so keep focus on it.
      if (e.key === "Tab") {
        e.preventDefault();
        closeRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="modal-header">
          <h2 id={titleId}>How scoring works</h2>
          <button ref={closeRef} type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            &times;
          </button>
        </div>

        <p className="muted">
          Each match is scored separately, by comparing your prediction with the full-time score.
        </p>

        <ul className="scoring-rules">
          {SCORING_RULES.map((rule) => (
            <li className="scoring-rule" key={rule.points}>
              <span className={`points-badge points-${rule.points}`}>
                {rule.points} {rule.points === 1 ? "pt" : "pts"}
              </span>
              <div>
                <strong>{rule.title}</strong>
                <p className="muted small">{rule.detail}</p>
                <p className="scoring-example small">
                  {EXAMPLE_MATCH}: you predict {rule.predicted[0]}-{rule.predicted[1]}, it finishes{" "}
                  {rule.actual[0]}-{rule.actual[1]}.
                </p>
              </div>
            </li>
          ))}
        </ul>

        <h3>Adding it up</h3>
        <ul className="scoring-notes">
          <li>
            Your gameweek score is the total of your points from every match in that gameweek.
            Matches you didn't predict score 0.
          </li>
          <li>
            In a league table, <strong>Total</strong> only counts the gameweeks since you joined
            that league - points you scored beforehand never carry into it, so everyone who joins
            starts level. Clicking a player's name shows their gameweek-by-gameweek record there.
          </li>
          <li>
            The <strong>GW</strong> column shows your points so far in the current gameweek - they
            move into Total once the gameweek is finalised, about 2&frac12; hours after its last
            kickoff. Players on the same total share a rank (e.g. =3rd).
          </li>
          <li>
            Predictions lock 1 hour before the first match of the gameweek, and other players'
            predictions stay hidden until that match kicks off. Postponed matches aren't scored.
          </li>
        </ul>
      </div>
    </div>
  );
}

export default function ScoringInfo() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef(null);

  const close = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus();
  }, []);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="info-button"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        <span className="info-icon" aria-hidden="true">
          i
        </span>
        How scoring works
      </button>
      {open && createPortal(<ScoringDialog onClose={close} />, document.body)}
    </>
  );
}
