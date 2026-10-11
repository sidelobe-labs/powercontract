# PowerContract documentation

Start with [Getting started](getting-started.md) if you have a scope export and want to run your first check.

## User guides

- [Getting started](getting-started.md): install the tool, inspect a capture, write a contract, and run it.
- [Writing contracts](contracts.md): signals, events, requirements, uncertainty, and requirement sources.
- [Input formats](input-formats.md): CSV layouts accepted by the parser.
- [Oscilloscope vendor notes](vendors.md): export notes and compatibility limits for Siglent, Rigol, Keysight, Tektronix, and Teledyne LeCroy.
- [CI usage](ci.md): exit codes, JSON reports, and a GitHub Actions example.
- [Publishing a release](releasing.md): PyPI Trusted Publishing and the tag release flow.
- [Troubleshooting](troubleshooting.md): common input and contract errors.

PowerContract evaluates exported waveform data. It does not acquire waveforms, control instruments, or decode protocols.
