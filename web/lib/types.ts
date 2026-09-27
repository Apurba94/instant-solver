/** Mirrors the engine's serialised SolveResult. */

export type Confidence = "VERIFIED" | "STRONG" | "LIKELY" | "UNVERIFIED" | "FAILED";

export type Verdict =
  | "ACCEPTED"
  | "WRONG_ANSWER"
  | "TIME_LIMIT_EXCEEDED"
  | "MEMORY_LIMIT_EXCEEDED"
  | "RUNTIME_ERROR"
  | "COMPILATION_ERROR"
  | "OUTPUT_LIMIT_EXCEEDED"
  | "SECURITY_VIOLATION"
  | "JUDGE_ERROR";

export interface StageEvent {
  stage: string;
  message: string;
  ok: boolean;
  at: number;
  [key: string]: unknown;
}

export interface Constraint {
  symbol: string;
  lo: number | null;
  hi: number | null;
  raw: string;
  kind: "size" | "value";
}

export interface Problem {
  statement: string;
  title: string;
  samples: { input: string; output: string; note: string }[];
  time_limit_ms: number;
  memory_limit_mb: number;
  constraints: Constraint[];
  multi_test: boolean;
  interactive: boolean;
  output_is_float: boolean;
}

export interface ComplexityBudget {
  max_n: number | null;
  ops_budget: number;
  allowed: string[];
  forbidden: string[];
  reasoning: string;
}

export interface Analysis {
  summary: string;
  io_format: string;
  budget: ComplexityBudget | null;
  candidate_techniques: string[];
  chosen_technique: string;
  key_observations: string[];
  difficulty_estimate: string;
  rating_estimate: number | null;
  topics: string[];
  pitfalls: string[];
}

export interface SampleCheck {
  index: number;
  verdict: Verdict;
  expected: string;
  actual: string;
  time_ms: number;
  diff_hint: string;
}

export interface StressReport {
  ran: boolean;
  cases: number;
  passed: number;
  counterexample: string | null;
  counterexample_expected: string;
  counterexample_actual: string;
  reason_skipped: string;
}

export interface PerfProbe {
  ran: boolean;
  n_used: number | null;
  time_ms: number;
  limit_ms: number;
  headroom: number;
  reason_skipped: string;
}

export interface Attempt {
  index: number;
  language: string;
  code: string;
  compiled: boolean;
  compile_log: string;
  sample_checks: SampleCheck[];
  verdict: Verdict;
  notes: string;
}

export interface Explanation {
  intuition: string;
  observations: string[];
  approach: string;
  algorithm_steps: string[];
  correctness: string;
  time_complexity: string;
  space_complexity: string;
  complexity_justification: string;
  code_walkthrough: { lines: string; what: string }[];
  dry_run: { step: string; state: string }[];
  pitfalls: string[];
  alternatives: string[];
  related_topics: string[];
  why_this_works_here: string;
}

export interface SolveResult {
  solve_id: string;
  problem: Problem | null;
  analysis: Analysis | null;
  language: string;
  solution_code: string;
  confidence: Confidence;
  verdict: Verdict;
  attempts: Attempt[];
  sample_checks: SampleCheck[];
  stress: StressReport;
  perf: PerfProbe;
  explanation: Explanation | null;
  brute_force_code: string;
  generator_code: string;
  timeline: StageEvent[];
  elapsed_ms: number;
  provider: string;
  warnings: string[];
  headline: string;
}

export interface ExampleProblem {
  key: string;
  title: string;
  statement: string;
  sample_input: string;
  sample_output: string;
}

export interface Health {
  status: string;
  version: string;
  provider: string;
  model_configured: boolean;
  sandbox: string;
  languages: Record<string, boolean>;
}
