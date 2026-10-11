# PowerContract

PowerContract validates oscilloscope captures against explicit electrical requirements.

It is intended for board bring-up and regression checks where requirements such as rail ordering, reset timing, voltage limits, and transition time should be checked from measured data rather than by comparing screenshots or golden traces.

PowerContract does not control instruments, decode protocols, or compare waveforms for similarity.

## Status

Version 0.1.0 is intentionally small. It supports CSV captures, threshold events, stability windows, sequencing delays, bounded voltage extrema, and rise/fall-time limits.

## Install

    python -m pip install -e .

For development:

    python -m pip install -e '.[dev]'
    pytest

## Example

    powercontract check examples/boot.csv examples/boot.yaml

A contract names capture columns, defines events, and applies requirements to the measured waveform:

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

PowerContract reports the measured value and margin for every requirement. A requirement can be `PASS`, `FAIL`, or `INDETERMINATE`. `INDETERMINATE` means the capture does not contain enough evidence to evaluate the requirement safely, including when an explicitly declared measurement uncertainty overlaps a requirement boundary; it is not presented as an electrical failure. Exit code 0 means all requirements passed, 1 means at least one requirement failed or was indeterminate, and 2 means the input or contract was invalid.

Use `--json report.json` for machine-readable output. Contract parsing is strict: unknown fields, invalid numeric values, and inconsistent references are rejected instead of being silently ignored.

## Measurement uncertainty

Every requirement may declare an optional `uncertainty` for the quantity being evaluated. Voltage requirements use volts; timing requirements accept the same duration syntax as their limits.

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

PowerContract evaluates the interval `measured ± uncertainty` conservatively:

- the entire interval satisfies the active limit(s): `PASS`
- the entire interval violates a limit: `FAIL`
- the interval overlaps a limit boundary: `INDETERMINATE`

The reported margin is the worst-case margin after uncertainty is applied. PowerContract does not infer uncertainty from waveform noise, scope settings, or filtering; the contract must state it explicitly.

## Requirement provenance

A requirement may carry an optional human-readable `source`, such as a datasheet section, table, ticket, or internal specification identifier:

    - id: PWR-001
      type: delay
      from: vdd_valid
      to: reset_release
      min: 50us
      source: "ESP32-C3 Series Datasheet v2.4, Table 2-11"

The source is preserved in machine-readable findings, including FAIL and INDETERMINATE results. PowerContract treats it as provenance metadata; it does not fetch, parse, or trust the referenced document automatically.

A chip-level ESP32-C3 example using Siglent-style per-channel CSV files is included under `examples/esp32-c3/`:

    powercontract check examples/esp32-c3/usr_wf_C2_data.csv \
      examples/esp32-c3/contract.yaml \
      --with examples/esp32-c3/usr_wf_C3_data.csv

That example encodes the ESP32-C3 3.0–3.6 V recommended supply range and the 50 us minimum power-rail stabilization interval before CHIP_EN release. It intentionally does not claim requirements for a development board's 5 V input or onboard regulator.

## Requirement types

### delay

Measures the time from one named event to another. `min`, `max`, or both may be supplied.

### max_value

Requires the maximum observed signal value to be at or below a limit.

Optional `from` and `to` event names restrict the measurement to a meaningful interval. Window boundaries are evaluated by linear interpolation between adjacent samples.

### min_value

Requires the minimum observed signal value to be at or above a limit. It accepts the same optional `from` and `to` event bounds as `max_value`.

### rise_time

Measures a completed upward transition between two fractions of a signal's declared nominal voltage. The default fractions are 10% and 90%. The high threshold is found first, then the most recent low-threshold crossing before it is used, which avoids pairing a real rise with unrelated earlier threshold noise.

### fall_time

Measures the first downward transition from the high fraction to the low fraction of a signal's declared nominal voltage. The default fractions are 90% and 10%.

## Events

An event is the first threshold crossing that satisfies its optional stability window. Crossing time is linearly interpolated between adjacent samples. A stable event is not reported if the capture ends before the entire stability window has been observed.

## CSV input

For ordinary table CSV, the configured time and signal columns are explicit. PowerContract scans the first 100 lines for a matching table header, which permits common oscilloscope metadata preambles. Comma, semicolon, and tab delimiters are accepted.

Time values are seconds. Signal values are volts in 0.1.0.

### Siglent SDS800X HD per-channel CSV

SDS800X HD exports one CSV per analog channel. PowerContract accepts those files as one capture group when they are passed explicitly:

    powercontract check usr_wf_C1_data.csv contract.yaml \
      --with usr_wf_C2_data.csv \
      --with usr_wf_C3_data.csv

For this input form, each signal's `column` names the Siglent `Source` metadata value:

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

The loader treats explicitly supplied per-channel files as one capture group and validates every supplied file, including channels not referenced by the contract. It requires a shared time axis, matching record/sample metadata and instrument identity when present, validates the declared record length, checks that the declared sample interval matches the actual time axis, rejects duplicate metadata fields, and requires seconds/volts units.

The CSV format itself does not contain an acquisition identifier, so compatible per-channel files are treated as one group because the user supplied them together. PowerContract does not claim stronger provenance than the files provide.

## Project boundary

A feature belongs in PowerContract when it helps answer:

> **Did these measured signals satisfy these declared electrical requirements?**

Features whose main purpose is inspecting, visualizing, controlling, decoding, or comparing waveforms belong elsewhere.

## Non-goals for 0.1

- instrument control or SCPI
- a waveform viewer
- protocol decoding
- golden-waveform comparison
- automatic datasheet parsing
- a general expression language
- a plugin framework

These are deliberately outside the first release.

## License

MIT
