"""Engine test suite.

Runs with pytest, or standalone via ``python3 tests/test_engine.py``.

The tests that matter most are the ones in ``TestVerificationCatchesBugs``. It
is easy to build a solver that produces confident answers; the question this
suite exists to answer is whether the verification layer actually catches a
wrong solution that passes the samples. If those tests ever start passing
trivially, the product's core claim has quietly stopped being true.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import Solver, SolveConfig                              # noqa: E402
from engine.analyze import analyze, normalize_complexity            # noqa: E402
from engine.checker import compare                                  # noqa: E402
from engine.ingest import ingest                                    # noqa: E402
from engine.models import Confidence, Language, Verdict             # noqa: E402
from engine.pipeline import perf_probe, stress_test                 # noqa: E402
from engine.providers.base import Plan, Synthesis                   # noqa: E402
from engine.providers.offline import OfflineProvider                # noqa: E402
from engine.sandbox import CompileError, compile_source, pick_runner  # noqa: E402
from tests import problems                                          # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not condition else ""))


# --------------------------------------------------------------------------

def test_ingestion() -> None:
    print("\nIngestion")
    p = ingest(problems.MAX_SUBARRAY["statement"],
               problems.MAX_SUBARRAY["sample_input"],
               problems.MAX_SUBARRAY["sample_output"])
    check("parses the time limit", p.time_limit_ms == 1000, f"got {p.time_limit_ms}")
    check("parses the memory limit", p.memory_limit_mb == 256, f"got {p.memory_limit_mb}")
    check("separates size from value bounds", p.max_n == 200_000 and p.max_value == 10**9,
          f"max_n={p.max_n} max_value={p.max_value}")

    u = ingest(problems.UNICODE_PARSE["statement"],
               problems.UNICODE_PARSE["sample_input"],
               problems.UNICODE_PARSE["sample_output"])
    check("decodes unicode superscripts (2·10⁵)", u.max_n == 200_000, f"got {u.max_n}")

    multi = ingest("The first line contains an integer t, the number of test cases.\n"
                   "1 <= t <= 10^4\n1 <= n <= 10^5")
    check("detects multi-test input", multi.multi_test)

    flt = ingest("Print the area. Answers with an absolute or relative error of at most "
                 "10^-6 are accepted.\n1 <= n <= 1000")
    check("detects a tolerance-judged answer", flt.output_is_float)

    embedded = ingest("Add two numbers.\n\nConstraints\n1 <= a <= 100\n\n"
                      "Input\n3 4\n\nOutput\n7\n")
    check("scrapes samples out of the statement body", len(embedded.samples) == 1,
          f"found {len(embedded.samples)}")


def test_complexity_budget() -> None:
    print("\nComplexity budget")
    cases = {
        "O((V + E) log V)": "O(n log n)",
        "O(n log(sum))": "O(n log n)",
        "O(n log log n)": "O(n log log n)",
        "O(n * alpha(n))": "O(n)",
        "O(n^2)": "O(n^2)",
        "O(2^n * n)": "O(2^n * n)",
        "amortized O(n log n)": "O(n log n)",
        "O(pineapple)": None,
    }
    for text, expected in cases.items():
        got = normalize_complexity(text)
        check(f"normalises {text}", got == expected, f"got {got}, expected {expected}")

    small = analyze(ingest("Find the best permutation.\nConstraints\n1 <= n <= 18"))
    check("n <= 18 permits exponential", small.budget.permits("O(2^n * n)") is True)
    check("n <= 18 forbids O(n!)", small.budget.permits("O(n!)") is False)

    big = analyze(ingest("Process the array.\nConstraints\n1 <= n <= 200000\nTime limit: 1 second"))
    check("n <= 2*10^5 permits O(n log n)", big.budget.permits("O(n log n)") is True)
    check("n <= 2*10^5 forbids O(n^2)", big.budget.permits("O(n^2)") is False)
    check("unparsable complexity returns None", big.budget.permits("O(???)") is None)


def test_sandbox() -> None:
    print("\nSandbox")
    runner = pick_runner()

    with compile_source("#include <cstdio>\nint main(){int a,b;scanf(\"%d %d\",&a,&b);"
                        "printf(\"%d\\n\",a+b);}", Language.CPP, runner) as p:
        r = p.run("2 3\n", 2000, 256)
        check("accepts a correct program", r.verdict is Verdict.ACCEPTED and r.stdout.strip() == "5")

    with compile_source("int main(){while(1);}", Language.CPP, runner) as p:
        check("detects an infinite loop as TLE",
              p.run("", 800, 256).verdict is Verdict.TIME_LIMIT_EXCEEDED)

    with compile_source("#include <vector>\nint main(){std::vector<long long> v;"
                        "for(long long i=0;i<1e9;i++)v.push_back(i);}", Language.CPP, runner) as p:
        check("detects excessive allocation as MLE",
              p.run("", 3000, 64).verdict is Verdict.MEMORY_LIMIT_EXCEEDED)

    with compile_source("int main(){int*p=0;return *p;}", Language.CPP, runner) as p:
        check("detects a segfault as RE", p.run("", 2000, 256).verdict is Verdict.RUNTIME_ERROR)

    try:
        compile_source("int main(){ syntax error }", Language.CPP, runner)
        check("reports a compilation error", False, "no exception raised")
    except CompileError as exc:
        check("reports a compilation error", "error" in exc.log.lower())

    with compile_source("print(sum(map(int, input().split())))", Language.PYTHON, runner) as p:
        r = p.run("2 3\n", 2000, 256)
        check("runs Python too", r.verdict is Verdict.ACCEPTED and r.stdout.strip() == "5")


def test_checker() -> None:
    print("\nOutput checker")
    check("ignores whitespace layout", compare("1 2 3", "1\n2\n 3\n").ok)
    check("accepts float within tolerance",
          compare("3.14159265", "3.141592", float_mode=True).ok)
    check("rejects float outside tolerance",
          not compare("3.14159265", "3.14", float_mode=True).ok)
    check("accepts YES vs Yes", compare("YES", "Yes").ok)
    check("rejects YES vs NO", not compare("YES", "No").ok)
    check("rejects a missing token", not compare("1 2 3", "1 2").ok)
    check("explains a token-count mismatch",
          "Token count differs" in compare("1 2 3", "1 2").hint)
    check("rejects empty output", not compare("42", "").ok)


# --------------------------------------------------------------------------
# The tests that justify the product
# --------------------------------------------------------------------------

class _FixedProvider:
    """A provider that always returns one predetermined solution.

    Used to inject a *known-bad* solution into the pipeline so the verification
    layer can be tested against it.
    """

    name = "fixed"

    def __init__(self, code: str, delegate: OfflineProvider):
        self.code = code
        self.delegate = delegate
        self.repairs = 0

    def plan(self, problem, analysis):
        return self.delegate.plan(problem, analysis)

    def synthesize(self, problem, analysis, plan, language):
        return Synthesis(code=self.code, language=Language.CPP)

    def repair(self, problem, analysis, plan, language, previous_code, failure_report):
        self.repairs += 1
        return Synthesis(code=self.code, language=Language.CPP)   # never improves

    def brute_force(self, problem, analysis, language):
        return self.delegate.brute_force(problem, analysis, language)

    def generator(self, problem, analysis, small=True):
        return self.delegate.generator(problem, analysis, small)

    def explain(self, problem, analysis, plan, code, language):
        return self.delegate.explain(problem, analysis, plan, code, language)


# Passes the friendly sample (answer 9) but returns 0 for an all-negative array,
# because the running best starts at 0. This is the single most common real bug
# in this problem, and it is invisible to sample testing.
SUBTLY_WRONG_KADANE = r"""
#include <bits/stdc++.h>
using namespace std;
int main(){
    int n; if(!(cin>>n)) return 0;
    long long best = 0, cur = 0;            // BUG: best should start at -infinity
    for(int i=0;i<n;i++){ long long x; cin>>x; cur = max(0LL, cur + x); best = max(best, cur); }
    cout << best << "\n";
}
"""

# Correct, but quadratic: it will pass every small stress case and time out at scale.
SLOW_BUT_CORRECT_KADANE = r"""
#include <bits/stdc++.h>
using namespace std;
int main(){
    int n; if(!(cin>>n)) return 0;
    vector<long long> a(n); for(auto &x:a) cin>>x;
    long long best = LLONG_MIN;
    for(int l=0;l<n;l++){ long long s=0; for(int r=l;r<n;r++){ s+=a[r]; best=max(best,s);} }
    cout << best << "\n";
}
"""


def test_verification_catches_bugs() -> None:
    print("\nVerification (the part that matters)")
    corpus = OfflineProvider()
    p = problems.MAX_SUBARRAY

    # 1. A wrong solution that passes the sample must NOT be reported as verified.
    provider = _FixedProvider(SUBTLY_WRONG_KADANE, corpus)
    solver = Solver(provider=provider,
                    config=SolveConfig(max_attempts=2, stress_cases=300, stress_budget_s=20))
    result = solver.solve_text(p["statement"], p["sample_input"], p["sample_output"])

    sample_passed = bool(result.attempts and result.attempts[0].samples_pass)
    check("the buggy solution does pass the samples (so sample testing alone is not enough)",
          sample_passed, "the sample did not pass, so this test proves nothing")
    check("stress testing finds a counterexample",
          result.stress.counterexample is not None,
          f"no counterexample after {result.stress.cases} cases")
    check("the counterexample is a small, readable input",
          result.stress.counterexample is not None and len(result.stress.counterexample) < 120)
    check("the wrong solution is NOT reported as verified",
          result.confidence is not Confidence.VERIFIED,
          f"reported {result.confidence.value}")
    check("the user is warned in plain language",
          any("disagrees with an independent brute force" in w for w in result.warnings))

    # 2. A correct solution must still come out verified — no crying wolf.
    good = Solver(config=SolveConfig(stress_cases=200, stress_budget_s=15))
    ok_result = good.solve_text(p["statement"], p["sample_input"], p["sample_output"])
    check("a correct solution is still reported as verified",
          ok_result.confidence is Confidence.VERIFIED, f"got {ok_result.confidence.value}")
    check("no false counterexample is reported", ok_result.stress.counterexample is None)


def test_perf_probe_catches_slowness() -> None:
    print("\nPerformance probe")
    runner = pick_runner()
    problem = ingest(problems.MAX_SUBARRAY["statement"],
                     problems.MAX_SUBARRAY["sample_input"],
                     problems.MAX_SUBARRAY["sample_output"])
    big_gen_src = ("import random\nn=200000\nprint(n)\n"
                   "print(' '.join(str(random.randint(-10**9,10**9)) for _ in range(n)))\n")

    fast = compile_source(problems_solution(), Language.CPP, runner)
    slow = compile_source(SLOW_BUT_CORRECT_KADANE, Language.CPP, runner)
    gen = compile_source(big_gen_src, Language.PYTHON, runner)
    try:
        fast_probe = perf_probe(fast, gen, problem)
        slow_probe = perf_probe(slow, gen, problem)
        check("the linear solution is comfortably inside the limit",
              fast_probe.ran and fast_probe.headroom >= 1.0,
              f"{fast_probe.time_ms} ms vs {problem.time_limit_ms} ms")
        check("the quadratic solution is caught as too slow at full scale",
              slow_probe.ran and slow_probe.headroom < 1.0,
              f"{slow_probe.time_ms} ms vs {problem.time_limit_ms} ms")
    finally:
        fast.cleanup(); slow.cleanup(); gen.cleanup()


def problems_solution() -> str:
    from engine.providers.library import CORPUS_BY_KEY
    return CORPUS_BY_KEY["max_subarray"].solution_cpp


def test_full_pipeline() -> None:
    print("\nFull pipeline over the corpus")
    solver = Solver(config=SolveConfig(stress_cases=150, stress_budget_s=12))
    for key, p in problems.ALL.items():
        result = solver.solve_text(p["statement"], p["sample_input"], p["sample_output"],
                                   title=p["title"])
        ok = result.confidence in (Confidence.VERIFIED, Confidence.STRONG)
        check(f"{key}: solved and verified", ok, f"got {result.confidence.value}")
        check(f"{key}: explanation produced",
              result.explanation is not None and bool(result.explanation.intuition))
        check(f"{key}: dry run traces the sample",
              result.explanation is not None and len(result.explanation.dry_run) >= 2)
        check(f"{key}: result serialises to JSON", bool(result.to_json()))


def test_unknown_problem_fails_honestly() -> None:
    print("\nUnknown problem handling")
    solver = Solver(provider=OfflineProvider(), config=SolveConfig(explain=False))
    result = solver.solve_text(problems.UNKNOWN["statement"],
                               problems.UNKNOWN["sample_input"],
                               problems.UNKNOWN["sample_output"])
    check("an unrecognised problem fails rather than guessing",
          result.confidence is Confidence.FAILED, f"got {result.confidence.value}")
    check("the failure says why", bool(result.warnings))
    check("the headline does not claim an answer",
          "Not solved" in result.headline(), result.headline())


# --------------------------------------------------------------------------

def main() -> int:
    for suite in (test_ingestion, test_complexity_budget, test_sandbox, test_checker,
                  test_verification_catches_bugs, test_perf_probe_catches_slowness,
                  test_full_pipeline, test_unknown_problem_fails_honestly):
        suite()
    print(f"\n{'=' * 60}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("Failures:")
        for name in FAIL:
            print(f"  - {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
