import json
from math import nextafter, ulp

import pytest

from powercontract.cli import main
from powercontract.evaluate import evaluate
from powercontract.model import Capture
from powercontract.spec import parse_contract


# One representable timestamp step at the large origin, retained exactly when
# translating the same samples between a local and an absolute time axis.
STEP = 2 ** -22
ORIGIN = 1700000000.0


def contract(events, requirements, *, nominal=1):
    return parse_contract({
        "version": 1,
        "capture": {},
        "signals": {"rail": {"column": "V", "nominal": nominal}},
        "events": events,
        "requirements": requirements,
    })


def event(threshold, direction="above", stable_for=0):
    return {"signal": "rail", "direction": direction, "threshold": threshold, "stable_for": stable_for}


def capture(values, origin=ORIGIN, *, long_prefix=False):
    times = tuple(origin + index * STEP for index in range(len(values)))
    if long_prefix:
        times = (-2 ** 30, *times)
        values = (values[0], *values)
    return Capture(times, {"rail": tuple(values)})


@pytest.mark.parametrize("direction,values,start,end", [
    ("above", (0, 10), 1, 2),
    ("above", (0, 10), 8, 9),
    ("above", (0, 10), 4, 6),
    ("below", (10, 0), 9, 8),
    ("below", (10, 0), 2, 1),
    ("below", (10, 0), 6, 4),
])
def test_delay_is_invariant_to_time_origin_and_long_capture_prefix(direction, values, start, end):
    c = contract(
        {"start": event(start, direction), "end": event(end, direction)},
        [{"id": "DELAY", "type": "delay", "from": "start", "to": "end", "max": "10ns"}],
    )
    findings = [
        evaluate(c, capture(values, origin, long_prefix=prefix)).findings[0]
        for origin, prefix in [(0, False), (ORIGIN, False), (ORIGIN, True)]
    ]

    for finding in findings:
        assert finding.status == "FAIL"
        expected = abs(end - start) / 10 * STEP
        # The two interpolated offsets can each contribute one rounding unit.
        assert abs(finding.measured - expected) <= 2 * ulp(expected)
    assert findings[0].measured == findings[1].measured == findings[2].measured


@pytest.mark.parametrize("limits,uncertainty,status", [
    ({"max": STEP / 8}, 0, "PASS"),
    ({"max": STEP / 16}, 0, "FAIL"),
    ({"min": STEP / 8}, 0, "PASS"),
    ({"min": STEP / 4}, 0, "FAIL"),
    ({"max": STEP / 8}, STEP / 16, "INDETERMINATE"),
    ({"max": 3 * STEP / 16}, STEP / 16, "PASS"),
    ({"max": STEP / 16}, STEP / 32, "FAIL"),
])
def test_delay_preserves_exact_bounds_and_uncertainty(limits, uncertainty, status):
    c = contract(
        {"start": event(2), "end": event(4)},
        [{"id": "DELAY", "type": "delay", "from": "start", "to": "end", "uncertainty": uncertainty, **limits}],
    )
    finding = evaluate(c, capture((0, 16), long_prefix=True)).findings[0]

    assert finding.measured == STEP / 8
    assert finding.status == status


def test_delay_uses_later_stable_event_after_noise():
    c = contract(
        {"start": event(1, stable_for=1.1 * STEP), "end": event(8)},
        [{"id": "DELAY", "type": "delay", "from": "start", "to": "end", "max": STEP}],
    )
    finding = evaluate(c, capture((0, 2, 0, 0, 10, 10, 10), long_prefix=True)).findings[0]

    assert finding.status == "PASS"
    assert finding.measured == pytest.approx(0.7 * STEP, abs=1e-23)


@pytest.mark.parametrize("requirement_type,values", [
    ("rise_time", (0, 0.2, 0, 0, 10)),
    ("fall_time", (10, 0.8, 10, 10, 0)),
])
def test_transition_uses_latest_start_without_rounding_short_duration(requirement_type, values):
    c = contract({}, [{"id": "EDGE", "type": requirement_type, "signal": "rail", "max": "10ns"}])
    finding = evaluate(c, capture(values, long_prefix=True)).findings[0]

    assert finding.status == "FAIL"
    assert finding.measured == pytest.approx(0.08 * STEP, abs=1e-23)


@pytest.mark.parametrize("requirement_type,limit,status,measured", [
    ("max_value", 1.5, "FAIL", 2),
    ("max_value", 2, "PASS", 2),
    ("min_value", 1, "PASS", 1),
    ("min_value", 1.5, "FAIL", 1),
])
def test_voltage_window_interpolates_unrounded_event_boundaries(requirement_type, limit, status, measured):
    c = contract(
        {"start": event(1), "end": event(2)},
        [{"id": "WINDOW", "type": requirement_type, "signal": "rail", "from": "start", "to": "end", "value": limit}],
    )
    finding = evaluate(c, capture((0, 10), long_prefix=True)).findings[0]

    assert finding.status == status
    assert finding.measured == measured


def test_reversed_window_fails_even_when_reported_events_round_to_same_time():
    c = contract(
        {"start": event(2), "end": event(1)},
        [{"id": "WINDOW", "type": "max_value", "signal": "rail", "from": "start", "to": "end", "value": 10}],
    )
    result = evaluate(c, capture((0, 10)))

    assert result.events["start"] == result.events["end"] == ORIGIN
    assert result.findings[0].status == "FAIL"
    assert "reversed" in result.findings[0].summary


def test_same_event_window_still_measures_its_interpolated_value():
    c = contract(
        {"start": event(1)},
        [{"id": "WINDOW", "type": "max_value", "signal": "rail", "from": "start", "to": "start", "value": 1}],
    )
    finding = evaluate(c, capture((0, 10))).findings[0]

    assert finding.status == "PASS"
    assert finding.measured == 1


def test_cli_reports_short_failing_delay_without_changing_event_json(tmp_path, capsys):
    waveform = tmp_path / "capture.csv"
    waveform.write_text("Time,V\n1700000000,0\n1700000000.0000002,10\n")
    spec = tmp_path / "contract.yaml"
    spec.write_text(
        "version: 1\ncapture: {}\nsignals:\n  rail: {column: V}\n"
        "events:\n"
        "  start: {signal: rail, direction: above, threshold: 1}\n"
        "  end: {signal: rail, direction: above, threshold: 2}\n"
        "requirements:\n"
        "  - {id: DELAY, type: delay, from: start, to: end, max: 10ns}\n"
    )
    report = tmp_path / "report.json"

    assert main(["check", str(waveform), str(spec), "--json", str(report)]) == 1

    assert "PASS" not in capsys.readouterr().out
    payload = json.loads(report.read_text())
    assert payload["events"] == {"start": ORIGIN, "end": ORIGIN}
    assert payload["findings"][0]["status"] == "FAIL"
    assert payload["findings"][0]["measured"] == pytest.approx(STEP / 10, abs=1e-23)
    assert payload["schema_version"] == 1


@pytest.mark.parametrize("threshold", [nextafter(5, 0), 5, nextafter(5, 10)])
def test_midpoint_ordering_keeps_interpolated_windows_nonempty(threshold):
    c = contract(
        {"start": event(4), "middle": event(threshold), "end": event(6)},
        [
            {"id": "BEFORE", "type": "delay", "from": "start", "to": "middle", "min": 0},
            {"id": "AFTER", "type": "delay", "from": "middle", "to": "end", "min": 0},
            {"id": "WINDOW", "type": "min_value", "signal": "rail", "from": "middle", "to": "end", "value": 4},
        ],
    )
    result = evaluate(c, capture((0, 10), long_prefix=True))

    assert result.passed
    assert result.findings[0].measured > 0
    assert result.findings[1].measured > 0
    assert result.findings[2].measured == threshold


def test_irregular_intervals_and_exact_sample_events_preserve_window_values():
    c = contract(
        {"start": event(1), "sample": event(4), "end": event(8)},
        [
            {"id": "BEFORE", "type": "delay", "from": "start", "to": "sample", "max": STEP},
            {"id": "AFTER", "type": "delay", "from": "sample", "to": "end", "max": 6 * STEP},
            {"id": "WINDOW", "type": "max_value", "signal": "rail", "from": "start", "to": "end", "value": 8},
        ],
    )
    waveform = Capture((ORIGIN, ORIGIN + STEP, ORIGIN + 9 * STEP), {"rail": (0, 4, 12)})
    result = evaluate(c, waveform)

    assert result.passed
    assert result.findings[0].measured == 0.75 * STEP
    assert result.findings[1].measured == 4 * STEP
    assert result.findings[2].measured == 8


@pytest.mark.parametrize("stable_for,status", [(0, "PASS"), (STEP / 16, "INDETERMINATE")])
def test_adjacent_segments_share_an_exact_sample_boundary(stable_for, status):
    c = contract(
        {"entry": event(1, stable_for=stable_for)},
        [{"id": "WINDOW", "type": "max_value", "signal": "rail", "from": "entry", "value": 1}],
    )
    # Entry is at the end of the first segment. The stability exit is at the
    # start of the next segment, leaving exactly zero time above the threshold.
    waveform = Capture((ORIGIN, ORIGIN + STEP, ORIGIN + 9 * STEP), {"rail": (0, 1, 0)})
    result = evaluate(c, waveform)

    assert result.findings[0].status == status
    if stable_for == 0:
        assert result.events["entry"] == ORIGIN + STEP
        assert result.findings[0].measured == 1
    else:
        assert result.events == {}


def test_extreme_finite_timestamps_do_not_overflow_crossing_arithmetic():
    c = contract(
        {"start": event(4, stable_for=1e307), "end": event(6, stable_for=1e307)},
        [{"id": "DELAY", "type": "delay", "from": "start", "to": "end", "max": 7e307}],
    )
    waveform = Capture((-1.7e308, 1.7e308), {"rail": (0, 10)})
    result = evaluate(c, waveform)

    assert result.passed
    assert result.findings[0].measured == pytest.approx(6.8e307)
    assert result.events["start"] == pytest.approx(-3.4e307)
    assert result.events["end"] == pytest.approx(3.4e307)


def test_unrepresentable_duration_is_indeterminate_instead_of_nan_pass():
    c = contract(
        {"start": event(1), "end": event(9)},
        [{"id": "DELAY", "type": "delay", "from": "start", "to": "end", "max": 1e308}],
    )
    result = evaluate(c, Capture((-1.7e308, 1.7e308), {"rail": (0, 10)}))

    assert result.findings[0].status == "INDETERMINATE"
    assert result.findings[0].measured is None
    json.dumps(result.findings[0].as_dict(), allow_nan=False)


def test_extreme_finite_values_preserve_crossing_and_window_interpolation():
    c = contract(
        {"start": event(-3.4e307), "end": event(3.4e307)},
        [
            {"id": "DELAY", "type": "delay", "from": "start", "to": "end", "max": STEP},
            {"id": "WINDOW", "type": "max_value", "signal": "rail", "from": "start", "to": "end", "value": 4e307},
        ],
    )
    result = evaluate(c, capture((-1.7e308, 1.7e308)))

    assert result.passed
    assert result.findings[0].measured == pytest.approx(0.2 * STEP)
    assert result.findings[1].measured == pytest.approx(3.4e307)
