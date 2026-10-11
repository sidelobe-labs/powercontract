from __future__ import annotations

import csv
from pathlib import Path

from .errors import CaptureError
from .model import Capture, Contract


def load_capture(path: str | Path, contract: Contract) -> Capture:
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise CaptureError(f"cannot read capture: {exc}") from exc
    if not lines:
        raise CaptureError("capture is empty")

    expected = {contract.time_column, *(s.column for s in contract.signals.values())}
    header_index, delimiter = _find_header(lines, expected)
    reader = csv.DictReader(lines[header_index:], delimiter=delimiter)
    if reader.fieldnames is None:
        raise CaptureError("capture has no header")
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
        if times and t <= times[-1]:
            raise CaptureError(f"time must be strictly increasing (row {row_number})")
        times.append(t)
        for name, value in values.items():
            signal_values[name].append(value)

    if len(times) < 2:
        raise CaptureError("capture needs at least two samples")
    return Capture(tuple(times), {name: tuple(values) for name, values in signal_values.items()})


def _find_header(lines: list[str], expected: set[str]) -> tuple[int, str]:
    # Oscilloscope exports commonly contain metadata before the sample table.
    # Accept only a row containing every explicitly configured column.
    for index, line in enumerate(lines[:100]):
        for delimiter in (",", ";", "\t"):
            fields = [field.strip().strip('"') for field in next(csv.reader([line], delimiter=delimiter))]
            if expected.issubset(fields):
                return index, delimiter
    raise CaptureError("could not find a CSV header containing all configured columns")
