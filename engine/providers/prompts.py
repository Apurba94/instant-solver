"""Prompt library for the reasoning provider.

Kept in one file on purpose: prompts are the highest-leverage, fastest-changing
part of the system, and a team iterating on solve rate should be able to diff
them without reading the pipeline.

The design follows how a strong competitive programmer actually works, in the
order they actually work:

1. Restate the problem in one's own words (catches misreadings early).
2. Read the constraints and fix a complexity budget *before* thinking about
   algorithms — this is the step that separates strong solvers from weak ones.
3. Enumerate candidate techniques and eliminate them against that budget.
4. Prove the chosen approach is correct before typing.
5. Only then write code, and write it in a disciplined house style.

Separating planning from coding is deliberate. A model asked for code
immediately writes the first plausible thing; a model asked to commit to a
complexity budget first cannot then hand back an O(n^2) loop for n = 200000
without contradicting itself.
"""
from __future__ import annotations

SYSTEM_SOLVER = """\
You are a world-class competitive programmer — the level of a multiple-time \
ICPC World Finals medallist and Codeforces Legendary Grandmaster. You have \
solved tens of thousands of problems across Codeforces, AtCoder, ICPC \
regionals and the IOI.

How you work:

- You read the constraints BEFORE you think about algorithms. The bound on n \
fixes the complexity budget, and the budget eliminates most approaches before \
they are considered. n <= 20 means subsets. n <= 40 means meet in the middle. \
n <= 500 means cubic. n <= 5000 means quadratic. n <= 2*10^5 means O(n log n). \
n <= 10^6 means linear. n >= 10^9 means the answer is a formula, a logarithm, \
or number theory.
- You look for the observation that collapses the problem. Most problems are \
one insight plus a standard technique, not an exotic algorithm.
- You prove your approach before you type. A greedy needs an exchange \
argument. A DP needs a state definition, a transition, and a reason the \
subproblems are independent.
- You write clean, fast, idiomatic code: 64-bit types where values can \
overflow, fast I/O for large input, no undefined behaviour, correct handling of \
n = 1 and empty input.
- You are honest about uncertainty. If you are unsure your approach is \
correct, you say so plainly rather than projecting false confidence. An honest \
"I think this is right but the tricky case is X" is far more useful than a \
confident wrong answer.

You never write code that reads files, opens sockets, spawns processes, or does \
anything other than read stdin and write stdout.\
"""

PLAN_TEMPLATE = """\
Solve this competitive programming problem. Do NOT write the final solution \
code yet — this step is analysis only.

<problem>
{statement}
</problem>

<samples>
{samples}
</samples>

<mechanically_extracted_facts>
These were parsed from the statement automatically. They are hints, not \
authority — if the statement contradicts them, trust the statement and say so.

Time limit: {time_limit_ms} ms
Memory limit: {memory_limit_mb} MB
Parsed constraints: {constraints}
Complexity budget: {budget_reasoning}
Affordable complexities: {allowed}
Ruled out by the constraints: {forbidden}
Topic signals: {topics}
Candidate techniques worth considering: {techniques}
Shape: {io_format}
</mechanically_extracted_facts>

Work through it in this order:

1. Restate the problem in two or three sentences, in your own words. Include \
exactly what must be printed.
2. State the key observation(s) — the insight that makes the problem tractable. \
If the problem is a direct application of a standard technique, say that \
plainly instead of inventing depth that is not there.
3. Name the technique you will use, and say why the obvious alternatives are \
wrong or too slow. Reference the complexity budget explicitly.
4. Give the algorithm as numbered steps, concrete enough to implement from \
directly. For a DP, define the state, the transition and the base case. For a \
greedy, state the exchange argument.
5. State the time and space complexity and confirm it fits the budget.
6. List the risks: overflow, edge cases, off-by-one traps, precision, recursion \
depth, reset-between-test-cases.
7. Say honestly how confident you are that this approach is correct.

Reply with ONLY a JSON object inside a ```json fenced block, with these keys:

{{
  "restatement": "string",
  "observations": ["string", ...],
  "technique": "short name, e.g. 'Dijkstra with a binary heap'",
  "why_this_technique": "string, referencing the complexity budget",
  "algorithm_steps": ["string", ...],
  "time_complexity": "e.g. O(n log n)",
  "space_complexity": "e.g. O(n)",
  "fits_budget": true,
  "risks": ["string", ...],
  "confidence_note": "an honest sentence about how sure you are"
}}\
"""

SYNTHESIZE_TEMPLATE = """\
Implement the plan below as a complete, competition-ready {language_name} \
solution.

<problem>
{statement}
</problem>

<samples>
{samples}
</samples>

<plan>
Technique: {technique}
Why: {why_this_technique}
Steps:
{algorithm_steps}
Target complexity: {time_complexity} time, {space_complexity} space
Known risks: {risks}
</plan>

<limits>
Time limit: {time_limit_ms} ms
Memory limit: {memory_limit_mb} MB
Largest input bound parsed: {max_n}
</limits>

Requirements:

- Read from standard input, write to standard output. Nothing else.
- {io_requirement}
- Use 64-bit integers wherever a value or an intermediate sum can exceed \
2*10^9.
- Handle the degenerate cases: smallest n, empty structures, all-equal values, \
answer zero.
{multi_test_requirement}
- The code must compile with no warnings under `-O2 -std=c++17` (or the \
language's equivalent) and must not rely on undefined behaviour.
- Write it the way you would in a real contest: compact but readable, no \
unnecessary abstraction, meaningful variable names over single letters where it \
aids the reader.
- Add brief comments on the non-obvious steps only. Do not narrate every line.

Reply with ONLY the source code inside a single ```{language_tag} fenced block. \
No prose before or after.\
"""

REPAIR_TEMPLATE = """\
Your previous solution failed. Here is exactly how.

<problem>
{statement}
</problem>

<your_previous_solution>
```{language_tag}
{previous_code}
```
</your_previous_solution>

<failure_report>
{failure_report}
</failure_report>

<plan_you_were_following>
Technique: {technique}
Target complexity: {time_complexity}
</plan_you_were_following>

Diagnose before you fix:

1. What exactly went wrong? Name the specific defect — not "there was a bug".
2. Was the PLAN wrong, or only the implementation? If a compile error or an \
off-by-one, fix the code. If the samples disagree with the approach itself, or \
the solution is too slow for the constraints, change the approach — do not \
patch a fundamentally wrong algorithm.
3. Apply the fix.

If the failure is a time limit, the fix is a better asymptotic complexity, not \
micro-optimisation. If the failure is a wrong answer on a sample, trace that \
exact sample by hand until you find the divergence.

Reply with ONLY the corrected, complete source code inside a single \
```{language_tag} fenced block. No prose.\
"""

BRUTE_FORCE_TEMPLATE = """\
Write a deliberately SLOW but OBVIOUSLY CORRECT reference solution for this \
problem, to be used as the oracle in differential (stress) testing.

<problem>
{statement}
</problem>

<samples>
{samples}
</samples>

Rules:

- Correctness is the only goal. Ignore the time limit entirely.
- Use the most direct method possible: brute force every candidate, simulate \
literally, enumerate all subsets or permutations, recompute from scratch. The \
more naive, the more trustworthy.
- It must be correct for SMALL inputs — that is all stress testing needs. It \
may be exponential.
- It must NOT share any clever reasoning with the fast solution. The entire \
value of this program is that it is independent; if it repeats the fast \
solution's insight it will repeat its bug too.
- Same I/O format as the real problem: read stdin, write stdout.
- If the problem genuinely has no feasible brute force (for example the answer \
is only defined for huge inputs, or it is interactive), reply with exactly \
NO_BRUTE_FORCE and nothing else.

Reply with ONLY the source code in a single ```{language_tag} fenced block, or \
the bare token NO_BRUTE_FORCE.\
"""

GENERATOR_TEMPLATE = """\
Write a Python 3 random test generator for this problem, for stress testing.

<problem>
{statement}
</problem>

<samples>
{samples}
</samples>

<parsed_constraints>
{constraints}
</parsed_constraints>

Rules:

- Print ONE valid test case to stdout, in exactly the input format the problem \
specifies. Nothing else — no prompts, no labels, no trailing commentary.
- Use SMALL parameters so a brute force can handle it: sizes in the 1..8 range, \
values in a small range such as 1..10. Small tests find bugs; large tests just \
find timeouts.
- Every generated test MUST satisfy every constraint in the statement. If the \
input must be a tree, generate a tree. If it must be sorted, sort it. If a sum \
is bounded, respect the bound. An invalid test produces a fake counterexample, \
which is worse than no test at all.
- Bias towards the edges: minimum sizes, repeated values, all-equal values, \
already-sorted and reverse-sorted input, zeros and boundary values. Bugs live \
at the edges.
- Seed from `random.seed()` with no argument, or read an optional integer seed \
from sys.argv[1] if present, so repeated runs differ.
{multi_test_note}

Reply with ONLY the Python source inside a single ```python fenced block, or \
the bare token NO_GENERATOR if a valid random test cannot be generated \
mechanically.\
"""

MAX_GENERATOR_TEMPLATE = """\
Write a Python 3 generator that produces the LARGEST legal test case for this \
problem, to measure whether a solution is fast enough at full scale.

<problem>
{statement}
</problem>

<parsed_constraints>
{constraints}
</parsed_constraints>

Rules:

- Print ONE test case to stdout in exactly the problem's input format, using \
the MAXIMUM sizes the constraints permit. If n <= 200000, use n = 200000.
- Where the statement bounds a SUM across test cases, respect that bound rather \
than maximising each test independently.
- Make the case genuinely hard, not just large: random values across the full \
allowed range, a graph that is connected and not a trivial path, an array that \
is neither sorted nor constant. A maximal-size but trivially-structured test \
measures nothing.
- The generator itself must finish in a few seconds — build the test with \
bulk operations, not element-by-element Python loops where avoidable.
- Print nothing except the test case.

Reply with ONLY the Python source in a single ```python fenced block, or the \
bare token NO_GENERATOR if the maximum size cannot be determined from the \
statement.\
"""

EXPLAIN_TEMPLATE = """\
Write a complete editorial for this problem, explaining the solution below to a \
learner who is trying to get better — not just to someone who wants the answer.

<problem>
{statement}
</problem>

<samples>
{samples}
</samples>

<verified_solution>
```{language_tag}
{code}
```
</verified_solution>

<verification_status>
{verification_status}
</verification_status>

<approach_taken>
Technique: {technique}
Complexity: {time_complexity} time, {space_complexity} space
</approach_taken>

Explain the solution that is actually written above — not an idealised one. If \
the code takes a shortcut, explain the shortcut.

Teach the reasoning, not just the result. The reader should finish able to \
solve the NEXT problem of this kind on their own, which means the most \
valuable sentence you write is the one explaining how a solver could have \
FOUND this idea from the statement and constraints.

Reply with ONLY a JSON object inside a ```json fenced block:

{{
  "intuition": "2-4 sentences. How would a strong solver find this idea from the statement? What in the problem points to it?",
  "observations": ["the key insights, one per entry, each stated as a claim"],
  "approach": "a paragraph describing the approach as a whole",
  "algorithm_steps": ["numbered implementation steps in plain language"],
  "correctness": "why this is correct. For a greedy, the exchange argument. For a DP, why the state captures everything that matters and the subproblems are independent. Be rigorous but readable.",
  "time_complexity": "e.g. O(n log n)",
  "space_complexity": "e.g. O(n)",
  "complexity_justification": "where each factor comes from, and why it fits the given limits",
  "code_walkthrough": [
    {{"lines": "e.g. 'lines 8-14' or a function name", "what": "what this block does and why it is written this way"}}
  ],
  "dry_run": [
    {{"step": "what happens at this step on the FIRST sample input", "state": "the values of the important variables after it"}}
  ],
  "pitfalls": ["mistakes that cost people a wrong answer on this problem"],
  "alternatives": ["other approaches that work, with their complexity and their trade-off"],
  "related_topics": ["topics and named algorithms to study next"],
  "why_this_works_here": "one sentence tying the chosen technique back to the specific constraints of this problem"
}}

The dry_run must trace the FIRST sample input concretely, with real numbers \
from that sample — not a generic description. That trace is the single most \
useful part of an editorial for a struggling learner.\
"""
