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

      # Pin the version your project has validated.
      - run: python -m pip install powercontract==0.1.0

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

Pin the PowerContract version used by CI so electrical checks do not change when a new package release is published.

## Exit codes

- `0`: all requirements passed;
- `1`: at least one requirement failed or was indeterminate;
- `2`: invalid capture, contract, or output request.

An `INDETERMINATE` result returns exit code 1. A CI job therefore fails when the capture does not contain enough evidence for all requirements.

## JSON report

The report includes the report schema and PowerContract versions, input hashes, and the evaluated capture's sample count and time range:

```json
{
  "schema_version": 1,
  "powercontract_version": "0.1.2",
  "inputs": {
    "contract_sha256": "<64 hexadecimal characters>",
    "capture_sha256": ["<64 hexadecimal characters>"]
  },
  "capture": {
    "sample_count": 3,
    "time_range_s": [-0.001, 0.001]
  },
  "passed": true,
  "events": {},
  "findings": []
}
```

Each finding can include the requirement ID, status, measured value, limits, margin, unit, uncertainty, and source.

Hashes are SHA-256 digests of the exact file bytes parsed, including any byte-order mark or newline differences. Each input is read once so a later file change cannot alter the report's input identity. `capture_sha256` follows command-line order: the primary capture, then each `--with` file, including supplied channels unused by the contract. Paths, filenames and instrument metadata are not added to the report.

`sample_count` is the number of samples on the validated shared time axis, not a sum across channels. `time_range_s` contains its first and last timestamps in seconds; it is not an acquisition date or a claim of continuous measurement coverage. Hashes identify input bytes, but do not authenticate them or prove that files came from the same acquisition. Keep the inputs alongside the report when reproducibility matters.

The `inputs` and `capture` objects are additive fields in schema version 1. Consumers should tolerate unknown fields; older reports may omit these objects. Existing findings and exit codes are unchanged.

Store the report as a build artifact if you need to keep electrical-check results with a hardware or firmware revision.

## Acquisition

PowerContract does not acquire the waveform.

Typical setups are:

- an engineer exports a capture and stores it with the test data;
- a lab runner acquires the waveform and passes it to the evaluation job;
- a separate SCPI script controls the instrument;
- a HIL or manufacturing system writes a normal CSV.

Keeping acquisition separate allows the same contract evaluator to be used with different instruments.
