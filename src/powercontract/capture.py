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
        return _load_siglent_group(paths, contract)

    lines = _read_lines(paths[0])
    if _looks_like_siglent_csv(lines):
        return _load_siglent_group(paths, contract)
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
