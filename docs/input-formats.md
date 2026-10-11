# Input formats

PowerContract works with CSV because CSV is the common interchange format across oscilloscopes, scripts and lab tooling.

It does not identify a scope from its logo or filename. It identifies the structure of the data.

## Support levels

We use three labels in the vendor guide:

**Hardware-verified** means PowerContract has been exercised against a real export from that instrument family.

**Format-verified** means the parser is covered by fixtures that match a documented or publicly observed export shape, but we have not tested that path on the physical instrument ourselves.

**Generic CSV** means the vendor output fits PowerContract's normal table loader. There is no vendor-specific parser.

## 1. Normal table CSV

This is the preferred interchange format:

```text
Time,VDD,EN
-0.001,0.0,0.0
0.000,3.2,0.0
0.001,3.3,3.3
```

The header may appear after a metadata preamble. PowerContract scans the first 100 lines.

Comma, semicolon and tab delimiters are accepted.

Your contract names the columns explicitly:

```yaml
capture:
  time_column: Time

signals:
  vdd:
    column: VDD
  en:
    column: EN
```

This is the easiest format to create from Python, MATLAB, LabVIEW or custom acquisition code.

## 2. Siglent SDS800X HD per-channel CSV

Siglent SDS800X HD exports one file per channel with metadata followed by:

```text
Second,Value
...
```

and a metadata field such as:

```text
Source,CH2
```

Pass the files as one group:

```bash
powercontract check usr_wf_C1_data.csv power.yaml \
  --with usr_wf_C2_data.csv \
  --with usr_wf_C3_data.csv
```

The contract maps signals to the embedded source names:

```yaml
signals:
  vin:
    column: CH1
  vdd:
    column: CH2
  en:
    column: CH3
```

PowerContract checks the shared time axis, record length, sample interval, units, relevant horizontal metadata and instrument identity when present.

This path is hardware-verified on an SDS824X HD.

## 3. Rigol sequence CSV

A common Rigol layout stores the sample number and keeps the time origin and sample interval in the second header row:

```text
X,CH1,CH2,Start,Increment,
Sequence,Volt,Volt,-1.200000e-05,2.000000e-08
0,3.28,0.16,
1,3.44,0.08,
...
```

PowerContract derives:

```text
time = Start + Sequence * Increment
```

Signal columns keep their names, for example `CH1` and `CH2`.

## 4. Source + units matrix

Some scope families export one shared time axis followed by several channels:

```text
Source,CH1,CH2
Second,Volt,Volt
-1.0e-6,3.08,0.004
-0.8e-6,3.00,0.004
...
```

PowerContract uses the first column as time and the names in the first row as signal sources.

This shape is documented for Teledyne LeCroy WaveAce-family CSV exports and appears in other scope tooling as well.

## 5. Paired XY columns

Another common Rigol-style layout gives every channel its own time/value pair:

```text
X(CH1),CH1,X(CH2),CH2
Second,Volt,Second,Volt
-1.0e-3,0.1,-1.0e-3,3.2
...
```

PowerContract requires the requested channels to have identical time axes before treating them as one capture.

## 6. Legacy metadata + XY

Some Tektronix and Teledyne LeCroy exports place metadata in the first three columns and waveform time/value data in columns four and five:

```text
Record Length,2500,Points,-0.005,0.012
Sample Interval,4e-7,s,-0.0049996,0.018
Trigger Point,1250,Samples,-0.0049992,0.012
...
```

This format contains one waveform and may not contain a channel name. PowerContract therefore accepts it only for a single-signal contract, using the neutral column alias `Value`:

```yaml
signals:
  rail:
    column: Value
```

For multi-rail sequencing, prefer a multi-channel export or normalize the traces into one table CSV.

## Multi-file groups

In v0.1, automatic multi-file grouping is intentionally limited to Siglent SDS800X HD per-channel exports because those files carry enough metadata to identify and cross-check the channels.

For other vendors, prefer one multi-channel CSV.

This is deliberate. PowerContract should not silently guess that unrelated files came from the same acquisition.
