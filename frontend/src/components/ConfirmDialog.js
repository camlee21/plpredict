import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

// A confirm/cancel window for destructive actions. Focus starts on Cancel so
// a stray Enter can't delete anything, Tab cycles between the two buttons,
// and while `busy` the dialog can't be dismissed mid-request.
export default function ConfirmDialog({
  title,
  children,
  confirmLabel,
  busyLabel,
  busy = false,
  error = "",
  onConfirm,
  onCancel,
}) {
  const titleId = useId();
  const cancelRef = useRef(null);
  const confirmRef = useRef(null);
  const busyRef = useRef(busy);
  busyRef.current = busy;

  useEffect(() => {
    cancelRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (e) => {
      if (e.key === "Escape" && !busyRef.current) onCancel();
      if (e.key === "Tab") {
        // Only two focusable controls: cycle focus between them ourselves.
        e.preventDefault();
        const buttons = [cancelRef.current, confirmRef.current].filter((b) => b && !b.disabled);
        if (buttons.length === 0) return;
        const index = buttons.indexOf(document.activeElement);
        const step = e.shiftKey ? -1 : 1;
        const next = index === -1 ? (e.shiftKey ? buttons.length - 1 : 0) : (index + step + buttons.length) % buttons.length;
        buttons[next].focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onCancel]);

  return createPortal(
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div className="modal confirm-modal" role="alertdialog" aria-modal="true" aria-labelledby={titleId}>
        <h2 id={titleId}>{title}</h2>
        <div className="confirm-body">{children}</div>
        {error && <div className="error-banner">{error}</div>}
        <div className="confirm-actions">
          <button ref={cancelRef} type="button" className="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button ref={confirmRef} type="button" className="danger-solid" onClick={onConfirm} disabled={busy}>
            {busy ? busyLabel || "Working..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
