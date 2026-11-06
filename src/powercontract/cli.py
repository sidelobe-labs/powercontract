from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .batch import evaluate_runs, evaluation_report, load_runs
from .capture import load_capture
from .errors import PowerContractError
from .evaluate import evaluate
from .spec import load_contract
from .units import format_seconds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="powercontract",
        description="Validate oscilloscope captures against electrical requirements.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="evaluate capture data against one contract")
    check.add_argument("capture", type=Path)
    check.add_argument("contract", type=Path)
    check.add_argument(
        "--with",
        dest="additional_captures",
        action="append",
        default=[],
        type=Path,
        metavar="CAPTURE",
        help="add another per-channel capture file from the same acquisition",
    )
    check.add_argument("--json", dest="json_path", type=Path, help="write a machine-readable report")
    batch = sub.add_parser("batch", help="evaluate independent acquisitions from a JSON manifest")
    batch.add_argument("manifest", type=Path)
    batch.add_argument("contract", type=Path)
    batch.add_argument("--json", dest="json_path", type=Path, required=True, help="write the aggregate report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "batch":
        return _batch(args)
    try:
        contract = load_contract(args.contract)
        capture = load_capture(args.capture, contract, args.additional_captures)
        result = evaluate(contract, capture)
    except PowerContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for finding in result.findings:
        margin = ""
        if finding.margin is not None:
            if finding.unit == "s":
                margin = f"; margin {format_seconds(finding.margin)}"
            else:
                margin = f"; margin {finding.margin:.6g} {finding.unit or ''}".rstrip()
        print(f"{finding.status:<13} {finding.requirement_id:<16} {finding.summary}{margin}")

    passed = sum(f.status == "PASS" for f in result.findings)
    failed = sum(f.status == "FAIL" for f in result.findings)
    indeterminate = sum(f.status == "INDETERMINATE" for f in result.findings)
    print(
        f"\n{passed}/{len(result.findings)} requirements passed"
        f"; {failed} failed; {indeterminate} indeterminate"
    )

    if args.json_path:
        payload = {
            "schema_version": 1,
            "powercontract_version": __version__,
            **evaluation_report(contract, capture, result),
        }
        try:
            args.json_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"error: cannot write JSON report: {exc}", file=sys.stderr)
            return 2

    return 0 if result.passed else 1


def _batch(args) -> int:
    try:
        contract = load_contract(args.contract)
        runs = load_runs(args.manifest)
        inputs = [args.contract, args.manifest, *(path for _, paths in runs for path in paths)]
        if args.json_path.resolve() in {path.resolve() for path in inputs}:
            raise PowerContractError("batch report must not overwrite an input")
        reports, exit_code = evaluate_runs(contract, runs)
        payload = {"schema_version": 1, "powercontract_version": __version__, "runs": reports}
        args.json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (PowerContractError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for report in reports:
        print(f"{report['status']:<13} {report['label']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
