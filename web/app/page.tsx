"use client";

import { useEffect, useRef, useState } from "react";
import { getExamples, getHealth, solveStream } from "@/lib/api";
import type { ExampleProblem, Health, SolveResult, StageEvent } from "@/lib/types";
import { Pipeline } from "@/components/Pipeline";
import { Results } from "@/components/Results";
import { Badge, Card, Field, cx } from "@/components/ui";

const PLACEHOLDER = `Paste the whole problem statement here — title, description,
input format, output format and constraints.

The constraints matter most. "1 <= n <= 2*10^5" is what tells the
solver that an O(n^2) answer is wrong before a line of code exists.`;

export default function Page() {
  const [statement, setStatement] = useState("");
  const [sampleInput, setSampleInput] = useState("");
  const [sampleOutput, setSampleOutput] = useState("");
  const [language, setLanguage] = useState("cpp");
  const [stress, setStress] = useState(true);

  const [events, setEvents] = useState<StageEvent[]>([]);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const [health, setHealth] = useState<Health | null>(null);
  const [examples, setExamples] = useState<ExampleProblem[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    getExamples().then(setExamples).catch(() => setExamples([]));
  }, []);

  async function handleSolve() {
    if (!statement.trim() || running) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setRunning(true);
    setEvents([]);
    setResult(null);
    setError(null);

    try {
      await solveStream(
        {
          statement,
          sample_input: sampleInput,
          sample_output: sampleOutput,
          language,
          stress,
          stress_cases: stress ? 400 : 0,
        },
        {
          onStage: (event) => setEvents((prev) => [...prev, event]),
          onResult: setResult,
          onError: setError,
        },
        controller.signal,
      );
    } catch (exc) {
      if ((exc as Error).name !== "AbortError") setError((exc as Error).message);
    } finally {
      setRunning(false);
    }
  }

  function loadExample(example: ExampleProblem) {
    setStatement(example.statement);
    setSampleInput(example.sample_input);
    setSampleOutput(example.sample_output);
    setResult(null);
    setEvents([]);
    setError(null);
  }

  const inputClass =
    "w-full rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)] px-3 py-2 " +
    "font-[family-name:var(--font-mono)] text-[12.5px] leading-relaxed placeholder:text-[var(--color-ink-faint)] " +
    "focus:border-[var(--color-accent)] focus:outline-none";

  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-16 sm:px-6">
      <Header health={health} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        {/* ------------------------------------------------ input column */}
        <div className="space-y-4">
          <Card
            title="The problem"
            subtitle="Paste it exactly as it appears on the judge"
          >
            <div className="space-y-3">
              <textarea
                value={statement}
                onChange={(e) => setStatement(e.target.value)}
                placeholder={PLACEHOLDER}
                rows={14}
                spellCheck={false}
                className={cx(inputClass, "resize-y")}
              />

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Sample input">
                  <textarea
                    value={sampleInput}
                    onChange={(e) => setSampleInput(e.target.value)}
                    rows={5}
                    spellCheck={false}
                    placeholder="8&#10;-1 3 -2 5 3 -5 2 2"
                    className={cx(inputClass, "resize-y")}
                  />
                </Field>
                <Field label="Sample output">
                  <textarea
                    value={sampleOutput}
                    onChange={(e) => setSampleOutput(e.target.value)}
                    rows={5}
                    spellCheck={false}
                    placeholder="9"
                    className={cx(inputClass, "resize-y")}
                  />
                </Field>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2.5 py-1.5 text-xs"
                >
                  <option value="cpp">C++17</option>
                  <option value="python">Python 3</option>
                  <option value="java">Java 17</option>
                  <option value="c">C17</option>
                </select>

                <label className="flex items-center gap-2 text-xs text-[var(--color-ink-muted)]">
                  <input
                    type="checkbox"
                    checked={stress}
                    onChange={(e) => setStress(e.target.checked)}
                    className="accent-[var(--color-accent)]"
                  />
                  Hunt for counterexamples
                </label>

                <button
                  onClick={handleSolve}
                  disabled={running || !statement.trim()}
                  className={cx(
                    "ml-auto rounded-md px-4 py-2 text-sm font-medium transition-colors",
                    running || !statement.trim()
                      ? "cursor-not-allowed bg-[var(--color-surface-2)] text-[var(--color-ink-faint)]"
                      : "bg-[var(--color-accent)] text-[#06101f] hover:brightness-110",
                  )}
                >
                  {running ? "Solving…" : "Solve"}
                </button>
              </div>

              <p className="text-xs leading-relaxed text-[var(--color-ink-faint)]">
                Every solution is compiled, run against your samples, and checked against an
                independently written brute force on hundreds of random inputs before you see it.
              </p>
            </div>
          </Card>

          {examples.length > 0 && !result && !running && (
            <Card title="Try one" subtitle="Real problems, solved end to end">
              <div className="flex flex-wrap gap-1.5">
                {examples.map((example) => (
                  <button
                    key={example.key}
                    onClick={() => loadExample(example)}
                    className="rounded border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2.5 py-1 text-xs text-[var(--color-ink-muted)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-ink)]"
                  >
                    {example.title}
                  </button>
                ))}
              </div>
            </Card>
          )}

          {events.length > 0 && (
            <Card title="Pipeline" subtitle="What the solver is doing, live">
              <Pipeline events={events} running={running} />
            </Card>
          )}
        </div>

        {/* ----------------------------------------------- result column */}
        <div className="space-y-4">
          {error && (
            <div className="rounded-lg border border-[var(--color-bad)]/40 bg-[var(--color-bad-dim)] p-4 text-sm text-[var(--color-bad)]">
              {error}
            </div>
          )}
          {result ? (
            <Results result={result} />
          ) : (
            !running && !error && <EmptyState />
          )}
          {running && !result && <RunningState />}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Chrome */

function Header({ health }: { health: Health | null }) {
  return (
    <header className="flex flex-wrap items-center gap-3 py-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">
          Instant Solver
          <span className="ml-2 font-normal text-[var(--color-ink-faint)]">
            Think. Code. Solve. Compete.
          </span>
        </h1>
        <p className="mt-0.5 text-xs text-[var(--color-ink-muted)]">
          Paste a problem. Get a verified solution, and the reasoning behind it.
        </p>
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-1.5">
        {health ? (
          <>
            <Badge tone={health.model_configured ? "ok" : "warn"}>
              {health.model_configured ? "model connected" : "corpus only"}
            </Badge>
            <Badge tone="neutral" mono>
              sandbox: {health.sandbox}
            </Badge>
          </>
        ) : (
          <Badge tone="bad">engine offline</Badge>
        )}
      </div>
    </header>
  );
}

function EmptyState() {
  const steps = [
    ["Read the constraints", "n ≤ 2·10⁵ fixes the complexity budget before any algorithm is chosen."],
    ["Choose and justify", "A technique is picked, and the alternatives are ruled out on the record."],
    ["Write it, then break it", "Compile, run your samples, then stress-test against an independent brute force."],
    ["Explain it", "Intuition, proof of correctness, complexity, a dry run, and the traps."],
  ];
  return (
    <div className="rounded-lg border border-dashed border-[var(--color-line-strong)] p-8">
      <h2 className="text-sm font-semibold">What happens when you press Solve</h2>
      <ol className="mt-4 space-y-4">
        {steps.map(([title, body], i) => (
          <li key={title} className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-[var(--color-surface-2)] font-[family-name:var(--font-mono)] text-xs text-[var(--color-ink-muted)]">
              {i + 1}
            </span>
            <div>
              <p className="text-[13px] font-medium">{title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-[var(--color-ink-muted)]">
                {body}
              </p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-6 border-t border-[var(--color-line)] pt-4 text-xs leading-relaxed text-[var(--color-ink-faint)]">
        Nothing is shown as an answer until it has survived an attempt to break it. When
        verification cannot be completed, the result says so instead of pretending.
      </p>
    </div>
  );
}

function RunningState() {
  return (
    <div className="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-8">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 animate-pulse-dot rounded-full bg-[var(--color-accent)]" />
        <span className="text-sm text-[var(--color-ink-muted)]">
          Working through the pipeline — watch the stages on the left.
        </span>
      </div>
    </div>
  );
}
