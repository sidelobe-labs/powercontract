# PowerContract

**Executable electrical requirements for oscilloscope captures.**

PowerContract checks measured waveforms against explicit power and timing requirements. It is aimed at board bring-up and hardware regression work where rail ordering, reset timing, voltage limits, and transition times should be reviewed as code rather than as screenshots or golden traces.

It deliberately does **not** control instruments, decode protocols, or compare waveforms for similarity.

## Quick start

Install from a checkout:

    python -m pip install .

Then evaluate a capture:

    powercontract check examples/boot.csv examples/boot.yaml

PowerContract prints one verdict per requirement and exits with:

- `0` when every requirement passes;
- `1` when at least one requirement fails or is indeterminate;
- `2` when the contract, capture, or requested output is invalid.

Check the installed version with:

    powercontract --version

For development:

    python -m pip install -e '.[dev]'
    pytest

## Contract

A contract names measured signals, defines observable events, and applies electrical requirements:

    version: 1
    capture:
      time_column: Time

    signals:
      vdd_3v3:
        column: C1
        nominal: 3.3
      reset_n:
        column: C2

    events:
      vdd_valid:
        signal: vdd_3v3
        direction: above
        threshold: 3.0
        stable_for: 2ms

      reset_release:
        signal: reset_n
        direction: above
        threshold: 1.5

    requirements:
      - id: PWR-001
        type: delay
        from: vdd_valid
        to: reset_release
        min: 5ms

      - id: PWR-002
        type: max_value
        signal: vdd_3v3
        value: 3.55
        from: vdd_valid
        to: reset_release

      - id: PWR-003
        type: rise_time
        signal: vdd_3v3
        low: 0.1
        high: 0.9
        max: 5ms

Each result retains the requirement ID, measured value, limits, margin, optional uncertainty, and optional source provenance.

## Verdicts and uncertainty

A requirement can be `PASS`, `FAIL`, or `INDETERMINATE`.

`INDETERMINATE` means the capture does not contain enough evidence to make a safe compliance claim. Missing events are indeterminate rather than electrical failures.

Requirements may also declare explicit measurement uncertainty:

    - id: VDD-MAX
      type: max_value
      signal: vdd_3v3
      value: 3.60
      uncertainty: 0.05

    - id: RESET-DELAY
      type: delay
      from: vdd_valid
      to: reset_release
      min: 50us
      uncertainty: 10us

PowerContract evaluates `measured ± uncertainty` conservatively:

- the entire interval satisfies the active limits → `PASS`;
- the entire interval violates a limit → `FAIL`;
- the interval crosses a limit boundary → `INDETERMINATE`.

The reported margin is the worst-case margin after uncertainty is applied. PowerContract does not infer uncertainty from noise, filtering, or scope settings.

## Requirement provenance

Every requirement may carry an optional human-readable `source`:

    - id: PWR-001
      type: delay
      from: vdd_valid
      to: reset_release
      min: 50us
      source: "ESP32-C3 Series Datasheet v2.4, Table 2-11"

The source is preserved in machine-readable output, including FAIL and INDETERMINATE findings. It is metadata only: PowerContract does not fetch or interpret the referenced document.

## Requirement types

### `delay`

Measures the time from one named event to another. `min`, `max`, or both may be supplied.

### `max_value`

Requires the maximum observed signal value to be at or below a limit. Optional `from` and `to` events restrict the measurement window.

### `min_value`

Requires the minimum observed signal value to be at or above a limit. It accepts the same optional event bounds as `max_value`.

### `rise_time`

Measures a completed upward transition between two fractions of a signal's declared nominal voltage. Defaults to 10%–90%. The evaluator pairs the high-threshold crossing with the most recent matching low-threshold crossing so unrelated earlier threshold noise is not mistaken for the start of the transition.

### `fall_time`

Measures a completed downward transition between the high and low fractions of a signal's declared nominal voltage. Defaults to 90%–10%.

## Events

An event is the first threshold crossing that satisfies its optional stability window. Crossing times are linearly interpolated between adjacent samples. A stable event is not reported if the capture ends before the requested stability interval has been fully observed.

## Input formats

### Ordinary CSV

Signal columns and the time column are configured explicitly. PowerContract scans the first 100 lines for the configured header, allowing common oscilloscope metadata preambles. Comma, semicolon, and tab delimiters are accepted.

Time values are seconds and signal values are volts in v0.1.0.

### Siglent SDS800X HD per-channel CSV

SDS800X HD scopes export one CSV per analog channel. Pass those files as one explicit capture group:

    powercontract check usr_wf_C1_data.csv contract.yaml \
      --with usr_wf_C2_data.csv \
      --with usr_wf_C3_data.csv

For grouped Siglent input, each signal's `column` names the `Source` metadata value:

    signals:
      vin:
        column: CH1
        nominal: 5.0
      vdd_3v3:
        column: CH2
        nominal: 3.3
      reset_n:
        column: CH3
        nominal: 3.3

PowerContract validates every supplied file. It checks the shared time axis, declared sample interval, record length, relevant horizontal metadata, duplicate metadata fields, volts/seconds units, and instrument identity when present.

The CSV format does not contain an acquisition identifier. Files are treated as one acquisition because the user supplied them together; PowerContract does not claim stronger provenance than the export provides.

## ESP32-C3 example

`examples/esp32-c3/` contains a chip-level example using Siglent-style per-channel CSV:

    powercontract check examples/esp32-c3/usr_wf_C2_data.csv \
      examples/esp32-c3/contract.yaml \
      --with examples/esp32-c3/usr_wf_C3_data.csv

The example encodes ESP32-C3 chip requirements from the Espressif datasheet. It intentionally does not claim requirements for a development board's 5 V input or onboard regulator.

## JSON output

Use `--json report.json` to write a machine-readable report.

The v0.1.0 report includes a top-level `schema_version` and `powercontract_version` so downstream tooling can identify the format and evaluator version explicitly.

## Project boundary

A feature belongs in PowerContract when it helps answer:

> **Did these measured signals satisfy these declared electrical requirements?**

Features whose main purpose is inspecting, visualizing, controlling, decoding, or comparing waveforms belong elsewhere.

Explicit non-goals for v0.1.0:

- instrument control or SCPI;
- waveform viewing;
- protocol decoding;
- golden-waveform comparison;
- automatic datasheet parsing;
- a general expression language;
- a plugin framework.

## License

MIT. See [LICENSE](LICENSE).

Release history is documented in [CHANGELOG.md](CHANGELOG.md).
