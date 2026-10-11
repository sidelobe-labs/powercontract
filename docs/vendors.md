# Oscilloscope vendor guide

The safest workflow is always the same:

1. stop or single-shot the acquisition;
2. export waveform data, not a screenshot;
3. keep time in seconds and amplitude in volts;
4. inspect the first 10–20 lines;
5. map the actual source names in the contract.

The notes below describe formats, not every model a vendor has ever shipped.

## Compatibility matrix

| Vendor / format | Status | Recommended path |
| --- | --- | --- |
| Siglent SDS800X HD per-channel CSV | **Hardware-verified** | native grouped CSV |
| Rigol sequence CSV with `Start` / `Increment` | **Format-verified** | native single-file parser |
| Rigol paired XY CSV | **Format-verified** | native single-file parser |
| Teledyne LeCroy WaveAce source+units CSV | **Format-verified** | native single-file parser |
| Tektronix legacy five-column CSV | **Format-verified** | single trace, `column: Value` |
| Teledyne LeCroy legacy header+XY CSV | **Format-verified** | single trace, `column: Value` |
| Keysight InfiniiVision multi-column CSV | **Generic CSV** | map the exported table headers |
| Python / pandas / MATLAB / LabVIEW CSV | **Generic CSV** | export one time column plus named signal columns |

“Format-verified” means the parser is tested against a fixture that matches vendor documentation or a publicly observed export shape. It is not a claim that every scope in that vendor's catalogue emits exactly the same CSV.

## Siglent

### SDS800X HD

This is the strongest compatibility path today because it was developed against real SDS824X HD captures.

Save waveform data as CSV. The scope writes one file per displayed analog channel.

Run:

```bash
powercontract check usr_wf_C1_data.csv contract.yaml \
  --with usr_wf_C2_data.csv \
  --with usr_wf_C3_data.csv
```

The parser uses the embedded `Source` field and rejects groups with incompatible time axes or acquisition metadata.

For deep-memory captures, the scope may ask you to save binary data instead. PowerContract v0.1 does not make the Siglent binary format part of its public input contract; use CSV for reproducible checks.

## Rigol

Rigol has used more than one CSV layout across product generations.

PowerContract supports two useful families directly.

### Sequence + Start/Increment

Typical shape:

```text
X,CH1,CH2,Start,Increment,
Sequence,Volt,Volt,-5.999998e-02,2.000000e-05
0,3.28,0.16,
1,3.44,0.08,
```

The first field is a sample sequence number. PowerContract reconstructs the time axis from `Start` and `Increment`.

### Paired XY

Typical shape:

```text
X(CH1),CH1,X(CH2),CH2
Second,Volt,Second,Volt
...
```

Each signal has a time/value pair. PowerContract verifies that the requested channels share the same time axis.

Rigol's manuals document CSV waveform saving across several families, but exact layouts differ by generation. If your file does not resemble either shape, check whether it is already a normal table CSV before opening an issue.

## Keysight / Agilent InfiniiVision

InfiniiVision scopes can save multi-channel CSV and separate ASCII XY files.

For PowerContract, prefer **multi-channel CSV**. It keeps all rails in one file and avoids having to infer whether several separate files came from the same acquisition.

Keysight documents that CSV stores displayed waveforms as multiple columns and uses waveform labels as headers on modern InfiniiVision families. If those headers are present, use the normal table loader:

```yaml
capture:
  time_column: Time

signals:
  vdd:
    column: VDD
  en:
    column: EN
```

Use the exact labels in your file; do not copy the example blindly.

Segmented-memory CSV can contain repeated segments. PowerContract v0.1 does not join or reinterpret segments automatically.

## Tektronix

Tektronix has several CSV generations.

A long-running legacy format uses:

- metadata in columns 1–3;
- time in column 4;
- amplitude in column 5.

PowerContract recognizes this layout for a single waveform:

```yaml
signals:
  rail:
    column: Value
```

This is useful for rise/fall and voltage-limit checks on one trace.

For multi-rail sequencing, use a Tektronix export that produces one normal multi-channel table, or normalize the individual traces into one table before evaluation. PowerContract does not guess that several unnamed CSV files came from one acquisition.

## Teledyne LeCroy

Two useful layouts are supported.

WaveAce-family exports can use a multi-channel source/unit header:

```text
Source,CH1,CH2
Second,Volt,Volt
...
```

This works directly for sequencing checks.

Some MAUI/XStream-era ASCII exports use metadata in the first columns with time and amplitude later in the row, similar to the legacy Tektronix shape. Those are accepted as a single trace using `column: Value`.

## Generic exports and scripts

If your scope is not listed, PowerContract does not need to know its brand.

The most portable CSV looks like:

```text
Time,VDD_5V,VDD_3V3,EN
-0.002,0.0,0.0,0.0
...
```

That format is easy to produce from:

- pandas;
- MATLAB;
- LabVIEW;
- SCPI acquisition scripts;
- vendor conversion utilities.

If a vendor-native parser would only duplicate a simple conversion into this shape, keep the conversion outside PowerContract.

## References

Vendor format notes were checked against the manufacturers' documentation where available:

- Siglent SDS800X HD user documentation: https://www.siglent.com/resource-detail/1297/
- Rigol support and manuals: https://www.rigolna.com/support/
- Keysight InfiniiVision user manuals: https://www.keysight.com/
- Tektronix oscilloscope manuals and support: https://www.tek.com/
- Teledyne LeCroy oscilloscope manuals: https://www.teledynelecroy.com/support/techlib/productmanuals.aspx?cat=1&type=2

If a specific model produces a different CSV, open an issue with the model, firmware version, the first 20 lines of a sanitized export, and the expected signal mapping.
