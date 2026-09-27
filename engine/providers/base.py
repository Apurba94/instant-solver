"""The reasoning provider interface.

Everything model-specific lives behind this interface so the pipeline — parse,
compile, judge, stress, explain — is identical no matter what is doing the
thinking. That matters for three reasons: the engine can be tested end to end
with no network, a self-hosted model can be dropped in for cost control, and a
future stronger model is a one-line swap rather than a rewrite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from ..models import Analysis, Explanation, Language, Problem


@dataclass
class Plan:
    """The reasoning output that precedes any code."""
    restatement: str = ""
    observations: list[str] = field(default_factory=list)
    technique: str = ""
    why_this_technique: str = ""
    algorithm_steps: list[str] = field(default_factory=list)
    time_complexity: str = ""
    space_complexity: str = ""
    fits_budget: bool = True
    risks: list[str] = field(default_factory=list)
    confidence_note: str = ""


@dataclass
class Synthesis:
    code: str
    language: Language = Language.CPP
    notes: str = ""


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce usable output."""


class SolverProvider(Protocol):
    """What the pipeline needs from a reasoner."""

    name: str

    def plan(self, problem: Problem, analysis: Analysis) -> Plan:
        """Decide the approach before writing any code."""
        ...

    def synthesize(self, problem: Problem, analysis: Analysis, plan: Plan,
                   language: Language) -> Synthesis:
        """Write a competition-grade solution implementing ``plan``."""
        ...

    def repair(self, problem: Problem, analysis: Analysis, plan: Plan,
               language: Language, previous_code: str, failure_report: str) -> Synthesis:
        """Fix a solution given concrete evidence of how it failed."""
        ...

    def brute_force(self, problem: Problem, analysis: Analysis,
                    language: Language) -> Optional[Synthesis]:
        """Write an obviously-correct slow solution for differential testing."""
        ...

    def generator(self, problem: Problem, analysis: Analysis,
                  small: bool = True) -> Optional[Synthesis]:
        """Write a random test generator (Python) for stress testing."""
        ...

    def explain(self, problem: Problem, analysis: Analysis, plan: Plan,
                code: str, language: Language) -> Explanation:
        """Explain the verified solution in depth."""
        ...
