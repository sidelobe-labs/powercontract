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


def write_siglent_trace(tmp_path: Path, source: str, rows: str) -> Path:
    path = tmp_path / f"usr_wf_{source}_data.csv"
    count = len([line for line in rows.splitlines() if line.strip()])
    path.write_text(
        "\n".join([
            f"Record Length,Analog:{count}",
            "Sample Interval,1.000000E-03",
            "Vertical Units,V,",
            "Vertical Scale,+2.000000E+00",
            "Vertical Offset,+0.000000E+00",
            "Horizontal Units,s",
            "Horizontal Scale,+5.000000E-03",
            "Model,SDS824X HD",
            "Serial Number,TEST",
            "Software Version,3.8.12.1.1.6.5",
            f"Source,{source}",
            "Second,Value",
            rows,
            "",
        ]),
        encoding="utf-8",
    )
    return path


def test_loads_realistic_siglent_per_channel_csv_group(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Second"},
        "signals": {
            "vin": {"column": "CH1", "nominal": 5.0},
            "vdd": {"column": "CH2", "nominal": 3.3},
            "reset": {"column": "CH3", "nominal": 3.3},
        },
        "events": {
            "vdd_valid": {"signal": "vdd", "direction": "above", "threshold": 3.0},
            "reset_release": {"signal": "reset", "direction": "above", "threshold": 1.5},
        },
        "requirements": [{
            "id": "ORDER",
            "type": "delay",
            "from": "vdd_valid",
            "to": "reset_release",
            "min": "0ms",
        }],
    })
    ch1 = write_siglent_trace(tmp_path, "CH1", "-0.002,0.5\n-0.001,1.0\n0,3.0\n0.001,5.0")
    ch2 = write_siglent_trace(tmp_path, "CH2", "-0.002,0\n-0.001,0.5\n0,2.0\n0.001,3.3")
    ch3 = write_siglent_trace(tmp_path, "CH3", "-0.002,0\n-0.001,0\n0,1.0\n0.001,3.3")

    capture = load_capture(ch1, c, [ch2, ch3])
    assert capture.time == (-0.002, -0.001, 0.0, 0.001)
    assert capture.signals["vin"][-1] == pytest.approx(5.0)
    assert capture.signals["vdd"][-1] == pytest.approx(3.3)
    assert capture.signals["reset"][-1] == pytest.approx(3.3)


def test_siglent_group_rejects_mismatched_time_axes(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Second"},
        "signals": {
            "a": {"column": "CH1"},
            "b": {"column": "CH2"},
        },
        "events": {},
        "requirements": [{"id": "A", "type": "max_value", "signal": "a", "value": 6}],
    })
    ch1 = write_siglent_trace(tmp_path, "CH1", "0,0\n0.001,1")
    ch2 = write_siglent_trace(tmp_path, "CH2", "0,0\n0.002,1")
    with pytest.raises(CaptureError, match="same time axis"):
        load_capture(ch1, c, [ch2])


def test_rise_time_pairs_low_threshold_with_same_completed_edge(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vin": {"column": "C1", "nominal": 5.0}},
        "events": {},
        "requirements": [{
            "id": "VIN-RISE",
            "type": "rise_time",
            "signal": "vin",
            "low": 0.1,
            "high": 0.9,
            "max": "10ms",
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text(
        "Time,C1\n"
        "-0.010,0.45\n"
        "-0.009,0.55\n"
        "-0.008,0.45\n"
        "-0.001,0.45\n"
        "0.000,0.60\n"
        "0.003,2.50\n"
        "0.007,4.60\n",
        encoding="utf-8",
    )
    result = evaluate(c, load_capture(path, c))
    assert result.passed
    # The early noise crossing at -9.5 ms must not become the start of the rise.
    assert result.findings[0].measured == pytest.approx(0.00747619, rel=1e-5)


def test_siglent_csv_rejects_declared_record_length_mismatch(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Second"},
        "signals": {"a": {"column": "CH1"}},
        "events": {},
        "requirements": [{"id": "A", "type": "max_value", "signal": "a", "value": 6}],
    })
    path = tmp_path / "usr_wf_CH1_data.csv"
    path.write_text(
        "\n".join([
            "Record Length,Analog:3",
            "Sample Interval,1.000000E-03",
            "Vertical Units,V,",
            "Horizontal Units,s",
            "Horizontal Scale,+5.000000E-03",
            "Source,CH1",
            "Second,Value",
            "0,0",
            "0.001,1",
            "",
        ]),
        encoding="utf-8",
    )
    with pytest.raises(CaptureError, match="declares 3 samples but file contains 2"):
        load_capture(path, c)


def test_voltage_uncertainty_straddling_limit_is_indeterminate(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1"}},
        "events": {},
        "requirements": [{
            "id": "VDD-MAX",
            "type": "max_value",
            "signal": "vdd",
            "value": 3.6,
            "uncertainty": 0.05,
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text("Time,C1\n0,3.58\n0.001,3.58\n", encoding="utf-8")
    finding = evaluate(c, load_capture(path, c)).findings[0]
    assert finding.status == "INDETERMINATE"
    assert finding.margin == pytest.approx(-0.03)
    assert finding.uncertainty == pytest.approx(0.05)


def test_voltage_uncertainty_wholly_outside_limit_is_failure(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1"}},
        "events": {},
        "requirements": [{
            "id": "VDD-MAX",
            "type": "max_value",
            "signal": "vdd",
            "value": 3.6,
            "uncertainty": 0.05,
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text("Time,C1\n0,3.70\n0.001,3.70\n", encoding="utf-8")
    finding = evaluate(c, load_capture(path, c)).findings[0]
    assert finding.status == "FAIL"
    assert finding.margin == pytest.approx(-0.15)


def test_delay_uncertainty_straddling_minimum_is_indeterminate(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"a": {"column": "C1"}, "b": {"column": "C2"}},
        "events": {
            "a_on": {"signal": "a", "direction": "above", "threshold": 0.5},
            "b_on": {"signal": "b", "direction": "above", "threshold": 0.5},
        },
        "requirements": [{
            "id": "SEQ",
            "type": "delay",
            "from": "a_on",
            "to": "b_on",
            "min": "2ms",
            "uncertainty": "0.2ms",
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text(
        "Time,C1,C2\n"
        "0,0,0\n"
        "0.001,1,0\n"
        "0.0029,1,1\n"
        "0.004,1,1\n",
        encoding="utf-8",
    )
    finding = evaluate(c, load_capture(path, c)).findings[0]
    assert finding.measured == pytest.approx(0.0019)
    assert finding.status == "INDETERMINATE"
    assert finding.uncertainty == pytest.approx(0.0002)


def test_uncertainty_clear_of_limit_can_pass(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1"}},
        "events": {},
        "requirements": [{
            "id": "VDD-MAX",
            "type": "max_value",
            "signal": "vdd",
            "value": 3.6,
            "uncertainty": 0.05,
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text("Time,C1\n0,3.50\n0.001,3.50\n", encoding="utf-8")
    finding = evaluate(c, load_capture(path, c)).findings[0]
    assert finding.status == "PASS"
    assert finding.margin == pytest.approx(0.05)


def test_contract_rejects_negative_voltage_uncertainty():
    with pytest.raises(SpecError, match="uncertainty must be >= 0"):
        parse_contract({
            "version": 1,
            "capture": {},
            "signals": {"vdd": {"column": "C1"}},
            "events": {},
            "requirements": [{
                "id": "VDD-MAX",
                "type": "max_value",
                "signal": "vdd",
                "value": 3.6,
                "uncertainty": -0.01,
            }],
        })


def test_min_value_accepts_uncertainty(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1"}},
        "events": {},
        "requirements": [{
            "id": "VDD-MIN",
            "type": "min_value",
            "signal": "vdd",
            "value": 3.0,
            "uncertainty": 0.05,
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text("Time,C1\n0,3.10\n0.001,3.10\n", encoding="utf-8")
    finding = evaluate(c, load_capture(path, c)).findings[0]
    assert finding.status == "PASS"
    assert finding.margin == pytest.approx(0.05)


def test_fall_time_accepts_duration_uncertainty(tmp_path):
    c = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1", "nominal": 3.3}},
        "events": {},
        "requirements": [{
            "id": "VDD-FALL",
            "type": "fall_time",
            "signal": "vdd",
            "max": "4ms",
            "uncertainty": "0.5ms",
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text(
        "Time,C1\n"
        "0,3.3\n"
        "0.001,3.0\n"
        "0.002,2.0\n"
        "0.003,1.0\n"
        "0.004,0.2\n",
        encoding="utf-8",
    )
    finding = evaluate(c, load_capture(path, c)).findings[0]
    assert finding.uncertainty == pytest.approx(0.0005)
