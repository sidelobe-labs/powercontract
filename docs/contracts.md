# Writing contracts

A contract is a YAML file with five top-level fields:

```yaml
version: 1
capture: {}
signals: {}
events: {}
requirements: []
```

The parser rejects unknown fields and duplicate keys in the same mapping. YAML anchors and merges are supported: an explicit field can override an inherited value, and the first mapping in a merge list takes precedence.

## Capture

For a normal table CSV, `time_column` is the exact header used for time:

```yaml
capture:
  time_column: Time
```

Time values are seconds in contract version 1.

Some vendor-specific parsers derive time from the file format instead of this column. The field remains part of the contract so the expected convention is visible.

## Signals

Signals map names used in the contract to columns or source names in the capture:

```yaml
signals:
  vdd:
    column: CH1
    nominal: 3.3

  reset_n:
    column: CH2
```

`nominal` is required for rise-time and fall-time checks because their thresholds are fractions of nominal voltage.

Signal values are volts in contract version 1.

## Events

An event is a threshold crossing:

```yaml
events:
  vdd_valid:
    signal: vdd
    direction: above
    threshold: 3.0
    stable_for: 100us
```

`direction` is `above` or `below`.

Crossing times are linearly interpolated between adjacent samples.

If `stable_for` is set, the signal must stay on the requested side of the threshold for the full interval. If the capture ends before that interval can be checked, the event is not reported.

## Requirements

### `delay`

Measures the interval between two events:

```yaml
- id: SEQ-001
  type: delay
  from: vdd_valid
  to: reset_release
  min: 50us
  max: 2ms
```

Use `min`, `max`, or both.

### `max_value`

Checks that the highest measured voltage does not exceed a limit:

```yaml
- id: VDD-MAX
  type: max_value
  signal: vdd
  value: 3.6
```

Use optional event bounds to restrict the measurement interval:

```yaml
- id: VDD-MAX-AFTER-START
  type: max_value
  signal: vdd
  value: 3.6
  from: vdd_valid
  to: reset_release
```

### `min_value`

Checks that the lowest measured voltage stays above a limit:

```yaml
- id: VDD-MIN
  type: min_value
  signal: vdd
  value: 3.0
```

It accepts the same optional `from` and `to` event bounds as `max_value`.

### `rise_time`

Measures a completed upward transition between two fractions of nominal voltage:

```yaml
- id: VDD-RISE
  type: rise_time
  signal: vdd
  low: 0.1
  high: 0.9
  max: 5ms
```

The defaults are 10% and 90%.

The evaluator uses the first high-threshold crossing that has a low-threshold crossing before it in the capture, paired with the most recent such low crossing. If the capture begins partway through a rise, an unmatched high crossing is skipped. This avoids using an unrelated earlier noise crossing as the start of the rise. If no complete pair is present, the result is `INDETERMINATE`.

### `fall_time`

Measures a completed downward transition:

```yaml
- id: VDD-FALL
  type: fall_time
  signal: vdd
  low: 0.1
  high: 0.9
  max: 5ms
```

The defaults are 90% to 10%.

Fall-time uses the same pairing rule with the thresholds and direction reversed.

## Measurement uncertainty

Uncertainty is supplied by the contract. PowerContract does not estimate it from waveform noise or scope settings.

For voltage requirements, use volts:

```yaml
uncertainty: 0.03
```

For timing requirements, use a duration:

```yaml
uncertainty: 10us
```

The measurement is evaluated as `measured ± uncertainty`:

- the full interval satisfies the requirement: `PASS`;
- the full interval violates the requirement: `FAIL`;
- the interval crosses a limit: `INDETERMINATE`.

The reported margin is the worst-case margin after uncertainty is applied.

## Requirement source

Use `source` to record where a limit came from:

```yaml
source: "TPS62130A datasheet, section 8.4"
```

The string is copied into JSON output. PowerContract does not fetch or parse the referenced document.

## Durations

Accepted suffixes:

- `s`
- `ms`
- `us` or `µs`
- `ns`

A bare numeric duration is interpreted as seconds. Durations must be finite and non-negative; NaN and infinity are not valid durations.
