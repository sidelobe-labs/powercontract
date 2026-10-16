from __future__ import annotations

import csv
from math import isclose, isfinite
from pathlib import Path

from .errors import CaptureError
from .model import Capture, Contract


def load_capture(
    path: str | Path,
    contract: Contract,
    additional_paths: list[str | Path] | None = None,
) -> Capture:
    paths = [Path(path), *(Path(p) for p in (additional_paths or []))]
    if len(paths) > 1:
        if all(_looks_like_siglent_csv(_read_lines(path)) for path in paths):
            return _load_siglent_group(paths, contract)
        raise CaptureError(
            "multi-file capture groups currently require Siglent per-channel CSV; "
            "use a single multi-channel CSV for other formats"
        )

    path = paths[0]
    lines = _read_lines(path)
    if _looks_like_siglent_csv(lines):
        return _load_siglent_group(paths, contract)
    if _looks_like_rigol_sequence_csv(lines):
        return _load_rigol_sequence_csv(lines, contract, path)
    if _looks_like_paired_xy_csv(lines):
        return _load_paired_xy_csv(lines, contract, path)
    if _looks_like_source_units_csv(lines):
        return _load_source_units_csv(lines, contract, path)
    if _looks_like_legacy_metadata_xy_csv(lines):
        return _load_legacy_metadata_xy_csv(lines, contract, path)
    return _load_table_csv(lines, contract)


def _read_lines(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise CaptureError(f"cannot read capture {path}: {exc}") from exc
    if not lines:
        raise CaptureError(f"capture {path} is empty")
    return lines


def _load_table_csv(lines: list[str], contract: Contract) -> Capture:
    expected = {contract.time_column, *(s.column for s in contract.signals.values())}
    header_index, delimiter = _find_header(lines, expected)
    reader = csv.DictReader(lines[header_index:], delimiter=delimiter)
    if reader.fieldnames is None:
        raise CaptureError("capture has no header")
    reader.fieldnames = [field.strip().strip('"') for field in reader.fieldnames]
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise CaptureError("capture has duplicate column names")
    missing = expected.difference(reader.fieldnames)
    if missing:
        raise CaptureError(f"capture is missing columns: {', '.join(sorted(missing))}")

    times: list[float] = []
    signal_values: dict[str, list[float]] = {name: [] for name in contract.signals}
    for row_number, row in enumerate(reader, start=header_index + 2):
        if None in row:
            raise CaptureError(f"row {row_number} has more fields than the CSV header")
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            t = float(row[contract.time_column])
            values = {name: float(row[signal.column]) for name, signal in contract.signals.items()}
        except (TypeError, ValueError) as exc:
            raise CaptureError(f"row {row_number} contains non-numeric waveform data") from exc
        _validate_sample_row(t, values.values(), row_number)
        if times and t <= times[-1]:
            raise CaptureError(f"time must be strictly increasing (row {row_number})")
        times.append(t)
        for name, value in values.items():
            signal_values[name].append(value)

    if len(times) < 2:
        raise CaptureError("capture needs at least two samples")
    return Capture(tuple(times), {name: tuple(values) for name, values in signal_values.items()})



def _row(line: str) -> list[str]:
    fields = [field.strip().strip('"') for field in next(csv.reader([line]))]
    while fields and not fields[-1]:
        fields.pop()
    return fields


def _looks_like_rigol_sequence_csv(lines: list[str]) -> bool:
    if len(lines) < 3:
        return False
    names = _row(lines[0])
    units = _row(lines[1])
    return (
        len(names) >= 4
        and len(units) >= len(names) - 1
        and names[0].lower() == "x"
        and "Start" in names
        and "Increment" in names
        and units[0].lower() == "sequence"
    )


def _load_rigol_sequence_csv(lines: list[str], contract: Contract, path: Path) -> Capture:
    names = _row(lines[0])
    units = _row(lines[1])
    start_index = names.index("Start")
    increment_index = names.index("Increment")
    source_names = names[1:start_index]
    if not source_names:
        raise CaptureError(f"{path}: Rigol CSV contains no analog sources")
    if len(set(source_names)) != len(source_names):
        raise CaptureError(f"{path}: Rigol CSV contains duplicate source names")
    if any(units[index].lower() not in {"volt", "v"} for index in range(1, start_index)):
        raise CaptureError(f"{path}: Rigol CSV analog sources must be in volts")

    expected = {signal.column for signal in contract.signals.values()}
    missing = expected.difference(source_names)
    if missing:
        raise CaptureError(f"{path}: Rigol CSV is missing source(s): {', '.join(sorted(missing))}")

    try:
        start = float(units[start_index])
        increment = float(units[increment_index])
    except (IndexError, ValueError) as exc:
        raise CaptureError(f"{path}: Rigol CSV has invalid Start/Increment metadata") from exc
    if not isfinite(start) or not isfinite(increment) or increment <= 0:
        raise CaptureError(f"{path}: Rigol Start/Increment must be finite and increment > 0")

    source_positions = {name: names.index(name) for name in expected}
    times: list[float] = []
    signal_values: dict[str, list[float]] = {name: [] for name in contract.signals}
    for row_number, line in enumerate(lines[2:], start=3):
        fields = _row(line)
        if not fields or not any(fields):
            continue
        try:
            sequence = float(fields[0])
            t = start + sequence * increment
            values = {
                name: float(fields[source_positions[signal.column]])
                for name, signal in contract.signals.items()
            }
        except (IndexError, ValueError) as exc:
            raise CaptureError(f"{path}: row {row_number} contains invalid Rigol waveform data") from exc
        _validate_sample_row(t, values.values(), row_number, path)
        if times and t <= times[-1]:
            raise CaptureError(f"{path}: derived time must be strictly increasing (row {row_number})")
        times.append(t)
        for name, value in values.items():
            signal_values[name].append(value)

    if len(times) < 2:
        raise CaptureError(f"{path}: capture needs at least two samples")
    return Capture(tuple(times), {name: tuple(values) for name, values in signal_values.items()})


def _looks_like_source_units_csv(lines: list[str]) -> bool:
    if len(lines) < 3:
        return False
    names = _row(lines[0])
    units = _row(lines[1])
    if len(names) < 2 or len(units) < len(names):
        return False
    return (
        names[0].lower() in {"source", "x-axis", "x", "time"}
        and units[0].lower() in {"second", "seconds", "s"}
        and all(unit.lower() in {"volt", "volts", "v"} for unit in units[1:len(names)])
    )


def _load_source_units_csv(lines: list[str], contract: Contract, path: Path) -> Capture:
    names = _row(lines[0])
    source_names = names[1:]
    if len(set(source_names)) != len(source_names):
        raise CaptureError(f"{path}: capture contains duplicate source names")
    expected = {signal.column for signal in contract.signals.values()}
    missing = expected.difference(source_names)
    if missing:
        raise CaptureError(f"{path}: capture is missing source(s): {', '.join(sorted(missing))}")

    positions = {source: source_names.index(source) + 1 for source in expected}
    times: list[float] = []
    signal_values: dict[str, list[float]] = {name: [] for name in contract.signals}
    for row_number, line in enumerate(lines[2:], start=3):
        fields = _row(line)
        if not fields or not any(fields):
            continue
        try:
            t = float(fields[0])
            values = {
                name: float(fields[positions[signal.column]])
                for name, signal in contract.signals.items()
            }
        except (IndexError, ValueError) as exc:
            raise CaptureError(f"{path}: row {row_number} contains invalid waveform data") from exc
        _validate_sample_row(t, values.values(), row_number, path)
        if times and t <= times[-1]:
            raise CaptureError(f"{path}: time must be strictly increasing (row {row_number})")
        times.append(t)
        for name, value in values.items():
            signal_values[name].append(value)

    if len(times) < 2:
        raise CaptureError(f"{path}: capture needs at least two samples")
    return Capture(tuple(times), {name: tuple(values) for name, values in signal_values.items()})


def _looks_like_paired_xy_csv(lines: list[str]) -> bool:
    if len(lines) < 3:
        return False
    names = _row(lines[0])
    units = _row(lines[1])
    if len(names) < 2 or len(names) % 2 or len(units) < len(names):
        return False
    return all(
        units[index].lower() in {"second", "seconds", "s"}
        and units[index + 1].lower() in {"volt", "volts", "v"}
        for index in range(0, len(names), 2)
    )


def _load_paired_xy_csv(lines: list[str], contract: Contract, path: Path) -> Capture:
    names = _row(lines[0])
    source_positions = {names[index + 1]: (index, index + 1) for index in range(0, len(names), 2)}
    if len(source_positions) != len(names) // 2:
        raise CaptureError(f"{path}: paired XY CSV contains duplicate source names")
    expected = {signal.column for signal in contract.signals.values()}
    missing = expected.difference(source_positions)
    if missing:
        raise CaptureError(f"{path}: paired XY CSV is missing source(s): {', '.join(sorted(missing))}")

    source_times: dict[str, list[float]] = {source: [] for source in expected}
    source_values: dict[str, list[float]] = {source: [] for source in expected}
    for row_number, line in enumerate(lines[2:], start=3):
        fields = _row(line)
        if not fields or not any(fields):
            continue
        for source in expected:
            time_index, value_index = source_positions[source]
            try:
                t = float(fields[time_index])
                value = float(fields[value_index])
            except (IndexError, ValueError) as exc:
                raise CaptureError(f"{path}: row {row_number} contains invalid paired XY data") from exc
            _validate_sample_row(t, (value,), row_number, path)
            if source_times[source] and t <= source_times[source][-1]:
                raise CaptureError(f"{path}: {source} time must be strictly increasing (row {row_number})")
            source_times[source].append(t)
            source_values[source].append(value)

    reference_source = next(iter(sorted(expected)))
    reference_times = tuple(source_times[reference_source])
    if len(reference_times) < 2:
        raise CaptureError(f"{path}: capture needs at least two samples")
    for source in expected:
        if tuple(source_times[source]) != reference_times:
            raise CaptureError(f"{path}: paired XY source {source} does not share the same time axis")

    signal_values = {
        name: tuple(source_values[signal.column])
        for name, signal in contract.signals.items()
    }
    return Capture(reference_times, signal_values)


_LEGACY_XY_METADATA = {
    "Record Length",
    "Sample Interval",
    "Trigger Point",
    "Trigger Time",
    "Horizontal Offset",
}


def _looks_like_legacy_metadata_xy_csv(lines: list[str]) -> bool:
    hits = 0
    numeric_xy = 0
    for line in lines[:20]:
        fields = _row(line)
        if fields and fields[0] in _LEGACY_XY_METADATA:
            hits += 1
        if len(fields) >= 5:
            try:
                float(fields[3])
                float(fields[4])
            except ValueError:
                pass
            else:
                numeric_xy += 1
    return hits >= 2 and numeric_xy >= 2


def _load_legacy_metadata_xy_csv(lines: list[str], contract: Contract, path: Path) -> Capture:
    if len(contract.signals) != 1:
        raise CaptureError(
            f"{path}: legacy metadata+XY CSV contains one waveform; "
            "use a single-signal contract or normalize multiple traces into one table"
        )
    signal_name, signal = next(iter(contract.signals.items()))
    if signal.column.lower() not in {"value", "voltage", "amplitude"}:
        raise CaptureError(
            f"{path}: legacy metadata+XY CSV has no embedded channel name; "
            f"map signals.{signal_name}.column to Value"
        )

    times: list[float] = []
    values: list[float] = []
    for row_number, line in enumerate(lines, start=1):
        fields = _row(line)
        if len(fields) < 5:
            continue
        try:
            t = float(fields[3])
            value = float(fields[4])
        except ValueError:
            continue
        _validate_sample_row(t, (value,), row_number, path)
        if times and t <= times[-1]:
            raise CaptureError(f"{path}: time must be strictly increasing (row {row_number})")
        times.append(t)
        values.append(value)

    if len(times) < 2:
        raise CaptureError(f"{path}: capture needs at least two waveform samples")
    return Capture(tuple(times), {signal_name: tuple(values)})


def _looks_like_siglent_csv(lines: list[str]) -> bool:
    head = lines[:100]
    return "Second,Value" in head and any(line.startswith("Source,CH") for line in head)


def _load_siglent_group(paths: list[Path], contract: Contract) -> Capture:
    traces: dict[str, tuple[dict[str, str], tuple[float, ...], tuple[float, ...]]] = {}
    for path in paths:
        metadata, times, values = _read_siglent_trace(path)
        source = metadata["Source"]
        if source in traces:
            raise CaptureError(f"Siglent source {source} appears more than once")
        traces[source] = (metadata, times, values)

    expected_sources = {signal.column for signal in contract.signals.values()}
    missing = expected_sources.difference(traces)
    if missing:
        raise CaptureError(
            "Siglent capture group is missing source(s): " + ", ".join(sorted(missing))
        )

    reference_source = next(iter(sorted(traces)))
    reference_meta, reference_times, _ = traces[reference_source]
    comparable_metadata = (
        "Record Length",
        "Sample Interval",
        "Horizontal Units",
        "Horizontal Scale",
        "Model",
        "Serial Number",
        "Software Version",
    )
    # Validate every file the user supplied, not only the sources referenced by
    # the contract. Silently ignoring an incompatible extra file would make a
    # claimed capture group less trustworthy.
    for source in sorted(traces):
        metadata, times, _ = traces[source]
        if times != reference_times:
            raise CaptureError(f"Siglent source {source} does not share the same time axis")
        for key in comparable_metadata:
            if metadata.get(key) != reference_meta.get(key):
                raise CaptureError(
                    f"Siglent source {source} has different {key!r}: "
                    f"{metadata.get(key)!r} != {reference_meta.get(key)!r}"
                )
        if metadata.get("Horizontal Units") != "s":
            raise CaptureError(f"Siglent source {source} horizontal units must be seconds")
        if metadata.get("Vertical Units") != "V":
            raise CaptureError(f"Siglent source {source} vertical units must be volts")

    signal_values = {
        name: traces[signal.column][2]
        for name, signal in contract.signals.items()
    }
    return Capture(reference_times, signal_values)


def _read_siglent_trace(
    path: Path,
) -> tuple[dict[str, str], tuple[float, ...], tuple[float, ...]]:
    lines = _read_lines(path)
    try:
        header_index = lines.index("Second,Value")
    except ValueError as exc:
        raise CaptureError(f"{path} is not a supported Siglent CSV export") from exc

    metadata: dict[str, str] = {}
    for line in lines[:header_index]:
        fields = next(csv.reader([line]))
        if len(fields) >= 2:
            key = fields[0].strip()
            if not key:
                continue
            if key in metadata:
                raise CaptureError(f"{path}: duplicate Siglent metadata field {key!r}")
            metadata[key] = fields[1].strip()

    required_meta = {
        "Record Length",
        "Sample Interval",
        "Vertical Units",
        "Horizontal Units",
        "Source",
    }
    missing_meta = required_meta.difference(metadata)
    if missing_meta:
        raise CaptureError(
            f"{path} is missing Siglent metadata: {', '.join(sorted(missing_meta))}"
        )

    reader = csv.DictReader(lines[header_index:])
    times: list[float] = []
    values: list[float] = []
    for row_number, row in enumerate(reader, start=header_index + 2):
        try:
            t = float(row["Second"])
            value = float(row["Value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CaptureError(f"{path}: row {row_number} is not numeric") from exc
        _validate_sample_row(t, (value,), row_number, path)
        if times and t <= times[-1]:
            raise CaptureError(f"{path}: time must be strictly increasing (row {row_number})")
        times.append(t)
        values.append(value)

    if len(times) < 2:
        raise CaptureError(f"{path}: capture needs at least two samples")

    record_length = metadata["Record Length"]
    if not record_length.startswith("Analog:"):
        raise CaptureError(f"{path}: unsupported Record Length {record_length!r}")
    try:
        declared = int(record_length.removeprefix("Analog:"))
    except ValueError as exc:
        raise CaptureError(f"{path}: invalid Record Length {record_length!r}") from exc
    if declared != len(times):
        raise CaptureError(
            f"{path}: Record Length declares {declared} samples but file contains {len(times)}"
        )

    try:
        declared_interval = float(metadata["Sample Interval"])
    except ValueError as exc:
        raise CaptureError(
            f"{path}: invalid Sample Interval {metadata['Sample Interval']!r}"
        ) from exc
    if not isfinite(declared_interval) or declared_interval <= 0:
        raise CaptureError(
            f"{path}: Sample Interval must be finite and > 0, got {metadata['Sample Interval']!r}"
        )

    interval_abs_tol = max(1e-15, declared_interval * 1e-9)
    for index in range(1, len(times)):
        observed_interval = times[index] - times[index - 1]
        if not isclose(
            observed_interval,
            declared_interval,
            rel_tol=1e-6,
            abs_tol=interval_abs_tol,
        ):
            raise CaptureError(
                f"{path}: time axis interval at sample {index} is {observed_interval:.9g} s "
                f"but metadata declares {declared_interval:.9g} s"
            )

    return metadata, tuple(times), tuple(values)


def _validate_sample_row(
    time: float,
    values,
    row_number: int,
    path: Path | None = None,
) -> None:
    prefix = f"{path}: " if path is not None else ""
    if not isfinite(time) or any(not isfinite(value) for value in values):
        raise CaptureError(f"{prefix}row {row_number} contains non-finite waveform data")


def _find_header(lines: list[str], expected: set[str]) -> tuple[int, str]:
    for index, line in enumerate(lines[:100]):
        for delimiter in (",", ";", "\t"):
            fields = [field.strip().strip('"') for field in next(csv.reader([line], delimiter=delimiter))]
            if expected.issubset(fields):
                return index, delimiter
    raise CaptureError("could not find a CSV header containing all configured columns")
