import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmDialog from "./ConfirmDialog";

const renderDialog = (props = {}) => {
  const onConfirm = jest.fn();
  const onCancel = jest.fn();
  render(
    <ConfirmDialog title="Delete it?" confirmLabel="Delete" onConfirm={onConfirm} onCancel={onCancel} {...props}>
      <p>This can't be undone.</p>
    </ConfirmDialog>
  );
  return { onConfirm, onCancel };
};

describe("ConfirmDialog", () => {
  test("shows the title and message, with focus on Cancel", () => {
    renderDialog();
    expect(screen.getByRole("alertdialog", { name: "Delete it?" })).toBeInTheDocument();
    expect(screen.getByText("This can't be undone.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  test("only confirms when the confirm button is clicked", () => {
    const { onConfirm, onCancel } = renderDialog();
    userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  test("Cancel, Esc and a backdrop click all cancel without confirming", () => {
    const { onConfirm, onCancel } = renderDialog();
    userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.mouseDown(document.querySelector(".modal-overlay"));
    expect(onCancel).toHaveBeenCalledTimes(3);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  test("clicking inside the dialog does not dismiss it", () => {
    const { onCancel } = renderDialog();
    fireEvent.mouseDown(screen.getByText("This can't be undone."));
    expect(onCancel).not.toHaveBeenCalled();
  });

  test("while busy it can't be dismissed and both buttons are disabled", () => {
    const { onCancel } = renderDialog({ busy: true, busyLabel: "Deleting..." });
    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.mouseDown(document.querySelector(".modal-overlay"));
    expect(onCancel).not.toHaveBeenCalled();
  });

  test("Tab cycles between the two buttons", () => {
    renderDialog();
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Delete" });

    fireEvent.keyDown(document, { key: "Tab" });
    expect(confirm).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(cancel).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(confirm).toHaveFocus();
  });

  test("shows an error and locks page scroll while open", () => {
    const { unmount } = render(
      <ConfirmDialog title="t" confirmLabel="Delete" error="Only the creator can delete it." onConfirm={() => {}} onCancel={() => {}}>
        body
      </ConfirmDialog>
    );
    expect(screen.getByText("Only the creator can delete it.")).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).not.toBe("hidden");
  });
});
