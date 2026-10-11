from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from .errors import PowerContractError
from .model import Capture, Contract, EventSpec, Finding, RequirementSpec
from .units import duration_seconds, finite_float, format_seconds


@dataclass(frozen=True)
class Evaluation:
    findings: tuple[Finding, ...]
    events: dict[str, float]

    @property
    def passed(self) -> bool:
        return all(f.status == "PASS" for f in self.findings)


def evaluate(contract: Contract, capture: Capture) -> Evaluation:
    events: dict[str, float] = {}
    for name, spec in contract.events.items():
        event_time = _find_event(capture, spec)
        if event_time is not None:
            events[name] = event_time

    findings = tuple(_evaluate_requirement(req, contract, capture, events) for req in contract.requirements)
    return Evaluation(findings, events)


def _condition(value: float, spec: EventSpec) -> bool:
    return value >= spec.threshold if spec.direction == "above" else value <= spec.threshold


def _crossing_time(t0: float, v0: float, t1: float, v1: float, threshold: float) -> float:
    if v1 == v0:
        return t1
    ratio = (threshold - v0) / (v1 - v0)
    ratio = min(1.0, max(0.0, ratio))
    return t0 + ratio * (t1 - t0)


def _find_event(capture: Capture, spec: EventSpec) -> float | None:
    values = capture.signals[spec.signal]
    times = capture.time
    for i in range(1, len(times)):
        before = _condition(values[i - 1], spec)
        after = _condition(values[i], spec)
        if before or not after:
            continue
        crossing = _crossing_time(times[i - 1], values[i - 1], times[i], values[i], spec.threshold)
        if spec.stable_for == 0:
            return crossing

        deadline = crossing + spec.stable_for
        if times[-1] < deadline:
            continue
        exit_time = _next_condition_exit(times, values, spec, start_index=i)
        if exit_time is None or exit_time >= deadline:
            return crossing
    return None


def _next_condition_exit(
    times: tuple[float, ...],
    values: tuple[float, ...],
    spec: EventSpec,
    *,
    start_index: int,
) -> float | None:
    for i in range(start_index + 1, len(times)):
        before = _condition(values[i - 1], spec)
        after = _condition(values[i], spec)
        if before and not after:
            return _crossing_time(times[i - 1], values[i - 1], times[i], values[i], spec.threshold)
    return None


def _evaluate_requirement(req: RequirementSpec, contract: Contract, capture: Capture, events: dict[str, float]) -> Finding:
    raw = req.raw
    if req.type == "delay":
        start, end = str(raw["from"]), str(raw["to"])
        if start not in events or end not in events:
            return _missing_event_finding(req.id, [name for name in (start, end) if name not in events])
        measured = events[end] - events[start]
        minimum = duration_seconds(raw["min"], field=f"{req.id}.min") if "min" in raw else None
        maximum = duration_seconds(raw["max"], field=f"{req.id}.max") if "max" in raw else None
        failures: list[str] = []
        margins: list[float] = []
        if minimum is not None:
            margins.append(measured - minimum)
            if measured < minimum:
                failures.append(f"below minimum {format_seconds(minimum)}")
        if maximum is not None:
            margins.append(maximum - measured)
            if measured > maximum:
                failures.append(f"above maximum {format_seconds(maximum)}")
        margin = min(margins) if margins else None
        status = "FAIL" if failures else "PASS"
        summary = f"{end} - {start} = {format_seconds(measured)}"
        if failures:
            summary += f" ({'; '.join(failures)})"
        return Finding(req.id, status, summary, measured, minimum, maximum, margin, "s")

    signal = str(raw["signal"])
    values = capture.signals[signal]
    if req.type in {"max_value", "min_value"}:
        window = _measurement_window(req, capture, events)
        if isinstance(window, Finding):
            return window
        start, end, label = window
        measured_values = _values_in_window(capture.time, values, start, end)
        measured = max(measured_values) if req.type == "max_value" else min(measured_values)
        limit = finite_float(raw["value"], field=f"{req.id}.value")
        if req.type == "max_value":
            margin = limit - measured
            summary = f"max({signal}{label}) = {measured:.6g} V; limit <= {limit:.6g} V"
            return Finding(req.id, "PASS" if margin >= 0 else "FAIL", summary, measured, None, limit, margin, "V")
        margin = measured - limit
        summary = f"min({signal}{label}) = {measured:.6g} V; limit >= {limit:.6g} V"
        return Finding(req.id, "PASS" if margin >= 0 else "FAIL", summary, measured, limit, None, margin, "V")

    if req.type in {"rise_time", "fall_time"}:
        nominal = contract.signals[signal].nominal
        assert nominal is not None
        low_fraction = finite_float(raw.get("low", 0.1), field=f"{req.id}.low")
        high_fraction = finite_float(raw.get("high", 0.9), field=f"{req.id}.high")
        if req.type == "rise_time":
            start_time = _first_up_crossing(capture.time, values, nominal * low_fraction)
            end_time = _first_up_crossing(capture.time, values, nominal * high_fraction, after=start_time)
            transition = f"{low_fraction:.0%}-{high_fraction:.0%} rise time"
        else:
            start_time = _first_down_crossing(capture.time, values, nominal * high_fraction)
            end_time = _first_down_crossing(capture.time, values, nominal * low_fraction, after=start_time)
            transition = f"{high_fraction:.0%}-{low_fraction:.0%} fall time"
        if start_time is None or end_time is None:
            return Finding(req.id, "FAIL", f"{signal} did not cross required {req.type.replace('_', '-')} thresholds")
        measured = end_time - start_time
        limit = duration_seconds(raw["max"], field=f"{req.id}.max")
        margin = limit - measured
        return Finding(
            req.id,
            "PASS" if margin >= 0 else "FAIL",
            f"{signal} {transition} = {format_seconds(measured)}; limit <= {format_seconds(limit)}",
            measured,
            None,
            limit,
            margin,
            "s",
        )
    raise PowerContractError(f"unsupported requirement type {req.type!r}")


def _missing_event_finding(requirement_id: str, missing: list[str]) -> Finding:
    return Finding(requirement_id, "FAIL", f"event not observed: {', '.join(missing)}")


def _measurement_window(
    req: RequirementSpec,
    capture: Capture,
    events: dict[str, float],
) -> tuple[float, float, str] | Finding:
    raw = req.raw
    from_name = str(raw["from"]) if "from" in raw else None
    to_name = str(raw["to"]) if "to" in raw else None
    missing = [name for name in (from_name, to_name) if name is not None and name not in events]
    if missing:
        return _missing_event_finding(req.id, missing)

    start = events[from_name] if from_name is not None else capture.time[0]
    end = events[to_name] if to_name is not None else capture.time[-1]
    if start > end:
        return Finding(req.id, "FAIL", f"measurement window is reversed: {from_name} occurs after {to_name}")

    if from_name is None and to_name is None:
        label = ""
    elif from_name is None:
        label = f", start..{to_name}"
    elif to_name is None:
        label = f", {from_name}..end"
    else:
        label = f", {from_name}..{to_name}"
    return start, end, label


def _values_in_window(
    times: tuple[float, ...],
    values: tuple[float, ...],
    start: float,
    end: float,
) -> tuple[float, ...]:
    if start == end:
        return (_value_at(times, values, start),)
    result = [_value_at(times, values, start)]
    result.extend(value for time, value in zip(times, values) if start < time < end)
    result.append(_value_at(times, values, end))
    return tuple(result)


def _value_at(times: tuple[float, ...], values: tuple[float, ...], time: float) -> float:
    if time <= times[0]:
        return values[0]
    if time >= times[-1]:
        return values[-1]
    right = bisect_right(times, time)
    left = right - 1
    if times[left] == time:
        return values[left]
    t0, t1 = times[left], times[right]
    v0, v1 = values[left], values[right]
    fraction = (time - t0) / (t1 - t0)
    return v0 + fraction * (v1 - v0)


def _first_up_crossing(
    times: tuple[float, ...],
    values: tuple[float, ...],
    threshold: float,
    after: float | None = None,
) -> float | None:
    for i in range(1, len(times)):
        if after is not None and times[i] < after:
            continue
        if values[i - 1] < threshold <= values[i]:
            crossing = _crossing_time(times[i - 1], values[i - 1], times[i], values[i], threshold)
            if after is None or crossing >= after:
                return crossing
    return None


def _first_down_crossing(
    times: tuple[float, ...],
    values: tuple[float, ...],
    threshold: float,
    after: float | None = None,
) -> float | None:
    for i in range(1, len(times)):
        if after is not None and times[i] < after:
            continue
        if values[i - 1] > threshold >= values[i]:
            crossing = _crossing_time(times[i - 1], values[i - 1], times[i], values[i], threshold)
            if after is None or crossing >= after:
                return crossing
    return None
