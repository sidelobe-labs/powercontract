from textwrap import dedent

import pytest

from powercontract.capture import load_capture
from powercontract.cli import main
from powercontract.errors import CaptureError
from powercontract.evaluate import evaluate
from powercontract.spec import parse_contract


def _contract(include_second_channel=False):
    signals = {"rail": {"column": "CH1"}}
    if include_second_channel:
        signals["enable"] = {"column": "CH2"}
    return parse_contract({
        "version": 1,
        "capture": {},
        "signals": signals,
        "requirements": [{"id": "MAX", "type": "max_value", "signal": "rail", "value": 3.6}],
    })


def _capture(tmp_path, first_row):
    path = tmp_path / "rigol.csv"
    path.write_text(
        "X,CH1,CH2,Start,Increment,\n"
        "Sequence,Volt,Volt,0,0.001\n"
        f"{first_row}\n"
        "1,3.3,3.3,\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("suffix", [",999", ",,999", ",,,999"], ids=["start", "increment", "past-header"])
def test_rigol_samples_reject_nonempty_fields_after_channels(tmp_path, suffix):
    path = _capture(tmp_path, "0,0,0" + suffix)

    with pytest.raises(CaptureError, match="row 3 has more fields than the Rigol sample columns"):
        load_capture(path, _contract())


@pytest.mark.parametrize("suffix", ["", ",", ",,", ",,,", ", , ,"])
@pytest.mark.parametrize("include_second_channel", [False, True])
def test_rigol_samples_accept_empty_metadata_placeholders(tmp_path, suffix, include_second_channel):
    path = _capture(tmp_path, "0,0,0" + suffix)
    contract = _contract(include_second_channel)

    capture = load_capture(path, contract)

    assert capture.time == (0.0, 0.001)
    assert capture.signals["rail"] == (0.0, 3.3)
    assert evaluate(contract, capture).passed


def test_cli_does_not_pass_a_rigol_sample_with_extra_values(tmp_path, capsys):
    path = _capture(tmp_path, "0,0,0,999")
    contract = tmp_path / "contract.yaml"
    contract.write_text(dedent("""\
        version: 1
        capture: {}
        signals:
          rail: {column: CH1}
        requirements:
          - {id: MAX, type: max_value, signal: rail, value: 3.6}
        """), encoding="utf-8")
    report = tmp_path / "report.json"

    assert main(["check", str(path), str(contract), "--json", str(report)]) == 2

    output = capsys.readouterr()
    assert "row 3 has more fields than the Rigol sample columns" in output.err
    assert "PASS" not in output.out
    assert not report.exists()
