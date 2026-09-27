"""Output comparison.

A judge that only does ``expected == actual`` rejects correct solutions over a
trailing newline and accepts wrong ones that print ``0.30000000000000004``.
This module implements the comparison rules real judges use, and — just as
importantly — explains *why* two outputs differ, because that explanation is
what the repair loop feeds back to the synthesiser.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

DEFAULT_EPS = 1e-6
_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_YES_NO = {"yes", "no", "true", "false", "possible", "impossible"}


@dataclass
class CheckOutcome:
    ok: bool
    hint: str = ""
    first_bad_token: Optional[int] = None


def tokenize(text: str) -> list[str]:
    return text.split()


def _is_number(token: str) -> bool:
    return bool(_NUMBER.match(token))


def _numbers_match(a: str, b: str, eps: float) -> bool:
    try:
        x, y = float(a), float(b)
    except ValueError:
        return False
    if math.isnan(x) or math.isnan(y):
        return False
    if x == y:
        return True
    if math.isinf(x) or math.isinf(y):
        return False
    # Judges accept a token when EITHER the absolute or the relative error is
    # inside the tolerance, which is what lets 1e9-scale answers pass.
    return abs(x - y) <= eps or abs(x - y) <= eps * max(abs(x), abs(y))


def compare(expected: str, actual: str, *, float_mode: bool = False,
            eps: float = DEFAULT_EPS) -> CheckOutcome:
    """Compare two outputs the way an online judge does.

    Whitespace between tokens is irrelevant, numeric tokens compare with a
    tolerance in float mode, and yes/no answers compare case-insensitively
    (statements almost always say "you may print it in any case").
    """
    exp_tokens, act_tokens = tokenize(expected), tokenize(actual)

    if not act_tokens and exp_tokens:
        return CheckOutcome(False, "Your program printed nothing, but the expected "
                                   f"output has {len(exp_tokens)} token(s).")

    if len(exp_tokens) != len(act_tokens):
        return CheckOutcome(
            False,
            f"Token count differs: expected {len(exp_tokens)}, got {len(act_tokens)}. "
            + _shape_hint(expected, actual),
        )

    for i, (e, a) in enumerate(zip(exp_tokens, act_tokens)):
        if e == a:
            continue
        if e.lower() in _YES_NO and a.lower() in _YES_NO:
            if e.lower() == a.lower():
                continue
            return CheckOutcome(False, f"Token {i + 1}: expected '{e}', got '{a}'.", i)
        if _is_number(e) and _is_number(a):
            if float_mode or ("." in e or "." in a or "e" in e.lower() or "e" in a.lower()):
                if _numbers_match(e, a, eps):
                    continue
                return CheckOutcome(
                    False,
                    f"Token {i + 1} is numerically wrong: expected {e}, got {a} "
                    f"(difference {abs(float(e) - float(a)):.6g}, tolerance {eps:g}).",
                    i,
                )
            return CheckOutcome(False, f"Token {i + 1}: expected {e}, got {a}.", i)
        return CheckOutcome(False, f"Token {i + 1}: expected '{e}', got '{a}'.", i)

    return CheckOutcome(True)


def _shape_hint(expected: str, actual: str) -> str:
    """Explain a length mismatch in terms a programmer can act on."""
    exp_lines = [ln for ln in expected.strip().split("\n") if ln.strip()]
    act_lines = [ln for ln in actual.strip().split("\n") if ln.strip()]
    if len(exp_lines) != len(act_lines):
        return (f"Expected {len(exp_lines)} non-empty line(s), got {len(act_lines)} — "
                "check whether the answer for every test case (or query) is being printed.")
    return "The values are on the right number of lines, so a field is missing or extra."


def diff_preview(expected: str, actual: str, max_lines: int = 12) -> str:
    """A short side-by-side of the first divergence, for the UI and the log."""
    exp_lines = expected.strip().split("\n")
    act_lines = actual.strip().split("\n")
    out: list[str] = []
    for i in range(max(len(exp_lines), len(act_lines))):
        e = exp_lines[i] if i < len(exp_lines) else "<missing>"
        a = act_lines[i] if i < len(act_lines) else "<missing>"
        mark = " " if e.split() == a.split() else ">"
        out.append(f"{mark} line {i + 1:>3} | expected: {e[:60]:<60} | got: {a[:60]}")
        if len(out) >= max_lines:
            out.append(f"  ... ({max(len(exp_lines), len(act_lines)) - max_lines} more lines)")
            break
    return "\n".join(out)
