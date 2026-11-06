import json

import pytest
import yaml

from powercontract.cli import main
from powercontract.evaluate import _TimePoint, _values_in_window


def setup_batch(tmp_path, runs):
    contract = tmp_path / "contract.yaml"
    contract.write_text(yaml.safe_dump({"version": 1, "capture": {}, "signals": {"v": {"column": "C1"}}, "requirements": [{"id": "limit", "type": "max_value", "signal": "v", "value": 4}]}))
    manifest = tmp_path / "runs.json"
    manifest.write_text(json.dumps({"version": 1, "runs": runs}))
    return ["batch", str(manifest), str(contract), "--json", str(tmp_path / "report.json")]


def test_batch_keeps_results_after_bad_run_and_resolves_relative_paths(tmp_path, monkeypatch):
    for name, value in [("pass", 3), ("fail", 5)]:
        (tmp_path / f"{name}.csv").write_text(f"Time,C1\n0,0\n1,{value}\n")
    args = setup_batch(tmp_path, [{"label": label, "captures": [label + ".csv"]} for label in ["pass", "missing", "fail"]])
    monkeypatch.chdir(tmp_path.parent)
    assert main(args) == 2
    reports = json.loads((tmp_path / "report.json").read_text())["runs"]
    assert [r["status"] for r in reports] == ["PASS", "ERROR", "FAIL"]
    assert len(reports[0]["inputs"]["capture_sha256"][0]) == 64
    assert reports[0]["capture"]["sample_count"] == 2
    assert reports[2]["findings"][0]["measured"] == 5


@pytest.mark.parametrize("value,code", [(3, 0), (5, 1)])
def test_batch_exit_codes(tmp_path, value, code):
    (tmp_path / "run.csv").write_text(f"Time,C1\n0,0\n1,{value}\n")
    args = setup_batch(tmp_path, [{"label": "one", "captures": ["run.csv"]}])
    assert main(args) == code


def test_batch_indeterminate_is_not_success(tmp_path):
    (tmp_path / "run.csv").write_text("Time,C1\n0,0\n1,3.9\n")
    args = setup_batch(tmp_path, [{"label": "one", "captures": ["run.csv"]}])
    contract = tmp_path / "contract.yaml"
    data = yaml.safe_load(contract.read_text()); data["requirements"][0]["uncertainty"] = 0.2
    contract.write_text(yaml.safe_dump(data))
    assert main(args) == 1
    assert json.loads((tmp_path / "report.json").read_text())["runs"][0]["status"] == "INDETERMINATE"


@pytest.mark.parametrize("runs", [[], [{}], [{"label": [], "captures": ["a"]}], [{"label": "a", "captures": []}], [{"label": "a", "captures": [2]}], [{"label": "a", "captures": ["x"]}] * 2])
def test_invalid_manifest_is_input_error(tmp_path, runs):
    args = setup_batch(tmp_path, runs)
    assert main(args) == 2
    assert not (tmp_path / "report.json").exists()


def test_batch_cannot_overwrite_capture(tmp_path):
    path = tmp_path / "run.csv"; path.write_text("Time,C1\n0,0\n1,1\n")
    args = setup_batch(tmp_path, [{"label": "one", "captures": ["run.csv"]}]); args[-1] = str(path)
    assert main(args) == 2
    assert path.read_text().startswith("Time,C1")


def test_voltage_window_streams_samples_and_interpolates_endpoints():
    values = _values_in_window((0., 1., 2., 3.), (0., 10., 20., 30.), _TimePoint(0, .25), _TimePoint(3, -.25))
    assert iter(values) is values
    assert list(values) == [2.5, 10., 20., 27.5]
