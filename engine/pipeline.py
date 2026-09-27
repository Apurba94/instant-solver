"""The solve pipeline.

    ingest -> analyse -> plan -> synthesise -> compile -> sample-test
           -> repair (loop) -> stress-test -> perf-probe -> explain

The design principle throughout: **nothing is shown to the user as an answer
until a machine has tried to break it.** Generating plausible code is the easy
part and every model can do it. What makes the output trustworthy is the chain
of falsification attempts behind it — compile it, run the samples, then write an
independent brute force and a random generator and hunt for a counterexample.

When a counterexample is found, that is a success, not a failure: it is fed back
into the repair loop as evidence. When none is found after thousands of cases,
the user is told exactly how hard the system tried, so they can calibrate their
own trust instead of taking the answer on faith.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from . import analyze as analysis_mod
from . import checker
from .ingest import ingest
from .models import (
    Analysis, Attempt, Confidence, Explanation, Language, PerfProbe, Problem,
    RunResult, SampleCheck, SolveResult, Stage, StressReport, Verdict,
)
from .providers import ProviderError, SolverProvider, build_provider
from .providers.base import Plan
from .sandbox import CompileError, Program, compile_source, pick_runner

ProgressFn = Callable[[Stage, str, dict], None]


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

class SolveConfig:
    def __init__(
        self,
        language: Language = Language.CPP,
        max_attempts: int = 4,
        stress_cases: int = 400,
        stress_budget_s: float = 25.0,
        run_stress: bool = True,
        run_perf_probe: bool = True,
        explain: bool = True,
        workdir_root: Optional[str] = None,
    ):
        self.language = language
        self.max_attempts = max_attempts
        self.stress_cases = stress_cases
        self.stress_budget_s = stress_budget_s
        self.run_stress = run_stress
        self.run_perf_probe = run_perf_probe
        self.explain = explain
        self.workdir_root = workdir_root


# --------------------------------------------------------------------------
# Sample judging
# --------------------------------------------------------------------------

def judge_samples(program: Program, problem: Problem) -> list[SampleCheck]:
    """Run the program on every sample and report per-sample verdicts."""
    checks: list[SampleCheck] = []
    for i, sample in enumerate(problem.samples, 1):
        run: RunResult = program.run(sample.input, problem.time_limit_ms,
                                     problem.memory_limit_mb)
        if run.verdict is not Verdict.ACCEPTED:
            checks.append(SampleCheck(
                index=i, verdict=run.verdict, expected=sample.output,
                actual=run.stdout, time_ms=run.time_ms,
                diff_hint=run.message or run.stderr.strip()[:400],
            ))
            continue

        outcome = checker.compare(sample.output, run.stdout,
                                  float_mode=problem.output_is_float)
        checks.append(SampleCheck(
            index=i,
            verdict=Verdict.ACCEPTED if outcome.ok else Verdict.WRONG_ANSWER,
            expected=sample.output,
            actual=run.stdout,
            time_ms=run.time_ms,
            diff_hint="" if outcome.ok else outcome.hint,
        ))
    return checks


def _failure_report(attempt: Attempt, problem: Problem) -> str:
    """Turn a failed attempt into evidence the synthesiser can act on.

    Vague feedback produces vague fixes. This deliberately includes the exact
    input, the exact expected output and the exact produced output, because a
    concrete divergence is what makes a repair targeted rather than a reroll.
    """
    if not attempt.compiled:
        return (f"The code failed to COMPILE. Compiler output:\n\n{attempt.compile_log}\n\n"
                "Fix the compilation errors. Do not change the algorithm unless the error "
                "shows the approach itself is unimplementable.")

    lines: list[str] = []
    for check in attempt.sample_checks:
        if check.verdict.is_ok:
            lines.append(f"Sample {check.index}: PASSED ({check.time_ms} ms).")
            continue

        sample = problem.samples[check.index - 1]
        lines.append(f"Sample {check.index}: {check.verdict.value}")
        lines.append(f"  Input:\n{_indent(sample.input)}")
        lines.append(f"  Expected output:\n{_indent(check.expected)}")
        lines.append(f"  Your output:\n{_indent(check.actual) if check.actual.strip() else '    (nothing)'}")
        if check.diff_hint:
            lines.append(f"  Diagnosis: {check.diff_hint}")
        if check.verdict is Verdict.TIME_LIMIT_EXCEEDED:
            lines.append(f"  The limit is {problem.time_limit_ms} ms and the largest input is "
                         f"n = {problem.max_n}. You need a better asymptotic complexity, not "
                         f"micro-optimisation.")
        if check.verdict is Verdict.RUNTIME_ERROR:
            lines.append("  A runtime error on a SAMPLE means an out-of-bounds index, a null "
                         "dereference, division by zero, or recursion too deep. Find it by "
                         "tracing this exact input.")
    return "\n".join(lines)


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.rstrip().split("\n"))


# --------------------------------------------------------------------------
# Stress testing
# --------------------------------------------------------------------------

def stress_test(fast: Program, brute: Program, generator: Program,
                problem: Problem, cases: int, budget_s: float,
                progress: Optional[ProgressFn] = None) -> StressReport:
    """Differential-test the fast solution against an independent brute force.

    This is the step that catches solutions which are plausible, pass the
    samples, and are still wrong — the exact failure mode that makes naive AI
    solvers untrustworthy. Small random inputs are used on purpose: a bug that
    exists at n = 10^5 almost always also exists at n = 5, where the
    counterexample is small enough for a human to read.
    """
    report = StressReport(ran=True)
    deadline = time.monotonic() + budget_s

    for i in range(cases):
        if time.monotonic() > deadline:
            report.reason_skipped = f"Stopped after {report.cases} cases (time budget reached)."
            break

        gen = generator.run(str(i), 5000, 256)
        if gen.verdict is not Verdict.ACCEPTED or not gen.stdout.strip():
            continue
        test_input = gen.stdout

        expected = brute.run(test_input, 10_000, problem.memory_limit_mb)
        if expected.verdict is not Verdict.ACCEPTED:
            continue                       # oracle cannot handle this case; not evidence

        actual = fast.run(test_input, problem.time_limit_ms, problem.memory_limit_mb)
        report.cases += 1

        if actual.verdict is not Verdict.ACCEPTED:
            report.counterexample = test_input
            report.counterexample_expected = expected.stdout
            report.counterexample_actual = f"[{actual.verdict.value}] {actual.message}"
            return report

        if checker.compare(expected.stdout, actual.stdout,
                           float_mode=problem.output_is_float).ok:
            report.passed += 1
        else:
            report.counterexample = test_input
            report.counterexample_expected = expected.stdout
            report.counterexample_actual = actual.stdout
            return report

        if progress and report.cases % 50 == 0:
            progress(Stage.STRESS_TEST, f"{report.cases} random cases checked, no mismatch",
                     {"cases": report.cases})

    return report


# --------------------------------------------------------------------------
# Performance probe
# --------------------------------------------------------------------------

def perf_probe(fast: Program, big_generator: Optional[Program],
               problem: Problem) -> PerfProbe:
    """Time the solution on a worst-case-sized input."""
    probe = PerfProbe(limit_ms=problem.time_limit_ms)
    if big_generator is None:
        probe.reason_skipped = "No maximum-size test generator was available."
        return probe

    gen = big_generator.run("", 30_000, 1024)
    if gen.verdict is not Verdict.ACCEPTED or not gen.stdout.strip():
        probe.reason_skipped = f"The maximum-size generator failed ({gen.verdict.value})."
        return probe

    run = fast.run(gen.stdout, problem.time_limit_ms * 3, problem.memory_limit_mb)
    probe.ran = True
    probe.n_used = problem.max_n
    probe.time_ms = run.time_ms
    probe.headroom = (problem.time_limit_ms / run.time_ms) if run.time_ms > 0 else 999.0
    if run.verdict in (Verdict.TIME_LIMIT_EXCEEDED, Verdict.MEMORY_LIMIT_EXCEEDED):
        probe.time_ms = max(probe.time_ms, problem.time_limit_ms * 3)
        probe.headroom = 0.0
    return probe


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------

def score_confidence(result: SolveResult, plan: Optional[Plan],
                     analysis: Analysis) -> Confidence:
    """Assign a confidence level from evidence only — never from vibes."""
    if not result.sample_checks or not all(c.verdict.is_ok for c in result.sample_checks):
        return Confidence.FAILED
    if not result.problem or not result.problem.samples:
        return Confidence.UNVERIFIED
    if not result.stress.clean:
        return Confidence.LIKELY

    # Samples pass and stress testing found nothing. The remaining question is
    # whether it is fast enough at the largest input the constraints allow.
    if result.perf.ran:
        # A measurement beats an argument.
        return Confidence.VERIFIED if result.perf.headroom >= 1.0 else Confidence.STRONG

    budget = analysis.budget
    if plan and plan.time_complexity and budget and budget.max_n is not None:
        verdict = budget.permits(plan.time_complexity.strip())
        if verdict is True:
            return Confidence.VERIFIED
        if verdict is False:
            return Confidence.STRONG
    # Complexity could not be established either way — correct as far as anyone
    # can tell, speed unproven. That is exactly what STRONG means.
    return Confidence.STRONG


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

class Solver:
    """Runs the full pipeline for one problem."""

    def __init__(self, provider: Optional[SolverProvider] = None,
                 config: Optional[SolveConfig] = None):
        self.provider = provider or build_provider()
        self.config = config or SolveConfig()
        self.runner = pick_runner()

    # -- public API ---------------------------------------------------------

    def solve_text(self, statement: str, sample_input: str = "", sample_output: str = "",
                   title: str = "", progress: Optional[ProgressFn] = None) -> SolveResult:
        problem = ingest(statement, sample_input, sample_output, title=title)
        return self.solve(problem, progress=progress)

    def solve(self, problem: Problem,
              progress: Optional[ProgressFn] = None) -> SolveResult:
        started = time.monotonic()
        result = SolveResult(problem=problem, language=self.config.language)
        result.provider = getattr(self.provider, "name", "unknown")
        emit = _make_emitter(result, progress)

        emit(Stage.INGEST, f"Parsed '{problem.title}' — {len(problem.samples)} sample(s), "
                           f"{len(problem.constraints)} constraint(s) found")

        if problem.interactive:
            result.warnings.append(
                "This looks like an INTERACTIVE problem. Batch stdin/stdout judging cannot "
                "validate it, so the solution below is unverified."
            )

        # ---- analyse ------------------------------------------------------
        analysis = analysis_mod.analyze(problem)
        result.analysis = analysis
        emit(Stage.ANALYZE,
             analysis.budget.reasoning if analysis.budget else "No constraints parsed",
             {"topics": analysis.topics, "difficulty": analysis.difficulty_estimate})

        # ---- plan ---------------------------------------------------------
        try:
            plan = self.provider.plan(problem, analysis)
        except ProviderError as exc:
            emit(Stage.PLAN, f"Planning failed: {exc}", ok=False)
            result.confidence = Confidence.FAILED
            result.warnings.append(str(exc))
            result.elapsed_ms = int((time.monotonic() - started) * 1000)
            return result

        analysis.chosen_technique = plan.technique
        analysis.key_observations = plan.observations
        analysis.summary = plan.restatement
        emit(Stage.PLAN, f"{plan.technique} — target {plan.time_complexity}",
             {"why": plan.why_this_technique, "steps": plan.algorithm_steps})

        if analysis.budget and plan.time_complexity and analysis.budget.max_n is not None:
            if analysis.budget.permits(plan.time_complexity.strip()) is False:
                result.warnings.append(
                    f"The planned complexity {plan.time_complexity} is outside the budget implied "
                    f"by n <= {analysis.budget.max_n:,}. It may be too slow on the full tests."
                )

        # ---- synthesise, compile, judge, repair ---------------------------
        accepted_program, accepted_attempt = self._synthesis_loop(
            problem, analysis, plan, result, emit)

        if accepted_program is None:
            result.confidence = Confidence.FAILED
            result.verdict = (result.attempts[-1].verdict if result.attempts
                              else Verdict.JUDGE_ERROR)
            emit(Stage.DONE, "No candidate passed the samples", ok=False)
            result.elapsed_ms = int((time.monotonic() - started) * 1000)
            return result

        result.solution_code = accepted_attempt.code
        result.sample_checks = accepted_attempt.sample_checks
        result.verdict = Verdict.ACCEPTED

        try:
            # ---- stress test ----------------------------------------------
            if self.config.run_stress and not problem.interactive:
                self._run_stress(problem, analysis, accepted_program, result, emit)
            else:
                result.stress.reason_skipped = (
                    "Interactive problem — differential testing does not apply."
                    if problem.interactive else "Stress testing was disabled for this run."
                )

            # ---- performance probe -----------------------------------------
            if self.config.run_perf_probe and problem.max_n:
                self._run_perf(problem, analysis, accepted_program, result, emit)
            else:
                result.perf.reason_skipped = "No maximum input size was parsed from the statement."

            # ---- explain ---------------------------------------------------
            result.confidence = score_confidence(result, plan, analysis)
            if self.config.explain:
                self._run_explain(problem, analysis, plan, result, emit)
        finally:
            accepted_program.cleanup()

        emit(Stage.DONE, result.headline(), {"confidence": result.confidence.value})
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        return result

    # -- stages -------------------------------------------------------------

    def _synthesis_loop(self, problem: Problem, analysis: Analysis, plan: Plan,
                        result: SolveResult, emit) -> tuple[Optional[Program], Optional[Attempt]]:
        """Generate, compile, judge and repair until the samples pass."""
        language = self.config.language
        previous_code = ""
        failure_report = ""

        for index in range(1, self.config.max_attempts + 1):
            stage = Stage.SYNTHESIZE if index == 1 else Stage.REPAIR
            try:
                if index == 1:
                    synthesis = self.provider.synthesize(problem, analysis, plan, language)
                else:
                    emit(Stage.REPAIR, f"Attempt {index}: repairing from the failure evidence")
                    synthesis = self.provider.repair(problem, analysis, plan, language,
                                                     previous_code, failure_report)
            except ProviderError as exc:
                emit(stage, f"Attempt {index} could not be produced: {exc}", ok=False)
                break

            previous_code = synthesis.code
            attempt = Attempt(index=index, language=language, code=synthesis.code)
            result.attempts.append(attempt)
            emit(stage, f"Attempt {index}: {len(synthesis.code.splitlines())} lines generated")

            # compile
            try:
                program = compile_source(synthesis.code, language, self.runner,
                                         self.config.workdir_root)
                attempt.compiled = True
            except CompileError as exc:
                attempt.compiled = False
                attempt.compile_log = exc.log
                attempt.verdict = Verdict.COMPILATION_ERROR
                emit(Stage.COMPILE, f"Attempt {index} failed to compile", ok=False,
                     extra={"log": exc.log[:600]})
                failure_report = _failure_report(attempt, problem)
                continue

            emit(Stage.COMPILE, f"Attempt {index} compiled cleanly")

            # judge samples
            if not problem.samples:
                attempt.verdict = Verdict.JUDGE_ERROR
                attempt.notes = "No samples were supplied, so correctness could not be checked."
                result.warnings.append(attempt.notes)
                emit(Stage.SAMPLE_TEST, "No samples to check against", ok=False)
                return program, attempt

            attempt.sample_checks = judge_samples(program, problem)
            passed = sum(1 for c in attempt.sample_checks if c.verdict.is_ok)
            total = len(attempt.sample_checks)

            if attempt.samples_pass:
                attempt.verdict = Verdict.ACCEPTED
                slowest = max((c.time_ms for c in attempt.sample_checks), default=0)
                emit(Stage.SAMPLE_TEST, f"All {total} sample(s) pass (slowest {slowest} ms)")
                return program, attempt

            attempt.verdict = next(c.verdict for c in attempt.sample_checks if not c.verdict.is_ok)
            emit(Stage.SAMPLE_TEST, f"Attempt {index}: {passed}/{total} samples pass — "
                                    f"{attempt.verdict.value}", ok=False)
            failure_report = _failure_report(attempt, problem)
            program.cleanup()

        return None, (result.attempts[-1] if result.attempts else None)

    def _run_stress(self, problem: Problem, analysis: Analysis, fast: Program,
                    result: SolveResult, emit) -> None:
        emit(Stage.STRESS_TEST, "Writing an independent brute force and a random generator")

        brute_src = self.provider.brute_force(problem, analysis, Language.CPP)
        gen_src = self.provider.generator(problem, analysis, small=True)

        if brute_src is None or gen_src is None:
            result.stress.reason_skipped = (
                "No brute-force oracle could be written for this problem, so differential "
                "testing was not possible."
                if brute_src is None else
                "No valid random test generator could be written for this input format."
            )
            emit(Stage.STRESS_TEST, result.stress.reason_skipped, ok=False)
            return

        result.brute_force_code = brute_src.code
        result.generator_code = gen_src.code

        brute = generator = None
        try:
            brute = compile_source(brute_src.code, Language.CPP, self.runner,
                                   self.config.workdir_root)
            generator = compile_source(gen_src.code, Language.PYTHON, self.runner,
                                       self.config.workdir_root)
        except CompileError as exc:
            result.stress.reason_skipped = f"The brute-force oracle did not compile: {exc.log[:200]}"
            emit(Stage.STRESS_TEST, result.stress.reason_skipped, ok=False)
            if brute:
                brute.cleanup()
            return

        try:
            result.stress = stress_test(
                fast, brute, generator, problem,
                cases=self.config.stress_cases,
                budget_s=self.config.stress_budget_s,
                progress=lambda s, m, e: emit(s, m, e),
            )
        finally:
            brute.cleanup()
            generator.cleanup()

        if result.stress.counterexample:
            emit(Stage.STRESS_TEST,
                 f"Counterexample found after {result.stress.cases} cases", ok=False,
                 extra={"input": result.stress.counterexample[:500]})
            result.warnings.append(
                "Differential testing found an input where this solution disagrees with an "
                "independent brute force. The counterexample is shown below — the solution is "
                "wrong, despite passing every sample."
            )
        elif result.stress.cases == 0:
            result.stress.reason_skipped = (
                result.stress.reason_skipped
                or "The generator produced no test the oracle could evaluate."
            )
            emit(Stage.STRESS_TEST, result.stress.reason_skipped, ok=False)
        else:
            emit(Stage.STRESS_TEST,
                 f"{result.stress.passed} of {result.stress.cases} random cases agree with the "
                 f"brute force — no counterexample found")

    def _run_perf(self, problem: Problem, analysis: Analysis, fast: Program,
                  result: SolveResult, emit) -> None:
        big_gen_src = None
        try:
            big_gen_src = self.provider.generator(problem, analysis, small=False)
        except ProviderError:
            big_gen_src = None

        if big_gen_src is None:
            result.perf.reason_skipped = "No maximum-size generator was available."
            result.perf.limit_ms = problem.time_limit_ms
            return

        big_gen = None
        try:
            big_gen = compile_source(big_gen_src.code, Language.PYTHON, self.runner,
                                     self.config.workdir_root)
            emit(Stage.PERF_PROBE, f"Timing the solution on a maximum-size input (n = {problem.max_n:,})")
            result.perf = perf_probe(fast, big_gen, problem)
        except CompileError:
            result.perf.reason_skipped = "The maximum-size generator did not run."
        finally:
            if big_gen:
                big_gen.cleanup()

        if result.perf.ran:
            if result.perf.headroom >= 1.0:
                emit(Stage.PERF_PROBE,
                     f"{result.perf.time_ms} ms against a {problem.time_limit_ms} ms limit "
                     f"({result.perf.headroom:.1f}x headroom)")
            else:
                emit(Stage.PERF_PROBE,
                     f"Too slow at full scale: {result.perf.time_ms} ms against a "
                     f"{problem.time_limit_ms} ms limit", ok=False)
                result.warnings.append(
                    "At the maximum input size allowed by the constraints, this solution exceeds "
                    "the time limit. It is correct but not fast enough."
                )

    def _run_explain(self, problem: Problem, analysis: Analysis, plan: Plan,
                     result: SolveResult, emit) -> None:
        analysis.summary = _verification_summary(result)
        emit(Stage.EXPLAIN, "Writing the explanation")
        try:
            result.explanation = self.provider.explain(
                problem, analysis, plan, result.solution_code, result.language)
        except ProviderError as exc:
            result.warnings.append(f"The explanation could not be generated: {exc}")
            emit(Stage.EXPLAIN, f"Explanation unavailable: {exc}", ok=False)


def _verification_summary(result: SolveResult) -> str:
    bits = [f"{len(result.sample_checks)} sample(s) passed"]
    if result.stress.clean:
        bits.append(f"{result.stress.cases} randomised cases agreed with an independent brute force")
    elif result.stress.reason_skipped:
        bits.append(f"stress testing skipped ({result.stress.reason_skipped})")
    if result.perf.ran:
        bits.append(f"ran in {result.perf.time_ms} ms against a {result.perf.limit_ms} ms limit")
    return "; ".join(bits) + "."


def _make_emitter(result: SolveResult, progress: Optional[ProgressFn]):
    def emit(stage: Stage, message: str, extra: Optional[dict] = None,
             ok: bool = True, **kwargs) -> None:
        payload = dict(extra or {})
        payload.update(kwargs.pop("extra", {}) or {})
        payload.update(kwargs)
        result.log(stage, message, ok=ok, **payload)
        if progress:
            progress(stage, message, {"ok": ok, **payload})
    return emit
