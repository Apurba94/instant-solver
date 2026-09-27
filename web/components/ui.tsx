"use client";

import { ReactNode, useState } from "react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/* ---------------------------------------------------------------- Card */

export function Card({
  title,
  subtitle,
  right,
  children,
  className,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cx(
        "rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)]",
        className,
      )}
    >
      {(title || right) && (
        <header className="flex items-start justify-between gap-3 border-b border-[var(--color-line)] px-4 py-3">
          <div className="min-w-0">
            {title && (
              <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-[var(--color-ink-muted)]">{subtitle}</p>
            )}
          </div>
          {right && <div className="shrink-0">{right}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

/* --------------------------------------------------------------- Badge */

type Tone = "neutral" | "ok" | "warn" | "bad" | "info" | "accent";

const TONE_CLASS: Record<Tone, string> = {
  neutral:
    "bg-[var(--color-surface-2)] text-[var(--color-ink-muted)] border-[var(--color-line-strong)]",
  ok: "bg-[var(--color-ok-dim)] text-[var(--color-ok)] border-[var(--color-ok)]/35",
  warn: "bg-[var(--color-warn-dim)] text-[var(--color-warn)] border-[var(--color-warn)]/35",
  bad: "bg-[var(--color-bad-dim)] text-[var(--color-bad)] border-[var(--color-bad)]/35",
  info: "bg-[var(--color-accent-dim)]/40 text-[var(--color-info)] border-[var(--color-info)]/30",
  accent:
    "bg-[var(--color-accent-dim)]/40 text-[var(--color-accent)] border-[var(--color-accent)]/35",
};

export function Badge({
  tone = "neutral",
  children,
  mono,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        mono && "font-[family-name:var(--font-mono)]",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ---------------------------------------------------------- Verdict map */

export function verdictTone(verdict: string): Tone {
  if (verdict === "ACCEPTED") return "ok";
  if (verdict === "COMPILATION_ERROR" || verdict === "JUDGE_ERROR") return "warn";
  return "bad";
}

export function verdictLabel(verdict: string) {
  return verdict.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());
}

/* ---------------------------------------------------------------- Tabs */

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string; badge?: ReactNode }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      role="tablist"
      className="flex gap-1 overflow-x-auto border-b border-[var(--color-line)]"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={active === tab.id}
          onClick={() => onChange(tab.id)}
          className={cx(
            "flex items-center gap-2 border-b-2 px-3 py-2 text-sm whitespace-nowrap transition-colors",
            active === tab.id
              ? "border-[var(--color-accent)] text-[var(--color-ink)]"
              : "border-transparent text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]",
          )}
        >
          {tab.label}
          {tab.badge}
        </button>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------- Code block */

export function CodeBlock({
  code,
  label,
  maxHeight = "none",
}: {
  code: string;
  label?: string;
  maxHeight?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked — the code is still selectable */
    }
  }

  return (
    <div className="overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]">
      <div className="flex items-center justify-between border-b border-[var(--color-line)] px-3 py-1.5">
        <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--color-ink-faint)]">
          {label ?? "source"}
        </span>
        <button
          onClick={copy}
          className="rounded px-2 py-0.5 text-xs text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-line)] hover:text-[var(--color-ink)]"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        className="overflow-auto p-3 font-[family-name:var(--font-mono)] text-[12.5px] leading-[1.6]"
        style={{ maxHeight }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

/* ---------------------------------------------------------------- Misc */

export function Prose({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-3 text-[13.5px] leading-relaxed text-[var(--color-ink)]">
      {children}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-[var(--color-ink-muted)]">{label}</span>
        {hint && <span className="text-xs text-[var(--color-ink-faint)]">{hint}</span>}
      </div>
      {children}
    </label>
  );
}

export function NumberedList({ items }: { items: string[] }) {
  return (
    <ol className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3 text-[13.5px] leading-relaxed">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--color-surface-2)] font-[family-name:var(--font-mono)] text-[11px] text-[var(--color-ink-muted)]">
            {i + 1}
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ol>
  );
}

export function BulletList({ items, tone }: { items: string[]; tone?: Tone }) {
  const dot =
    tone === "bad"
      ? "bg-[var(--color-bad)]"
      : tone === "warn"
        ? "bg-[var(--color-warn)]"
        : "bg-[var(--color-ink-faint)]";
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3 text-[13.5px] leading-relaxed">
          <span className={cx("mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full", dot)} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
