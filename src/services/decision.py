"""Deterministic decision service for PARA-GIP.

The service combines the readiness result, critical findings, Evidence
Confidence, GPU Planning Confidence, and optional governance state into one
configured DecisionResult. It preserves the numerical score and never grants
automatic production approval.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.results import (
    ConfidenceLevel,
    ConfidenceResult,
    CriticalFinding,
    DecisionResult,
    DecisionStatus,
    GPUPlanningResult,
    ReadinessClassification,
    ScoreResult,
)


class DecisionEvaluationError(ValueError):
    """Raised when configured decision rules cannot be evaluated safely."""


_DECISION_STATUS_BY_ID = {
    "DECISION-DISCOVERY-REQUIRED": DecisionStatus.DISCOVERY_REQUIRED,
    "DECISION-FOUNDATION-REQUIRED": DecisionStatus.FOUNDATION_REQUIRED,
    "DECISION-CONTROLLED-PROTOTYPE": DecisionStatus.CONTROLLED_PROTOTYPE,
    "DECISION-BENCHMARKED-PILOT": DecisionStatus.BENCHMARKED_PILOT,
    "DECISION-PRODUCTION-ASSESSMENT": DecisionStatus.PRODUCTION_ASSESSMENT,
    "DECISION-PROCEED-CONDITIONS": DecisionStatus.PROCEED_WITH_CONDITIONS,
    "DECISION-GOVERNANCE-REVIEW": DecisionStatus.GOVERNANCE_REVIEW_REQUIRED,
    "DECISION-DEPLOYMENT-BLOCKED": DecisionStatus.DEPLOYMENT_BLOCKED,
}


def _plain_value(value: Any) -> Any:
    """Return the value of an enum or the original ordinary value."""

    return value.value if isinstance(value, Enum) else value


def _active_blockers(findings: list[CriticalFinding]) -> list[CriticalFinding]:
    """Return triggered blocking findings only."""

    return [
        finding
        for finding in findings
        if finding.triggered and _plain_value(finding.severity) == "blocking"
    ]


def _build_facts(
    score_result: ScoreResult,
    critical_findings: list[CriticalFinding],
    evidence_confidence: ConfidenceResult,
    gpu_planning_result: GPUPlanningResult,
    *,
    unresolved_governance_findings: bool,
    benchmark_evidence_available: bool,
) -> dict[str, Any]:
    """Create the normalized fact set used by configured decision rules."""

    blockers = _active_blockers(critical_findings)
    return {
        "critical_stops_present": bool(blockers),
        "unresolved_governance_findings": unresolved_governance_findings,
        "evidence_confidence": _plain_value(evidence_confidence.level),
        "gpu_planning_confidence": _plain_value(
            gpu_planning_result.planning_confidence.level
        ),
        "classification": _plain_value(score_result.final_classification),
        "final_classification": _plain_value(score_result.final_classification),
        "benchmark_evidence_available": benchmark_evidence_available,
    }


def _condition_matches(
    condition_name: str,
    expected: Any,
    facts: Mapping[str, Any],
) -> bool:
    """Evaluate one supported decision-rule condition."""

    if condition_name.endswith("_in"):
        fact_name = condition_name.removesuffix("_in")
        if not isinstance(expected, (list, tuple)):
            raise DecisionEvaluationError(
                f"condition '{condition_name}' requires a list of values"
            )
        return facts.get(fact_name) in expected

    if condition_name not in facts:
        raise DecisionEvaluationError(
            f"unsupported decision condition: {condition_name}"
        )

    return facts[condition_name] == expected


def _rule_matches(rule: Mapping[str, Any], facts: Mapping[str, Any]) -> bool:
    """Return whether all conditions of one decision rule match."""

    conditions = rule.get("when")
    if not isinstance(conditions, Mapping) or not conditions:
        raise DecisionEvaluationError(
            f"decision rule {rule.get('rule_id')} requires non-empty conditions"
        )

    return all(
        _condition_matches(name, expected, facts)
        for name, expected in conditions.items()
    )


def _validate_safeguards(rules: Mapping[str, Any]) -> None:
    """Fail closed when mandatory decision safeguards are disabled."""

    safeguards = rules.get("safeguards")
    if not isinstance(safeguards, Mapping):
        raise DecisionEvaluationError("decision safeguards must be configured")

    required_true = (
        "blocker_overrides_proceed_decisions",
        "blocker_does_not_erase_score",
        "low_confidence_requires_conditions",
        "production_candidate_is_not_production_ready",
        "prohibit_automatic_production_approval",
        "require_human_approval",
    )
    disabled = [name for name in required_true if safeguards.get(name) is not True]
    if disabled:
        raise DecisionEvaluationError(
            "mandatory decision safeguards are disabled: " + ", ".join(disabled)
        )

    if safeguards.get("optional_narrative_may_modify_decision") is not False:
        raise DecisionEvaluationError(
            "optional narrative must not modify deterministic decisions"
        )


def evaluate_decision(
    score_result: ScoreResult,
    critical_findings: list[CriticalFinding],
    evidence_confidence: ConfidenceResult,
    gpu_planning_result: GPUPlanningResult,
    *,
    unresolved_governance_findings: bool = False,
    benchmark_evidence_available: bool = False,
    configuration: ConfigurationBundle | None = None,
) -> DecisionResult:
    """Evaluate configured decision rules and return one DecisionResult.

    Rules are evaluated by ascending numeric priority. The first matching rule
    determines the status and recommended next stage. All contributing blocker
    rule IDs remain traceable in the result.
    """

    bundle = configuration or load_configuration_bundle()
    rules = bundle.decision_rules
    _validate_safeguards(rules)

    if evidence_confidence.confidence_type != "evidence":
        raise DecisionEvaluationError(
            "evidence_confidence must have confidence_type 'evidence'"
        )
    if gpu_planning_result.planning_confidence.confidence_type != "gpu_planning":
        raise DecisionEvaluationError(
            "GPU confidence must have confidence_type 'gpu_planning'"
        )

    facts = _build_facts(
        score_result,
        critical_findings,
        evidence_confidence,
        gpu_planning_result,
        unresolved_governance_findings=unresolved_governance_findings,
        benchmark_evidence_available=benchmark_evidence_available,
    )

    configured_rules = rules.get("rules")
    if not isinstance(configured_rules, (list, tuple)) or not configured_rules:
        raise DecisionEvaluationError("decision rules must be a non-empty list")

    sorted_rules = sorted(configured_rules, key=lambda item: int(item["priority"]))
    matched_rule = next(
        (rule for rule in sorted_rules if _rule_matches(rule, facts)),
        None,
    )
    if matched_rule is None:
        raise DecisionEvaluationError(
            "no configured decision rule matched the supplied results"
        )

    status_id = matched_rule["decision_status"]
    try:
        status = _DECISION_STATUS_BY_ID[status_id]
    except KeyError as exc:
        raise DecisionEvaluationError(
            f"unsupported decision status ID: {status_id}"
        ) from exc

    blockers = _active_blockers(critical_findings)
    originating_rule_ids = [matched_rule["rule_id"]]
    originating_rule_ids.extend(finding.rule_id for finding in blockers)
    originating_rule_ids.extend(
        cap.rule_id for cap in score_result.applied_caps
    )
    originating_rule_ids.extend(evidence_confidence.applied_rule_ids)
    originating_rule_ids.extend(
        gpu_planning_result.planning_confidence.applied_rule_ids
    )

    rationale = matched_rule["rationale_template"].strip()
    if blockers:
        blocker_names = ", ".join(finding.name for finding in blockers)
        rationale = f"{rationale} Triggered blockers: {blocker_names}."

    return DecisionResult(
        status_id=status_id,
        status=status,
        recommended_next_stage=matched_rule["recommended_next_stage"],
        rationale=rationale,
        overall_score=score_result.overall_score,
        score_band_classification=score_result.score_band_classification,
        final_classification=score_result.final_classification,
        applied_caps=score_result.applied_caps,
        triggered_critical_stops=blockers,
        evidence_confidence=evidence_confidence.level,
        gpu_planning_confidence=gpu_planning_result.planning_confidence.level,
        originating_rule_ids=list(dict.fromkeys(originating_rule_ids)),
        rule_set_version=str(rules["rule_set_version"]),
    )


__all__ = ["DecisionEvaluationError", "evaluate_decision"]
