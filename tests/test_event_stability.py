import json

import pytest

from powercontract.cli import main


def check_stability(tmp_path, direction, samples, stable_for):
    capture = tmp_path / "capture.csv"
    capture.write_text(
        "Time,V\n" + "".join(f"{time},{value}\n" for time, value in samples),
        encoding="utf-8",
    )
    contract = tmp_path / "contract.yaml"
    contract.write_text(
        "version: 1\n"
        "capture: {}\n"
        "signals:\n"
        "  rail: {column: V}\n"
        "events:\n"
        f"  ready: {{signal: rail, direction: {direction}, threshold: 1, stable_for: {stable_for}}}\n"
        "requirements:\n"
        "  - {id: MAX, type: max_value, signal: rail, from: ready, value: 2}\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    status = main(["check", str(capture), str(contract), "--json", str(report)])
    return status, json.loads(report.read_text(encoding="utf-8"))


@pytest.mark.parametrize("direction, outside", [("above", 0), ("below", 2)])
@pytest.mark.parametrize("continues", [False, True], ids=["capture-end", "early-exit"])
def test_short_stability_interval_is_not_lost_at_large_time_origin(
    tmp_path, direction, outside, continues,
):
    samples = [(1699999999, outside), (1700000000, 1)]
    if continues:
        samples.append((1700000001, outside))

    status, report = check_stability(tmp_path, direction, samples, "100ns")

    assert status == 1
    assert report["passed"] is False
    assert report["events"] == {}
    assert report["findings"][0]["status"] == "INDETERMINATE"


@pytest.mark.parametrize("direction, values", [("above", (0, 2)), ("below", (2, 0))])
@pytest.mark.parametrize("continues, stable_for, expected", [
    (False, "200ns", 1),
    (False, "100ns", 0),
    (True, "300ns", 1),
    (True, "200ns", 0),
])
def test_stability_uses_the_interpolated_crossing_before_timestamp_rounding(
    tmp_path, direction, values, continues, stable_for, expected,
):
    samples = list(zip((1700000000.0, 1700000000.0000002), values))
    if continues:
        samples.append((1700000000.0000005, values[0]))

    status, report = check_stability(tmp_path, direction, samples, stable_for)

    assert status == expected
    assert report["passed"] is (expected == 0)
    assert report["findings"][0]["status"] == ("PASS" if expected == 0 else "INDETERMINATE")


@pytest.mark.parametrize("direction, outside", [("above", 0), ("below", 2)])
@pytest.mark.parametrize("stable_for, tail", [
    ("0", []),
    ("1s", [(1700000001, 1)]),
    ("1s", [(1700000001, 1), (1700000002, None)]),
], ids=["no-stability-window", "exact-capture-end", "exact-exit"])
def test_stability_interval_boundaries_can_still_pass(
    tmp_path, direction, outside, stable_for, tail,
):
    samples = [(1699999999, outside), (1700000000, 1)]
    samples.extend((time, outside if value is None else value) for time, value in tail)

    status, report = check_stability(tmp_path, direction, samples, stable_for)

    assert status == 0
    assert report["passed"] is True
    assert report["events"] == {"ready": 1700000000}
    assert report["findings"][0]["status"] == "PASS"
