"""Claude-backed reasoning provider.

Implements :class:`SolverProvider` against the Anthropic Messages API. All
prompt text lives in :mod:`prompts`; this module is transport, parsing and
error handling only.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from ..models import Analysis, Explanation, DryRunStep, Language, Problem
from .base import Plan, ProviderError, Synthesis
from . import prompts

DEFAULT_MODEL = os.environ.get("CPSOLVE_MODEL", "claude-opus-5")
# low | medium | high | xhigh | max. Higher thinks longer and costs more per solve.
DEFAULT_EFFORT = os.environ.get("CPSOLVE_EFFORT", "high")
# Room for adaptive thinking plus the answer; streaming keeps a large cap safe
# from HTTP timeouts.
MAX_OUTPUT_TOKENS = 64000
# Server-side refusal fallback: a declined request is re-run on the model
# Anthropic recommends for that refusal category, inside the same call.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5")
_LANGUAGE_TAG = {
    Language.CPP: "cpp", Language.C: "c",
    Language.PYTHON: "python", Language.JAVA: "java",
}
_LANGUAGE_NAME = {
    Language.CPP: "C++17", Language.C: "C17",
    Language.PYTHON: "Python 3", Language.JAVA: "Java 17",
}


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------

def extract_code_block(text: str, tag: str = "") -> Optional[str]:
    """Pull source out of a fenced block, tolerating a missing language tag."""
    if tag:
        m = re.search(rf"```{re.escape(tag)}\s*\n(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).rstrip()
    m = re.search(r"```[a-zA-Z0-9+#-]*\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    # Unfenced but obviously code (models occasionally drop the fence).
    if re.search(r"^\s*#include|^\s*import |^\s*def |^\s*public class ", text, re.MULTILINE):
        return text.strip()
    return None


def extract_json_block(text: str) -> dict[str, Any]:
    """Pull a JSON object out of the response, repairing common damage."""
    candidates: list[str] = []
    m = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    if m:
        candidates.append(m.group(1))
    m = re.search(r"```\s*\n(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        candidates.append(m.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        candidates.append(brace.group(0))

    for candidate in candidates:
        for attempt in (candidate, _repair_json(candidate)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    raise ProviderError("Model response contained no parsable JSON object.")


def _repair_json(text: str) -> str:
    """Fix the two things that actually break model-emitted JSON."""
    text = re.sub(r",(\s*[}\]])", r"\1", text)          # trailing commas
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)  # comments
    return text


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


# --------------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------------

class ClaudeProvider:
    """Reasoning provider backed by the Anthropic Messages API."""

    name = "claude"

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 effort: str = DEFAULT_EFFORT, max_retries: int = 2,
                 timeout_s: float = 600.0):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("The 'anthropic' package is not installed.") from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY is not set.")
        # The SDK retries connection errors, 429 and 5xx with backoff itself.
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=key, timeout=timeout_s,
                                           max_retries=max_retries)
        self.model = model
        self.effort = effort
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    # -- transport ----------------------------------------------------------

    def _ask(self, prompt: str) -> str:
        request: dict[str, Any] = dict(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            system=prompts.SYSTEM_SOLVER,
            messages=[{"role": "user", "content": prompt}],
        )
        if self.model.startswith(_FALLBACK_MODELS):
            request.update(betas=[_FALLBACK_BETA], fallbacks="default")

        errors = self._anthropic
        try:
            with self._client.beta.messages.stream(**request) as stream:
                response = stream.get_final_message()
        except errors.AuthenticationError as exc:
            raise ProviderError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY.") from exc
        except errors.PermissionDeniedError as exc:
            raise ProviderError(f"The API key cannot use this model: {exc.message}") from exc
        except errors.NotFoundError as exc:
            raise ProviderError(f"Unknown model '{self.model}'. Check CPSOLVE_MODEL.") from exc
        except errors.BadRequestError as exc:
            raise ProviderError(f"The model API rejected the request: {exc.message}") from exc
        except errors.RateLimitError as exc:
            raise ProviderError("The model API rate limit was reached. Try again shortly.") from exc
        except errors.APIStatusError as exc:
            raise ProviderError(f"Model API error {exc.status_code}: {exc.message}") from exc
        except errors.APIConnectionError as exc:
            raise ProviderError("Could not reach the model API. Check the network connection.") from exc

        self.calls += 1
        usage = response.usage
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0

        if response.stop_reason == "refusal":
            raise ProviderError("The model declined this request.")
        if response.stop_reason == "max_tokens":
            raise ProviderError("The model's answer was cut off at the output limit.")
        return "".join(block.text for block in response.content if block.type == "text")

    # -- prompt context helpers --------------------------------------------

    @staticmethod
    def _samples_text(problem: Problem) -> str:
        if not problem.samples:
            return "(no samples were provided)"
        parts = []
        for i, s in enumerate(problem.samples, 1):
            parts.append(f"Sample {i} input:\n{s.input.rstrip()}\n\n"
                         f"Sample {i} output:\n{s.output.rstrip()}")
        return "\n\n".join(parts)

    @staticmethod
    def _constraints_text(problem: Problem) -> str:
        if not problem.constraints:
            return "(none could be parsed automatically)"
        return "; ".join(str(c) for c in problem.constraints[:12])

    # -- interface ----------------------------------------------------------

    def plan(self, problem: Problem, analysis: Analysis) -> Plan:
        budget = analysis.budget
        prompt = prompts.PLAN_TEMPLATE.format(
            statement=problem.statement,
            samples=self._samples_text(problem),
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
            constraints=self._constraints_text(problem),
            budget_reasoning=budget.reasoning if budget else "unknown",
            allowed=", ".join(budget.allowed) if budget else "unknown",
            forbidden=", ".join(budget.forbidden) if budget else "unknown",
            topics=", ".join(analysis.topics) or "none detected",
            techniques=", ".join(analysis.candidate_techniques),
            io_format=analysis.io_format,
        )
        data = extract_json_block(self._ask(prompt))
        return Plan(
            restatement=str(data.get("restatement", "")),
            observations=_as_list(data.get("observations")),
            technique=str(data.get("technique", "")),
            why_this_technique=str(data.get("why_this_technique", "")),
            algorithm_steps=_as_list(data.get("algorithm_steps")),
            time_complexity=str(data.get("time_complexity", "")),
            space_complexity=str(data.get("space_complexity", "")),
            fits_budget=bool(data.get("fits_budget", True)),
            risks=_as_list(data.get("risks")),
            confidence_note=str(data.get("confidence_note", "")),
        )

    def synthesize(self, problem: Problem, analysis: Analysis, plan: Plan,
                   language: Language) -> Synthesis:
        tag = _LANGUAGE_TAG[language]
        io_requirement = (
            "Use fast I/O: ios_base::sync_with_stdio(false); cin.tie(nullptr);"
            if language in (Language.CPP, Language.C)
            else "Use buffered I/O (sys.stdin.buffer.read / BufferedReader) — line-by-line "
                 "input() is too slow for large inputs."
        )
        multi_test = (
            "- The input contains multiple test cases. Reset every array, counter and "
            "visited marker between test cases, and make the reset cost O(n) for THIS "
            "test, never O(maxN).\n"
            if problem.multi_test else ""
        )
        prompt = prompts.SYNTHESIZE_TEMPLATE.format(
            language_name=_LANGUAGE_NAME[language],
            language_tag=tag,
            statement=problem.statement,
            samples=self._samples_text(problem),
            technique=plan.technique,
            why_this_technique=plan.why_this_technique,
            algorithm_steps="\n".join(f"  {i}. {s}" for i, s in enumerate(plan.algorithm_steps, 1)),
            time_complexity=plan.time_complexity,
            space_complexity=plan.space_complexity,
            risks="; ".join(plan.risks + analysis.pitfalls) or "none identified",
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
            max_n=f"{problem.max_n:,}" if problem.max_n else "unknown",
            io_requirement=io_requirement,
            multi_test_requirement=multi_test,
        )
        code = extract_code_block(self._ask(prompt), tag)
        if not code:
            raise ProviderError("Model returned no code block for synthesis.")
        return Synthesis(code=code, language=language)

    def repair(self, problem: Problem, analysis: Analysis, plan: Plan,
               language: Language, previous_code: str, failure_report: str) -> Synthesis:
        tag = _LANGUAGE_TAG[language]
        prompt = prompts.REPAIR_TEMPLATE.format(
            statement=problem.statement,
            language_tag=tag,
            previous_code=previous_code,
            failure_report=failure_report,
            technique=plan.technique,
            time_complexity=plan.time_complexity,
        )
        code = extract_code_block(self._ask(prompt), tag)
        if not code:
            raise ProviderError("Model returned no code block for repair.")
        return Synthesis(code=code, language=language)

    def brute_force(self, problem: Problem, analysis: Analysis,
                    language: Language) -> Optional[Synthesis]:
        tag = _LANGUAGE_TAG[language]
        prompt = prompts.BRUTE_FORCE_TEMPLATE.format(
            statement=problem.statement,
            samples=self._samples_text(problem),
            language_tag=tag,
        )
        text = self._ask(prompt)
        if "NO_BRUTE_FORCE" in text and not extract_code_block(text, tag):
            return None
        code = extract_code_block(text, tag)
        return Synthesis(code=code, language=language) if code else None

    def generator(self, problem: Problem, analysis: Analysis,
                  small: bool = True) -> Optional[Synthesis]:
        if small:
            multi_note = (
                "- The problem is multi-test: print the test count first, and keep it at 1-3."
                if problem.multi_test else ""
            )
            prompt = prompts.GENERATOR_TEMPLATE.format(
                statement=problem.statement,
                samples=self._samples_text(problem),
                constraints=self._constraints_text(problem),
                multi_test_note=multi_note,
            )
        else:
            prompt = prompts.MAX_GENERATOR_TEMPLATE.format(
                statement=problem.statement,
                constraints=self._constraints_text(problem),
            )
        text = self._ask(prompt)
        if "NO_GENERATOR" in text and not extract_code_block(text, "python"):
            return None
        code = extract_code_block(text, "python")
        return Synthesis(code=code, language=Language.PYTHON) if code else None

    def explain(self, problem: Problem, analysis: Analysis, plan: Plan,
                code: str, language: Language) -> Explanation:
        prompt = prompts.EXPLAIN_TEMPLATE.format(
            statement=problem.statement,
            samples=self._samples_text(problem),
            language_tag=_LANGUAGE_TAG[language],
            code=code,
            verification_status=analysis.summary or "verified against the provided samples",
            technique=plan.technique,
            time_complexity=plan.time_complexity,
            space_complexity=plan.space_complexity,
        )
        data = extract_json_block(self._ask(prompt))
        return Explanation(
            intuition=str(data.get("intuition", "")),
            observations=_as_list(data.get("observations")),
            approach=str(data.get("approach", "")),
            algorithm_steps=_as_list(data.get("algorithm_steps")),
            correctness=str(data.get("correctness", "")),
            time_complexity=str(data.get("time_complexity", plan.time_complexity)),
            space_complexity=str(data.get("space_complexity", plan.space_complexity)),
            complexity_justification=str(data.get("complexity_justification", "")),
            code_walkthrough=[
                {"lines": str(item.get("lines", "")), "what": str(item.get("what", ""))}
                for item in data.get("code_walkthrough", []) if isinstance(item, dict)
            ],
            dry_run=[
                DryRunStep(step=str(item.get("step", "")), state=str(item.get("state", "")))
                for item in data.get("dry_run", []) if isinstance(item, dict)
            ],
            pitfalls=_as_list(data.get("pitfalls")),
            alternatives=_as_list(data.get("alternatives")),
            related_topics=_as_list(data.get("related_topics")),
            why_this_works_here=str(data.get("why_this_works_here", "")),
        )
