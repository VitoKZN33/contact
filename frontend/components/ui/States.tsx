import type { ReactNode } from "react";

import { Button } from "./Button";

export function SkeletonLines({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy aria-label="Загрузка">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-[76px] animate-pulse rounded-[var(--radius-card)] bg-card" />
      ))}
    </div>
  );
}

export function FullScreenLoader({ label = "Загрузка" }: { label?: string }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6" aria-busy>
      <div className="flex gap-1.5" aria-hidden>
        <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
        <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
        <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
      </div>
      <p className="text-small text-muted">{label}</p>
    </div>
  );
}

export function ErrorState({
  title = "Не загрузилось",
  message,
  onRetry,
  action,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-[var(--radius-card)] bg-card p-5" role="alert">
      <p className="text-body font-semibold">{title}</p>
      <p className="mt-1 text-small text-muted text-pretty">{message}</p>
      {onRetry || action ? (
        <div className="mt-4 flex flex-col gap-2">
          {onRetry ? (
            <Button variant="secondary" onClick={onRetry}>
              Повторить
            </Button>
          ) : null}
          {action}
        </div>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-dashed border-line p-6 text-center">
      <p className="text-body font-semibold">{title}</p>
      <p className="mx-auto mt-1 max-w-xs text-small text-muted text-pretty">{message}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
