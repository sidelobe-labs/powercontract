# Oscilloscope vendor notes

Export waveform data rather than a screenshot. Before writing a contract, inspect the first 10–20 lines of the CSV and use the names that are actually present in the file.

CSV layouts vary between model families and firmware versions. The table below describes file layouts covered by PowerContract, not every model sold by each vendor.

## Compatibility

| Vendor / format | Project status | Recommended input |
| --- | --- | --- |
| Siglent SDS800X HD per-channel CSV | Tested with hardware from this series | grouped per-channel CSV |
| Older Siglent `Source` + units CSV | Parser tested against public examples | single multi-channel CSV |
| Teledyne LeCroy WaveAce `Source` / `Second` / `Volt` CSV | Parser tested against the documented layout | single CSV |
| Rigol sequence CSV with `Start` / `Increment` | Parser tested against public examples | single CSV |
| Rigol paired XY CSV | Parser tested against public examples | single CSV |
| Tektronix five-column CSV | Parser tested against the vendor-documented layout | single trace with `column: Value` |
| Keysight InfiniiVision multi-channel CSV | Normal table CSV when named headers are present | one multi-channel CSV |

## Siglent

### SDS800X HD

This is the only vendor-specific path currently tested with physical hardware in this project.

Save waveform data as CSV. The scope writes separate files for displayed analog channels.

Example:

```bash
powercontract check usr_wf_C1_data.csv contract.yaml \
  --with usr_wf_C2_data.csv \
  --with usr_wf_C3_data.csv
```

The parser uses the embedded `Source` value and checks that the supplied files have compatible timing and acquisition metadata.

For captures too large for CSV, SDS800X HD may ask for binary export. Binary input is not part of PowerContract v0.1.

### Older Siglent CSV

Older Siglent families are publicly documented and observed with a layout such as:

```text
Source,CH1,CH2
Second,Volt,Volt
...
```

PowerContract accepts this as a single multi-channel CSV through the source+units parser.

## Teledyne LeCroy WaveAce

The WaveAce 1000/2000 manual describes CSV output containing `Source`, `Second`, and `Volt`, with optional fields such as record length, sample interval, units, scale, model, serial number, and software version.

PowerContract accepts the two-row source+units waveform table described above. This parser has not been tested against a physical WaveAce in this project. WaveAce's optional parameter-save mode can add metadata, so inspect the first lines of the exported file before assuming it matches this layout.

## Rigol

Rigol model families do not all use one CSV layout.

PowerContract covers two formats seen in public Rigol tooling and captures.

### Sequence + Start/Increment

```text
X,CH1,CH2,Start,Increment,
Sequence,Volt,Volt,-5.999998e-02,2.000000e-05
0,3.28,0.16,
1,3.44,0.08,
```

PowerContract reconstructs time from `Start`, `Sequence`, and `Increment`.

### Paired XY

```text
X(CH1),CH1,X(CH2),CH2
Second,Volt,Second,Volt
...
```

PowerContract requires the requested channels to share the same time axis.

Rigol manuals confirm CSV waveform export, but the exact layout depends on model and generation. Inspect the file rather than assuming one of these formats.

## Keysight / Agilent InfiniiVision

Keysight documents two different text export approaches:

- CSV: one spreadsheet-style file containing all displayed analog channels;
- ASCII XY: separate files for individual channels and other waveform sources.

For PowerContract, prefer CSV because a single file preserves the multi-channel relationship.

If the CSV contains a header row with time and waveform labels, use the normal table loader:

```yaml
capture:
  time_column: Time

signals:
  vdd:
    column: VDD
  en:
    column: EN
```

Use the exact labels from your file.

Segmented-memory exports may contain multiple segments. PowerContract v0.1 does not combine or reinterpret them.

## Tektronix

Tektronix documents a five-column CSV layout:

- parameter name;
- parameter value;
- parameter unit;
- sample time;
- sample value.

PowerContract reads the time and sample value columns for a single waveform.

Use:

```yaml
signals:
  rail:
    column: Value
```

For multi-rail sequencing, use a multi-channel table export if the instrument provides one, or normalize separate traces into one table before running PowerContract.

## Other instruments

If a file already contains one time column and named signal columns, use the normal table CSV loader. No vendor-specific parser is needed.

A portable layout is:

```text
Time,VDD_5V,VDD_3V3,EN
-0.002,0.0,0.0,0.0
...
```

This is also the recommended output from custom SCPI scripts, pandas, MATLAB, or LabVIEW.

## References

The compatibility notes above were checked against these sources:

- Siglent SDS800X HD user manual: https://int.siglent.com/u_file/download/24_02_20/SDS800X_HD_UserManual_EN01A.pdf
- Rigol DS1000Z-E user guide: https://tw.rigol.com/tw/Images/DS1000ZEUserGuideEN_tcm17-2861.pdf
- Rigol MSO8000A user guide: https://www.rigol.com/dam/global/downloads/brochures/en/user-manual/oscillosopes/MSO8000A_UserGuide_EN.pdf
- Keysight InfiniiVision 3000 X-Series programming guide: https://www.keysight.com/us/en/assets/9018-06894/programming-guides/9018-06894.pdf
- Tektronix DSA/DPO70000 and MSO/DPO5000 printable help, CSV text format: https://download.tek.com/manual/DSA-DPO70000D-MSO-DPO-DSA70000C-DPO7000C-and-MSO-DPO5000-.pdf
- Teledyne LeCroy WaveAce 1000/2000 operator's manual: https://cdn.teledynelecroy.com/files/manuals/waveace-1000_2000-oscilloscopes-operators-manual.pdf
- Rigol paired-XY example in pyRigolWFM: https://github.com/mabl/pyRigolWFM
- Rigol sequence-layout parser example: https://github.com/vidavidorra/rigol-csv-analyser

If your model produces a different layout, include the model, firmware version, export mode, and the first 20 sanitized lines when reporting it.
