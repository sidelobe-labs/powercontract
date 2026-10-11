from __future__ import annotations

import re

from .errors import SpecError

_DURATION_RE = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(s|ms|us|µs|ns)?\s*$", re.I)
_DURATION_SCALE = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9}


def duration_seconds(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise SpecError(f"{field} must be a duration")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        match = _DURATION_RE.match(value)
        if not match:
            raise SpecError(f"{field} has invalid duration {value!r}")
        number, unit = match.groups()
        result = float(number) * _DURATION_SCALE[(unit or "s").lower()]
    else:
        raise SpecError(f"{field} must be a duration")
    if result < 0:
        raise SpecError(f"{field} must be >= 0")
    return result


def finite_float(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise SpecError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise SpecError(f"{field} must be numeric") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise SpecError(f"{field} must be finite")
    return result


def format_seconds(seconds: float) -> str:
    absolute = abs(seconds)
    if absolute >= 1:
        return f"{seconds:.6g} s"
    if absolute >= 1e-3:
        return f"{seconds * 1e3:.6g} ms"
    if absolute >= 1e-6:
        return f"{seconds * 1e6:.6g} us"
    return f"{seconds * 1e9:.6g} ns"
