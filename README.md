# PowerContract

PowerContract evaluates oscilloscope waveform data against electrical requirements defined in YAML.

For each requirement it reports `PASS`, `FAIL`, or `INDETERMINATE`, together with the measured value, limit, margin, and optional uncertainty and source.

It does not control the oscilloscope or replace the vendor's waveform-analysis software. Acquisition and evaluation are separate.

## Try it

Install from a checkout:

```bash
python -m pip install .
```

Run the bundled example:

```bash
powercontract check examples/boot.csv examples/boot.yaml
```

Check the installed version:

```bash
powercontract --version
```

For your own capture, inspect the CSV first and use its actual column names in the contract. The [getting-started guide](docs/getting-started.md) walks through the full process.

## Example contract

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

Run it with:

```bash
powercontract check capture.csv power.yaml
```

Write a JSON report with:

```bash
powercontract check capture.csv power.yaml --json report.json
```

## Requirements supported in v0.1

Contract version 1 uses seconds for time and volts for signal values.


- delay between named threshold events;
- minimum and maximum voltage;
- event-bounded voltage windows;
- rise time and fall time;
- threshold stability windows;
- explicit measurement uncertainty;
- optional requirement source;
- terminal and JSON output.

If the capture does not contain enough evidence to evaluate a requirement, the result is `INDETERMINATE`.

## Capture formats

| Input | Support |
| --- | --- |
| Normal table CSV with one time column and named signal columns | Supported |
| Siglent SDS800X HD per-channel CSV | Tested with a real SDS824X HD |
| Older Siglent / WaveAce-style `Source` + units CSV | Parser tested against documented/public examples |
| Rigol sequence CSV with `Start` / `Increment` | Parser tested against public format examples |
| Rigol paired XY CSV | Parser tested against public format examples |
| Tektronix five-column CSV | Parser tested against the Tektronix-documented layout |
| Keysight InfiniiVision multi-channel CSV | Supported through the normal table CSV loader when the file contains named columns |
| CSV from Python, pandas, MATLAB, LabVIEW, or custom acquisition code | Supported through the normal table CSV loader |

Only the Siglent SDS800X HD per-channel path is currently tested on physical hardware in this project. Other vendor-specific rows describe file-format support, not blanket support for every model from that vendor.

See [Input formats](docs/input-formats.md) and [Oscilloscope vendor notes](docs/vendors.md) for details.

## Documentation

- [Getting started](docs/getting-started.md)
- [Writing contracts](docs/contracts.md)
- [Input formats](docs/input-formats.md)
- [Oscilloscope vendor notes](docs/vendors.md)
- [CI usage](docs/ci.md)
- [Troubleshooting](docs/troubleshooting.md)

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | all requirements passed |
| `1` | at least one requirement failed or was indeterminate |
| `2` | invalid capture, contract, or output request |

## Scope

PowerContract answers one question: did the measured signals satisfy the declared electrical requirements?

It is not a waveform viewer, protocol decoder, SCPI control framework, automatic datasheet parser, or golden-waveform comparison tool.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

CI runs the test suite on Python 3.11 and 3.12, builds the package, runs `twine check`, and installs the built wheel in a clean virtual environment.

## License

MIT. See [LICENSE](LICENSE).

Release history is in [CHANGELOG.md](CHANGELOG.md).
