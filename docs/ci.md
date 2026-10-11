# CI usage

PowerContract can run in CI without an oscilloscope attached to the runner. The runner only needs the capture file and contract.

## GitHub Actions example

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
          powercontract check \
            captures/power-up.csv \
            contracts/power-up.yaml \
            --json power-up-report.json

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: powercontract-report
          path: power-up-report.json
```

PowerContract is not yet published to PyPI. Until it is, replace the install command with a pinned repository revision or a built wheel.

## Exit codes

- `0`: all requirements passed;
- `1`: at least one requirement failed or was indeterminate;
- `2`: invalid capture, contract, or output request.

An `INDETERMINATE` result returns exit code 1. A CI job therefore fails when the capture does not contain enough evidence for all requirements.

## JSON report

The report includes both the report schema version and PowerContract version:

```json
{
  "schema_version": 1,
  "powercontract_version": "0.1.0",
  "passed": true,
  "events": {},
  "findings": []
}
```

Each finding can include the requirement ID, status, measured value, limits, margin, unit, uncertainty, and source.

Store the report as a build artifact if you need to keep electrical-check results with a hardware or firmware revision.

## Acquisition

PowerContract does not acquire the waveform.

Typical setups are:

- an engineer exports a capture and stores it with the test data;
- a lab runner acquires the waveform and passes it to the evaluation job;
- a separate SCPI script controls the instrument;
- a HIL or manufacturing system writes a normal CSV.

Keeping acquisition separate allows the same contract evaluator to be used with different instruments.
