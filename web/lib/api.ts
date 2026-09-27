import type { ExampleProblem, Health, SolveResult, StageEvent } from "./types";

/**
 * Where the engine lives.
 *
 * Empty by default, so requests are same-origin and Next's rewrite forwards
 * them. Set NEXT_PUBLIC_API_URL in production to have the browser call the
 * engine directly: it keeps the proxy out of the Server-Sent Events path, which
 * is where buffering bugs come from.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const url = (path: string) => `${API_BASE}${path}`;

export interface SolveOptions {
  statement: string;
  sample_input: string;
  sample_output: string;
  title?: string;
  language?: string;
  stress?: boolean;
  perf_probe?: boolean;
  explain?: boolean;
  stress_cases?: number;
}

export async function getHealth(): Promise<Health> {
  const res = await fetch(url("/api/health"), { cache: "no-store" });
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return res.json();
}

export async function getExamples(): Promise<ExampleProblem[]> {
  const res = await fetch(url("/api/examples"), { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function runCustom(body: {
  code: string;
  language: string;
  stdin: string;
}): Promise<{
  verdict: string;
  stdout: string;
  stderr: string;
  time_ms: number;
  memory_kb: number;
  message: string;
  compile_log: string;
}> {
  const res = await fetch(url("/api/run"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Run failed (${res.status})`);
  return res.json();
}

/**
 * Stream a solve.
 *
 * Parses Server-Sent Events by hand rather than using EventSource, because
 * EventSource cannot issue a POST and the problem statement is far too large
 * for a query string.
 */
export async function solveStream(
  options: SolveOptions,
  handlers: {
    onStage: (event: StageEvent) => void;
    onResult: (result: SolveResult) => void;
    onError: (message: string) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url("/api/solve/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
    signal,
  });

  if (!res.ok || !res.body) {
    handlers.onError(`The solver returned ${res.status}.`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      dispatch(frame, handlers);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

function dispatch(
  frame: string,
  handlers: {
    onStage: (event: StageEvent) => void;
    onResult: (result: SolveResult) => void;
    onError: (message: string) => void;
  },
) {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }

  if (event === "stage") handlers.onStage(payload as StageEvent);
  else if (event === "result") handlers.onResult(payload as SolveResult);
  else if (event === "error")
    handlers.onError((payload as { message?: string }).message ?? "Unknown error");
}
