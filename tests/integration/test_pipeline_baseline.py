"""Scenario 1: Foundation baseline end-to-end validation."""

from __future__ import annotations

import json

import pytest

from src.config_loader import load_configuration_bundle
from src.models import ConfidenceLevel, DecisionStatus, ReadinessClassification
from src.services import run_assessment_pipeline
from src.services.reporting import report_to_json, report_to_markdown

from .factories import build_assessment, build_use_case, build_workload


@pytest.fixture(scope="module")
def configuration():
    """Load the Version 1 configuration once for this scenario."""

    return load_configuration_bundle()


@pytest.fixture(scope="module")
def baseline_result(configuration):
    """Execute the complete Foundation baseline scenario."""

    return run_assessment_pipeline(
        assessment=build_assessment(configuration),
        use_case=build_use_case(),
        workload=build_workload(),
        configuration=configuration,
    )


def test_baseline_scoring(baseline_result) -> None:
    """All level-2 answers must produce a 50-point Foundation result."""

    score = baseline_result.score_result

    assert len(score.question_scores) == 35
    assert len(score.domain_scores) == 7
    assert score.overall_score == pytest.approx(50.0)
    assert (
        score.score_band_classification
        is ReadinessClassification.FOUNDATION_REQUIRED
    )
    assert (
        score.final_classification
        is ReadinessClassification.FOUNDATION_REQUIRED
    )
    assert score.applied_caps == []
    assert all(
        domain.percentage == pytest.approx(50.0)
        for domain in score.domain_scores
    )


def test_baseline_has_no_critical_stops(baseline_result) -> None:
    """The acceptable internal-data baseline must not be blocked."""

    assert baseline_result.critical_findings == ()
    assert baseline_result.deployment_blocked is False


def test_baseline_confidence_results(baseline_result) -> None:
    """Self-declared evidence is Low and no benchmark caps GPU at Medium."""

    assert (
        baseline_result.evidence_confidence.level
        is ConfidenceLevel.LOW
    )
    assert baseline_result.evidence_confidence.score == pytest.approx(25.0)
    assert (
        baseline_result.gpu_planning_result.planning_confidence.level
        is ConfidenceLevel.MEDIUM
    )
    assert "Measured workload benchmark evidence" in (
        baseline_result.gpu_planning_result.missing_inputs
    )


def test_baseline_gpu_planning(baseline_result) -> None:
    """The configured 8B INT4 estimate must remain neutral and traceable."""

    gpu = baseline_result.gpu_planning_result

    assert gpu.infrastructure_tier == "Controlled Prototype"
    assert gpu.gpu_memory_class == "Small GPU memory class"
    assert gpu.deployment_pattern == "Single-node controlled deployment"
    assert gpu.planning_estimates[
        "estimated_model_runtime_memory_gb"
    ] == pytest.approx(5.4)
    assert gpu.planning_estimates["estimate_label"] == "planning_estimate"
    assert gpu.recommended_benchmark_action
    assert gpu.applied_rule_ids


def test_baseline_decision(baseline_result) -> None:
    """A Foundation classification maps to the Foundation decision."""

    decision = baseline_result.decision_result

    assert decision.status is DecisionStatus.FOUNDATION_REQUIRED
    assert decision.recommended_next_stage == "foundation"
    assert decision.overall_score == pytest.approx(50.0)
    assert decision.triggered_critical_stops == []
    assert decision.originating_rule_ids


def test_baseline_roadmap(baseline_result) -> None:
    """The roadmap must request evidence and benchmarking, not production."""

    roadmap = baseline_result.roadmap_result
    all_actions = [
        *roadmap.seven_day_action_plan,
        *roadmap.thirty_day_pilot_plan,
        *roadmap.ninety_day_scale_plan,
    ]
    action_text = " ".join(
        action.action.casefold() for action in all_actions
    )

    assert roadmap.seven_day_action_plan
    assert roadmap.thirty_day_pilot_plan
    assert any(
        "evidence" in action.action.casefold()
        for action in roadmap.seven_day_action_plan
    )
    assert "benchmark" in action_text
    assert "production rollout" not in action_text
    assert roadmap.recommended_next_decision == "foundation"
    assert all(action.source_rule_ids for action in all_actions)


def test_baseline_report_consistency(baseline_result) -> None:
    """The report must preserve IDs, versions, and deterministic outputs."""

    report = baseline_result.report_snapshot

    assert report.assessment_id == baseline_result.score_result.assessment_id
    assert (
        report.decision_result.status
        is DecisionStatus.FOUNDATION_REQUIRED
    )
    assert report.rule_set_versions
    assert report.optional_narrative is None

    decoded = json.loads(report_to_json(report))
    assert decoded["score_result"]["overall_score"] == pytest.approx(50.0)
    assert decoded["decision_result"]["status"] == "Foundation Required"

    markdown = report_to_markdown(report)
    assert "# PARA-GIP Executive Readiness Report" in markdown
    assert "Foundation Required" in markdown
    assert "5.4" not in markdown or "GPU" in markdown
    assert "not an automatic deployment" in markdown


def test_baseline_is_deterministic(configuration) -> None:
    """Equivalent business inputs must produce equivalent rule outputs."""

    first = run_assessment_pipeline(
        assessment=build_assessment(configuration),
        use_case=build_use_case(),
        workload=build_workload(),
        configuration=configuration,
    )
    second = run_assessment_pipeline(
        assessment=build_assessment(configuration),
        use_case=build_use_case(),
        workload=build_workload(),
        configuration=configuration,
    )

    assert first.score_result.overall_score == second.score_result.overall_score
    assert (
        first.score_result.final_classification
        == second.score_result.final_classification
    )
    assert first.decision_result.status == second.decision_result.status
    assert (
        first.gpu_planning_result.planning_estimates
        == second.gpu_planning_result.planning_estimates
    )
    assert (
        first.decision_result.originating_rule_ids
        == second.decision_result.originating_rule_ids
    )
