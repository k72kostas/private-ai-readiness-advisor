"""Deterministic adoption-roadmap service for PARA-GIP.

The service transforms readiness, governance, confidence, GPU-planning,
and decision outputs into prioritized 7-day, 30-day, and 90-day actions.
All actions retain their originating rule identifiers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, Mapping

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.results import (
    ConfidenceLevel,
    ConfidenceResult,
    CriticalFinding,
    DecisionResult,
    GPUPlanningResult,
    RoadmapAction,
    RoadmapHorizon,
    RoadmapPriority,
    RoadmapResult,
    ScoreResult,
)


class RoadmapGenerationError(ValueError):
    """Raised when configured roadmap rules cannot be applied safely."""


_HORIZON_BY_ID = {
    "HORIZON-7-DAY": RoadmapHorizon.SEVEN_DAY,
    "HORIZON-30-DAY": RoadmapHorizon.THIRTY_DAY,
    "HORIZON-90-DAY": RoadmapHorizon.NINETY_DAY,
}

_PRIORITY_BY_ID = {
    "PRIORITY-1": RoadmapPriority.PRIORITY_1,
    "PRIORITY-2": RoadmapPriority.PRIORITY_2,
    "PRIORITY-3": RoadmapPriority.PRIORITY_3,
    "PRIORITY-4": RoadmapPriority.PRIORITY_4,
    "PRIORITY-5": RoadmapPriority.PRIORITY_5,
}

_PRIORITY_RANK = {
    RoadmapPriority.PRIORITY_1: 1,
    RoadmapPriority.PRIORITY_2: 2,
    RoadmapPriority.PRIORITY_3: 3,
    RoadmapPriority.PRIORITY_4: 4,
    RoadmapPriority.PRIORITY_5: 5,
}

_HORIZON_DAYS = {
    RoadmapHorizon.SEVEN_DAY: 7,
    RoadmapHorizon.THIRTY_DAY: 30,
    RoadmapHorizon.NINETY_DAY: 90,
}


def _plain_value(value: Any) -> Any:
    """Return an enum value or the original ordinary value."""

    return value.value if isinstance(value, Enum) else value


def _validate_safeguards(rules: Mapping[str, Any]) -> None:
    """Fail closed when mandatory roadmap safeguards are disabled."""

    safeguards = rules.get("safeguards")
    if not isinstance(safeguards, Mapping):
        raise RoadmapGenerationError("roadmap safeguards must be configured")

    required_true = (
        "critical_stops_must_be_first",
        "governance_before_optimization",
        "evidence_actions_when_confidence_low",
        "benchmark_actions_when_gpu_confidence_low_or_medium",
        "prohibit_automatic_production_rollout",
        "production_candidate_means_assessment_only",
        "require_human_approval",
        "require_validation_before_investment",
    )
    disabled = [name for name in required_true if safeguards.get(name) is not True]
    if disabled:
        raise RoadmapGenerationError(
            "mandatory roadmap safeguards are disabled: " + ", ".join(disabled)
        )


def _action(
    rule: Mapping[str, Any],
    *,
    text: str,
    rationale: str,
    source_rule_ids: Iterable[str],
    owner_role: str | None = None,
    completion_criterion: str | None = None,
) -> RoadmapAction:
    """Build one validated roadmap action from a configured rule."""

    try:
        horizon = _HORIZON_BY_ID[rule["horizon"]]
        priority = _PRIORITY_BY_ID[rule["priority"]]
    except KeyError as exc:
        raise RoadmapGenerationError(
            f"rule {rule.get('rule_id')} references an unknown horizon or priority"
        ) from exc

    sources = list(dict.fromkeys([rule["rule_id"], *source_rule_ids]))
    return RoadmapAction(
        horizon=horizon,
        priority=priority,
        action=text.strip(),
        rationale=rationale.strip(),
        owner_role=(owner_role or rule["default_owner_role"]).strip(),
        completion_criterion=(
            completion_criterion or rule["completion_criterion"]
        ).strip(),
        source_rule_ids=sources,
    )


def _rule_index(rules: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Index configured roadmap rules by rule ID."""

    configured = rules.get("roadmap_rules")
    if not isinstance(configured, (list, tuple)):
        raise RoadmapGenerationError("roadmap_rules must be a list")
    return {rule["rule_id"]: rule for rule in configured}


def _lowest_domains(score_result: ScoreResult) -> list[Any]:
    """Return all domains tied for the lowest percentage."""

    if not score_result.domain_scores:
        return []
    minimum = min(domain.percentage for domain in score_result.domain_scores)
    return [
        domain
        for domain in score_result.domain_scores
        if domain.percentage == minimum
    ]


def _deduplicate_and_sort(actions: list[RoadmapAction]) -> list[RoadmapAction]:
    """Deduplicate equivalent actions and apply deterministic ordering."""

    unique: dict[tuple[str, str, str], RoadmapAction] = {}
    for action in actions:
        key = (
            action.horizon.value,
            action.priority.value,
            action.action.casefold(),
        )
        if key not in unique:
            unique[key] = action
            continue

        existing = unique[key]
        merged_sources = list(
            dict.fromkeys([*existing.source_rule_ids, *action.source_rule_ids])
        )
        unique[key] = existing.model_copy(
            update={"source_rule_ids": merged_sources}
        )

    return sorted(
        unique.values(),
        key=lambda item: (
            _PRIORITY_RANK[item.priority],
            _HORIZON_DAYS[item.horizon],
            item.source_rule_ids[0],
            item.action.casefold(),
        ),
    )


def generate_roadmap(
    score_result: ScoreResult,
    critical_findings: list[CriticalFinding],
    evidence_confidence: ConfidenceResult,
    gpu_planning_result: GPUPlanningResult,
    decision_result: DecisionResult,
    *,
    unresolved_governance_findings: list[str] | None = None,
    configuration: ConfigurationBundle | None = None,
) -> RoadmapResult:
    """Generate a traceable 7-day, 30-day, and 90-day adoption roadmap."""

    bundle = configuration or load_configuration_bundle()
    rules = bundle.roadmap_rules
    _validate_safeguards(rules)
    indexed = _rule_index(rules)
    governance_findings = unresolved_governance_findings or []
    actions: list[RoadmapAction] = []

    blocker_rule = indexed["RM-CRITICAL-STOP-001"]
    for finding in critical_findings:
        if not finding.triggered:
            continue
        text = (
            f"Resolve blocker: {finding.name}. "
            f"Complete corrective action: {finding.corrective_action}"
        )
        actions.append(
            _action(
                blocker_rule,
                text=text,
                rationale=finding.rationale,
                source_rule_ids=[finding.rule_id],
            )
        )

    governance_rule = indexed["RM-GOVERNANCE-001"]
    for finding in governance_findings:
        actions.append(
            _action(
                governance_rule,
                text=f"Resolve governance or security finding: {finding}.",
                rationale=(
                    "Governance and security findings must be resolved before "
                    "optimization or scaling activities."
                ),
                source_rule_ids=[],
            )
        )

    if evidence_confidence.level is ConfidenceLevel.LOW:
        evidence_rule = indexed["RM-EVIDENCE-LOW-001"]
        targets = (
            evidence_confidence.missing_inputs_or_evidence
            or ["the assessment evidence set"]
        )
        for target in targets:
            actions.append(
                _action(
                    evidence_rule,
                    text=f"Collect and review missing evidence for {target}",
                    rationale=(
                        "Low Evidence Confidence requires evidence collection "
                        "before material investment decisions."
                    ),
                    source_rule_ids=evidence_confidence.applied_rule_ids,
                )
            )

    lowest_rule = indexed["RM-LOWEST-DOMAIN-001"]
    lowest = _lowest_domains(score_result)
    for domain in lowest:
        actions.append(
            _action(
                lowest_rule,
                text=(
                    f"Improve readiness in {domain.domain_name}; current domain "
                    f"result is {domain.percentage:.1f} percent."
                ),
                rationale=(
                    "The lowest-scoring readiness domain is prioritized after "
                    "blockers and governance findings."
                ),
                source_rule_ids=domain.applied_rule_ids,
            )
        )

    gpu_confidence = gpu_planning_result.planning_confidence.level
    if gpu_confidence is ConfidenceLevel.LOW:
        gpu_low_rule = indexed["RM-GPU-CONFIDENCE-LOW-001"]
        actions.append(
            _action(
                gpu_low_rule,
                text=(
                    "Complete missing workload assumptions for responsible "
                    "GPU planning."
                ),
                rationale="GPU Planning Confidence is Low.",
                source_rule_ids=(
                    gpu_planning_result.planning_confidence.applied_rule_ids
                ),
            )
        )

    benchmark_missing = any(
        "benchmark" in value.casefold()
        for value in gpu_planning_result.missing_inputs
    )
    if benchmark_missing or gpu_confidence in {
        ConfidenceLevel.LOW,
        ConfidenceLevel.MEDIUM,
    }:
        benchmark_rule = indexed["RM-GPU-NO-BENCHMARK-001"]
        actions.append(
            _action(
                benchmark_rule,
                text=gpu_planning_result.recommended_benchmark_action,
                rationale=(
                    "Measured workload evidence is required to improve GPU "
                    "planning confidence and validate capacity assumptions."
                ),
                source_rule_ids=gpu_planning_result.applied_rule_ids,
            )
        )

    if decision_result.status.value in {
        "Ready for Controlled Prototype",
        "Ready for Benchmarked Pilot",
        "Proceed with Conditions",
    }:
        pilot_rule = indexed["RM-PILOT-VALIDATION-001"]
        actions.append(
            _action(
                pilot_rule,
                text=(
                    "Run a controlled pilot within the approved use-case and "
                    "data boundaries."
                ),
                rationale=decision_result.rationale,
                source_rule_ids=decision_result.originating_rule_ids,
            )
        )

    if decision_result.status.value == "Candidate for Production Assessment":
        production_rule = indexed["RM-PRODUCTION-ASSESSMENT-001"]
        actions.append(
            _action(
                production_rule,
                text=(
                    "Perform formal architecture, security, compliance, "
                    "capacity, and operational reviews."
                ),
                rationale=(
                    "Candidate status authorizes formal assessment only, not "
                    "automatic production rollout."
                ),
                source_rule_ids=decision_result.originating_rule_ids,
            )
        )

    pilot_evidence_available = (
        gpu_confidence is ConfidenceLevel.HIGH
        and evidence_confidence.level is ConfidenceLevel.HIGH
    )
    if (
        not decision_result.triggered_critical_stops
        and not governance_findings
        and pilot_evidence_available
    ):
        optimization_rule = indexed["RM-OPTIMIZATION-001"]
        actions.append(
            _action(
                optimization_rule,
                text=(
                    "Evaluate capacity, performance, cost, support, and "
                    "expansion improvements."
                ),
                rationale=(
                    "Optimization may be assessed because blockers are absent "
                    "and reviewed evidence is available."
                ),
                source_rule_ids=decision_result.originating_rule_ids,
            )
        )

    ordered = _deduplicate_and_sort(actions)
    seven_day = [a for a in ordered if a.horizon is RoadmapHorizon.SEVEN_DAY]
    thirty_day = [a for a in ordered if a.horizon is RoadmapHorizon.THIRTY_DAY]
    ninety_day = [a for a in ordered if a.horizon is RoadmapHorizon.NINETY_DAY]

    priority_areas = list(
        dict.fromkeys(
            [
                *(finding.name for finding in critical_findings if finding.triggered),
                *governance_findings,
                *(domain.domain_name for domain in lowest),
            ]
        )
    )
    next_actions = [action.action for action in ordered[:5]]
    applied_rule_ids = list(
        dict.fromkeys(
            source
            for action in ordered
            for source in action.source_rule_ids
        )
    )
    if not applied_rule_ids:
        applied_rule_ids = [rules["processing_sequence"]["rule_id"]]

    rationale = (
        "Actions are ordered by critical stops, governance and evidence, "
        "lowest readiness domains, GPU planning gaps, then optimization. "
        f"Generated {len(ordered)} actions across the configured horizons."
    )

    return RoadmapResult(
        priority_improvement_areas=priority_areas,
        recommended_next_actions=next_actions,
        seven_day_action_plan=seven_day,
        thirty_day_pilot_plan=thirty_day,
        ninety_day_scale_plan=ninety_day,
        roadmap_rationale=rationale,
        recommended_next_decision=decision_result.recommended_next_stage,
        applied_rule_ids=applied_rule_ids,
        rule_set_version=str(rules["rule_set_version"]),
    )


__all__ = ["RoadmapGenerationError", "generate_roadmap"]
