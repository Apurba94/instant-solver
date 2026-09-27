"""Provider selection.

The default is a two-tier arrangement: try retrieval from the curated corpus
first, fall back to the model. Retrieval is faster, free and more reliable when
it fires; the model handles everything else.
"""
from __future__ import annotations

import os
from typing import Optional

from ..models import Analysis, Explanation, Language, Problem
from .base import Plan, ProviderError, SolverProvider, Synthesis
from .offline import OfflineProvider, match_archetype

__all__ = [
    "Plan", "ProviderError", "SolverProvider", "Synthesis",
    "OfflineProvider", "TieredProvider", "build_provider", "match_archetype",
]


class TieredProvider:
    """Retrieval first, model second, transparently.

    Every call checks whether the corpus recognises the problem. If it does, the
    curated answer is served; otherwise the call is forwarded to the model. The
    tier that actually answered is exposed through :attr:`last_tier` so the UI
    can tell the user where the solution came from — which matters, because a
    curated solution and a freshly generated one deserve different trust.
    """

    def __init__(self, model_provider: Optional[SolverProvider] = None,
                 corpus: Optional[OfflineProvider] = None):
        self.corpus = corpus or OfflineProvider()
        self.model = model_provider
        self.last_tier = "none"

    @property
    def name(self) -> str:
        model_name = getattr(self.model, "name", "unavailable")
        return f"tiered(corpus+{model_name})"

    def _pick(self, problem: Problem):
        if self.corpus.can_handle(problem):
            self.last_tier = "corpus"
            return self.corpus
        if self.model is None:
            raise ProviderError(
                "No model provider is configured and this problem is not in the offline "
                "corpus. Set ANTHROPIC_API_KEY to solve arbitrary problems."
            )
        self.last_tier = "model"
        return self.model

    def plan(self, problem: Problem, analysis: Analysis) -> Plan:
        return self._pick(problem).plan(problem, analysis)

    def synthesize(self, problem: Problem, analysis: Analysis, plan: Plan,
                   language: Language) -> Synthesis:
        provider = self._pick(problem)
        try:
            return provider.synthesize(problem, analysis, plan, language)
        except ProviderError:
            # A corpus miss for this language (or any other refusal) must not end
            # the solve if a model is available to take over.
            if provider is self.corpus and self.model is not None:
                self.last_tier = "model"
                return self.model.synthesize(problem, analysis, plan, language)
            raise

    def repair(self, problem: Problem, analysis: Analysis, plan: Plan,
               language: Language, previous_code: str, failure_report: str) -> Synthesis:
        # Repair is always the model's job: the corpus has nothing to iterate on.
        if self.model is None:
            raise ProviderError("Repair requires a model provider.")
        self.last_tier = "model"
        return self.model.repair(problem, analysis, plan, language, previous_code, failure_report)

    def brute_force(self, problem: Problem, analysis: Analysis,
                    language: Language) -> Optional[Synthesis]:
        try:
            return self._pick(problem).brute_force(problem, analysis, language)
        except ProviderError:
            return None

    def generator(self, problem: Problem, analysis: Analysis,
                  small: bool = True) -> Optional[Synthesis]:
        try:
            return self._pick(problem).generator(problem, analysis, small)
        except ProviderError:
            return None

    def explain(self, problem: Problem, analysis: Analysis, plan: Plan,
                code: str, language: Language) -> Explanation:
        return self._pick(problem).explain(problem, analysis, plan, code, language)


def build_provider(prefer: str = "auto") -> SolverProvider:
    """Construct the provider for this deployment.

    ``auto``    corpus + model when a key is present, corpus alone otherwise
    ``offline`` corpus only — used by the test suite so CI never needs a key
    ``claude``  model only, bypassing retrieval
    """
    if prefer == "offline":
        return OfflineProvider()

    model = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from .claude import ClaudeProvider
            model = ClaudeProvider()
        except ProviderError:
            model = None

    if prefer == "claude":
        if model is None:
            raise ProviderError("ANTHROPIC_API_KEY is not set, so the model provider is unavailable.")
        return model

    return TieredProvider(model_provider=model)
