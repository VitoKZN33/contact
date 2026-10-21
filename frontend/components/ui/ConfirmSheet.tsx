"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "./Button";

type Props = {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/** Нижний лист подтверждения — для действий, которые нельзя отменить. */
export function ConfirmSheet({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel = "Отмена",
  destructive = false,
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" role="dialog" aria-modal aria-labelledby="sheet-title">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/60" onClick={onCancel} />
      <div className="message-in relative w-full max-w-lg rounded-t-[24px] bg-card px-5 pb-[max(20px,env(safe-area-inset-bottom))] pt-6">
        <h2 id="sheet-title" className="text-title font-semibold">
          {title}
        </h2>
        <div className="mt-2 text-small text-muted text-pretty">{message}</div>
        <div className="mt-6 flex flex-col gap-2">
          <Button variant={destructive ? "danger" : "primary"} loading={loading} onClick={onConfirm}>
            {confirmLabel}
          </Button>
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="h-12 rounded-[var(--radius-control)] text-small font-medium text-muted active:text-text"
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
