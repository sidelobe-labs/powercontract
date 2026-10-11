from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="evaluate one capture against one contract")
    check.add_argument("capture", type=Path)
    check.add_argument("contract", type=Path)
    check.add_argument("--json", dest="json_path", type=Path, help="write a machine-readable report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        contract = load_contract(args.contract)
        capture = load_capture(args.capture, contract)
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
            "passed": result.passed,
            "events": result.events,
            "findings": [finding.as_dict() for finding in result.findings],
        }
        args.json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
