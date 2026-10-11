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

PowerContract reports the measured value and margin for every requirement. Exit code 0 means all requirements passed, 1 means at least one failed, and 2 means the input or contract was invalid.

Use `--json report.json` for machine-readable output.

## Requirement types

### delay

Measures the time from one named event to another. `min`, `max`, or both may be supplied.

### max_value

Requires the maximum observed signal value to be at or below a limit.

Optional `from` and `to` event names restrict the measurement to a meaningful interval. Window boundaries are evaluated by linear interpolation between adjacent samples.

### min_value

Requires the minimum observed signal value to be at or above a limit. It accepts the same optional `from` and `to` event bounds as `max_value`.

### rise_time

Measures the first upward transition between two fractions of a signal's declared nominal voltage. The default fractions are 10% and 90%.

### fall_time

Measures the first downward transition from the high fraction to the low fraction of a signal's declared nominal voltage. The default fractions are 90% and 10%.

## Events

An event is the first threshold crossing that satisfies its optional stability window. Crossing time is linearly interpolated between adjacent samples. A stable event is not reported if the capture ends before the entire stability window has been observed.

## CSV input

The configured time and signal columns are explicit. PowerContract scans the first 100 lines for a matching table header, which permits common oscilloscope metadata preambles. Comma, semicolon, and tab delimiters are accepted.

Time values are seconds. Signal values are volts in 0.1.0.

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
