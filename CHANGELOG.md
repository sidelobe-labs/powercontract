# Changelog

## Unreleased

### Fixed

- reject non-empty fields after the declared channels in Rigol sequence CSV sample rows instead of ignoring them.
- reject incomplete or non-numeric samples in Tektronix five-column CSV files instead of skipping them.

## 0.1.2 - 2026-10-20

### Fixed

- reject Siglent CSV sample rows with more fields than the declared two-column header.
- reject NaN, infinity and overflowing timing values before evaluating a capture;
- reject duplicate YAML keys instead of silently replacing contract values; preserve anchors and merge overrides.
- measure the first complete rise or fall after an edge that began before the capture.

## 0.1.1 - 2026-10-14

### Changed

- made PyPI the default installation path in user documentation;
- added PyPI, Python, CI, and license badges to the README;
- made README documentation links work from both GitHub and PyPI;
- updated release documentation for the post-0.1.0 workflow;
- added PyPI, documentation, and changelog project links to package metadata;
- clarified the README introduction and package summary;
- checked links in the built package description before publishing.

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
