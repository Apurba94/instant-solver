# Instant Solver

Paste a competitive programming problem with its sample input and output. Get a
solution back, **verified**, with a full explanation of why and how it works.

This is the first module of the larger platform. It is deliberately the first
one, because it is the piece that is hard to fake: anything can generate
plausible C++, but a solution nobody has tried to break is not an answer.

---

## What makes this different from asking a chatbot

A model writes plausible code. Plausible code passes the samples and fails the
hidden tests. So the engine treats generation as a *hypothesis* and spends most
of its time trying to falsify it:

| Stage | What it does | What it catches |
|---|---|---|
| Analyse | Derives a complexity budget from the constraints before any code exists | Approaches that cannot possibly fit the time limit |
| Plan | Commits to a technique and justifies it against that budget | Reaching for the first idea instead of the right one |
| Compile | Builds it in the sandbox | Code that does not build |
| Sample test | Runs your samples, compares tokens with float tolerance | Obvious wrong answers |
| Repair | Feeds the exact failing input, expected and actual output back in | Off-by-ones, missed edge cases |
| Stress test | Writes an **independent brute force** plus a random generator and hunts for a disagreement over hundreds of small cases | **Wrong solutions that pass every sample** |
| Perf probe | Times the solution on the largest input the constraints allow | Correct but too slow |

Every result carries an honest confidence level. `VERIFIED` means the
verification chain completed. `LIKELY` means the samples passed and nothing
else could be checked. The system says which one it is instead of projecting
confidence it has not earned.

```
VERIFIED    samples pass + no counterexample in N random cases + fits the time budget
STRONG      samples pass + no counterexample, but speed at full scale is unproven
LIKELY      samples pass; stress testing could not run
UNVERIFIED  compiles, but correctness was never checked
FAILED      no candidate passed the samples — the attempt log says why
```

---

## Quick start

```bash
make install          # Python deps + npm deps
cp .env.example .env  # optional: add ANTHROPIC_API_KEY to solve arbitrary problems
make api              # terminal 1 — engine on :8000
make web              # terminal 2 — UI on :3000
```

Open <http://localhost:3000>.

On Windows, and for deploying to a Hostinger VPS, see [DEPLOY.md](DEPLOY.md).

Without an API key the engine still runs end to end against a curated corpus of
classic problems (Kadane, LIS, Dijkstra, DSU, binary search on the answer, sieve,
two-sum). That is what the test suite uses, so **CI needs no key and no network**.

---

## Repository layout

```
engine/                the solver — framework-free, importable, testable
  models.py            domain types: Problem, Verdict, Confidence, SolveResult
  ingest.py            statement -> structured Problem (unicode maths, constraints, samples)
  analyze.py           complexity budget, topic priors, pitfalls, difficulty
  sandbox.py           compilation + isolated execution; real AC/WA/TLE/MLE/RE verdicts
  checker.py           judge-grade output comparison and diff explanation
  pipeline.py          orchestration: synthesise -> verify -> repair -> stress -> explain
  providers/
    base.py            the provider interface
    prompts.py         every prompt, in one file, for fast iteration
    claude.py          Anthropic-backed reasoning
    offline.py         retrieval from the corpus
    library.py         the archetype corpus (solution + brute force + generator + editorial)
api/main.py            FastAPI: /api/solve, /api/solve/stream (SSE), /api/run, /api/analyze
web/                   Next.js 16 + TypeScript + Tailwind 4 front end
tests/                 engine suite + Playwright UI smoke test
docs/                  architecture, security model, roadmap
```

---

## The API

```bash
# Health, languages, which sandbox backend is active
curl localhost:8000/api/health

# Analysis only — free, instant, and useful on its own
curl -X POST localhost:8000/api/analyze -H 'Content-Type: application/json' \
  -d '{"statement":"...\nConstraints\n1 <= n <= 2*10^5"}'

# Full solve
curl -X POST localhost:8000/api/solve -H 'Content-Type: application/json' \
  -d '{"statement":"...","sample_input":"...","sample_output":"..."}'

# Streaming solve (Server-Sent Events) — what the UI uses
curl -N -X POST localhost:8000/api/solve/stream -H 'Content-Type: application/json' -d '{...}'
```

Interactive docs at `http://localhost:8000/docs`.

---

## Security

User code is never executed in the application process. `engine/sandbox.py`
exposes a `Runner` interface with two backends:

- `LocalRlimitRunner` — fork/exec with `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`,
  `RLIMIT_NPROC` and `RLIMIT_CORE`, plus a wall-clock kill. Correct for CPU,
  memory and runaway output. **Development only.**
- `NsjailRunner` — the same limits plus private mount, PID, IPC, UTS and network
  namespaces, a read-only root and a seccomp policy. Selected automatically when
  `nsjail` is on `PATH`.

RLIMITs stop accidents; namespaces stop attacks. Production must run the second
backend, on machines that do nothing else. `docs/` has the full threat model.

---

## Testing

```bash
make test           # 74 assertions, no network required
make screenshots    # drives the real UI in Chromium and fails on console errors
```

The suite's centre of gravity is `TestVerificationCatchesBugs`, which injects a
known-bad solution — a Kadane variant that starts the running maximum at zero,
passes every friendly sample, and returns 0 for an all-negative array — and
asserts that stress testing finds the counterexample and that the result is
**not** reported as verified. If those assertions ever pass trivially, the
product's core claim has quietly stopped being true.

---

## Known limits

Worth stating plainly, because the value of this system is that it does not
overclaim:

- **Novel hard problems.** On genuinely new Div 1 E / ICPC-level problems the
  model often fails to find the intended insight. It will say so rather than
  produce a confident wrong answer, but it will not solve them.
- **Stress testing needs a brute force.** When no feasible brute force exists
  (the answer is only defined at huge n, or the problem is interactive), the
  strongest available verdict is `LIKELY`.
- **Interactive problems** are not judged at all; batch stdin/stdout cannot
  simulate a live judge. They are flagged and left unverified.
- **Generator validity.** A random generator that produces inputs violating the
  constraints yields fake counterexamples. The prompt guards against it and the
  generator is always shown to the user so it can be checked.
