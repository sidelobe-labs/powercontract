# PowerContract

**Executable electrical requirements for oscilloscope captures.**

PowerContract checks measured waveforms against power and timing requirements written in YAML. It is for the point where “the waveform looks fine” is no longer a useful engineering answer.

A typical check is simple:

```text
datasheet / board requirement
            +
       scope capture
            ↓
      PowerContract
            ↓
PASS / FAIL / INDETERMINATE
measured value + margin + source
```

It does not control the oscilloscope, decode protocols or compare captures to a golden waveform.

## Quick start

Install from a checkout:

```bash
python -m pip install .
powercontract --version
```

Given a CSV:

```text
Time,VDD_3V3,EN
-0.001,0.00,0.00
0.000,3.20,0.00
0.001,3.30,3.30
```

write a contract:

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

and run:

```bash
powercontract check capture.csv power.yaml
```

PowerContract returns one verdict per requirement and a non-zero exit code when the evidence is not good enough to call the run clean.

For machine-readable output:

```bash
powercontract check capture.csv power.yaml --json report.json
```

## What it can check

v0.1 supports:

- delay between named threshold events;
- minimum and maximum voltage;
- event-bounded voltage windows;
- rise time and fall time;
- threshold stability windows;
- explicit measurement uncertainty;
- requirement provenance through a human-readable `source`;
- `PASS`, `FAIL` and `INDETERMINATE` verdicts;
- terminal output and versioned JSON reports.

Missing evidence is `INDETERMINATE`, not a fabricated electrical failure.

## Capture compatibility

PowerContract understands several common CSV families.

| Input | Status |
| --- | --- |
| Normal table CSV with one time column and named signals | **Supported** |
| Siglent SDS800X HD per-channel CSV | **Hardware-verified on SDS824X HD** |
| Rigol sequence CSV with `Start` / `Increment` | **Format-verified** |
| Rigol paired XY CSV | **Format-verified** |
| Teledyne LeCroy WaveAce source+units CSV | **Format-verified** |
| Tektronix / LeCroy legacy metadata+XY CSV | **Format-verified, single trace** |
| Keysight InfiniiVision multi-column CSV | **Generic CSV path** |
| CSV produced by Python, MATLAB, LabVIEW or custom acquisition code | **Generic CSV path** |

“Format-verified” means the parser has tests matching a documented or publicly observed file layout. It does **not** mean every scope from that vendor has been tested on hardware.

See [Input formats](docs/input-formats.md) and the [oscilloscope vendor guide](docs/vendors.md) before assuming a particular model uses one of these layouts.

## Documentation

- [Getting started](docs/getting-started.md)
- [Writing contracts](docs/contracts.md)
- [Input formats](docs/input-formats.md)
- [Oscilloscope vendor guide](docs/vendors.md)
- [Using PowerContract in CI](docs/ci.md)
- [Troubleshooting](docs/troubleshooting.md)

The full documentation index is in [`docs/README.md`](docs/README.md).

## Siglent grouped capture example

The repository contains an ESP32-C3 chip-level example using Siglent-style per-channel CSV:

```bash
powercontract check examples/esp32-c3/usr_wf_C2_data.csv \
  examples/esp32-c3/contract.yaml \
  --with examples/esp32-c3/usr_wf_C3_data.csv
```

The electrical limits in that example come from the ESP32-C3 datasheet. It intentionally does not invent requirements for the development board's 5 V input or onboard regulator.

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | every requirement passed |
| `1` | at least one requirement failed or was indeterminate |
| `2` | invalid contract, capture or requested output |

## Project boundary

A feature belongs in PowerContract when it helps answer:

> Did these measured signals satisfy these declared electrical requirements?

A waveform viewer, protocol decoder, SCPI control framework, automatic datasheet parser or golden-trace regression engine is a different tool.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

CI runs the test suite on Python 3.11 and 3.12 and also builds and smoke-tests the wheel outside the repository checkout.

## License

MIT. See [LICENSE](LICENSE).

Release history is in [CHANGELOG.md](CHANGELOG.md).
