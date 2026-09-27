"""Instant Solver engine.

Public surface:

    from engine import Solver, SolveConfig, ingest
    result = Solver().solve_text(statement, sample_input, sample_output)
"""
from .ingest import ingest
from .models import (
    Analysis, Attempt, Confidence, Explanation, Language, Problem, Sample,
    SolveResult, Stage, Verdict,
)
from .pipeline import SolveConfig, Solver
from .providers import build_provider

__all__ = [
    "Solver", "SolveConfig", "ingest", "build_provider",
    "Problem", "Sample", "Analysis", "Attempt", "Explanation", "SolveResult",
    "Confidence", "Language", "Stage", "Verdict",
]

__version__ = "0.1.0"
