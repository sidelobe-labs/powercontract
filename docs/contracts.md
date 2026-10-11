# Writing contracts

A PowerContract file is YAML with five top-level sections:

```yaml
version: 1
capture: {}
signals: {}
events: {}
requirements: []
```

Parsing is strict. Unknown fields are errors instead of being silently ignored.

## Capture

For a normal table CSV, `time_column` is the exact name of the time column:

```yaml
capture:
  time_column: Time
```

Vendor-specific parsers may derive the time axis from the file itself. Keeping `time_column` in the contract still makes the expected capture convention visible.

Time values are seconds in contract version 1.

## Signals

Signals give stable names to measured columns:

```yaml
signals:
  vdd:
    column: CH1
    nominal: 3.3

  reset_n:
    column: CH2
```

`nominal` is required for rise- and fall-time requirements because their thresholds are expressed as fractions of nominal voltage.

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

`direction` is either `above` or `below`.

Crossing times are linearly interpolated between samples.

If `stable_for` is present, the signal must remain on the requested side of the threshold for the full interval. If the capture ends before that interval can be observed, the event is not considered proven.

## Requirements

### delay

Measures the interval between two named events:

```yaml
- id: SEQ-001
  type: delay
  from: vdd_valid
  to: reset_release
  min: 50us
  max: 2ms
```

Use `min`, `max`, or both.

### max_value

Requires the maximum observed voltage to stay at or below a limit:

```yaml
- id: VDD-MAX
  type: max_value
  signal: vdd
  value: 3.6
```

The measurement can be restricted to an event window:

```yaml
- id: VDD-MAX-AFTER-START
  type: max_value
  signal: vdd
  value: 3.6
  from: vdd_valid
  to: reset_release
```

### min_value

The inverse of `max_value`:

```yaml
- id: VDD-MIN
  type: min_value
  signal: vdd
  value: 3.0
```

It accepts the same optional `from` and `to` bounds.

### rise_time

Measures a completed upward transition between fractions of nominal voltage:

```yaml
- id: VDD-RISE
  type: rise_time
  signal: vdd
  low: 0.1
  high: 0.9
  max: 5ms
```

The defaults are 10% and 90%.

PowerContract pairs the completed high-threshold crossing with the most recent matching low-threshold crossing. That avoids measuring from an unrelated earlier noise crossing.

### fall_time

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

## Measurement uncertainty

Uncertainty is explicit. PowerContract does not estimate it from noise or scope settings.

Voltage requirements use volts:

```yaml
uncertainty: 0.03
```

Timing requirements use a duration:

```yaml
uncertainty: 10us
```

The evaluator treats the measurement as `measured ± uncertainty`:

- the full interval satisfies the requirement: `PASS`;
- the full interval violates the requirement: `FAIL`;
- the interval crosses the limit: `INDETERMINATE`.

The reported margin is the worst-case margin after uncertainty is applied.

## Requirement provenance

A requirement can retain where it came from:

```yaml
source: "TPS62130A datasheet, section 8.4"
```

The source is included in JSON results. PowerContract does not fetch or parse it.

This is useful in reviews: a failing measurement can point back to the exact datasheet table or internal requirement that defined the limit.

## Durations

Durations accept:

- seconds: `1s`
- milliseconds: `2ms`
- microseconds: `50us` or `50µs`
- nanoseconds: `100ns`

A bare numeric duration is interpreted as seconds.
