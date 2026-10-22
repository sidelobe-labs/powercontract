import json

import pytest

from powercontract.cli import main


def check_legacy_capture(tmp_path, middle_row, record_length=3):
    capture = tmp_path / "capture.csv"
    capture.write_text(
        f"Record Length,{record_length},Points,0,3.3\n"
        + middle_row + "\n"
        + "Sample Interval,0.001,s,0.002,3.3\n",
        encoding="utf-8",
    )
    contract = tmp_path / "contract.yaml"
    contract.write_text(
        "version: 1\n"
        "capture: {}\n"
        "signals:\n"
        "  rail: {column: Value}\n"
        "requirements:\n"
        "  - {id: MAX, type: max_value, signal: rail, value: 3.6}\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    return main(["check", str(capture), str(contract), "--json", str(report)])


@pytest.mark.parametrize("sample", [
    "0.001,invalid",
    "invalid,3.3",
    "0.001",
    "0.001,",
    ",3.3",
])
def test_legacy_capture_rejects_damaged_sample(tmp_path, capsys, sample):
    result = check_legacy_capture(tmp_path, f"Trigger Point,1,Samples,{sample}")

    assert result == 2
    output = capsys.readouterr()
    assert "row 2 contains invalid legacy XY data" in output.err
    assert "PASS" not in output.out
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize("middle_row", [
    "Trigger Point,1,Samples",
    "Trigger Point,1,Samples,,",
    "",
])
def test_legacy_capture_allows_rows_without_waveform_data(tmp_path, capsys, middle_row):
    assert check_legacy_capture(tmp_path, middle_row, record_length=2) == 0

    assert "PASS" in capsys.readouterr().out
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["findings"][0]["measured"] == 3.3
