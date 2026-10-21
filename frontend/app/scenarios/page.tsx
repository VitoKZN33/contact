"use client";

import Link from "next/link";
import { useState } from "react";

import { Screen } from "@/components/ui/Screen";
import { ErrorState, SkeletonLines } from "@/components/ui/States";
import { useCategories, useScenarios } from "@/features/queries";
import { errorText } from "@/lib/api";

export default function ScenariosPage() {
  const [category, setCategory] = useState<string | null>(null);
  const categories = useCategories();
  const scenarios = useScenarios(category);

  return (
    <Screen title="Выберите ситуацию" subtitle="Собеседника и сложность настроите на следующем шаге." back="/">
      <div className="no-scrollbar -mx-4 mb-5 flex gap-2 overflow-x-auto px-4" role="tablist" aria-label="Категории">
        <CategoryChip label="Все" active={category === null} onClick={() => setCategory(null)} />
        {categories.data?.items.map((c) => (
          <CategoryChip key={c.key} label={c.title} active={category === c.key} onClick={() => setCategory(c.key)} />
        ))}
      </div>

      {scenarios.isPending ? <SkeletonLines rows={5} /> : null}
      {scenarios.isError ? <ErrorState message={errorText(scenarios.error)} onRetry={() => scenarios.refetch()} /> : null}

      {scenarios.data ? (
        <ul className="space-y-2">
          {scenarios.data.items.map((s) => (
            <li key={s.id}>
              <Link
                href={`/setup/?id=${s.id}`}
                className="block rounded-[var(--radius-card)] bg-card p-4 active:bg-surface"
              >
                <span className="block text-caption text-muted">{s.category_title}</span>
                <span className="mt-1 block text-body font-semibold">{s.title}</span>
                <span className="mt-1 block text-small text-muted text-pretty">{s.description}</span>
                <span className="mt-2 block text-caption text-muted">
                  {s.requires_custom_situation
                    ? "Опишете сами"
                    : s.starts === "persona"
                      ? "Собеседник начнёт первым"
                      : "Вы начинаете разговор"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </Screen>
  );
}

function CategoryChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`h-9 shrink-0 rounded-full px-3.5 text-caption font-medium transition-colors ${
        active ? "bg-text text-bg" : "bg-card text-muted"
      }`}
    >
      {label}
    </button>
  );
}
