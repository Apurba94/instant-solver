"""Offline / retrieval provider.

Matches a pasted problem against the curated archetype corpus and serves the
stored plan, solution, brute force, generator and editorial.

In production this runs *first*, ahead of the model: a large share of what
people paste is a standard problem in disguise, and a curated answer is faster,
cheaper and more trustworthy than re-deriving it. In development and CI it runs
*instead of* the model, which is what lets the whole pipeline — compile, judge,
stress, explain — be tested with no API key and no network.

The matcher is deliberately conservative. A wrong archetype match produces a
confidently wrong answer, which is the worst failure mode this system has, so a
weak match returns nothing and lets the model do the work.
"""
from __future__ import annotations

import re
from typing import Optional

from ..models import Analysis, DryRunStep, Explanation, Language, Problem
from .base import Plan, ProviderError, Synthesis
from .library import CORPUS, Archetype

# A match needs this many signal hits before it is trusted. Two independent
# signals is the floor; one keyword is a coincidence.
MIN_SIGNAL_HITS = 2


def match_archetype(problem: Problem) -> tuple[Optional[Archetype], float]:
    """Score the statement against every archetype and return the best match."""
    text = problem.statement.lower()
    best: Optional[Archetype] = None
    best_score = 0.0

    for arch in CORPUS:
        if arch.required and not all(re.search(p, text, re.IGNORECASE) for p in arch.required):
            continue
        hits = sum(1 for p in arch.signals if re.search(p, text, re.IGNORECASE))
        if hits < MIN_SIGNAL_HITS:
            continue
        score = hits / max(1, len(arch.signals))
        if score > best_score:
            best, best_score = arch, score

    return best, best_score


class OfflineProvider:
    """Serves stored answers for recognised archetypes."""

    name = "offline-corpus"

    def __init__(self, strict: bool = True):
        # strict=True refuses to guess. Turning it off is only for demos.
        self.strict = strict
        self._cache: dict[str, Archetype] = {}

    # -- matching ----------------------------------------------------------

    def _archetype(self, problem: Problem) -> Archetype:
        cached = self._cache.get(problem.fingerprint)
        if cached:
            return cached
        arch, score = match_archetype(problem)
        if arch is None:
            raise ProviderError(
                "This problem does not match any archetype in the offline corpus. "
                "Configure ANTHROPIC_API_KEY to solve arbitrary problems."
            )
        self._cache[problem.fingerprint] = arch
        return arch

    def can_handle(self, problem: Problem) -> bool:
        return match_archetype(problem)[0] is not None

    # -- interface ---------------------------------------------------------

    def plan(self, problem: Problem, analysis: Analysis) -> Plan:
        arch = self._archetype(problem)
        return Plan(
            restatement=f"Recognised as: {arch.title}.",
            observations=arch.explanation.get("observations", [])[:3],
            technique=arch.technique,
            why_this_technique=arch.why,
            algorithm_steps=arch.steps,
            time_complexity=arch.time_complexity,
            space_complexity=arch.space_complexity,
            fits_budget=True,
            risks=arch.risks,
            confidence_note=(
                "Matched against a curated archetype, so the approach is known-good; "
                "the implementation is still verified against your samples before being shown."
            ),
        )

    def synthesize(self, problem: Problem, analysis: Analysis, plan: Plan,
                   language: Language) -> Synthesis:
        arch = self._archetype(problem)
        if language is not Language.CPP:
            raise ProviderError(
                f"The offline corpus only stores C++ solutions; {language.value} needs a model provider."
            )
        return Synthesis(code=arch.solution_cpp, language=Language.CPP,
                         notes=f"From archetype '{arch.key}'.")

    def repair(self, problem: Problem, analysis: Analysis, plan: Plan,
               language: Language, previous_code: str, failure_report: str) -> Synthesis:
        # A stored solution that fails the samples means the MATCH was wrong, not
        # the code. Retrying the same stored code would loop forever, so stop.
        raise ProviderError(
            "The stored solution did not match this problem's samples, which means the "
            "archetype match was wrong. The offline corpus cannot repair; a model provider is needed."
        )

    def brute_force(self, problem: Problem, analysis: Analysis,
                    language: Language) -> Optional[Synthesis]:
        arch = self._archetype(problem)
        if not arch.brute_cpp:
            return None
        return Synthesis(code=arch.brute_cpp, language=Language.CPP)

    def generator(self, problem: Problem, analysis: Analysis,
                  small: bool = True) -> Optional[Synthesis]:
        if not small:
            # The corpus stores small generators only. Returning the small one for a
            # performance probe would time a tiny input and report a reassuring
            # headroom figure that means nothing — worse than reporting nothing.
            return None
        arch = self._archetype(problem)
        if not arch.generator_py:
            return None
        return Synthesis(code=arch.generator_py, language=Language.PYTHON)

    def explain(self, problem: Problem, analysis: Analysis, plan: Plan,
                code: str, language: Language) -> Explanation:
        arch = self._archetype(problem)
        data = arch.explanation
        return Explanation(
            intuition=data.get("intuition", ""),
            observations=data.get("observations", []),
            approach=data.get("approach", ""),
            algorithm_steps=data.get("algorithm_steps", []),
            correctness=data.get("correctness", ""),
            time_complexity=data.get("time_complexity", arch.time_complexity),
            space_complexity=data.get("space_complexity", arch.space_complexity),
            complexity_justification=data.get("complexity_justification", ""),
            code_walkthrough=data.get("code_walkthrough", []),
            dry_run=[DryRunStep(step=d.get("step", ""), state=d.get("state", ""))
                     for d in data.get("dry_run", [])],
            pitfalls=data.get("pitfalls", []),
            alternatives=data.get("alternatives", []),
            related_topics=data.get("related_topics", []),
            why_this_works_here=data.get("why_this_works_here", ""),
        )
