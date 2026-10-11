# Input formats

PowerContract reads CSV. It chooses a parser from the structure of the file, not from the filename or oscilloscope brand.

## Compatibility labels

The vendor notes use three descriptions:

**Tested with hardware** means the project has been run against a real export from that instrument family.

**Parser tested** means automated tests cover the documented or publicly observed file layout, but the project has not tested that path on the physical instrument.

**Normal table CSV** means no vendor-specific parser is needed.

## 1. Normal table CSV

This is the preferred interchange format:

```text
Time,VDD,EN
-0.001,0.0,0.0
0.000,3.2,0.0
0.001,3.3,3.3
```

The header may appear after a metadata preamble. PowerContract searches the first 100 lines for the configured columns.

Comma, semicolon, and tab delimiters are accepted.

Example mapping:

```yaml
capture:
  time_column: Time

signals:
  vdd:
    column: VDD
  en:
    column: EN
```

Use this format when you control the export or convert data in Python, MATLAB, LabVIEW, or another script.

## 2. Siglent SDS800X HD per-channel CSV

SDS800X HD exports one CSV per analog channel. Each file contains metadata, including a `Source` field, followed by:

```text
Second,Value
...
```

Pass all files from the acquisition explicitly:

```bash
powercontract check usr_wf_C1_data.csv power.yaml \
  --with usr_wf_C2_data.csv \
  --with usr_wf_C3_data.csv
```

Map signals to the embedded source names:

```yaml
signals:
  vin:
    column: CH1
  vdd:
    column: CH2
  en:
    column: CH3
```

PowerContract checks the shared time axis, record length, sample interval, units, horizontal metadata, and instrument identity fields when present.

This layout has been tested using an export from hardware in the SDS800X HD series.

## 3. Source + units CSV

WaveAce documentation and public exports from older Siglent families describe a shared-time-axis layout such as:

```text
Source,CH1,CH2
Second,Volt,Volt
-1.0e-6,3.08,0.004
-0.8e-6,3.00,0.004
...
```

The first column is time. The remaining names in the first row are signal sources.

This parser is covered by format fixtures. It has not been tested on physical WaveAce hardware in this project, and vendor options that add extra parameter rows can change the exact file layout.

## 4. Rigol sequence CSV

A Rigol layout used by several tools and captures stores a sample sequence number and places the time origin and interval in the second row:

```text
X,CH1,CH2,Start,Increment,
Sequence,Volt,Volt,-1.200000e-05,2.000000e-08
0,3.28,0.16,
1,3.44,0.08,
...
```

PowerContract calculates:

```text
time = Start + Sequence * Increment
```

Signal names remain `CH1`, `CH2`, and so on.

## 5. Rigol paired XY CSV

Another Rigol layout gives each channel a time/value pair:

```text
X(CH1),CH1,X(CH2),CH2
Second,Volt,Second,Volt
-1.0e-3,0.1,-1.0e-3,3.2
...
```

PowerContract checks that the requested channels use the same time axis before combining them into one capture.

## 6. Tektronix five-column CSV

Tektronix documents a CSV format in which:

- columns 1–3 contain metadata;
- column 4 contains sample time;
- column 5 contains sample value.

Example:

```text
Record Length,2500,Points,-0.005,0.012
Sample Interval,4e-7,s,-0.0049996,0.018
Trigger Point,1250,Samples,-0.0049992,0.012
...
```

The format contains one waveform and does not provide a stable channel name in the waveform columns. Use a single-signal contract with `column: Value`:

```yaml
signals:
  rail:
    column: Value
```

For multi-rail checks, export one multi-channel table or normalize separate traces into one table before evaluation.

## Multi-file input

Automatic multi-file grouping is limited to the Siglent SDS800X HD per-channel format in v0.1.

For other formats, use one multi-channel CSV or normalize the files first. PowerContract does not infer that unrelated files came from the same acquisition.
