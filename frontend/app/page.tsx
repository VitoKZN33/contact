"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { z } from "zod";

import { apiGet } from "@/lib/api";
import { getInitData, getWebApp } from "@/lib/telegram";

// Этап 2: служебная стартовая страница для проверки связки
// Telegram → Nginx → backend → PostgreSQL. Главная появится на Этапе 5.

const liveSchema = z.object({ status: z.literal("ok") });

const readySchema = z.object({
  status: z.string(),
  checks: z.object({ database: z.string() }),
});

type Check = { label: string; state: "ok" | "fail" | "pending"; hint?: string };

export default function HomePage() {
  const [telegram, setTelegram] = useState<{ inside: boolean; platform: string } | null>(null);

  useEffect(() => {
    const app = getWebApp();
    setTelegram({ inside: getInitData() !== null, platform: app?.platform ?? "браузер" });
  }, []);

  const live = useQuery({
    queryKey: ["health-live"],
    queryFn: () => apiGet("/health/live", liveSchema),
  });
  const ready = useQuery({
    queryKey: ["health-ready"],
    queryFn: () => apiGet("/health/ready", readySchema),
  });

  const checks: Check[] = [
    {
      label: "Открыто из Telegram",
      state: telegram === null ? "pending" : telegram.inside ? "ok" : "fail",
      hint: telegram === null ? undefined : telegram.inside ? telegram.platform : "откройте через бота",
    },
    {
      label: "Backend",
      state: live.isPending ? "pending" : live.isSuccess ? "ok" : "fail",
      hint: live.error?.message,
    },
    {
      label: "База данных",
      state: ready.isPending ? "pending" : ready.isSuccess ? "ok" : "fail",
      hint: ready.isError ? "backend не видит PostgreSQL" : undefined,
    },
  ];

  const refresh = () => {
    void live.refetch();
    void ready.refetch();
  };
  const fetching = live.isFetching || ready.isFetching;

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col px-4 pb-8 pt-10">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted">Каркас · Этап 2</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Контакт</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Тренажёр живого общения. Эта страница проверяет, что все части приложения связаны.
      </p>

      <ul className="mt-8 space-y-2">
        {checks.map((check) => (
          <li
            key={check.label}
            className="flex items-center justify-between rounded-[var(--radius-card)] bg-card px-4 py-4"
          >
            <div>
              <p className="text-sm font-medium">{check.label}</p>
              {check.hint ? <p className="mt-0.5 text-xs text-muted">{check.hint}</p> : null}
            </div>
            <StatusDot state={check.state} />
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={refresh}
        disabled={fetching}
        className="mt-6 h-12 rounded-[var(--radius-control)] bg-accent text-sm font-semibold text-bg transition-opacity active:opacity-80 disabled:opacity-50"
      >
        {fetching ? "Проверяю…" : "Проверить ещё раз"}
      </button>
    </main>
  );
}

function StatusDot({ state }: { state: Check["state"] }) {
  const label = state === "ok" ? "работает" : state === "fail" ? "ошибка" : "проверка";
  const color = state === "ok" ? "bg-success" : state === "fail" ? "bg-danger" : "bg-surface animate-pulse";
  return (
    <span className="flex items-center gap-2 text-xs text-muted">
      {label}
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} aria-hidden />
    </span>
  );
}
