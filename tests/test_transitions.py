import pytest

from powercontract.capture import load_capture
from powercontract.evaluate import evaluate
from powercontract.spec import parse_contract


def transition_finding(tmp_path, requirement_type, values, maximum="1ms"):
    contract = parse_contract({
        "version": 1,
        "capture": {"time_column": "Time"},
        "signals": {"vdd": {"column": "C1", "nominal": 1.0}},
        "requirements": [{
            "id": "VDD-TRANSITION",
            "type": requirement_type,
            "signal": "vdd",
            "max": maximum,
        }],
    })
    path = tmp_path / "capture.csv"
    path.write_text(
        "Time,C1\n" + "".join(f"{index / 1000:.3f},{value}\n" for index, value in enumerate(values)),
        encoding="utf-8",
    )
    return evaluate(contract, load_capture(path, contract)).findings[0]


@pytest.mark.parametrize("requirement_type, values", [
    ("rise_time", (0.5, 1.0, 0.0, 0.0, 1.0)),
    ("fall_time", (0.5, 0.0, 1.0, 1.0, 0.0)),
])
@pytest.mark.parametrize("maximum, status", [("1ms", "PASS"), ("500us", "FAIL")])
def test_transition_after_truncated_edge_is_measured(
    tmp_path, requirement_type, values, maximum, status,
):
    finding = transition_finding(tmp_path, requirement_type, values, maximum)

    # The edge at the start lacks its first threshold. The complete edge spans
    # 3.1 ms to 3.9 ms after interpolating the 10% and 90% crossings.
    assert finding.status == status
    assert finding.measured == pytest.approx(0.0008)


@pytest.mark.parametrize("requirement_type, values", [
    ("rise_time", (0.5, 1.0, 0.5, 1.0)),
    ("fall_time", (0.5, 0.0, 0.5, 0.0)),
])
def test_trace_without_a_complete_transition_remains_indeterminate(
    tmp_path, requirement_type, values,
):
    finding = transition_finding(tmp_path, requirement_type, values)

    assert finding.status == "INDETERMINATE"
    assert finding.measured is None


@pytest.mark.parametrize("requirement_type, values", [
    ("rise_time", (0.0, 0.2, 0.6, 1.0, 0.0, 1.0)),
    ("fall_time", (1.0, 0.8, 0.4, 0.0, 1.0, 0.0)),
])
def test_first_complete_transition_is_used_even_when_a_later_edge_passes(
    tmp_path, requirement_type, values,
):
    finding = transition_finding(tmp_path, requirement_type, values)

    assert finding.status == "FAIL"
    assert finding.measured == pytest.approx(0.00225)
