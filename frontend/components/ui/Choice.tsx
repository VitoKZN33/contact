"use client";

import type { Option } from "@/lib/schemas";
import { haptic } from "@/lib/telegram";

/** Выбор одного варианта: сегменты для 2–3 коротких опций, плитки — для остальных. */
export function Choice({
  label,
  options,
  value,
  onChange,
  layout = "tiles",
  hints,
}: {
  label: string;
  options: Option[];
  value: string | null;
  onChange: (key: string) => void;
  layout?: "segments" | "tiles";
  hints?: Record<string, string>;
}) {
  const select = (key: string) => {
    haptic("tap");
    onChange(key);
  };
  return (
    <fieldset>
      <legend className="mb-2.5 text-small font-semibold">{label}</legend>
      {layout === "segments" ? (
        <div className="grid auto-cols-fr grid-flow-col gap-1 rounded-[var(--radius-control)] bg-card p-1" role="radiogroup">
          {options.map((o) => {
            const active = o.key === value;
            return (
              <button
                key={o.key}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => select(o.key)}
                className={`h-11 rounded-[11px] text-small font-medium transition-colors ${
                  active ? "bg-surface text-text" : "text-muted"
                }`}
              >
                {o.title}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2" role="radiogroup">
          {options.map((o) => {
            const active = o.key === value;
            return (
              <button
                key={o.key}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => select(o.key)}
                className={`min-h-[52px] rounded-[var(--radius-control)] px-3.5 py-3 text-left text-small transition-colors ${
                  active ? "bg-accent-soft text-text ring-1 ring-inset ring-accent" : "bg-card text-text"
                }`}
              >
                <span className="font-medium">{o.title}</span>
                {hints?.[o.key] ? <span className="mt-0.5 block text-caption text-muted">{hints[o.key]}</span> : null}
              </button>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}
