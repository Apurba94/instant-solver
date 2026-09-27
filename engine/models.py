"""Core domain models for the Instant Solver engine.

Everything that flows through the solve pipeline is one of these objects.
They are deliberately plain dataclasses so the engine stays framework-free and
can be reused by the API, the CLI, batch jobs and the test suite alike.
"""
from __future__ import annotations

import enum
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------

class Verdict(str, enum.Enum):
    """Judge verdicts, matching the platform-wide verdict vocabulary."""
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    JUDGE_ERROR = "JUDGE_ERROR"

    @property
    def is_ok(self) -> bool:
        return self is Verdict.ACCEPTED


class Confidence(str, enum.Enum):
    """How much the engine is willing to vouch for a solution.

    The whole point of this enum is honesty. A solution that merely compiles
    and prints the right thing for two sample cases is *not* the same artifact
    as one that survived 3,000 randomised cases against an independent brute
    force, and the user deserves to be told which one they are looking at.
    """
    VERIFIED = "VERIFIED"        # samples + stress test vs brute force + fits budget
    STRONG = "STRONG"            # samples + stress test, no independent brute force
    LIKELY = "LIKELY"            # samples pass only
    UNVERIFIED = "UNVERIFIED"    # compiles, samples not conclusively checked
    FAILED = "FAILED"            # no candidate survived

    @property
    def rank(self) -> int:
        return {
            Confidence.VERIFIED: 4,
            Confidence.STRONG: 3,
            Confidence.LIKELY: 2,
            Confidence.UNVERIFIED: 1,
            Confidence.FAILED: 0,
        }[self]


class Language(str, enum.Enum):
    CPP = "cpp"
    PYTHON = "python"
    JAVA = "java"
    C = "c"


class Stage(str, enum.Enum):
    """Pipeline stages, streamed to the UI so the user sees thinking happen."""
    INGEST = "ingest"
    ANALYZE = "analyze"
    RETRIEVE = "retrieve"
    PLAN = "plan"
    SYNTHESIZE = "synthesize"
    COMPILE = "compile"
    SAMPLE_TEST = "sample_test"
    REPAIR = "repair"
    STRESS_TEST = "stress_test"
    PERF_PROBE = "perf_probe"
    EXPLAIN = "explain"
    DONE = "done"


# --------------------------------------------------------------------------
# Problem
# --------------------------------------------------------------------------

@dataclass
class Sample:
    """One sample test case as printed in the statement."""
    input: str
    output: str
    note: str = ""

    def normalized(self) -> "Sample":
        return Sample(self.input.strip() + "\n", self.output.strip() + "\n", self.note)


@dataclass
class Constraint:
    """A single parsed numeric bound, e.g. ``n <= 200000``.

    ``kind`` separates *how many things there are* from *how big each thing is*.
    The distinction is not cosmetic: the complexity budget must come from the
    size bound, while overflow risk comes from the value bound. Conflating them
    is how a solver concludes that ``-10^9 <= a_i <= 10^9`` means n can be a
    billion and that therefore nothing better than O(sqrt n) is allowed.
    """
    symbol: str
    lo: Optional[int] = None
    hi: Optional[int] = None
    raw: str = ""
    kind: str = "value"          # "size" | "value"

    def __str__(self) -> str:
        if self.lo is not None and self.hi is not None:
            return f"{self.lo} <= {self.symbol} <= {self.hi}"
        if self.hi is not None:
            return f"{self.symbol} <= {self.hi}"
        if self.lo is not None:
            return f"{self.symbol} >= {self.lo}"
        return self.raw


@dataclass
class Problem:
    """A problem as the solver understands it after ingestion."""
    statement: str
    title: str = "Untitled Problem"
    samples: list[Sample] = field(default_factory=list)
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    constraints: list[Constraint] = field(default_factory=list)
    source: str = ""
    tags: list[str] = field(default_factory=list)
    multi_test: bool = False          # statement begins with a test-count T
    interactive: bool = False
    output_is_float: bool = False

    @property
    def fingerprint(self) -> str:
        """Stable hash used for the solution cache and duplicate detection."""
        basis = (self.statement.strip() + "||"
                 + "||".join(f"{s.input.strip()}=>{s.output.strip()}" for s in self.samples))
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]

    @property
    def max_n(self) -> Optional[int]:
        """Largest INPUT SIZE bound, which is what fixes the complexity budget.

        Returns ``None`` when no size bound could be identified, and the budget
        then declines to rule anything out rather than inventing a limit.
        """
        highs = [c.hi for c in self.constraints if c.kind == "size" and c.hi is not None]
        return max(highs) if highs else None

    @property
    def max_value(self) -> Optional[int]:
        """Largest magnitude any single input value can take — the overflow signal."""
        magnitudes = [
            abs(bound)
            for c in self.constraints if c.kind == "value"
            for bound in (c.hi, c.lo) if bound is not None
        ]
        return max(magnitudes) if magnitudes else None


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

@dataclass
class ComplexityBudget:
    """What the constraints permit, expressed as an operation budget.

    Competitive programmers read ``n <= 2*10^5`` and immediately think
    "O(n log n), maybe O(n sqrt n)". This object makes that reflex explicit so
    the synthesiser can be held to it and the verifier can reject a solution
    whose asymptotics cannot possibly fit.
    """
    max_n: Optional[int]
    ops_budget: int
    allowed: list[str]
    forbidden: list[str]
    reasoning: str

    def permits(self, complexity: str) -> Optional[bool]:
        """Does this complexity fit? ``None`` means it could not be understood.

        A three-valued answer matters: "I could not parse that" must not be
        reported to the user as "too slow".
        """
        from .analyze import normalize_complexity   # local import: avoids a cycle
        canonical = normalize_complexity(complexity)
        if canonical is None:
            return None
        return canonical in self.allowed


@dataclass
class Analysis:
    """Structured understanding of the problem, produced before any code."""
    summary: str = ""
    io_format: str = ""
    budget: Optional[ComplexityBudget] = None
    candidate_techniques: list[str] = field(default_factory=list)
    chosen_technique: str = ""
    key_observations: list[str] = field(default_factory=list)
    difficulty_estimate: str = "Unknown"
    rating_estimate: Optional[int] = None
    topics: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Execution + verification
# --------------------------------------------------------------------------

@dataclass
class RunResult:
    """Outcome of executing one program on one input inside the sandbox."""
    verdict: Verdict
    stdout: str = ""
    stderr: str = ""
    time_ms: int = 0
    memory_kb: int = 0
    exit_code: int = 0
    message: str = ""


@dataclass
class SampleCheck:
    index: int
    verdict: Verdict
    expected: str
    actual: str
    time_ms: int
    diff_hint: str = ""


@dataclass
class StressReport:
    """Result of differential testing against an independent brute force."""
    ran: bool = False
    cases: int = 0
    passed: int = 0
    counterexample: Optional[str] = None
    counterexample_expected: str = ""
    counterexample_actual: str = ""
    reason_skipped: str = ""

    @property
    def clean(self) -> bool:
        return self.ran and self.cases > 0 and self.passed == self.cases


@dataclass
class PerfProbe:
    """Worst-case timing measurement against the problem's time limit."""
    ran: bool = False
    n_used: Optional[int] = None
    time_ms: int = 0
    limit_ms: int = 0
    headroom: float = 0.0
    reason_skipped: str = ""

    @property
    def comfortable(self) -> bool:
        return self.ran and self.limit_ms > 0 and self.time_ms <= self.limit_ms * 0.5


@dataclass
class Attempt:
    """One synthesis attempt and everything learned from it."""
    index: int
    language: Language
    code: str
    compiled: bool = False
    compile_log: str = ""
    sample_checks: list[SampleCheck] = field(default_factory=list)
    verdict: Verdict = Verdict.JUDGE_ERROR
    notes: str = ""

    @property
    def samples_pass(self) -> bool:
        return bool(self.sample_checks) and all(c.verdict.is_ok for c in self.sample_checks)


# --------------------------------------------------------------------------
# Explanation
# --------------------------------------------------------------------------

@dataclass
class DryRunStep:
    step: str
    state: str


@dataclass
class Explanation:
    """The 'why and how' half of the product."""
    intuition: str = ""
    observations: list[str] = field(default_factory=list)
    approach: str = ""
    algorithm_steps: list[str] = field(default_factory=list)
    correctness: str = ""
    time_complexity: str = ""
    space_complexity: str = ""
    complexity_justification: str = ""
    code_walkthrough: list[dict[str, str]] = field(default_factory=list)
    dry_run: list[DryRunStep] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    related_topics: list[str] = field(default_factory=list)
    why_this_works_here: str = ""


# --------------------------------------------------------------------------
# The full solve result
# --------------------------------------------------------------------------

@dataclass
class SolveResult:
    """Everything the endpoint returns for one submitted problem."""
    solve_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    problem: Optional[Problem] = None
    analysis: Optional[Analysis] = None
    language: Language = Language.CPP
    solution_code: str = ""
    confidence: Confidence = Confidence.UNVERIFIED
    verdict: Verdict = Verdict.JUDGE_ERROR
    attempts: list[Attempt] = field(default_factory=list)
    sample_checks: list[SampleCheck] = field(default_factory=list)
    stress: StressReport = field(default_factory=StressReport)
    perf: PerfProbe = field(default_factory=PerfProbe)
    explanation: Optional[Explanation] = None
    brute_force_code: str = ""
    generator_code: str = ""
    timeline: list[dict[str, Any]] = field(default_factory=list)
    elapsed_ms: int = 0
    provider: str = ""
    warnings: list[str] = field(default_factory=list)
    cached: bool = False

    def log(self, stage: Stage, message: str, ok: bool = True, **extra: Any) -> None:
        self.timeline.append({
            "stage": stage.value,
            "message": message,
            "ok": ok,
            "at": round(time.time() * 1000),
            **extra,
        })

    def to_dict(self) -> dict[str, Any]:
        def encode(obj: Any) -> Any:
            if isinstance(obj, enum.Enum):
                return obj.value
            if isinstance(obj, dict):
                return {k: encode(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [encode(v) for v in obj]
            return obj
        return encode(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    # -- the honest headline -------------------------------------------------

    def headline(self) -> str:
        """One sentence the UI shows above the solution. Never overstates."""
        samples = len(self.sample_checks)

        if self.confidence is Confidence.VERIFIED:
            speed = (f", and runs in {self.perf.time_ms} ms against a {self.perf.limit_ms} ms "
                     f"limit at the maximum input size" if self.perf.ran else
                     ", and its complexity fits the constraints")
            return (f"Verified — passes all {samples} sample(s) and {self.stress.cases} randomised "
                    f"cases against an independent brute force{speed}.")

        if self.confidence is Confidence.STRONG:
            if self.perf.ran and self.perf.headroom < 1.0:
                return (f"Correct but too slow — agrees with an independent brute force on "
                        f"{self.stress.cases} cases, but exceeds the time limit at full input size.")
            return (f"Strong — passes all {samples} sample(s) and agrees with an independent brute "
                    f"force on {self.stress.cases} randomised cases. Speed at the maximum input "
                    f"size was not measured.")

        if self.confidence is Confidence.LIKELY:
            reason = self.stress.reason_skipped or "stress testing could not be run"
            return (f"Likely correct — passes all {samples} sample(s), but {reason[0].lower()}"
                    f"{reason[1:].rstrip('.')}, so an untested edge case may still break it.")

        if self.confidence is Confidence.FAILED:
            if not self.attempts:
                reason = self.warnings[0] if self.warnings else "the problem could not be analysed"
                return f"Not solved — {reason[0].lower()}{reason[1:]}"
            return (f"Not solved — {len(self.attempts)} attempt(s) were made and none passed the "
                    f"samples. The attempt log below shows how each one failed.")

        return "Unverified — treat this as a starting point, not an answer."
