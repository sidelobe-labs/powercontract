# Repeated acquisitions

Use `powercontract batch runs.json contract.yaml --json results.json` to check independent acquisitions against the same contract. Each acquisition uses the existing `check` evaluator. A capture list groups channels from one acquisition; it does not concatenate separate runs. Multi-file groups currently require Siglent per-channel CSV.

```json
{
  "version": 1,
  "runs": [
    {"label": "cold-start-1", "captures": ["captures/start-1.csv"]},
    {"label": "cold-start-2", "captures": ["captures/start-2.csv"]}
  ]
}
```

Paths are relative to the manifest, and labels must be unique. Runs are processed sequentially. Reports include each label, exact-byte input hashes, sample count, time range, events and findings. A run with invalid capture input records `ERROR`; subsequent runs still execute. An invalid contract or manifest stops before evaluation. The report cannot replace a manifest, contract or capture input.

Exit status is 0 when every run passes, 1 when any run fails or is indeterminate, and 2 for any input or report-writing error. A successfully written aggregate retains completed results even when another run has an input error. The single `check` report format is unchanged. Reports can contain manifest labels and error paths; choose labels and report destinations accordingly.
