import hashlib
import json
from pathlib import Path

import pytest

from powercontract import __version__
from powercontract.cli import main


def write_contract(path, *, column="V", value=4):
    content = (
        "version: 1\r\ncapture: {}\r\n"
        f"signals:\r\n  rail: {{column: {column}}}\r\n"
        "requirements:\r\n"
        f"  - {{id: MAX, type: max_value, signal: rail, value: {value}}}\r\n"
    ).encode("utf-8-sig")
    path.write_bytes(content)
    return content


def write_siglent(path, source):
    content = (
        "Record Length,Analog:2\nSample Interval,0.001\n"
        "Vertical Units,V\nHorizontal Units,s\n"
        f"Source,{source}\nSecond,Value\n-0.001,1\n0,2\n"
    ).encode()
    path.write_bytes(content)
    return content


@pytest.mark.parametrize("limit, exit_code", [(4, 0), (1, 1)])
def test_report_records_exact_input_bytes_and_capture_range(tmp_path, limit, exit_code):
    contract = tmp_path / "private-contract.yaml"
    capture = tmp_path / "private-capture.csv"
    report = tmp_path / "report.json"
    contract_bytes = write_contract(contract, value=limit)
    capture_bytes = b"\xef\xbb\xbfTime,V\r\n-0.001,1\r\n0,2\r\n0.003,3\r\n"
    capture.write_bytes(capture_bytes)

    assert main(["check", str(capture), str(contract), "--json", str(report)]) == exit_code

    payload = json.loads(report.read_text())
    assert payload["inputs"] == {
        "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
        "capture_sha256": [hashlib.sha256(capture_bytes).hexdigest()],
    }
    assert payload["capture"] == {"sample_count": 3, "time_range_s": [-0.001, 0.003]}
    assert payload["schema_version"] == 1
    assert payload["powercontract_version"] == __version__
    assert payload["passed"] is (exit_code == 0)
    assert "private-" not in report.read_text()
    assert str(tmp_path) not in report.read_text()


def test_report_hashes_all_capture_files_in_argument_order(tmp_path):
    contract = tmp_path / "contract.yaml"
    write_contract(contract, column="CH2")
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first_bytes = write_siglent(first, "CH2")
    second_bytes = write_siglent(second, "CH1")
    report = tmp_path / "report.json"

    assert main(["check", str(first), str(contract), "--with", str(second), "--json", str(report)]) == 0

    payload = json.loads(report.read_text())
    assert payload["inputs"]["capture_sha256"] == [
        hashlib.sha256(first_bytes).hexdigest(),
        hashlib.sha256(second_bytes).hexdigest(),
    ]
    assert payload["capture"] == {"sample_count": 2, "time_range_s": [-0.001, 0.0]}


@pytest.mark.parametrize("format", ["table", "siglent", "siglent-group"])
def test_inputs_are_read_once_and_hashed_before_they_can_change(tmp_path, monkeypatch, format):
    contract = tmp_path / "contract.yaml"
    contract_bytes = write_contract(contract, column="V" if format == "table" else "CH1")
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    if format != "table":
        first_bytes = write_siglent(first, "CH1")
    else:
        first_bytes = b"Time,V\n0,1\n0.001,2\n"
        first.write_bytes(first_bytes)
    expected = {contract: contract_bytes, first: first_bytes}
    if format == "siglent-group":
        expected[second] = write_siglent(second, "CH2")
    reads = []
    original_read = Path.read_bytes

    def read_then_replace(path):
        content = original_read(path)
        if path in expected:
            reads.append(path)
            path.write_bytes(b"changed after read")
        return content

    monkeypatch.setattr(Path, "read_bytes", read_then_replace)
    report = tmp_path / "report.json"
    arguments = ["check", str(first), str(contract), "--json", str(report)]
    if format == "siglent-group":
        arguments.extend(["--with", str(second)])

    assert main(arguments) == 0

    assert reads == list(expected)
    payload = json.loads(report.read_text())
    assert payload["inputs"]["contract_sha256"] == hashlib.sha256(contract_bytes).hexdigest()
    assert payload["inputs"]["capture_sha256"] == [
        hashlib.sha256(content).hexdigest() for path, content in expected.items() if path != contract
    ]
    assert payload["findings"][0]["measured"] == 2
