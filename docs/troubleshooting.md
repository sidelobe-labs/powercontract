# Troubleshooting

## “could not find a CSV header containing all configured columns”

PowerContract did not find the exact `time_column` and signal `column` names from the contract.

Inspect the file:

```bash
head -n 20 capture.csv
```

Then copy the real header names into the contract.

If the file is a vendor format with two header rows, check [Input formats](input-formats.md).

## “capture is missing columns”

The table header was found, but at least one configured signal is not present.

Typical causes:

- the channel was not enabled when the scope exported the file;
- the scope used a different label;
- the contract still refers to an old channel assignment.

## “time must be strictly increasing”

The input contains duplicate or reversed timestamps.

PowerContract does not sort the data silently because doing so could hide a malformed export or mix segments from different acquisitions.

For segmented-memory captures, export one segment or normalize the segments deliberately before evaluation.

## “multi-file capture groups currently require Siglent”

Only Siglent SDS800X HD per-channel files are grouped automatically in v0.1.

For other vendors, prefer one multi-channel CSV. This avoids pretending that several unrelated files definitely came from the same acquisition.

## “map signals.<name>.column to Value”

You are using a legacy single-waveform CSV that contains time and amplitude but no channel name.

Use:

```yaml
signals:
  rail:
    column: Value
```

That input format is intentionally single-signal.

## A requirement is INDETERMINATE

Read the summary.

Common reasons are:

- a required threshold crossing never occurred;
- the capture ended before a `stable_for` interval could be proven;
- the capture does not contain both thresholds needed for rise/fall time;
- the declared uncertainty overlaps the requirement boundary.

Do not automatically convert indeterminate results to pass.

## A maximum looks noisier than the scope display

PowerContract evaluates the samples in the file. It does not apply hidden smoothing.

A scope display may be decimated, filtered, bandwidth-limited or based on different measurement data than the exported file.

If a requirement depends on bandwidth or filtering, make that part of the capture procedure and document it with the requirement.

## The vendor is not listed

Try the normal table CSV path first.

If the file has a clear time column and named signal columns, no vendor-specific support is needed.

If it has a different structural format, open an issue with:

- scope vendor and model;
- firmware version;
- export mode used;
- first 20 lines of a sanitized CSV;
- expected time and signal columns.

Do not upload a proprietary or sensitive capture if the values themselves are confidential.
