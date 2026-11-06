# Troubleshooting

## “could not find a CSV header containing all configured columns”

PowerContract did not find the configured `time_column` and signal columns.

Inspect the beginning of the file:

```bash
head -n 20 capture.csv
```

On Windows:

```powershell
Get-Content .\capture.csv -TotalCount 20
```

Use the exact names present in the export.

If the file has two header rows or vendor metadata, see [Input formats](input-formats.md).

## “capture is missing columns”

At least one configured signal is not present in the detected table.

Check that:

- the channel was enabled when the file was exported;
- the exported label matches the contract;
- the contract is not using an old channel assignment.

## “time must be strictly increasing”

The input contains duplicate or decreasing timestamps.

PowerContract does not reorder samples automatically.

For segmented-memory captures, export one segment or normalize the segments before evaluation.

## “more fields than the Rigol sample columns”

A Rigol sequence CSV row contains a non-empty field after the sequence number and declared channels. Check the reported row for shifted delimiters or appended values.

`Start` and `Increment` contain metadata in the second header row. Those positions may be empty in sample rows, but additional values are not waveform channels. Re-export the capture or correct the conversion that produced it.

## “multi-file capture groups currently require Siglent”

Automatic multi-file grouping is limited to the Siglent SDS800X HD per-channel format in v0.1.

For other vendors, use one multi-channel CSV or normalize separate files into one table.

## “map signals.<name>.column to Value”

The detected file contains one waveform with time and amplitude data but no usable channel name.

Use a single-signal contract:

```yaml
signals:
  rail:
    column: Value
```

## A requirement is `INDETERMINATE`

Read the finding summary. Common causes are:

- a required threshold crossing was not observed;
- the capture ended before a `stable_for` interval could be checked;
- rise/fall thresholds were not both present;
- declared uncertainty overlaps the requirement boundary.

Do not treat `INDETERMINATE` as `PASS`.

## A peak is larger than the value shown on the scope

PowerContract evaluates the samples in the exported file and does not apply hidden smoothing.

The scope display or built-in measurement may use decimation, bandwidth limits, filtering, or a different data path.

If bandwidth or filtering is part of the requirement, record those acquisition settings in the test procedure.

## The vendor or model is not listed

Try the normal table CSV loader first.

If the file has a clear time column and named signal columns, no vendor-specific parser is needed.

If the structure is different, report:

- vendor and model;
- firmware version;
- export mode;
- first 20 sanitized lines;
- expected time and signal mapping.

Do not attach confidential capture data if the waveform values are sensitive.
