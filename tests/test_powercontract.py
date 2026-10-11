from pathlib import Path

import pytest

from powercontract.capture import load_capture
from powercontract.errors import CaptureError, SpecError
from powercontract.evaluate import evaluate
from powercontract.spec import parse_contract


def contract():
    return parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {
            "vdd": {"column": "C1", "nominal": 3.3},
            "reset": {"column": "C2"},
        },
        "events": {
            "vdd_valid": {"signal": "vdd", "direction": "above", "threshold": 3.0, "stable_for": "2ms"},
            "reset_release": {"signal": "reset", "direction": "above", "threshold": 1.5},
        },
        "requirements": [
            {"id": "SEQ-1", "type": "delay", "from": "vdd_valid", "to": "reset_release", "min": "2ms", "max": "8ms"},
            {"id": "VDD-MAX", "type": "max_value", "signal": "vdd", "value": 3.6},
            {"id": "VDD-RISE", "type": "rise_time", "signal": "vdd", "low": 0.1, "high": 0.9, "max": "5ms"},
        ],
    })


def write_capture(tmp_path: Path, rows: str, preamble: str = "") -> Path:
    path = tmp_path / "capture.csv"
    path.write_text(preamble + "Time,C1,C2\n" + rows, encoding="utf-8")
    return path


def test_evaluates_sequence_voltage_and_rise_time(tmp_path):
    path = write_capture(tmp_path, "0,0,0\n0.001,0.5,0\n0.002,2.0,0\n0.003,3.1,0\n0.004,3.3,0\n0.005,3.3,0\n0.006,3.3,0\n0.007,3.3,2.0\n")
    result = evaluate(contract(), load_capture(path, contract()))
    assert result.passed
    assert result.findings[0].margin == pytest.approx(0.0018409, rel=1e-3)
    assert result.findings[1].margin == pytest.approx(0.3)


def test_stable_event_rejects_short_threshold_excursion(tmp_path):
    c = contract()
    path = write_capture(tmp_path, "0,0,0\n0.001,3.1,0\n0.002,2.8,0\n0.003,3.2,0\n0.004,3.2,0\n0.005,3.2,0\n0.007,3.2,2.0\n")
    result = evaluate(c, load_capture(path, c))
    assert result.events["vdd_valid"] > 0.002


def test_failing_delay_has_negative_margin(tmp_path):
    c = contract()
    path = write_capture(tmp_path, "0,0,0\n0.001,1.0,0\n0.002,3.1,0\n0.003,3.3,2.0\n0.004,3.3,2.0\n0.005,3.3,2.0\n")
    result = evaluate(c, load_capture(path, c))
    finding = result.findings[0]
    assert finding.status == "FAIL"
    assert finding.margin is not None and finding.margin < 0
    assert finding.minimum == pytest.approx(0.002)
    assert finding.maximum == pytest.approx(0.008)


def test_csv_header_can_follow_scope_metadata_preamble(tmp_path):
    c = contract()
    path = write_capture(tmp_path, "0,0,0\n0.001,1,0\n", preamble="Model,SDS824X HD\nSample Rate,1MSa/s\n")
    capture = load_capture(path, c)
    assert capture.time == (0.0, 0.001)


def test_capture_requires_monotonic_time(tmp_path):
    c = contract()
    path = write_capture(tmp_path, "0.001,0,0\n0.001,1,0\n")
    with pytest.raises(CaptureError, match="strictly increasing"):
        load_capture(path, c)


def test_contract_rejects_unknown_event_signal():
    with pytest.raises(SpecError, match="unknown signal"):
        parse_contract({
            "version": 1,
            "capture": {},
            "signals": {"vdd": {"column": "C1"}},
            "events": {"bad": {"signal": "missing", "direction": "above", "threshold": 1}},
            "requirements": [{"id": "A", "type": "max_value", "signal": "vdd", "value": 4}],
        })


def test_max_value_can_be_bounded_by_events(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1"}, "gate": {"column": "C2"}},
        "events": {
            "window_start": {"signal": "gate", "direction": "above", "threshold": 1.0},
            "window_end": {"signal": "gate", "direction": "below", "threshold": 1.0},
        },
        "requirements": [{
            "id": "WINDOW-MAX",
            "type": "max_value",
            "signal": "vdd",
            "value": 3.5,
            "from": "window_start",
            "to": "window_end",
        }],
    })
    path = write_capture(
        tmp_path,
        "0,4.0,0\n0.001,3.0,0\n0.002,3.3,2\n0.003,3.4,2\n0.004,3.4,0\n",
    )
    result = evaluate(c, load_capture(path, c))
    assert result.passed
    assert result.findings[0].measured == pytest.approx(3.4)


def test_fall_time_uses_high_to_low_fraction(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1", "nominal": 3.3}, "unused": {"column": "C2"}},
        "events": {},
        "requirements": [{
            "id": "VDD-FALL",
            "type": "fall_time",
            "signal": "vdd",
            "low": 0.1,
            "high": 0.9,
            "max": "5ms",
        }],
    })
    path = write_capture(
        tmp_path,
        "0,3.3,0\n0.001,3.0,0\n0.002,2.0,0\n0.003,1.0,0\n0.004,0.2,0\n",
    )
    result = evaluate(c, load_capture(path, c))
    assert result.passed
    assert result.findings[0].measured == pytest.approx(0.0028075, rel=1e-6)


def test_extremum_window_rejects_unknown_event():
    with pytest.raises(SpecError, match="unknown event"):
        parse_contract({
            "version": 1,
            "capture": {},
            "signals": {"vdd": {"column": "C1"}},
            "events": {},
            "requirements": [{
                "id": "WINDOW",
                "type": "max_value",
                "signal": "vdd",
                "value": 3.6,
                "from": "power_good",
            }],
        })


def test_stable_event_detects_interpolated_exit_between_sparse_samples(tmp_path):
    c = contract()
    path = write_capture(
        tmp_path,
        "0,0,0\n0.001,3.2,0\n0.003,2.0,0\n0.004,3.2,0\n0.007,3.2,2.0\n",
    )
    result = evaluate(c, load_capture(path, c))
    assert result.events["vdd_valid"] > 0.003


def test_capture_rejects_non_finite_samples(tmp_path):
    c = contract()
    path = write_capture(tmp_path, "0,0,0\n0.001,nan,0\n")
    with pytest.raises(CaptureError, match="non-finite"):
        load_capture(path, c)


def test_missing_event_is_indeterminate_not_failure(tmp_path):
    c = contract()
    path = write_capture(
        tmp_path,
        "0,0,0\n0.001,1.0,0\n0.002,2.0,0\n0.003,3.3,0\n0.004,3.3,0\n0.005,3.3,0\n",
    )
    result = evaluate(c, load_capture(path, c))
    finding = result.findings[0]
    assert finding.status == "INDETERMINATE"
    assert "reset_release" in finding.summary


def test_contract_rejects_unknown_fields_instead_of_ignoring_typos():
    with pytest.raises(SpecError, match="unknown field"):
        parse_contract({
            "version": 1,
            "capture": {},
            "signals": {"vdd": {"column": "C1"}},
            "events": {
                "valid": {
                    "signal": "vdd",
                    "direction": "above",
                    "threshold": 3.0,
                    "stabl_for": "2ms",
                }
            },
            "requirements": [{
                "id": "A",
                "type": "max_value",
                "signal": "vdd",
                "value": 4.0,
            }],
        })


def test_contract_rejects_non_positive_nominal_voltage():
    with pytest.raises(SpecError, match="nominal must be > 0"):
        parse_contract({
            "version": 1,
            "capture": {},
            "signals": {"vdd": {"column": "C1", "nominal": 0}},
            "events": {},
            "requirements": [{
                "id": "A",
                "type": "max_value",
                "signal": "vdd",
                "value": 4.0,
            }],
        })


def test_contract_rejects_boolean_numeric_values():
    with pytest.raises(SpecError, match="must be numeric"):
        parse_contract({
            "version": 1,
            "capture": {},
            "signals": {"vdd": {"column": "C1"}},
            "events": {},
            "requirements": [{
                "id": "A",
                "type": "max_value",
                "signal": "vdd",
                "value": True,
            }],
        })
