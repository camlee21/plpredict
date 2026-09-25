import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

// How far the pointer must move before a mouse drag counts as a scroll
// rather than a click on a card.
const DRAG_THRESHOLD = 5;

const prefersReducedMotion = () =>
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * A horizontally scrollable row of past gameweek scores in season order, so
 * earlier gameweeks sit to the left and the most recent to the right. It
 * opens scrolled to the right-hand end, where the newest scores are. How many
 * fit at once is down to the CSS (three on desktop, fewer as the screen
 * narrows). It can be scrolled by dragging with a mouse, swiping on a touch
 * screen (native scrolling - we deliberately don't intercept it), or with the
 * arrows on either side. Each card links to that gameweek's score breakdown.
 */
export default function GameweekScoreStrip({ items, heading = "Recent scores", cardProps }) {
  const trackRef = useRef(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(true);
  // Scroll snapping quantises scrollLeft, so a drag would jump from card to
  // card instead of following the cursor. Snapping is turned off for the
  // duration of the drag and restored on release, which settles it neatly.
  const [dragging, setDragging] = useState(false);
  // A drag in progress, plus whether it has passed the threshold - which is
  // what tells a click on a card apart from the end of a drag.
  const drag = useRef({ active: false, startX: 0, startScroll: 0, moved: false });

  const syncArrows = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    setAtStart(el.scrollLeft <= 1);
    // Sub-pixel widths mean scrollLeft can stop a fraction short of maxScroll.
    setAtEnd(el.scrollLeft >= maxScroll - 1);
  }, []);

  // The latest gameweek is the one you want first, and it lives at the far
  // right. Done before paint so the strip never flashes at the wrong end.
  useLayoutEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    el.scrollLeft = el.scrollWidth - el.clientWidth;
    syncArrows();
  }, [items, syncArrows]);

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return undefined;
    syncArrows();
    if (typeof ResizeObserver === "undefined") return undefined;
    // Card widths are percentage-based, so a resize changes what's reachable.
    const observer = new ResizeObserver(syncArrows);
    observer.observe(el);
    return () => observer.disconnect();
  }, [syncArrows, items]);

  const scrollByPage = (direction) => {
    const el = trackRef.current;
    if (!el) return;
    el.scrollBy({
      left: direction * el.clientWidth,
      behavior: prefersReducedMotion() ? "auto" : "smooth",
    });
  };

  const onPointerDown = (e) => {
    // Touch and pen get the browser's own scrolling, which already has
    // momentum and rubber-banding - hijacking it would feel worse.
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    drag.current = {
      active: true,
      startX: e.clientX,
      startScroll: trackRef.current.scrollLeft,
      moved: false,
    };
  };

  const onPointerMove = (e) => {
    const state = drag.current;
    if (!state.active) return;
    const dx = e.clientX - state.startX;
    if (!state.moved && Math.abs(dx) > DRAG_THRESHOLD) {
      state.moved = true;
      // Only capture once it's definitely a drag, so a plain click is untouched.
      trackRef.current.setPointerCapture?.(e.pointerId);
    }
    if (state.moved) {
      setDragging(true);
      e.preventDefault();
      trackRef.current.scrollLeft = state.startScroll - dx;
    }
  };

  const endDrag = (e) => {
    const state = drag.current;
    if (!state.active) return;
    state.active = false;
    setDragging(false);
    if (trackRef.current?.hasPointerCapture?.(e.pointerId)) {
      trackRef.current.releasePointerCapture(e.pointerId);
    }
  };

  // The click that ends a drag would otherwise open whichever card the mouse
  // happened to finish on. `moved` stays set until this fires; if no click
  // follows at all, the next pointerdown clears it.
  const onClickCapture = (e) => {
    if (!drag.current.moved) return;
    drag.current.moved = false;
    e.preventDefault();
    e.stopPropagation();
  };

  if (!items.length) return null;

  const hasArrows = !(atStart && atEnd);

  return (
    <section className="score-strip" aria-label={heading}>
      <h2>{heading}</h2>
      <div className="score-strip-row">
        {hasArrows && (
          <button
            type="button"
            className="score-strip-arrow"
            aria-label="Show earlier gameweeks"
            disabled={atStart}
            onClick={() => scrollByPage(-1)}
          >
            <span aria-hidden="true">&#8249;</span>
          </button>
        )}

        <div
          className={`score-strip-track${dragging ? " is-dragging" : ""}`}
          ref={trackRef}
          onScroll={syncArrows}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onClickCapture={onClickCapture}
        >
          {items.map((item) => (
            <Link
              key={item.gameweek}
              to={`/scores/${item.gameweek}`}
              className={`score-strip-card${item.hasPredictions ? "" : " is-empty"}`}
              // e.g. handlers that prefetch the gameweek before it's opened.
              {...cardProps?.(item)}
              // Without this the browser starts a native link drag, which
              // would cancel the scroll drag half way through.
              draggable={false}
              aria-label={
                item.hasPredictions
                  ? `Gameweek ${item.gameweek}: ${item.points} points`
                  : `Gameweek ${item.gameweek}: no predictions`
              }
            >
              <span className="score-strip-gw">GW{item.gameweek}</span>
              <span className="score-strip-points">
                {item.hasPredictions ? item.points : "-"}
              </span>
              <span className="score-strip-label">{item.hasPredictions ? "points" : "no predictions"}</span>
            </Link>
          ))}
        </div>

        {hasArrows && (
          <button
            type="button"
            className="score-strip-arrow"
            aria-label="Show more recent gameweeks"
            disabled={atEnd}
            onClick={() => scrollByPage(1)}
          >
            <span aria-hidden="true">&#8250;</span>
          </button>
        )}
      </div>
    </section>
  );
}
