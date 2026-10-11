from __future__ import annotations

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
        j = i
        while j < len(times) and times[j] < deadline:
            if not _condition(values[j], spec):
                break
            j += 1
        else:
            if times[-1] >= deadline:
                return crossing
    return None


def _evaluate_requirement(req: RequirementSpec, contract: Contract, capture: Capture, events: dict[str, float]) -> Finding:
    raw = req.raw
    if req.type == "delay":
        start, end = str(raw["from"]), str(raw["to"])
        if start not in events or end not in events:
            missing = [name for name in (start, end) if name not in events]
            return Finding(req.id, "FAIL", f"event not observed: {', '.join(missing)}")
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
    if req.type == "max_value":
        measured = max(values)
        limit = finite_float(raw["value"], field=f"{req.id}.value")
        margin = limit - measured
        return Finding(req.id, "PASS" if margin >= 0 else "FAIL", f"max({signal}) = {measured:.6g} V; limit <= {limit:.6g} V", measured, None, limit, margin, "V")
    if req.type == "min_value":
        measured = min(values)
        limit = finite_float(raw["value"], field=f"{req.id}.value")
        margin = measured - limit
        return Finding(req.id, "PASS" if margin >= 0 else "FAIL", f"min({signal}) = {measured:.6g} V; limit >= {limit:.6g} V", measured, limit, None, margin, "V")
    if req.type == "rise_time":
        nominal = contract.signals[signal].nominal
        assert nominal is not None
        low_fraction = finite_float(raw.get("low", 0.1), field=f"{req.id}.low")
        high_fraction = finite_float(raw.get("high", 0.9), field=f"{req.id}.high")
        low_time = _first_up_crossing(capture.time, values, nominal * low_fraction)
        high_time = _first_up_crossing(capture.time, values, nominal * high_fraction, after=low_time)
        if low_time is None or high_time is None:
            return Finding(req.id, "FAIL", f"{signal} did not cross required rise-time thresholds")
        measured = high_time - low_time
        limit = duration_seconds(raw["max"], field=f"{req.id}.max")
        margin = limit - measured
        return Finding(req.id, "PASS" if margin >= 0 else "FAIL", f"{signal} {low_fraction:.0%}-{high_fraction:.0%} rise time = {format_seconds(measured)}; limit <= {format_seconds(limit)}", measured, None, limit, margin, "s")
    raise PowerContractError(f"unsupported requirement type {req.type!r}")


def _first_up_crossing(times: tuple[float, ...], values: tuple[float, ...], threshold: float, after: float | None = None) -> float | None:
    for i in range(1, len(times)):
        if after is not None and times[i] < after:
            continue
        if values[i - 1] < threshold <= values[i]:
            crossing = _crossing_time(times[i - 1], values[i - 1], times[i], values[i], threshold)
            if after is None or crossing >= after:
                return crossing
    return None
