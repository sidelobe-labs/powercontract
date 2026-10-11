# PowerContract documentation

PowerContract is small on purpose. It reads measured waveforms, evaluates electrical requirements, and reports whether the capture contains enough evidence to call each requirement a pass or a fail.

If this is your first time using it, start with [Getting started](getting-started.md).

## Guides

- [Getting started](getting-started.md) — from a scope export to the first verdict.
- [Writing contracts](contracts.md) — signals, events, requirements, uncertainty and provenance.
- [Input formats](input-formats.md) — the CSV shapes PowerContract understands.
- [Oscilloscope vendor guide](vendors.md) — practical export notes for Siglent, Rigol, Keysight, Tektronix and Teledyne LeCroy.
- [Using PowerContract in CI](ci.md) — exit codes, JSON reports and a GitHub Actions example.
- [Troubleshooting](troubleshooting.md) — common parser and contract errors.

## What PowerContract is not

PowerContract is not a waveform viewer, a protocol decoder or an oscilloscope-control framework. It does not try to replace the analysis software that ships with a scope.

The boundary is simple:

> Did these measured signals satisfy these declared electrical requirements?

That is the job.
