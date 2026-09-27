"""Stage 1 — Ingestion.

Turns whatever the user pasted into a structured :class:`Problem`.

People paste problems from Codeforces, AtCoder, LeetCode, CSES, a PDF, or a
teacher's Word file. The text arrives with unicode maths (``1 ≤ n ≤ 2·10^5``),
inconsistent section headings, and samples formatted five different ways. This
module's job is to be forgiving about all of that, because every later stage is
only as good as the constraints it is handed.
"""
from __future__ import annotations

import re
from typing import Optional

from .models import Constraint, Problem, Sample

# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------

_UNICODE_MATH = {
    "\u2264": "<=", "\u2265": ">=", "\u003c\u003d": "<=",
    "\u2266": "<=", "\u2267": ">=",
    "\u00b7": "*", "\u00d7": "*", "\u22c5": "*",
    "\u2212": "-", "\u2013": "-", "\u2014": "-",
    "\u00a0": " ", "\u2009": " ", "\u200b": "",
    "\u2026": "...",
    "\u2032": "'", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u221e": "INF",
}


_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹",
                             "0123456789")
_SUPERSCRIPT_RUN = re.compile(r"[⁰¹²³⁴-⁹]+")


def _fold_superscripts(text: str) -> str:
    """Rewrite ``10⁵`` as ``10^5``.

    Statements copied out of a browser carry real superscript characters, and a
    parser that ignores them silently reads ``2·10⁵`` as the number 2 — which
    then drives the entire complexity budget off a cliff.
    """
    return _SUPERSCRIPT_RUN.sub(lambda m: "^" + m.group(0).translate(_SUPERSCRIPT), text)


def normalize_text(text: str) -> str:
    """Fold unicode maths into ASCII and tidy whitespace, keeping line breaks."""
    text = _fold_superscripts(text)
    for src, dst in _UNICODE_MATH.items():
        text = text.replace(src, dst)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # LaTeX leftovers that survive copy/paste from Codeforces / Overleaf
    text = re.sub(r"\$\$?([^$]{0,120}?)\$\$?", r"\1", text)
    text = re.sub(r"\\le(?![a-z])", "<=", text)
    text = re.sub(r"\\ge(?![a-z])", ">=", text)
    text = re.sub(r"\\leq\b", "<=", text)
    text = re.sub(r"\\geq\b", ">=", text)
    text = re.sub(r"\\cdot\b", "*", text)
    text = re.sub(r"\\times\b", "*", text)
    text = re.sub(r"\\ldots\b|\\dots\b", "...", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------
# Numeric literals
# --------------------------------------------------------------------------

# A signed literal: -10^9, 2*10^5, 1e6, 200,000, 200000.
_NUM = (r"(?:-\s*)?(?:\d+\s*\*\s*10\s*\^\s*\d+|10\s*\^\s*\d+|\d+\s*e\s*\d+|\d[\d,]*)")


def parse_number(token: str) -> Optional[int]:
    """Parse ``2*10^5``, ``-10^9``, ``1e6``, ``200,000`` and ``200000``."""
    t = token.strip().replace(" ", "").replace(",", "")
    if not t:
        return None
    sign = 1
    if t.startswith("-"):
        sign, t = -1, t[1:]
    elif t.startswith("+"):
        t = t[1:]

    m = re.fullmatch(r"(\d+)\*?10\^(\d+)", t)
    if m:
        exp = int(m.group(2))
        return sign * int(m.group(1)) * (10 ** exp) if exp <= 30 else None
    m = re.fullmatch(r"10\^(\d+)", t)
    if m:
        exp = int(m.group(1))
        return sign * (10 ** exp) if exp <= 30 else None
    m = re.fullmatch(r"(\d+)e(\d+)", t, re.IGNORECASE)
    if m:
        exp = int(m.group(2))
        return sign * int(m.group(1)) * (10 ** exp) if exp <= 30 else None
    if t.isdigit():
        try:
            return sign * int(t)
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------

_SYMBOL = r"[A-Za-z][A-Za-z0-9_]{0,15}(?:_\{?[a-z0-9]{1,4}\}?)?"

# Reject words that look like symbols but are prose ("the", "of", "at most").
_STOPWORDS = {
    "the", "of", "at", "to", "is", "in", "be", "it", "or", "and", "for", "all",
    "each", "sum", "that", "this", "with", "are", "you", "your", "if", "then",
    "given", "print", "output", "input", "line", "lines", "test", "cases",
    "integer", "integers", "number", "numbers", "second", "seconds", "mb",
}


# Symbols that conventionally count things rather than measure them. Everything
# else is treated as a value bound, which is the safe default: mistaking a size
# for a value only loosens the complexity budget, while the reverse silently
# tells the solver that quadratic is fine when it is not.
_SIZE_SYMBOLS = {
    "n", "m", "q", "t", "k", "c", "nm",
    "len", "length", "size", "count", "cnt", "num",
    "nodes", "vertices", "edges", "queries", "tests", "testcases",
}


def _clean_symbol(sym: str) -> str:
    return sym.replace("{", "").replace("}", "").strip()


def classify_symbol(symbol: str) -> str:
    """Decide whether a bound describes input SIZE or an input VALUE."""
    name = _clean_symbol(symbol)
    if "_" in name:                       # a_i, x_1 — an element of a collection
        return "value"
    return "size" if name.lower() in _SIZE_SYMBOLS else "value"


def extract_constraints(text: str) -> list[Constraint]:
    """Pull every numeric bound out of the statement.

    Handles the three shapes that cover almost all real statements::

        1 <= n <= 2*10^5        (two-sided)
        n <= 10^9               (one-sided)
        n is at most 1000       (prose)
    """
    found: dict[str, Constraint] = {}

    def record(symbol: str, lo: Optional[int], hi: Optional[int], raw: str) -> None:
        symbol = _clean_symbol(symbol)
        if not symbol or symbol.lower() in _STOPWORDS:
            return
        if hi is None and lo is None:
            return
        existing = found.get(symbol)
        if existing is None:
            found[symbol] = Constraint(symbol=symbol, lo=lo, hi=hi, raw=raw,
                                       kind=classify_symbol(symbol))
            return
        # Keep the tightest information we have seen for this symbol.
        if hi is not None and (existing.hi is None or hi > existing.hi):
            existing.hi = hi
        if lo is not None and (existing.lo is None or lo < existing.lo):
            existing.lo = lo

    # two-sided: 1 <= n <= 200000
    for m in re.finditer(rf"({_NUM})\s*<=\s*({_SYMBOL})\s*<=\s*({_NUM})", text):
        record(m.group(2), parse_number(m.group(1)), parse_number(m.group(3)), m.group(0))

    # one-sided: n <= 200000
    for m in re.finditer(rf"({_SYMBOL})\s*<=\s*({_NUM})", text):
        record(m.group(1), None, parse_number(m.group(2)), m.group(0))

    # reversed: 200000 >= n
    for m in re.finditer(rf"({_NUM})\s*>=\s*({_SYMBOL})", text):
        record(m.group(2), None, parse_number(m.group(1)), m.group(0))

    # one-sided lower: n >= 1
    for m in re.finditer(rf"({_SYMBOL})\s*>=\s*({_NUM})", text):
        record(m.group(1), parse_number(m.group(2)), None, m.group(0))

    # prose: "n is at most 1000", "n does not exceed 10^9", "n up to 1e6"
    prose = rf"({_SYMBOL})\s+(?:is\s+)?(?:at most|no more than|does not exceed|doesn't exceed|up to)\s+({_NUM})"
    for m in re.finditer(prose, text, re.IGNORECASE):
        record(m.group(1), None, parse_number(m.group(2)), m.group(0))

    # Size bounds first — they are what a reader (and the budget) cares about most.
    return sorted(found.values(), key=lambda c: (c.kind != "size", -(c.hi or 0), c.symbol))


# --------------------------------------------------------------------------
# Limits
# --------------------------------------------------------------------------

def extract_time_limit_ms(text: str, default: int = 2000) -> int:
    m = re.search(r"time\s*limit[^0-9]{0,20}(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|seconds?)",
                  text, re.IGNORECASE)
    if not m:
        return default
    value = float(m.group(1))
    unit = m.group(2).lower()
    ms = value if unit.startswith("m") else value * 1000
    return max(100, min(int(ms), 60_000))


def extract_memory_limit_mb(text: str, default: int = 256) -> int:
    m = re.search(r"memory\s*limit[^0-9]{0,20}(\d+(?:\.\d+)?)\s*(mb|megabytes?|gb|gigabytes?|kb)",
                  text, re.IGNORECASE)
    if not m:
        return default
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("g"):
        value *= 1024
    elif unit.startswith("k"):
        value /= 1024
    return max(16, min(int(value), 4096))


# --------------------------------------------------------------------------
# Samples
# --------------------------------------------------------------------------

_SAMPLE_IN = r"(?:sample\s*)?input(?:\s*(?:data|#)?\s*\d*)?\s*:?"
_SAMPLE_OUT = r"(?:sample\s*)?output(?:\s*(?:data|#)?\s*\d*)?\s*:?"


def extract_samples(text: str) -> list[Sample]:
    """Find ``Input ... Output ...`` blocks in the statement body.

    Only used when the user has not filled the dedicated sample boxes in the UI.
    Statement-embedded samples are inherently ambiguous, so the caller should
    always prefer explicitly supplied ones.
    """
    samples: list[Sample] = []
    pattern = re.compile(
        rf"^\s*{_SAMPLE_IN}\s*\n(?P<in>.*?)\n\s*{_SAMPLE_OUT}\s*\n(?P<out>.*?)"
        rf"(?=\n\s*(?:{_SAMPLE_IN}|note|explanation|constraints?)\b|\Z)",
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    for m in pattern.finditer(text):
        inp, out = m.group("in").strip(), m.group("out").strip()
        if inp and out:
            samples.append(Sample(input=inp + "\n", output=out + "\n"))
    return samples


# --------------------------------------------------------------------------
# Shape detection
# --------------------------------------------------------------------------

_MULTI_TEST_PATTERNS = [
    r"number of test\s*cases",
    r"first line contains (?:a single |one |an )?integer\s+t\b",
    r"\bt\s*test\s*cases",
    r"each test (?:case )?consists",
    r"for each test case",
]

_FLOAT_PATTERNS = [
    r"absolute or relative error",
    r"with (?:an )?error (?:of )?(?:at most|not exceeding|less than)",
    r"decimal places",
    r"real number",
    r"floating[- ]point",
    r"10\^\s*-\s*\d",
]

_INTERACTIVE_PATTERNS = [
    r"\binteractive problem\b",
    r"\bflush the output\b",
    r"fflush\(stdout\)",
    r"after (?:printing|each) (?:a )?query",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def guess_title(text: str) -> str:
    """Take the first short, non-boilerplate line as the title."""
    for line in text.split("\n"):
        line = line.strip().strip("#").strip()
        if not line:
            continue
        if re.match(r"^(time|memory)\s*limit", line, re.IGNORECASE):
            continue
        if len(line) <= 90 and not line.endswith("."):
            return line[:90]
        return (line[:70].rsplit(" ", 1)[0] + "...") if len(line) > 70 else line
    return "Untitled Problem"


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def ingest(
    raw_statement: str,
    sample_input: str = "",
    sample_output: str = "",
    title: str = "",
    time_limit_ms: Optional[int] = None,
    memory_limit_mb: Optional[int] = None,
    source: str = "",
) -> Problem:
    """Build a :class:`Problem` from user input.

    ``sample_input``/``sample_output`` are the dedicated UI boxes. When they are
    filled they win outright over anything scraped from the statement body,
    because an explicit sample is ground truth and a scraped one is a guess.
    """
    text = normalize_text(raw_statement)
    if not text:
        raise ValueError("Empty problem statement.")

    samples: list[Sample] = []
    if sample_input.strip() and sample_output.strip():
        samples.append(Sample(
            input=sample_input.replace("\r\n", "\n").strip() + "\n",
            output=sample_output.replace("\r\n", "\n").strip() + "\n",
        ))
    else:
        samples = extract_samples(text)

    problem = Problem(
        statement=text,
        title=(title.strip() or guess_title(text)),
        samples=samples,
        time_limit_ms=time_limit_ms or extract_time_limit_ms(text),
        memory_limit_mb=memory_limit_mb or extract_memory_limit_mb(text),
        constraints=extract_constraints(text),
        source=source,
        multi_test=_matches_any(text, _MULTI_TEST_PATTERNS),
        interactive=_matches_any(text, _INTERACTIVE_PATTERNS),
        output_is_float=_matches_any(text, _FLOAT_PATTERNS),
    )
    return problem
