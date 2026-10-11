# Changelog

## 0.1.0 - 2026-10-11

Initial release.

### Added

- strict YAML contracts for electrical requirements;
- threshold events with interpolation and optional stability windows;
- delay, minimum/maximum voltage, rise-time, and fall-time checks;
- `PASS`, `FAIL`, and `INDETERMINATE` results with measured margin;
- explicit per-requirement measurement uncertainty;
- optional requirement `source`;
- CLI output and versioned JSON reports;
- normal table CSV input;
- grouped Siglent SDS800X HD per-channel CSV input;
- source+units, Rigol sequence, Rigol paired-XY, and Tektronix five-column CSV parsers;
- Siglent group checks for time axis, sample interval, record length, metadata, and instrument identity;
- ESP32-C3 power-up example;
- user documentation for setup, contracts, input formats, vendor notes, CI, and troubleshooting;
- Python 3.11 and 3.12 CI;
- wheel and sdist build checks plus clean wheel-install smoke tests.
