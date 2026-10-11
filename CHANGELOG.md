# Changelog

All notable changes to PowerContract are documented here.

## 0.1.0 - 2026-10-11

Initial release.

### Added

- YAML electrical contracts with strict, typo-intolerant parsing.
- Named threshold events with linear interpolation and optional stability windows.
- Delay, minimum/maximum voltage, rise-time, and fall-time requirements.
- PASS, FAIL, and INDETERMINATE verdicts with measured worst-case margin.
- Explicit per-requirement measurement uncertainty.
- Optional requirement provenance through the `source` field.
- Human-readable CLI output and versioned JSON reports.
- Ordinary CSV input with configurable columns.
- Native grouped CSV input for Siglent SDS800X HD per-channel exports.
- Common oscilloscope CSV families: Rigol sequence/paired-XY, source+units
  multi-channel CSV, and legacy metadata+XY single-trace exports.
- Generic table CSV compatibility for vendor exports and custom acquisition scripts.
- Siglent capture-integrity checks for shared time axes, declared sample interval,
  record length, duplicate metadata, and instrument identity.
- Versioned documentation covering setup, contracts, formats, vendor exports, CI,
  and troubleshooting.
- Datasheet-backed ESP32-C3 power-up example.
- Python 3.11 and 3.12 CI.
- Wheel/sdist build validation and clean wheel-install smoke tests.
