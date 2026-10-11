# Getting started

Install PowerContract from PyPI, then point it at an exported waveform and a contract.

## 1. Install PowerContract

```bash
python -m pip install powercontract
powercontract --version
```

If you are working on PowerContract itself, clone the repository and use the development install instead:

```bash
python -m pip install -e '.[dev]'
pytest
```

## 2. Inspect your CSV

Do not guess the column names.

On Linux or macOS:

```bash
head -n 20 capture.csv
```

On Windows PowerShell:

```powershell
Get-Content .\capture.csv -TotalCount 20
```

A normal table export might look like:

```text
Time,VDD_3V3,EN
-0.002,0.01,0.00
-0.001,0.12,0.00
0.000,3.28,0.00
0.001,3.30,3.29
```

If the file has vendor-specific headers or more than one header row, see [Input formats](input-formats.md).

## 3. Write a contract

Create `power.yaml`:

```yaml
version: 1

capture:
  time_column: Time

signals:
  vdd:
    column: VDD_3V3
    nominal: 3.3

  en:
    column: EN
    nominal: 3.3

events:
  vdd_valid:
    signal: vdd
    direction: above
    threshold: 3.0

  en_release:
    signal: en
    direction: above
    threshold: 2.0

requirements:
  - id: PWR-001
    type: delay
    from: vdd_valid
    to: en_release
    min: 50us
    source: "Board power specification, section 3.2"

  - id: PWR-002
    type: max_value
    signal: vdd
    value: 3.6
    uncertainty: 0.03
```

The names under `signals` and `events` are local names used by the contract. Each signal's `column` must match the capture format.

## 4. Run the check

```bash
powercontract check capture.csv power.yaml
```

The CLI prints one line per requirement and a summary.

A typical result is:

```text
PASS          PWR-001          en_release - vdd_valid = 128 us; allowed >= 50 us; margin 78 us
PASS          PWR-002          max(vdd) = 3.41 V ± 0.03 V; limit <= 3.6 V; margin 0.16 V

2/2 requirements passed; 0 failed; 0 indeterminate
```

Measured values depend on your capture.

## 5. Save a JSON report

```bash
powercontract check capture.csv power.yaml --json report.json
```

The report includes:

- PowerContract version;
- report schema version;
- event timestamps;
- requirement status;
- measured value and limits;
- margin;
- declared uncertainty;
- optional requirement source.

See [CI usage](ci.md) if the report should be stored as a build artifact.

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | all requirements passed |
| `1` | at least one requirement failed or was indeterminate |
| `2` | invalid capture, contract, or output request |

`INDETERMINATE` means the requested result cannot be established from the available capture. It is not the same as `FAIL`.
