"""Sequential evaluation of independent acquisitions from an explicit manifest."""
from __future__ import annotations

import json
from pathlib import Path

from .capture import load_capture
from .errors import PowerContractError, SpecError
from .evaluate import evaluate
from .model import Contract


def load_runs(path: Path) -> list[tuple[str, list[Path]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SpecError(f"cannot read batch manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"version", "runs"} or type(data["version"]) is not int or data["version"] != 1:
        raise SpecError("batch manifest requires version: 1 and runs")
    if not isinstance(data["runs"], list) or not data["runs"]:
        raise SpecError("batch runs must be a non-empty list")
    runs = []
    labels = set()
    for index, run in enumerate(data["runs"]):
        if not isinstance(run, dict) or set(run) != {"label", "captures"}:
            raise SpecError(f"runs[{index}] requires label and captures")
        label, captures = run["label"], run["captures"]
        if not isinstance(label, str) or not label.strip() or label in labels:
            raise SpecError(f"runs[{index}].label must be a unique non-empty string")
        if not isinstance(captures, list) or not captures or any(not isinstance(p, str) or not p.strip() for p in captures):
            raise SpecError(f"runs[{index}].captures must be a non-empty list of paths")
        labels.add(label)
        runs.append((label, [path.parent / p for p in captures]))
    return runs


def evaluate_runs(contract: Contract, runs: list[tuple[str, list[Path]]]) -> tuple[list[dict], int]:
    reports = []
    exit_code = 0
    for label, paths in runs:
        try:
            # Only one acquisition is held at a time; additional files are channels
            # from that acquisition, exactly as in the single check command.
            capture = load_capture(paths[0], contract, paths[1:])
            result = evaluate(contract, capture)
            status = "PASS" if result.passed else ("FAIL" if any(f.status == "FAIL" for f in result.findings) else "INDETERMINATE")
            reports.append({"label": label, "status": status, **evaluation_report(contract, capture, result)})
            exit_code = max(exit_code, 0 if result.passed else 1)
            del capture
        except PowerContractError as exc:
            reports.append({"label": label, "status": "ERROR", "error": str(exc), "inputs": {"contract_sha256": contract.source_sha256}})
            exit_code = 2
    return reports, exit_code


def evaluation_report(contract, capture, result) -> dict:
    return {
        "inputs": {"contract_sha256": contract.source_sha256, "capture_sha256": list(capture.source_sha256)},
        "capture": {"sample_count": len(capture.time), "time_range_s": [capture.time[0], capture.time[-1]]},
        "passed": result.passed,
        "events": result.events,
        "findings": [finding.as_dict() for finding in result.findings],
    }
