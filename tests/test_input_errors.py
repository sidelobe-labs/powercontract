import pytest
import yaml

from powercontract.cli import main


def spec():
    return {
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"v": {"column": "C1", "nominal": 3.3}},
        "events": {"ready": {"signal": "v", "direction": "above", "threshold": 1}},
        "requirements": [{"id": "limit", "type": "max_value", "signal": "v", "value": 4}],
    }


@pytest.mark.parametrize("value", [[], {}])
@pytest.mark.parametrize("field", ["event_signal", "type", "signal", "from", "to", "delay_from", "delay_to", "rise_signal"])
def test_collection_references_are_cli_input_errors(tmp_path, capsys, field, value):
    data = spec()
    req = data["requirements"][0]
    if field == "event_signal":
        data["events"]["ready"]["signal"] = value
    elif field.startswith("delay_"):
        req.update(type="delay", **{"from": "ready", "to": "ready", "max": "1s"})
        req.pop("signal"); req.pop("value")
        req[field.removeprefix("delay_")] = value
    elif field == "rise_signal":
        req.update(type="rise_time", signal=value, max="1s")
        req.pop("value")
    else:
        req[field] = value
    contract = tmp_path / "contract.yaml"
    contract.write_text(yaml.safe_dump(data))
    assert main(["check", str(tmp_path / "missing.csv"), str(contract)]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "Traceback" not in captured.err
    assert "PASS" not in captured.out


@pytest.mark.parametrize("version", [True, 1.0])
def test_contract_version_requires_integer(tmp_path, capsys, version):
    data = spec(); data["version"] = version
    path = tmp_path / "contract.yaml"; path.write_text(yaml.safe_dump(data))
    assert main(["check", "missing.csv", str(path)]) == 2
    assert "version must be 1" in capsys.readouterr().err


def test_overflowing_numeric_contract_is_cli_error(tmp_path, capsys):
    data = spec(); data["signals"]["v"]["nominal"] = 10 ** 400
    path = tmp_path / "contract.yaml"; path.write_text(yaml.safe_dump(data))
    assert main(["check", "missing.csv", str(path)]) == 2
    assert "nominal" in capsys.readouterr().err


@pytest.mark.parametrize("target", ["contract", "capture"])
def test_invalid_utf8_is_cli_error_without_report(tmp_path, capsys, target):
    contract = tmp_path / "contract.yaml"; contract.write_text(yaml.safe_dump(spec()))
    capture = tmp_path / "capture.csv"; capture.write_text("Time,C1\n0,0\n1,1\n")
    (contract if target == "contract" else capture).write_bytes(b"\xff")
    report = tmp_path / "report.json"
    assert main(["check", str(capture), str(contract), "--json", str(report)]) == 2
    assert "UTF-8" in capsys.readouterr().err
    assert not report.exists()
