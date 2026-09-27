"use client";

import { useState } from "react";
import type { SolveResult } from "@/lib/types";
import {
  Badge,
  BulletList,
  Card,
  CodeBlock,
  NumberedList,
  Prose,
  Tabs,
  cx,
  verdictLabel,
  verdictTone,
} from "./ui";

/* ------------------------------------------------------- Confidence bar */

const CONFIDENCE_META: Record<
  string,
  { tone: "ok" | "warn" | "bad" | "accent" | "neutral"; label: string }
> = {
  VERIFIED: { tone: "ok", label: "Verified" },
  STRONG: { tone: "accent", label: "Strong" },
  LIKELY: { tone: "warn", label: "Likely" },
  UNVERIFIED: { tone: "warn", label: "Unverified" },
  FAILED: { tone: "bad", label: "Not solved" },
};

export function ConfidenceHeader({ result }: { result: SolveResult }) {
  const meta = CONFIDENCE_META[result.confidence] ?? CONFIDENCE_META.UNVERIFIED;
  const border =
    meta.tone === "ok"
      ? "border-[var(--color-ok)]/40"
      : meta.tone === "bad"
        ? "border-[var(--color-bad)]/40"
        : meta.tone === "warn"
          ? "border-[var(--color-warn)]/40"
          : "border-[var(--color-accent)]/40";

  return (
    <div className={cx("rounded-lg border bg-[var(--color-surface)] p-4", border)}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={meta.tone} className="text-xs uppercase tracking-wide">
          {meta.label}
        </Badge>
        {result.problem && (
          <span className="text-sm font-medium">{result.problem.title}</span>
        )}
        <span className="ml-auto font-[family-name:var(--font-mono)] text-xs text-[var(--color-ink-faint)]">
          {(result.elapsed_ms / 1000).toFixed(1)}s
        </span>
      </div>
      <p className="mt-2 text-[13.5px] leading-relaxed text-[var(--color-ink-muted)]">
        {result.headline}
      </p>
      {result.warnings.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-[var(--color-line)] pt-3">
          {result.warnings.map((warning, i) => (
            <li
              key={i}
              className="flex gap-2 text-xs leading-relaxed text-[var(--color-warn)]"
            >
              <span aria-hidden>▲</span>
              <span>{warning}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- Results */

export function Results({ result }: { result: SolveResult }) {
  const [tab, setTab] = useState("solution");
  const explanation = result.explanation;

  const tabs = [
    { id: "solution", label: "Solution" },
    { id: "explanation", label: "Explanation" },
    { id: "verification", label: "Verification" },
    { id: "analysis", label: "Analysis" },
  ];
  if (result.attempts.length > 1) tabs.push({ id: "attempts", label: `Attempts (${result.attempts.length})` });

  return (
    <div className="space-y-4">
      <ConfidenceHeader result={result} />

      <Card className="overflow-hidden">
        <div className="-m-4 mb-0">
          <Tabs tabs={tabs} active={tab} onChange={setTab} />
        </div>

        <div className="pt-4">
          {tab === "solution" && <SolutionTab result={result} />}
          {tab === "explanation" && <ExplanationTab result={result} />}
          {tab === "verification" && <VerificationTab result={result} />}
          {tab === "analysis" && <AnalysisTab result={result} />}
          {tab === "attempts" && <AttemptsTab result={result} />}
        </div>
      </Card>

      {explanation && tab === "explanation" && null}
    </div>
  );
}

/* ---------------------------------------------------------- Solution */

function SolutionTab({ result }: { result: SolveResult }) {
  if (!result.solution_code) {
    return (
      <p className="text-sm text-[var(--color-ink-muted)]">
        No solution was produced. The Attempts tab shows what was tried.
      </p>
    );
  }
  const complexity = result.explanation?.time_complexity || result.analysis?.budget?.allowed?.at(-1);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral" mono>
          {result.language}
        </Badge>
        {complexity && (
          <Badge tone="accent" mono>
            {complexity} time
          </Badge>
        )}
        {result.explanation?.space_complexity && (
          <Badge tone="neutral" mono>
            {result.explanation.space_complexity} space
          </Badge>
        )}
        {result.analysis?.chosen_technique && (
          <span className="text-xs text-[var(--color-ink-muted)]">
            {result.analysis.chosen_technique}
          </span>
        )}
      </div>
      <CodeBlock code={result.solution_code} label={`solution.${result.language}`} />
    </div>
  );
}

/* -------------------------------------------------------- Explanation */

function ExplanationTab({ result }: { result: SolveResult }) {
  const e = result.explanation;
  if (!e) {
    return (
      <p className="text-sm text-[var(--color-ink-muted)]">
        No explanation was generated for this solve.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <Block title="How you would find this">
        <Prose>
          <p>{e.intuition}</p>
        </Prose>
      </Block>

      {e.observations.length > 0 && (
        <Block title="Key observations">
          <BulletList items={e.observations} />
        </Block>
      )}

      {e.approach && (
        <Block title="Approach">
          <Prose>
            <p>{e.approach}</p>
          </Prose>
        </Block>
      )}

      {e.algorithm_steps.length > 0 && (
        <Block title="The algorithm">
          <NumberedList items={e.algorithm_steps} />
        </Block>
      )}

      {e.correctness && (
        <Block title="Why it is correct">
          <Prose>
            <p>{e.correctness}</p>
          </Prose>
        </Block>
      )}

      <Block title="Complexity">
        <div className="mb-2 flex flex-wrap gap-2">
          <Badge tone="accent" mono>
            {e.time_complexity} time
          </Badge>
          <Badge tone="neutral" mono>
            {e.space_complexity} space
          </Badge>
        </div>
        {e.complexity_justification && (
          <Prose>
            <p>{e.complexity_justification}</p>
          </Prose>
        )}
      </Block>

      {e.dry_run.length > 0 && (
        <Block
          title="Dry run on the first sample"
          subtitle="Step by step, with the real values from your sample input"
        >
          <ol className="space-y-0">
            {e.dry_run.map((step, i) => (
              <li key={i} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-accent)]" />
                  {i < e.dry_run.length - 1 && (
                    <span className="w-px flex-1 bg-[var(--color-line)]" />
                  )}
                </div>
                <div className="pb-3">
                  <p className="text-[13px] leading-relaxed">{step.step}</p>
                  <p className="mt-0.5 font-[family-name:var(--font-mono)] text-[11.5px] text-[var(--color-ink-muted)]">
                    {step.state}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </Block>
      )}

      {e.code_walkthrough.length > 0 && (
        <Block title="Line by line">
          <div className="space-y-2">
            {e.code_walkthrough.map((item, i) => (
              <div
                key={i}
                className="rounded border border-[var(--color-line)] bg-[var(--color-surface-2)] p-3"
              >
                <code className="font-[family-name:var(--font-mono)] text-[11.5px] text-[var(--color-accent)]">
                  {item.lines}
                </code>
                <p className="mt-1 text-[13px] leading-relaxed">{item.what}</p>
              </div>
            ))}
          </div>
        </Block>
      )}

      {e.pitfalls.length > 0 && (
        <Block title="What gets people wrong answers here">
          <BulletList items={e.pitfalls} tone="warn" />
        </Block>
      )}

      {e.alternatives.length > 0 && (
        <Block title="Other ways to solve it">
          <BulletList items={e.alternatives} />
        </Block>
      )}

      {e.why_this_works_here && (
        <div className="rounded border border-[var(--color-accent)]/30 bg-[var(--color-accent-dim)]/20 p-3">
          <p className="text-[13px] leading-relaxed">
            <span className="font-medium">Why this technique, here: </span>
            {e.why_this_works_here}
          </p>
        </div>
      )}

      {e.related_topics.length > 0 && (
        <Block title="Study next">
          <div className="flex flex-wrap gap-1.5">
            {e.related_topics.map((topic) => (
              <Badge key={topic} tone="neutral">
                {topic}
              </Badge>
            ))}
          </div>
        </Block>
      )}
    </div>
  );
}

/* ------------------------------------------------------- Verification */

function VerificationTab({ result }: { result: SolveResult }) {
  const { stress, perf, sample_checks } = result;

  return (
    <div className="space-y-6">
      <Block
        title="Sample tests"
        subtitle="Run against the samples you provided, in the sandbox"
      >
        {sample_checks.length === 0 ? (
          <p className="text-sm text-[var(--color-ink-muted)]">No samples were supplied.</p>
        ) : (
          <div className="space-y-2">
            {sample_checks.map((check) => (
              <div
                key={check.index}
                className="flex flex-wrap items-center gap-2 rounded border border-[var(--color-line)] bg-[var(--color-surface-2)] px-3 py-2"
              >
                <span className="text-[13px]">Sample {check.index}</span>
                <Badge tone={verdictTone(check.verdict)}>{verdictLabel(check.verdict)}</Badge>
                <span className="ml-auto font-[family-name:var(--font-mono)] text-xs text-[var(--color-ink-faint)]">
                  {check.time_ms} ms
                </span>
                {check.diff_hint && (
                  <p className="w-full text-xs text-[var(--color-bad)]">{check.diff_hint}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Block>

      <Block
        title="Differential (stress) testing"
        subtitle="Thousands of random inputs, checked against an independently written brute force"
      >
        {stress.counterexample ? (
          <div className="space-y-3">
            <p className="text-[13px] leading-relaxed text-[var(--color-bad)]">
              A counterexample was found after {stress.cases} cases. The solution passes every
              sample and is still wrong.
            </p>
            <div className="grid gap-3 md:grid-cols-3">
              <CodeBlock code={stress.counterexample} label="input" maxHeight="180px" />
              <CodeBlock
                code={stress.counterexample_expected}
                label="brute force says"
                maxHeight="180px"
              />
              <CodeBlock
                code={stress.counterexample_actual}
                label="this solution says"
                maxHeight="180px"
              />
            </div>
          </div>
        ) : stress.ran && stress.cases > 0 ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge tone="ok">
                {stress.passed}/{stress.cases} agree
              </Badge>
              <span className="text-xs text-[var(--color-ink-muted)]">
                no counterexample found
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
              <div
                className="h-full rounded-full bg-[var(--color-ok)]"
                style={{
                  width: `${stress.cases ? (stress.passed / stress.cases) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        ) : (
          <p className="text-[13px] leading-relaxed text-[var(--color-warn)]">
            {stress.reason_skipped || "Stress testing did not run."}
          </p>
        )}
      </Block>

      <Block
        title="Performance at full scale"
        subtitle="Timed on the largest input the constraints allow"
      >
        {perf.ran ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={perf.headroom >= 1 ? "ok" : "bad"} mono>
              {perf.time_ms} ms / {perf.limit_ms} ms
            </Badge>
            <span className="text-xs text-[var(--color-ink-muted)]">
              {perf.headroom >= 1
                ? `${perf.headroom.toFixed(1)}x headroom`
                : "exceeds the time limit"}
              {perf.n_used ? ` at n = ${perf.n_used.toLocaleString()}` : ""}
            </span>
          </div>
        ) : (
          <p className="text-[13px] text-[var(--color-ink-muted)]">
            {perf.reason_skipped || "Not measured."}
          </p>
        )}
      </Block>

      {(result.brute_force_code || result.generator_code) && (
        <Block
          title="The testing apparatus"
          subtitle="Written automatically, and shown so you can check it yourself"
        >
          <div className="grid gap-3 lg:grid-cols-2">
            {result.brute_force_code && (
              <CodeBlock
                code={result.brute_force_code}
                label="brute_force.cpp"
                maxHeight="320px"
              />
            )}
            {result.generator_code && (
              <CodeBlock code={result.generator_code} label="generator.py" maxHeight="320px" />
            )}
          </div>
        </Block>
      )}
    </div>
  );
}

/* ----------------------------------------------------------- Analysis */

function AnalysisTab({ result }: { result: SolveResult }) {
  const a = result.analysis;
  const p = result.problem;
  if (!a || !p) return null;

  return (
    <div className="space-y-6">
      <Block title="What the constraints allow" subtitle="Derived before any code was written">
        {a.budget && (
          <>
            <p className="mb-3 text-[13.5px] leading-relaxed">{a.budget.reasoning}</p>
            <div className="flex flex-wrap gap-1.5">
              {a.budget.allowed.map((c) => (
                <Badge key={c} tone="ok" mono>
                  {c}
                </Badge>
              ))}
              {a.budget.forbidden.map((c) => (
                <Badge key={c} tone="bad" mono className="opacity-60">
                  {c}
                </Badge>
              ))}
            </div>
          </>
        )}
      </Block>

      <Block title="Parsed from the statement">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-3">
          <Stat label="Time limit" value={`${p.time_limit_ms} ms`} />
          <Stat label="Memory limit" value={`${p.memory_limit_mb} MB`} />
          <Stat label="Difficulty" value={`${a.difficulty_estimate}${a.rating_estimate ? ` (~${a.rating_estimate})` : ""}`} />
          <Stat label="Shape" value={a.io_format} />
        </dl>
        {p.constraints.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {p.constraints.map((c, i) => (
              <Badge key={i} tone={c.kind === "size" ? "accent" : "neutral"} mono>
                {c.lo !== null ? `${c.lo} ≤ ` : ""}
                {c.symbol}
                {c.hi !== null ? ` ≤ ${c.hi.toLocaleString()}` : ""}
              </Badge>
            ))}
          </div>
        )}
      </Block>

      {a.topics.length > 0 && (
        <Block title="Topic signals">
          <div className="flex flex-wrap gap-1.5">
            {a.topics.map((t) => (
              <Badge key={t} tone="info">
                {t}
              </Badge>
            ))}
          </div>
        </Block>
      )}

      {a.pitfalls.length > 0 && (
        <Block title="Traps visible from the constraints alone">
          <BulletList items={a.pitfalls} tone="warn" />
        </Block>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-[var(--color-ink-faint)]">{label}</dt>
      <dd className="font-[family-name:var(--font-mono)] text-[13px]">{value}</dd>
    </div>
  );
}

/* ----------------------------------------------------------- Attempts */

function AttemptsTab({ result }: { result: SolveResult }) {
  return (
    <div className="space-y-4">
      <p className="text-[13px] leading-relaxed text-[var(--color-ink-muted)]">
        Each failed attempt is kept, along with the evidence that was fed back into the next
        one. This is what the repair loop actually saw.
      </p>
      {result.attempts.map((attempt) => (
        <div
          key={attempt.index}
          className="rounded border border-[var(--color-line)] bg-[var(--color-surface-2)] p-3"
        >
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-medium">Attempt {attempt.index}</span>
            <Badge tone={verdictTone(attempt.verdict)}>{verdictLabel(attempt.verdict)}</Badge>
            {attempt.sample_checks.length > 0 && (
              <span className="text-xs text-[var(--color-ink-muted)]">
                {attempt.sample_checks.filter((c) => c.verdict === "ACCEPTED").length}/
                {attempt.sample_checks.length} samples
              </span>
            )}
          </div>
          {attempt.compile_log && (
            <CodeBlock code={attempt.compile_log} label="compiler output" maxHeight="160px" />
          )}
        </div>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------- Block */

function Block({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-[13px] font-semibold tracking-tight">{title}</h3>
      {subtitle && (
        <p className="mt-0.5 mb-2.5 text-xs text-[var(--color-ink-faint)]">{subtitle}</p>
      )}
      <div className={subtitle ? "" : "mt-2.5"}>{children}</div>
    </div>
  );
}
