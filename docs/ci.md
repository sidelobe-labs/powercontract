# Using PowerContract in CI

PowerContract is useful in CI because its result is deterministic and its exit codes are simple.

It does not need an oscilloscope connected to the runner. Capture acquisition and capture evaluation are separate concerns.

## Minimal GitHub Actions job

```yaml
name: electrical-contracts

on:
  pull_request:

jobs:
  power:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: python -m pip install powercontract

      - name: Check power-up capture
        run: |
          powercontract check             captures/power-up.csv             contracts/power-up.yaml             --json power-up-report.json

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: powercontract-report
          path: power-up-report.json
```

Until PowerContract is published to PyPI, install from a pinned repository revision or a built wheel instead of the `pip install powercontract` line above.

## Exit codes

- `0`: every requirement passed;
- `1`: at least one requirement failed or is indeterminate;
- `2`: the contract, capture, or requested output is invalid.

An indeterminate result intentionally fails the CI step. CI should not turn missing evidence into a green build.

## JSON report

A report contains a schema version and evaluator version:

```json
{
  "schema_version": 1,
  "powercontract_version": "0.1.0",
  "passed": true,
  "events": {},
  "findings": []
}
```

Each finding includes its ID, status, measured value, bounds, margin, uncertainty, unit and source where applicable.

Keep the report as a build artifact if electrical evidence is part of a release or hardware-validation record.

## Acquisition is separate

PowerContract does not decide how the capture reaches CI.

Common patterns are:

- an engineer exports a scope capture and commits it with the board revision;
- a lab runner acquires data and uploads it as an artifact;
- a separate SCPI script controls the instrument;
- a manufacturing or HIL system writes a normal CSV.

Keeping acquisition separate avoids coupling the requirement engine to one scope vendor or lab topology.
