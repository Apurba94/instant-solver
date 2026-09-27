"""Stage 2 — Analysis.

Two deterministic jobs that happen *before* any model is asked for code:

1. **Complexity budget.** Read the constraints and decide what asymptotics are
   affordable. This is the single most valuable reflex a strong competitive
   programmer has — ``n <= 2*10^5`` means "O(n log n), and if you are writing a
   double loop you have already lost". Making it explicit lets the synthesiser
   be *told* its budget, and lets the verifier reject solutions that cannot fit.

2. **Topic priors.** Cheap keyword and structure signals that narrow the search
   space before the expensive reasoning step. These are priors, not verdicts:
   they are handed to the model as suggestions it is free to overrule.
"""
from __future__ import annotations

import re
from typing import Optional

from .models import Analysis, ComplexityBudget, Problem

# Operations a modern judge machine retires per second for non-trivial C++ code.
# Deliberately conservative: real throughput for tight array loops is nearer
# 1e9, but DP with random access, map lookups and pointer chasing lands here.
OPS_PER_SECOND = 1.2e8


# --------------------------------------------------------------------------
# Complexity budget
# --------------------------------------------------------------------------

# Ordered from cheapest to most expensive. ``cost`` estimates the operation
# count for input size n.
_COMPLEXITY_LADDER: list[tuple[str, callable]] = [
    ("O(1)", lambda n: 1),
    ("O(log n)", lambda n: max(1, n.bit_length())),
    ("O(sqrt n)", lambda n: int(n ** 0.5) + 1),
    ("O(n)", lambda n: n),
    # A sieve is n log log n, which is ~3n at n = 10^7 — nowhere near n log n.
    # Without its own rung, every sieve gets falsely flagged as too slow.
    ("O(n log log n)", lambda n: n * max(1, max(1, n.bit_length()).bit_length())),
    ("O(n log n)", lambda n: n * max(1, n.bit_length())),
    ("O(n log^2 n)", lambda n: n * max(1, n.bit_length()) ** 2),
    ("O(n sqrt n)", lambda n: n * (int(n ** 0.5) + 1)),
    ("O(n^2)", lambda n: n * n),
    ("O(n^2 log n)", lambda n: n * n * max(1, n.bit_length())),
    ("O(n^3)", lambda n: n ** 3),
    ("O(2^n)", lambda n: 2 ** n if n <= 40 else float("inf")),
    ("O(2^n * n)", lambda n: (2 ** n) * n if n <= 40 else float("inf")),
    ("O(n!)", lambda n: _factorial_capped(n)),
]


def _factorial_capped(n: int) -> float:
    if n > 20:
        return float("inf")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


# --------------------------------------------------------------------------
# Complexity normalisation
# --------------------------------------------------------------------------

# Ordered most specific first: "n log^2 n" must be tested before "n log n",
# and "n log n" before "n", or every pattern collapses to the loosest match.
_COMPLEXITY_PATTERNS: list[tuple[str, str]] = [
    (r"^1$|^c$|constant", "O(1)"),
    (r"^n!$|factorial", "O(n!)"),
    (r"2\^n.*\*?\s*n|n\s*\*\s*2\^n", "O(2^n * n)"),
    (r"2\^n|3\^n|exponential", "O(2^n)"),
    (r"n\^3|n\*n\*n|n\^2\s*\*\s*n|cubic", "O(n^3)"),
    (r"n\^2\s*log|n\*n\s*log", "O(n^2 log n)"),
    (r"n\^2|n\*n|n\s*\*\s*m|quadratic", "O(n^2)"),
    (r"n\s*sqrt|sqrt\s*n\s*\*\s*n|n\*sqrt", "O(n sqrt n)"),
    (r"n\s*log\s*log", "O(n log log n)"),    # must precede the n-log-n pattern
    (r"n\s*log\^?\s*2|n\s*log\s*n\s*log", "O(n log^2 n)"),
    (r"n\s*log", "O(n log n)"),
    (r"^sqrt|sqrt\s*n", "O(sqrt n)"),
    (r"^log|log\s*n|logarithmic", "O(log n)"),
    (r"^n$|linear|n\s*\+\s*m|n\s*\+\s*e|alpha", "O(n)"),
]


def normalize_complexity(text: str) -> Optional[str]:
    """Map a free-form complexity string onto the ladder, or ``None`` if unclear.

    Models write ``O((V + E) log V)``, ``O(n log(sum))`` and ``O(n * alpha(n))``.
    All three are affordable at n = 2*10^5, but a literal string comparison
    against the ladder rejects every one of them — which would make the engine
    warn about perfectly good solutions and refuse to call them verified.
    Returning ``None`` for anything genuinely unrecognised keeps the system
    silent rather than wrong.
    """
    if not text:
        return None
    s = text.strip().lower()
    s = re.sub(r"^o\s*[\(\[]?|[\)\]]?$", "", s).strip()
    s = re.sub(r"\b(?:amortized|amortised|expected|average|worst[- ]case)\b", "", s)
    s = re.sub(r"\balpha\s*\([^)]*\)", "alpha", s)      # inverse Ackermann ~ constant
    s = re.sub(r"log\s*\(\s*[^)]*\)", "log n", s)       # log(sum), log(maxA) -> log n
    # Any size-like variable becomes n; a product of two of them is caught as n^2
    # by the pattern list before this collapses them.
    s = re.sub(r"\b(?:v|e|m|q|k|s|len|size)\b", "n", s)
    # Drop the remaining grouping parentheses BEFORE collapsing sums, so that
    # "(V + E) log V" reduces to "n log n" and not to a bare "log n".
    s = re.sub(r"[()\[\]]", " ", s)
    s = re.sub(r"\bn(?:\s*\+\s*n)+\b", "n", s)
    s = re.sub(r"\s+", " ", s).strip()

    for pattern, canonical in _COMPLEXITY_PATTERNS:
        if re.search(pattern, s):
            return canonical
    return None


def complexity_budget(problem: Problem) -> ComplexityBudget:
    """Decide which asymptotics fit inside the time limit."""
    n = problem.max_n
    seconds = problem.time_limit_ms / 1000.0
    budget = int(OPS_PER_SECOND * seconds)

    if n is None:
        return ComplexityBudget(
            max_n=None,
            ops_budget=budget,
            allowed=[name for name, _ in _COMPLEXITY_LADDER],
            forbidden=[],
            reasoning=(
                "No numeric bound could be parsed from the statement, so no "
                "complexity can be ruled out. Treat the budget as unknown and "
                "prefer the asymptotically better solution when in doubt."
            ),
        )

    # Multi-test problems normally bound the SUM of n, so the per-test budget is
    # the whole budget; but a per-test bound with many tests needs headroom.
    if problem.multi_test and not re.search(r"sum of .{0,12}(n|m)\b", problem.statement, re.I):
        budget = budget // 4

    allowed, forbidden = [], []
    for name, cost_fn in _COMPLEXITY_LADDER:
        try:
            cost = cost_fn(n)
        except (OverflowError, ValueError):
            cost = float("inf")
        (allowed if cost <= budget else forbidden).append(name)

    reasoning = _budget_reasoning(n, seconds, budget, allowed, problem)
    return ComplexityBudget(
        max_n=n, ops_budget=budget, allowed=allowed,
        forbidden=forbidden, reasoning=reasoning,
    )


def _budget_reasoning(n: int, seconds: float, budget: int,
                      allowed: list[str], problem: Problem) -> str:
    best = allowed[-1] if allowed else "O(log n)"
    note = ""
    if n <= 20:
        note = (" A bound this small is a deliberate signal: exponential search over "
                "subsets or permutations is intended, most often bitmask DP.")
    elif n <= 40:
        note = (" n around 40 is the classic meet-in-the-middle signature — split the "
                "input in half, enumerate 2^(n/2) on each side, and combine.")
    elif n <= 500:
        note = " A cubic algorithm fits here, which is why Floyd-Warshall and interval DP live in this range."
    elif n <= 5000:
        note = " Quadratic fits; anything worse does not."
    elif n <= 10 ** 6:
        note = " This is the classic sorting / sweep / prefix-sum / segment-tree range."
    else:
        note = (" A bound this large rules out touching every element in a nested way; the "
                "answer is usually closed-form, logarithmic, or a number-theoretic identity.")
    if problem.multi_test:
        note += (" The problem is multi-test, so the per-test cost is multiplied by the "
                 "number of tests — check whether the statement bounds the sum of n.")
    return (
        f"Largest parsed bound is n = {n:,} with a {seconds:g}s limit, giving roughly "
        f"{budget:,} elementary operations. The most expensive shape that fits is {best}."
        + note
    )


# --------------------------------------------------------------------------
# Topic priors
# --------------------------------------------------------------------------

_TOPIC_SIGNALS: dict[str, list[str]] = {
    "graphs": [r"\bgraph\b", r"\bvertex\b", r"\bvertices\b", r"\bedges?\b", r"\bnodes?\b",
               r"\badjacen", r"\bconnected\b", r"\bcomponent"],
    "shortest paths": [r"shortest path", r"minimum (?:cost|distance|time) (?:to|from)",
                       r"\bdistance between\b", r"travel", r"\bweighted edges?\b"],
    "trees": [r"\btree\b", r"\brooted\b", r"\bsubtree\b", r"\bparent\b", r"\bleaf\b",
              r"\bn-1 edges\b", r"\bancestor\b"],
    "dynamic programming": [r"\bmaximum (?:sum|value|profit|score)\b", r"\bminimum cost\b",
                            r"number of ways", r"\bcount the number of\b", r"\bsubsequence\b",
                            r"\bpartition\b", r"\bknapsack\b", r"\boptimal\b"],
    "greedy": [r"\bas (?:many|few) .{0,20} as possible\b", r"\bminimum number of\b",
               r"\bmaximum number of\b", r"\bschedul", r"\bintervals?\b"],
    "binary search": [r"\bminimi[sz]e the maximum\b", r"\bmaximi[sz]e the minimum\b",
                      r"\bsmallest .{0,20} such that\b", r"\blargest .{0,20} such that\b",
                      r"\bsorted\b"],
    "two pointers / sliding window": [r"\bsubarray\b", r"\bcontiguous\b", r"\bwindow\b",
                                      r"\bconsecutive\b", r"\bsubstring\b"],
    "number theory": [r"\bprime\b", r"\bdivisor", r"\bgcd\b", r"\blcm\b", r"\bmodulo\b",
                      r"\bmod\s*10\^?9", r"\bcoprime\b", r"\bfactori[sz]", r"\bremainder\b"],
    "combinatorics": [r"number of ways", r"\bpermutations?\b", r"\bcombinations?\b",
                      r"\bbinomial\b", r"\bchoose\b", r"\bdistinct arrangements\b"],
    "strings": [r"\bstring\b", r"\bsubstring\b", r"\bpalindrom", r"\bprefix\b", r"\bsuffix\b",
                r"\bcharacters?\b", r"\blowercase\b"],
    "data structures": [r"\bquer(?:y|ies)\b", r"\bupdate\b", r"\brange\b", r"\bsegment\b",
                        r"\bafter each\b"],
    "sorting": [r"\bsort", r"\bnon-decreasing\b", r"\bincreasing order\b", r"\brearrange\b"],
    "geometry": [r"\bpoints?\b.{0,30}\bplane\b", r"\bcoordinates?\b", r"\bpolygon\b",
                 r"\bconvex\b", r"\barea\b", r"\bcircle\b", r"\bsegments? intersect"],
    "game theory": [r"\bgame\b", r"\boptimally\b", r"\bfirst player\b", r"\bwins?\b",
                    r"\balternat(?:e|ing) turns\b", r"\bmove\b.{0,20}\bturn\b"],
    "bit manipulation": [r"\bxor\b", r"\bbitwise\b", r"\bbits?\b", r"\bbinary representation\b"],
    "math": [r"\bsum of\b", r"\bformula\b", r"\bequation\b", r"\bsequence\b"],
}

# Techniques suggested once a topic fires and the budget allows it.
_TECHNIQUE_MAP: dict[str, list[str]] = {
    "shortest paths": ["Dijkstra", "0-1 BFS", "BFS on unweighted graph",
                       "Bellman-Ford", "Floyd-Warshall"],
    "graphs": ["BFS", "DFS", "Union-Find (DSU)", "Topological sort",
               "Strongly connected components"],
    "trees": ["Tree DP", "DFS with subtree aggregation", "LCA via binary lifting",
              "Euler tour + range structure", "Rerooting DP"],
    "dynamic programming": ["1D DP over prefixes", "Knapsack DP", "Interval DP",
                            "Bitmask DP", "Digit DP", "DP with monotonic optimisation"],
    "greedy": ["Sort then sweep", "Exchange argument", "Priority-queue greedy",
               "Interval scheduling"],
    "binary search": ["Binary search on the answer", "Binary search over a sorted array",
                      "Parametric search", "Ternary search on a unimodal function"],
    "two pointers / sliding window": ["Two pointers", "Sliding window with a counter",
                                      "Prefix sums", "Monotonic deque"],
    "number theory": ["Sieve of Eratosthenes", "Modular exponentiation", "Extended Euclid",
                      "Euler totient", "Factorisation by trial division to sqrt(n)"],
    "combinatorics": ["Precomputed factorials with modular inverse", "Inclusion-exclusion",
                      "Catalan / Stirling numbers", "Pascal's triangle DP"],
    "strings": ["Hashing", "KMP prefix function", "Z-algorithm", "Trie",
                "Manacher for palindromes"],
    "data structures": ["Fenwick tree (BIT)", "Segment tree", "Sparse table",
                        "Sqrt decomposition", "Mo's algorithm", "Ordered set"],
    "sorting": ["Sort with a custom comparator", "Coordinate compression",
                "Counting sort", "Counting inversions via BIT"],
    "geometry": ["Cross product orientation test", "Convex hull (monotone chain)",
                 "Line sweep", "Rotating calipers"],
    "game theory": ["Sprague-Grundy numbers", "Nim", "Minimax DP", "Parity argument"],
    "bit manipulation": ["Bitmask enumeration", "Trie over bits for XOR", "Submask sum (SOS DP)",
                         "Prefix XOR"],
    "math": ["Closed-form formula", "Matrix exponentiation", "Arithmetic/geometric series"],
}

# Complexity each technique typically costs, used to filter against the budget.
_TECHNIQUE_COST: dict[str, str] = {
    "Floyd-Warshall": "O(n^3)", "Bellman-Ford": "O(n^2)", "Bitmask DP": "O(2^n * n)",
    "Interval DP": "O(n^3)", "Mo's algorithm": "O(n sqrt n)",
    "Sqrt decomposition": "O(n sqrt n)", "Segment tree": "O(n log n)",
    "Fenwick tree (BIT)": "O(n log n)", "Dijkstra": "O(n log n)",
    "Sort then sweep": "O(n log n)", "Two pointers": "O(n)", "Prefix sums": "O(n)",
    "BFS": "O(n)", "DFS": "O(n)", "Matrix exponentiation": "O(log n)",
    "Closed-form formula": "O(1)",
}


def detect_topics(problem: Problem) -> list[str]:
    """Score topic signals against the statement and return the ones that fire."""
    text = problem.statement.lower()
    scores: dict[str, int] = {}
    for topic, patterns in _TOPIC_SIGNALS.items():
        hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
        if hits:
            scores[topic] = hits
    return [t for t, _ in sorted(scores.items(), key=lambda kv: -kv[1])][:5]


def suggest_techniques(topics: list[str], budget: ComplexityBudget) -> list[str]:
    """Union the techniques for the firing topics, dropping unaffordable ones."""
    out: list[str] = []
    for topic in topics:
        for technique in _TECHNIQUE_MAP.get(topic, []):
            if technique in out:
                continue
            cost = _TECHNIQUE_COST.get(technique)
            if cost and budget.max_n is not None and budget.permits(cost) is False:
                continue
            out.append(technique)
    if not out:
        out = ["Direct simulation", "Sorting", "Prefix sums", "Greedy", "Dynamic programming"]
    return out[:12]


# --------------------------------------------------------------------------
# Difficulty heuristic
# --------------------------------------------------------------------------

def estimate_difficulty(problem: Problem, topics: list[str],
                        budget: ComplexityBudget) -> tuple[str, Optional[int]]:
    """Rough Codeforces-style rating estimate from structure alone.

    This is a prior shown to the user as an estimate and nothing more; the model
    is free to disagree and the label is never used to gate anything.
    """
    score = 800
    advanced = {"geometry", "game theory", "data structures", "combinatorics"}
    score += 200 * len(set(topics) & advanced)
    if "dynamic programming" in topics:
        score += 300
    if "graphs" in topics or "trees" in topics:
        score += 200
    if budget.max_n is not None:
        if budget.max_n <= 20:
            score += 400            # exponential search is never a beginner topic
        elif budget.max_n >= 10 ** 9:
            score += 300            # needs a mathematical shortcut
    if len(problem.statement) > 2500:
        score += 200
    if problem.interactive:
        score += 400
    score = max(800, min(score, 3200))

    label = ("Beginner" if score < 1000 else "Easy" if score < 1300 else
             "Medium" if score < 1700 else "Hard" if score < 2100 else
             "Expert" if score < 2500 else "Master")
    return label, score


# --------------------------------------------------------------------------
# Pitfall priors
# --------------------------------------------------------------------------

def detect_pitfalls(problem: Problem, budget: ComplexityBudget) -> list[str]:
    """Traps that are visible from the constraints alone."""
    out: list[str] = []
    text = problem.statement

    max_value = problem.max_value
    if max_value is not None and max_value >= 10 ** 9:
        out.append(
            f"Individual values reach {max_value:,}. A sum or product of them overflows "
            "32-bit int — use long long in C++."
        )
    elif (max_value and budget.max_n
          and max_value * budget.max_n > 2 * 10 ** 9):
        out.append(
            f"Values are small individually, but {budget.max_n:,} of them sum to about "
            f"{max_value * budget.max_n:,}, which overflows 32-bit int."
        )
    if budget.max_n and budget.max_n >= 10 ** 5:
        out.append(
            "Input is large, so cin/cout must be untied and unsynchronised "
            "(ios_base::sync_with_stdio(false); cin.tie(nullptr);) or I/O alone can time out."
        )
    if problem.multi_test:
        out.append(
            "Multi-test problem: every global array, counter and visited flag must be reset "
            "per test case, and the reset must cost O(n) for this test, not O(maxN)."
        )
    if re.search(r"mod(?:ulo)?\s*(?:10\^9\s*\+\s*7|1000000007|998244353)", text, re.I):
        out.append(
            "Answers are taken modulo a prime. Reduce after every multiplication, and never "
            "let an intermediate product exceed 64 bits."
        )
    if problem.output_is_float:
        out.append(
            "The answer is a real number judged with a tolerance. Print with explicit "
            "precision (setprecision(10) or more) rather than default formatting."
        )
    if re.search(r"\bn\s*=\s*1\b|\bmay be empty\b|\bcan be zero\b", text, re.I):
        out.append("The statement explicitly allows a degenerate case — test n = 1 / empty input.")
    if "trees" in detect_topics(problem) and budget.max_n and budget.max_n >= 10 ** 5:
        out.append(
            "Recursion depth can reach n on a path-shaped tree; a recursive DFS may blow the "
            "stack. Prefer an iterative traversal or raise the stack limit."
        )
    return out


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def analyze(problem: Problem) -> Analysis:
    """Run the full deterministic analysis pass."""
    budget = complexity_budget(problem)
    topics = detect_topics(problem)
    techniques = suggest_techniques(topics, budget)
    label, rating = estimate_difficulty(problem, topics, budget)

    io_bits = []
    if problem.multi_test:
        io_bits.append("multi-test (leading test count)")
    if problem.output_is_float:
        io_bits.append("floating-point answer with tolerance")
    if problem.interactive:
        io_bits.append("INTERACTIVE — requires a live judge, not batch I/O")
    io_format = "; ".join(io_bits) if io_bits else "single test case, exact-match output"

    return Analysis(
        summary="",                      # filled by the reasoning provider
        io_format=io_format,
        budget=budget,
        candidate_techniques=techniques,
        topics=topics,
        difficulty_estimate=label,
        rating_estimate=rating,
        pitfalls=detect_pitfalls(problem, budget),
    )
