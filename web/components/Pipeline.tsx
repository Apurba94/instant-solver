"use client";

import type { StageEvent } from "@/lib/types";
import { Badge, cx } from "./ui";

/**
 * The live pipeline view.
 *
 * This is not decoration. A solve takes tens of seconds, and showing the stages
 * as they complete does three things at once: it proves the system is working,
 * it shows *what* verification is being done (which is the product's actual
 * claim), and it teaches — the user watches a complexity budget get derived
 * from the constraints, which is the habit they are here to learn.
 */

const STAGE_LABELS: Record<string, string> = {
  ingest: "Read the problem",
  analyze: "Derive the complexity budget",
  retrieve: "Check known problems",
  plan: "Choose an approach",
  synthesize: "Write the solution",
  compile: "Compile",
  sample_test: "Run the samples",
  repair: "Repair from the failure",
  stress_test: "Hunt for a counterexample",
  perf_probe: "Time it at full scale",
  explain: "Write the explanation",
  done: "Done",
};

export function Pipeline({
  events,
  running,
}: {
  events: StageEvent[];
  running: boolean;
}) {
  if (events.length === 0) return null;

  // Collapse repeated stages (stress testing emits progress ticks) so the list
  // reads as a sequence of steps, not a log file.
  const rows: StageEvent[] = [];
  for (const event of events) {
    const last = rows[rows.length - 1];
    if (last && last.stage === event.stage && last.ok === event.ok) rows[rows.length - 1] = event;
    else rows.push(event);
  }

  return (
    <ol className="space-y-0">
      {rows.map((event, i) => {
        const isLast = i === rows.length - 1;
        const active = running && isLast;
        return (
          <li key={`${event.stage}-${i}`} className="animate-slide-in flex gap-3">
            <div className="flex flex-col items-center">
              <span
                className={cx(
                  "mt-[7px] h-2 w-2 shrink-0 rounded-full",
                  !event.ok
                    ? "bg-[var(--color-bad)]"
                    : active
                      ? "animate-pulse-dot bg-[var(--color-accent)]"
                      : "bg-[var(--color-ok)]",
                )}
              />
              {!isLast && <span className="w-px flex-1 bg-[var(--color-line)]" />}
            </div>
            <div className={cx("min-w-0 pb-3", isLast && "pb-0")}>
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-[13px] font-medium">
                  {STAGE_LABELS[event.stage] ?? event.stage}
                </span>
                {!event.ok && (
                  <Badge tone="bad" className="text-[10px]">
                    failed
                  </Badge>
                )}
              </div>
              <p className="mt-0.5 text-xs leading-relaxed text-[var(--color-ink-muted)]">
                {event.message}
              </p>
              {typeof event.input === "string" && (
                <pre className="mt-1.5 overflow-auto rounded border border-[var(--color-bad)]/30 bg-[var(--color-bad-dim)] p-2 font-[family-name:var(--font-mono)] text-[11px]">
                  {event.input}
                </pre>
              )}
              {typeof event.log === "string" && (
                <pre className="mt-1.5 max-h-40 overflow-auto rounded border border-[var(--color-line)] bg-[var(--color-surface-2)] p-2 font-[family-name:var(--font-mono)] text-[11px]">
                  {event.log}
                </pre>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
