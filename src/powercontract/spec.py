from __future__ import annotations

from pathlib import Path

import yaml

from .errors import SpecError
from .model import Contract, EventSpec, RequirementSpec, SignalSpec
from .units import duration_seconds, finite_float

_SUPPORTED_REQUIREMENTS = {"delay", "max_value", "min_value", "rise_time", "fall_time"}

_ROOT_KEYS = {"version", "capture", "signals", "events", "requirements"}
_CAPTURE_KEYS = {"time_column"}
_SIGNAL_KEYS = {"column", "nominal"}
_EVENT_KEYS = {"signal", "direction", "threshold", "stable_for"}
_REQUIREMENT_KEYS = {
    "delay": {"id", "type", "from", "to", "min", "max", "uncertainty"},
    "max_value": {"id", "type", "signal", "value", "from", "to", "uncertainty"},
    "min_value": {"id", "type", "signal", "value", "from", "to", "uncertainty"},
    "rise_time": {"id", "type", "signal", "low", "high", "max", "uncertainty"},
    "fall_time": {"id", "type", "signal", "low", "high", "max", "uncertainty"},
}


def load_contract(path: str | Path) -> Contract:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SpecError(f"cannot read contract: {exc}") from exc
    except yaml.YAMLError as exc:
        raise SpecError(f"invalid YAML: {exc}") from exc
    return parse_contract(data)


def parse_contract(data: object) -> Contract:
    if not isinstance(data, dict):
        raise SpecError("contract root must be a mapping")
    _reject_unknown_keys(data, _ROOT_KEYS, "contract")
    if data.get("version") != 1:
        raise SpecError("contract version must be 1")

    capture = _mapping(data.get("capture"), "capture")
    _reject_unknown_keys(capture, _CAPTURE_KEYS, "capture")
    time_column = capture.get("time_column", "Time")
    if not isinstance(time_column, str) or not time_column:
        raise SpecError("capture.time_column must be a non-empty string")

    signal_map = _mapping(data.get("signals"), "signals")
    if not signal_map:
        raise SpecError("signals must not be empty")
    signals: dict[str, SignalSpec] = {}
    for name, raw in signal_map.items():
        if not isinstance(name, str) or not name:
            raise SpecError("signal names must be non-empty strings")
        item = _mapping(raw, f"signals.{name}")
        _reject_unknown_keys(item, _SIGNAL_KEYS, f"signals.{name}")
        column = item.get("column")
        if not isinstance(column, str) or not column:
            raise SpecError(f"signals.{name}.column must be a non-empty string")
        nominal_raw = item.get("nominal")
        nominal = None if nominal_raw is None else finite_float(nominal_raw, field=f"signals.{name}.nominal")
        if nominal is not None and nominal <= 0:
            raise SpecError(f"signals.{name}.nominal must be > 0")
        signals[name] = SignalSpec(name=name, column=column, nominal=nominal)

    events: dict[str, EventSpec] = {}
    for name, raw in _mapping(data.get("events", {}), "events").items():
        if not isinstance(name, str) or not name:
            raise SpecError("event names must be non-empty strings")
        item = _mapping(raw, f"events.{name}")
        _reject_unknown_keys(item, _EVENT_KEYS, f"events.{name}")
        signal = item.get("signal")
        if signal not in signals:
            raise SpecError(f"events.{name}.signal refers to unknown signal {signal!r}")
        direction = item.get("direction")
        if direction not in ("above", "below"):
            raise SpecError(f"events.{name}.direction must be 'above' or 'below'")
        events[name] = EventSpec(
            name=name,
            signal=str(signal),
            direction=direction,
            threshold=finite_float(item.get("threshold"), field=f"events.{name}.threshold"),
            stable_for=duration_seconds(item.get("stable_for", 0), field=f"events.{name}.stable_for"),
        )

    raw_requirements = data.get("requirements")
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise SpecError("requirements must be a non-empty list")
    requirements: list[RequirementSpec] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_requirements):
        item = _mapping(raw, f"requirements[{index}]")
        req_id = item.get("id")
        req_type = item.get("type")
        if not isinstance(req_id, str) or not req_id:
            raise SpecError(f"requirements[{index}].id must be a non-empty string")
        if req_id in seen:
            raise SpecError(f"duplicate requirement id {req_id!r}")
        seen.add(req_id)
        if req_type not in _SUPPORTED_REQUIREMENTS:
            raise SpecError(f"requirement {req_id!r} has unsupported type {req_type!r}")
        req_type = str(req_type)
        _reject_unknown_keys(item, _REQUIREMENT_KEYS[req_type], f"requirement {req_id!r}")
        _validate_requirement(req_id, req_type, item, signals, events)
        requirements.append(RequirementSpec(req_id, req_type, dict(item)))

    return Contract(time_column, signals, events, tuple(requirements))


def _mapping(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise SpecError(f"{field} must be a mapping")
    return value


def _reject_unknown_keys(item: dict, allowed: set[str], field: str) -> None:
    unknown = sorted(str(key) for key in item.keys() if key not in allowed)
    if unknown:
        raise SpecError(f"{field} has unknown field(s): {', '.join(unknown)}")


def _validate_requirement(req_id: str, req_type: str, item: dict, signals: dict, events: dict) -> None:
    if req_type == "delay":
        start, end = item.get("from"), item.get("to")
        if start not in events or end not in events:
            raise SpecError(f"{req_id}: delay requires existing 'from' and 'to' events")
        if "min" not in item and "max" not in item:
            raise SpecError(f"{req_id}: delay requires min and/or max")
        minimum = duration_seconds(item["min"], field=f"{req_id}.min") if "min" in item else None
        maximum = duration_seconds(item["max"], field=f"{req_id}.max") if "max" in item else None
        if minimum is not None and maximum is not None and minimum > maximum:
            raise SpecError(f"{req_id}: min must be <= max")
        if "uncertainty" in item:
            duration_seconds(item["uncertainty"], field=f"{req_id}.uncertainty")
    elif req_type in {"max_value", "min_value"}:
        if item.get("signal") not in signals:
            raise SpecError(f"{req_id}: unknown signal {item.get('signal')!r}")
        finite_float(item.get("value"), field=f"{req_id}.value")
        if "uncertainty" in item:
            uncertainty = finite_float(item["uncertainty"], field=f"{req_id}.uncertainty")
            if uncertainty < 0:
                raise SpecError(f"{req_id}.uncertainty must be >= 0")
        _validate_optional_event(req_id, "from", item, events)
        _validate_optional_event(req_id, "to", item, events)
    elif req_type in {"rise_time", "fall_time"}:
        signal = item.get("signal")
        if signal not in signals:
            raise SpecError(f"{req_id}: unknown signal {signal!r}")
        if signals[signal].nominal is None:
            raise SpecError(f"{req_id}: {req_type} requires signals.{signal}.nominal")
        low = finite_float(item.get("low", 0.1), field=f"{req_id}.low")
        high = finite_float(item.get("high", 0.9), field=f"{req_id}.high")
        if not (0 <= low < high <= 1):
            raise SpecError(f"{req_id}: low/high must satisfy 0 <= low < high <= 1")
        if "max" not in item:
            raise SpecError(f"{req_id}: {req_type} requires max")
        duration_seconds(item["max"], field=f"{req_id}.max")
        if "uncertainty" in item:
            duration_seconds(item["uncertainty"], field=f"{req_id}.uncertainty")


def _validate_optional_event(req_id: str, key: str, item: dict, events: dict) -> None:
    if key in item and item[key] not in events:
        raise SpecError(f"{req_id}: {key} refers to unknown event {item[key]!r}")
