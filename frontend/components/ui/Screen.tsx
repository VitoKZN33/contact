"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { showBackButton } from "@/lib/telegram";

type Props = {
  title?: string;
  subtitle?: string;
  /** Куда ведёт кнопка «Назад» Telegram; без значения кнопка скрыта */
  back?: string | "history";
  children: ReactNode;
  footer?: ReactNode;
};

/** Каркас экрана: заголовок, содержимое, закреплённая нижняя панель. */
export function Screen({ title, subtitle, back, children, footer }: Props) {
  useTelegramBack(back);
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-lg flex-col">
      <main className="flex-1 px-4 pb-6 pt-6">
        {title ? (
          <header className="mb-6">
            <h1 className="text-display font-semibold tracking-[-0.02em] text-balance">{title}</h1>
            {subtitle ? <p className="mt-2 text-small text-muted text-pretty">{subtitle}</p> : null}
          </header>
        ) : null}
        {children}
      </main>
      {footer ? (
        <div className="sticky bottom-0 border-t border-line/60 bg-bg/95 px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-3 backdrop-blur">
          {footer}
        </div>
      ) : null}
    </div>
  );
}

export function useTelegramBack(back?: string | "history") {
  const router = useRouter();
  useEffect(() => {
    if (!back) return;
    return showBackButton(() => {
      if (back === "history") router.back();
      else router.push(back);
    });
  }, [back, router]);
}

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="mt-8">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-title font-semibold tracking-[-0.01em]">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-[var(--radius-card)] bg-card p-4 ${className}`}>{children}</div>;
}
