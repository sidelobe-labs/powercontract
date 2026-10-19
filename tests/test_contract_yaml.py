import json
from textwrap import dedent

import pytest

from powercontract.cli import main


_CONTRACT = dedent("""\
    version: 1
    capture: {time_column: Time}
    signals:
      vdd: {column: C1, nominal: 3.3}
    events:
      vdd_valid: {signal: vdd, direction: above, threshold: 1.5}
    requirements:
      - id: rise
        type: rise_time
        signal: vdd
        max: 1 ms
    """)


def _check(tmp_path, text):
    capture = tmp_path / "capture.csv"
    capture.write_text("Time,C1\n0,0\n0.001,3.3\n")
    contract = tmp_path / "contract.yaml"
    contract.write_text(text)
    report = tmp_path / "report.json"
    return main(["check", str(capture), str(contract), "--json", str(report)])


@pytest.mark.parametrize(("before", "after", "key"), [
    ("version: 1", "version: 1\nversion: 1", "version"),
    ("time_column: Time", "time_column: Time, time_column: Time", "time_column"),
    ("vdd: {column: C1, nominal: 3.3}", "vdd: {column: C1}\n  vdd: {column: C1, nominal: 3.3}", "vdd"),
    ("column: C1, nominal: 3.3", "column: C1, column: C1, nominal: 3.3", "column"),
    ("threshold: 1.5", "threshold: 1.5, threshold: 2.0", "threshold"),
    ("max: 1 ms", "max: 100 us\n    max: 1 ms", "max"),
], ids=["root", "capture", "signal-name", "signal-field", "event-field", "requirement-limit"])
def test_cli_rejects_duplicate_contract_keys(tmp_path, capsys, before, after, key):
    assert _check(tmp_path, _CONTRACT.replace(before, after)) == 2

    output = capsys.readouterr()
    assert f"duplicate key {key!r}" in output.err
    assert "line " in output.err
    assert "column " in output.err
    assert "PASS" not in output.out
    assert not (tmp_path / "report.json").exists()


def test_duplicate_keys_in_inline_merge_source_are_rejected(tmp_path, capsys):
    text = _CONTRACT.split("requirements:")[0] + dedent("""\
        requirements:
          - <<: {id: rise, type: rise_time, signal: vdd, max: 100 us, max: 1 ms}
        """)

    assert _check(tmp_path, text) == 2
    assert "duplicate key 'max'" in capsys.readouterr().err


def test_duplicate_merge_keys_are_rejected(tmp_path, capsys):
    text = _CONTRACT.split("requirements:")[0] + dedent("""\
        requirements:
          - id: rise
            <<: {type: rise_time, signal: vdd}
            <<: {max: 1 ms}
        """)

    assert _check(tmp_path, text) == 2
    assert "duplicate key '<<'" in capsys.readouterr().err


def test_literal_merge_symbol_and_merge_key_are_distinct(tmp_path, capsys):
    text = _CONTRACT.replace(
        "vdd: {column: C1, nominal: 3.3}",
        '<<: {vdd: {column: C1, nominal: 3.3}}\n  "<<": {column: C1}',
    )

    assert _check(tmp_path, text) == 0
    assert not capsys.readouterr().err


def test_anchors_and_explicit_merge_overrides_remain_supported(tmp_path, capsys):
    text = dedent("""\
        version: 1
        capture: {}
        signals:
          vdd: &signal {column: C1, nominal: 3.3}
          mirror: *signal
        requirements:
          - &rise
            id: strict
            type: rise_time
            signal: vdd
            max: 100 us
          - <<: *rise
            id: relaxed
            signal: mirror
            max: 1 ms
          - <<: *rise
            id: reused
            max: 2 ms
        """)

    assert _check(tmp_path, text) == 1

    findings = json.loads((tmp_path / "report.json").read_text())["findings"]
    assert [(item["id"], item["status"]) for item in findings] == [
        ("strict", "FAIL"), ("relaxed", "PASS"), ("reused", "PASS"),
    ]
    assert not capsys.readouterr().err


def test_merge_sequence_keeps_the_first_mapping_precedence(tmp_path, capsys):
    text = _CONTRACT.split("requirements:")[0] + dedent("""\
        requirements:
          - id: rise
            <<: [{type: rise_time, signal: vdd, max: 1 ms}, {max: 100 us}]
        """)

    assert _check(tmp_path, text) == 0
    finding = json.loads((tmp_path / "report.json").read_text())["findings"][0]
    assert finding["maximum"] == pytest.approx(0.001)
    assert not capsys.readouterr().err
