import pytest

from tools.pqc_reference.workflow_scenarios import (
    pattern_models,
    run_workflow_scenarios,
)


def test_all_patterns_and_two_providers_without_forged_approval():
    output = run_workflow_scenarios()
    assert output == run_workflow_scenarios()
    assert len(output["scenarios"]) == 6
    for scenario in output["scenarios"]:
        assert scenario["result"] == "pass"
        assert scenario["state_after_external_close"] == "proposed"
        assert scenario["state_after_fixture_verification"] == "resolved"
        assert not scenario["live_execution_authorized"]
        assert not scenario["real_owner_approval"]
        assert not scenario["source_observation"]
        assert scenario["crypto_use_design_example"]["evidence"] == []


def test_unknown_pattern_denied():
    with pytest.raises(ValueError):
        pattern_models("unknown")
