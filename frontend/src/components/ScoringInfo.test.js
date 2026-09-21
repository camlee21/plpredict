import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calculatePoints } from "../utils/scoring";
import ScoringInfo, { SCORING_RULES } from "./ScoringInfo";

const openDialog = () => userEvent.click(screen.getByRole("button", { name: /how scoring works/i }));

describe("ScoringInfo", () => {
  test("is closed until the button is clicked", () => {
    render(<ScoringInfo />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    openDialog();
    expect(screen.getByRole("dialog", { name: /how scoring works/i })).toBeInTheDocument();
  });

  test("lists every scoring rule with an example", () => {
    render(<ScoringInfo />);
    openDialog();

    expect(screen.getByText("Exact score in a high-scoring match")).toBeInTheDocument();
    expect(screen.getByText("Exact score")).toBeInTheDocument();
    expect(screen.getByText("Correct result")).toBeInTheDocument();
    expect(screen.getByText("Wrong result")).toBeInTheDocument();
    expect(screen.getAllByText(/you predict/i)).toHaveLength(SCORING_RULES.length);
    expect(screen.getByText("4 pts")).toBeInTheDocument();
    expect(screen.getByText("1 pt")).toBeInTheDocument();
  });

  test("every example's points match the real scoring function", () => {
    SCORING_RULES.forEach((rule) => {
      expect(calculatePoints(...rule.predicted, ...rule.actual)).toBe(rule.points);
    });
  });

  test("closes with the X button and returns focus to the trigger", () => {
    render(<ScoringInfo />);
    openDialog();
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();

    userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /how scoring works/i })).toHaveFocus();
  });

  test("closes on Escape", () => {
    render(<ScoringInfo />);
    openDialog();

    userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("closes when the backdrop is clicked, but not when the dialog itself is", () => {
    render(<ScoringInfo />);
    openDialog();
    const dialog = screen.getByRole("dialog");

    fireEvent.mouseDown(dialog);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.mouseDown(dialog.parentElement);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("stops the page behind it from scrolling while open", () => {
    render(<ScoringInfo />);
    openDialog();
    expect(document.body.style.overflow).toBe("hidden");

    userEvent.keyboard("{Escape}");
    expect(document.body.style.overflow).not.toBe("hidden");
  });
});
