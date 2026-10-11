# Getting started

This guide assumes you already have a waveform export from an oscilloscope.

## 1. Install PowerContract

From a checkout:

```bash
python -m pip install .
powercontract --version
```

For development:

```bash
python -m pip install -e '.[dev]'
pytest
```

## 2. Look at the CSV before writing a contract

Do not guess the column names. Open the first few lines:

```bash
head -n 20 capture.csv
```

On Windows PowerShell:

```powershell
Get-Content .\capture.csv -TotalCount 20
```

You are looking for the time column and the names of the measured signals.

A plain export might look like this:

```text
Time,VDD_3V3,EN
-0.002,0.01,0.00
-0.001,0.12,0.00
0.000,3.28,0.00
0.001,3.30,3.29
```

Vendor-specific layouts are covered in [Input formats](input-formats.md) and the [Vendor guide](vendors.md).

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

The names under `signals` and `events` are yours. The `column` fields refer to names in the capture file.

## 4. Run the check

```bash
powercontract check capture.csv power.yaml
```

A result looks like this:

```text
PASS          PWR-001          en_release - vdd_valid = 128 us; allowed >= 50 us; margin 78 us
PASS          PWR-002          max(vdd) = 3.41 V ± 0.03 V; limit <= 3.6 V; margin 0.16 V

2/2 requirements passed; 0 failed; 0 indeterminate
```

The exact measured values depend on the capture.

## 5. Keep a machine-readable report

```bash
powercontract check capture.csv power.yaml --json report.json
```

The JSON report includes:

- the PowerContract version;
- the report schema version;
- event timestamps;
- every requirement verdict;
- measured values and limits;
- margin;
- declared uncertainty;
- requirement source.

See [Using PowerContract in CI](ci.md) for automation.

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | every requirement passed |
| `1` | at least one requirement failed or was indeterminate |
| `2` | the input, contract or requested output was invalid |

An `INDETERMINATE` result is not an electrical failure. It means the capture does not contain enough evidence to make the requested claim safely.
