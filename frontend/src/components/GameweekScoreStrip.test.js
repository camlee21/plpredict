import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import GameweekScoreStrip from "./GameweekScoreStrip";

// jsdom doesn't implement PointerEvent, so without this fireEvent falls back
// to a bare Event and pointerType/clientX never reach the handler.
beforeAll(() => {
  window.PointerEvent = class PointerEvent extends MouseEvent {
    constructor(type, init = {}) {
      super(type, init);
      this.pointerType = init.pointerType;
      this.pointerId = init.pointerId;
    }
  };
  // jsdom has no layout, so the track would always look like it fits. These
  // stand in for it, and have to exist before mount because the strip scrolls
  // itself to the newest gameweek on the way in.
  for (const [prop, key] of [["scrollWidth", "scrollWidth"], ["clientWidth", "clientWidth"]]) {
    Object.defineProperty(HTMLElement.prototype, prop, {
      configurable: true,
      get() {
        return this.classList.contains("score-strip-track") ? layout[key] : 0;
      },
    });
  }
  // Each card's position along the track, `cardStep` apart (0 = no layout).
  Object.defineProperty(HTMLElement.prototype, "offsetLeft", {
    configurable: true,
    get() {
      if (!this.classList.contains("score-strip-card")) return 0;
      return [...this.parentNode.children].indexOf(this) * layout.cardStep;
    },
  });
});

let layout;
beforeEach(() => {
  layout = { scrollWidth: 900, clientWidth: 300, cardStep: 0 };
});

const ITEMS = [
  { gameweek: 3, points: 4, hasPredictions: true },
  { gameweek: 4, points: 0, hasPredictions: false },
  { gameweek: 5, points: 12, hasPredictions: true },
];

function LocationDisplay() {
  return <span data-testid="location">{useLocation().pathname}</span>;
}

const currentPath = () => screen.getByTestId("location").textContent;
const track = () => document.querySelector(".score-strip-track");

function renderStrip(items = ITEMS) {
  const result = render(
    <MemoryRouter>
      <GameweekScoreStrip items={items} />
      <LocationDisplay />
    </MemoryRouter>
  );
  const el = track();
  if (el) {
    el.scrollTo = jest.fn(({ left }) => {
      el.scrollLeft = left;
      fireEvent.scroll(el);
    });
  }
  return result;
}

const earlierButton = () => screen.getByRole("button", { name: "Show earlier gameweeks" });
const recentButton = () => screen.getByRole("button", { name: "Show more recent gameweeks" });

describe("GameweekScoreStrip", () => {
  test("renders a card per gameweek in season order, linking to its score page", () => {
    renderStrip();
    const links = screen.getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/scores/3", "/scores/4", "/scores/5"]);
    expect(links[2]).toHaveAccessibleName("Gameweek 5: 12 points");
  });

  test("opens scrolled to the newest gameweek, at the right-hand end", () => {
    renderStrip();
    expect(track().scrollLeft).toBe(600);
    // Nothing more recent to reach, but there is earlier history to scroll back to.
    expect(recentButton()).toBeDisabled();
    expect(earlierButton()).toBeEnabled();
  });

  test("a gameweek with no predictions shows a dash, not a zero", () => {
    renderStrip();
    const card = screen.getByRole("link", { name: "Gameweek 4: no predictions" });
    expect(card).toHaveTextContent("-");
    expect(card).toHaveTextContent("no predictions");
    expect(card).not.toHaveTextContent("0");
  });

  test("renders nothing at all when there are no scored gameweeks", () => {
    renderStrip([]);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(document.querySelector(".score-strip")).not.toBeInTheDocument();
  });

  test("hides the arrows when every card already fits", () => {
    layout = { scrollWidth: 300, clientWidth: 300 };
    renderStrip();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  test("the arrows page backwards and forwards, disabling at each end", () => {
    renderStrip();
    const el = track();

    // Left goes back in time, towards gameweek 3.
    userEvent.click(earlierButton());
    expect(el.scrollTo).toHaveBeenCalledWith(expect.objectContaining({ left: 300 }));
    expect(el.scrollLeft).toBe(300);
    expect(recentButton()).toBeEnabled();

    userEvent.click(earlierButton());
    expect(el.scrollLeft).toBe(0);
    expect(earlierButton()).toBeDisabled();

    // Right comes back towards the newest.
    userEvent.click(recentButton());
    expect(el.scrollTo).toHaveBeenLastCalledWith(expect.objectContaining({ left: 300 }));
    expect(el.scrollLeft).toBe(300);
    expect(earlierButton()).toBeEnabled();
  });

  test("after a swipe part-way back, the arrow stops with the newest gameweek flush right", () => {
    // Nine cards 100px apart, three to a screen: the far end is at 600.
    layout = { scrollWidth: 890, clientWidth: 290, cardStep: 100 };
    const items = Array.from({ length: 9 }, (_, i) => ({ gameweek: i + 1, points: i, hasPredictions: true }));
    renderStrip(items);
    const el = track();

    // A swipe back of about one card leaves the track between cards.
    el.scrollLeft = 530;
    fireEvent.scroll(el);
    userEvent.click(recentButton());
    expect(el.scrollLeft).toBe(600);
    expect(recentButton()).toBeDisabled();

    // Going back pages by whole cards from there.
    userEvent.click(earlierButton());
    expect(el.scrollLeft).toBe(300);
    userEvent.click(recentButton());
    expect(el.scrollLeft).toBe(600);
  });

  test("dragging with the mouse scrolls the track and suspends snapping", () => {
    renderStrip();
    const el = track();
    el.setPointerCapture = jest.fn();
    el.hasPointerCapture = jest.fn(() => true);
    el.releasePointerCapture = jest.fn();
    el.scrollLeft = 300;

    fireEvent.pointerDown(el, { pointerType: "mouse", button: 0, clientX: 200, pointerId: 1 });
    fireEvent.pointerMove(el, { pointerType: "mouse", clientX: 120, pointerId: 1 });
    expect(el.scrollLeft).toBe(380);
    // Snapping would quantise the drag into card-sized jumps.
    expect(el).toHaveClass("is-dragging");

    fireEvent.pointerUp(el, { pointerType: "mouse", pointerId: 1 });
    expect(el).not.toHaveClass("is-dragging");
    expect(el.releasePointerCapture).toHaveBeenCalled();
  });

  test("the click ending a drag does not open the card underneath", () => {
    renderStrip();
    const el = track();
    el.setPointerCapture = jest.fn();
    const card = screen.getByRole("link", { name: "Gameweek 5: 12 points" });

    fireEvent.pointerDown(el, { pointerType: "mouse", button: 0, clientX: 200, pointerId: 1 });
    fireEvent.pointerMove(el, { pointerType: "mouse", clientX: 120, pointerId: 1 });
    fireEvent.pointerUp(el, { pointerType: "mouse", pointerId: 1 });
    fireEvent.click(card);
    expect(currentPath()).toBe("/");

    // A later click, with no drag before it, still navigates.
    fireEvent.click(card);
    expect(currentPath()).toBe("/scores/5");
  });

  test("a click without dragging opens the card", () => {
    renderStrip();
    const el = track();
    const card = screen.getByRole("link", { name: "Gameweek 5: 12 points" });

    fireEvent.pointerDown(el, { pointerType: "mouse", button: 0, clientX: 200, pointerId: 1 });
    fireEvent.pointerMove(el, { pointerType: "mouse", clientX: 202, pointerId: 1 });
    fireEvent.pointerUp(el, { pointerType: "mouse", pointerId: 1 });
    expect(el.scrollLeft).toBe(600);
    fireEvent.click(card);
    expect(currentPath()).toBe("/scores/5");
  });

  test("touch scrolling is left to the browser", () => {
    renderStrip();
    const el = track();
    el.setPointerCapture = jest.fn();

    fireEvent.pointerDown(el, { pointerType: "touch", clientX: 200, pointerId: 2 });
    fireEvent.pointerMove(el, { pointerType: "touch", clientX: 120, pointerId: 2 });
    expect(el.scrollLeft).toBe(600);
    expect(el.setPointerCapture).not.toHaveBeenCalled();
    expect(el).not.toHaveClass("is-dragging");
  });
});
