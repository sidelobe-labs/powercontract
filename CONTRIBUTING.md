# Contributing

Thanks for taking the time to improve PowerContract.

PowerContract has a narrow scope: it evaluates measured waveform data against declared electrical requirements. Changes should support that job directly.

## Development setup

Clone the repository and install the development dependencies:

```bash
git clone https://github.com/sidelobe-labs/powercontract.git
cd powercontract
python -m pip install -e '.[dev]'
pytest
```

Before opening a pull request, also run:

```bash
powercontract check examples/boot.csv examples/boot.yaml
powercontract check \
  examples/esp32-c3/usr_wf_C2_data.csv \
  examples/esp32-c3/contract.yaml \
  --with examples/esp32-c3/usr_wf_C3_data.csv
```

## Changes to measurement semantics

A change to event detection, interpolation, stability windows, uncertainty, margins, or requirement evaluation needs a focused test that shows the intended behavior.

Do not change an existing measurement rule only to make one capture pass. If a real waveform exposes an edge case, include a reduced fixture that reproduces it.

## New requirement types

Please open an issue before implementing a new requirement type.

A useful proposal should include:

- the electrical requirement as it appears in a datasheet or engineering specification;
- why the existing requirement types cannot express it;
- an example capture or reduced fixture;
- the expected measured quantity and units.

The project intentionally avoids a general expression language.

## New capture formats

For a new oscilloscope or CSV layout, include:

- vendor and model;
- firmware version when known;
- export mode used;
- the first 20 sanitized lines of the file;
- expected time and signal mapping;
- a small test fixture.

Do not commit confidential captures or device identifiers.

Prefer a normal table CSV when a simple external conversion is enough. Vendor-specific parsing should be added only when it removes a real interoperability problem.

## Documentation

Update the relevant file under `docs/` when user-facing behavior changes.

README should remain a short entry point. Detailed format and vendor notes belong under `docs/`.

## Pull requests

Keep pull requests focused.

A pull request should normally include:

- tests for behavioral changes;
- documentation for user-facing changes;
- an entry under `Unreleased` in `CHANGELOG.md` when the change affects users.

CI must pass before merge.

## Project scope

PowerContract is not intended to become:

- a waveform viewer;
- a protocol decoder;
- a general signal-processing package;
- an instrument-control framework;
- a golden-waveform comparison tool;
- an automatic datasheet parser.
