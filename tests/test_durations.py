from textwrap import dedent

import pytest

from powercontract.cli import main


def _check(tmp_path, contract_text):
    capture = tmp_path / "capture.csv"
    capture.write_text("Time,C1,C2\n0,0,0\n0.001,3.3,0\n0.002,3.3,3.3\n")
    contract = tmp_path / "contract.yaml"
    contract.write_text(contract_text)
    report = tmp_path / "report.json"
    return main(["check", str(capture), str(contract), "--json", str(report)])


@pytest.mark.parametrize("field", ["min", "max", "uncertainty", "stable_for"])
@pytest.mark.parametrize(
    "value",
    [".nan", ".inf", "-.inf", "9" * 400, "9" * 400 + " ms"],
    ids=["nan", "infinity", "negative-infinity", "integer-overflow", "string-overflow"],
)
def test_cli_rejects_non_finite_durations(tmp_path, capsys, field, value):
    stable_for = value if field == "stable_for" else "0"
    requirement_fields = f"    {field}: {value}\n" if field != "stable_for" else ""
    if field not in {"min", "max"}:
        requirement_fields += "    max: 1 s\n"
    text = dedent(f"""\
        version: 1
        capture: {{}}
        signals:
          vdd: {{column: C1}}
          reset: {{column: C2}}
        events:
          vdd_valid: {{signal: vdd, direction: above, threshold: 1.5, stable_for: {stable_for}}}
          reset_release: {{signal: reset, direction: above, threshold: 1.5}}
        requirements:
          - id: delay
            type: delay
            from: vdd_valid
            to: reset_release
        """) + requirement_fields

    assert _check(tmp_path, text) == 2

    output = capsys.readouterr()
    expected_field = "events.vdd_valid.stable_for" if field == "stable_for" else f"delay.{field}"
    assert f"{expected_field} must be finite" in output.err
    assert "PASS" not in output.out
    assert not (tmp_path / "report.json").exists()


def test_nan_uncertainty_does_not_make_a_failing_rise_pass(tmp_path, capsys):
    text = dedent("""\
        version: 1
        capture: {}
        signals:
          vdd: {column: C1, nominal: 3.3}
        requirements:
          - id: rise
            type: rise_time
            signal: vdd
            max: 100 us
            uncertainty: .nan
        """)

    assert _check(tmp_path, text) == 2

    output = capsys.readouterr()
    assert "rise.uncertainty must be finite" in output.err
    assert "PASS" not in output.out


@pytest.mark.parametrize(
    ("maximum", "expected"), [("100 us", 1), ("1 ms", 0), ("0.001", 0), ("0", 1)]
)
def test_finite_rise_time_limits_keep_their_verdict(tmp_path, capsys, maximum, expected):
    text = dedent(f"""\
        version: 1
        capture: {{}}
        signals:
          vdd: {{column: C1, nominal: 3.3}}
        requirements:
          - id: rise
            type: rise_time
            signal: vdd
            max: {maximum}
        """)

    assert _check(tmp_path, text) == expected
    assert "rise time = 800 us" in capsys.readouterr().out
