import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  // Янтарь — только у главного действия экрана
  primary: "bg-accent text-accent-ink font-semibold active:brightness-95",
  secondary: "bg-surface text-text font-medium active:bg-line",
  ghost: "bg-transparent text-muted font-medium active:text-text",
  danger: "bg-transparent text-danger font-medium ring-1 ring-inset ring-danger/40 active:bg-danger/10",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
  block?: boolean;
  children: ReactNode;
};

export function Button({ variant = "primary", loading = false, block = true, className = "", disabled, children, ...rest }: Props) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`${block ? "w-full" : ""} inline-flex h-13 min-h-[52px] items-center justify-center gap-2 rounded-[var(--radius-control)] px-5 text-small transition-[opacity,filter,background-color] duration-150 disabled:opacity-45 ${VARIANTS[variant]} ${className}`}
    >
      {loading ? <Spinner /> : null}
      <span>{children}</span>
    </button>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent ${className}`}
    />
  );
}
