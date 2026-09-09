"""Deterministic reporting and export service for PARA-GIP.

This module assembles validated service outputs into a ReportSnapshot and
provides JSON and Markdown serialization. Optional narrative text is stored
separately and cannot modify deterministic results.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.assessment import Assessment
from src.models.results import (
    ConfidenceResult,
    CriticalFinding,
    DecisionResult,
    GPUPlanningResult,
    ReportSnapshot,
    RoadmapAction,
    RoadmapResult,
    ScoreResult,
)


class ReportingError(ValueError):
    """Raised when a report cannot be assembled or exported safely."""


def _validate_result_consistency(
    assessment: Assessment,
    score_result: ScoreResult,
    critical_findings: list[CriticalFinding],
    evidence_confidence: ConfidenceResult,
    gpu_planning_result: GPUPlanningResult,
    decision_result: DecisionResult,
    roadmap_result: RoadmapResult,
) -> None:
    """Validate cross-service identifiers and deterministic result consistency."""

    if score_result.assessment_id != assessment.assessment_id:
        raise ReportingError(
            "assessment and score-result assessment IDs do not match"
        )

    if score_result.assessment_version != assessment.assessment_version:
        raise ReportingError(
            "assessment and score-result versions do not match"
        )

    if decision_result.overall_score != score_result.overall_score:
        raise ReportingError(
            "decision and score results contain different overall scores"
        )

    if (
        decision_result.score_band_classification
        != score_result.score_band_classification
    ):
        raise ReportingError(
            "decision and score-band classifications do not match"
        )

    if decision_result.final_classification != score_result.final_classification:
        raise ReportingError(
            "decision and final readiness classifications do not match"
        )

    score_cap_ids = [cap.rule_id for cap in score_result.applied_caps]
    decision_cap_ids = [cap.rule_id for cap in decision_result.applied_caps]
    if score_cap_ids != decision_cap_ids:
        raise ReportingError(
            "decision and score results contain different classification caps"
        )

    reported_finding_ids = {
        finding.rule_id for finding in critical_findings if finding.triggered
    }
    decision_finding_ids = {
        finding.rule_id
        for finding in decision_result.triggered_critical_stops
        if finding.triggered
    }
    if reported_finding_ids != decision_finding_ids:
        raise ReportingError(
            "critical findings and decision blockers are inconsistent"
        )

    if evidence_confidence.confidence_type != "evidence":
        raise ReportingError(
            "evidence confidence must have confidence_type 'evidence'"
        )

    if (
        gpu_planning_result.planning_confidence.confidence_type
        != "gpu_planning"
    ):
        raise ReportingError(
            "GPU planning confidence must have type 'gpu_planning'"
        )

    if decision_result.evidence_confidence != evidence_confidence.level:
        raise ReportingError(
            "decision and Evidence Confidence levels do not match"
        )

    if (
        decision_result.gpu_planning_confidence
        != gpu_planning_result.planning_confidence.level
    ):
        raise ReportingError(
            "decision and GPU Planning Confidence levels do not match"
        )

    if roadmap_result.recommended_next_decision != (
        decision_result.recommended_next_stage
    ):
        raise ReportingError(
            "roadmap recommendation and decision next stage do not match"
        )


def _rule_set_versions(
    bundle: ConfigurationBundle,
    score_result: ScoreResult,
    evidence_confidence: ConfidenceResult,
    gpu_planning_result: GPUPlanningResult,
    decision_result: DecisionResult,
    roadmap_result: RoadmapResult,
) -> dict[str, str]:
    """Build the configuration-version map retained by the report."""

    versions = bundle.versions()
    versions.update(
        {
            "score_result": score_result.rule_set_version,
            "evidence_confidence_result": evidence_confidence.rule_set_version,
            "gpu_planning_result": gpu_planning_result.rule_set_version,
            "decision_result": decision_result.rule_set_version,
            "roadmap_result": roadmap_result.rule_set_version,
        }
    )
    return versions


def create_report_snapshot(
    assessment: Assessment,
    score_result: ScoreResult,
    critical_findings: list[CriticalFinding],
    evidence_confidence: ConfidenceResult,
    gpu_planning_result: GPUPlanningResult,
    decision_result: DecisionResult,
    roadmap_result: RoadmapResult,
    *,
    optional_narrative: str | None = None,
    generated_at: datetime | None = None,
    configuration: ConfigurationBundle | None = None,
) -> ReportSnapshot:
    """Assemble one validated and reproducible report snapshot."""

    bundle = configuration or load_configuration_bundle()
    _validate_result_consistency(
        assessment,
        score_result,
        critical_findings,
        evidence_confidence,
        gpu_planning_result,
        decision_result,
        roadmap_result,
    )

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ReportingError("generated_at must be timezone-aware")

    narrative = optional_narrative.strip() if optional_narrative else None

    return ReportSnapshot(
        assessment_id=assessment.assessment_id,
        assessment_version=assessment.assessment_version,
        rule_set_versions=_rule_set_versions(
            bundle,
            score_result,
            evidence_confidence,
            gpu_planning_result,
            decision_result,
            roadmap_result,
        ),
        generated_at=timestamp,
        score_result=score_result,
        critical_findings=critical_findings,
        evidence_confidence=evidence_confidence,
        gpu_planning_result=gpu_planning_result,
        decision_result=decision_result,
        roadmap_result=roadmap_result,
        optional_narrative=narrative,
    )


def report_to_json(
    report: ReportSnapshot,
    *,
    indent: int = 2,
) -> str:
    """Serialize a report snapshot to stable UTF-8-compatible JSON text."""

    if indent < 0:
        raise ReportingError("JSON indentation cannot be negative")

    return json.dumps(
        report.model_dump_for_json(),
        indent=indent,
        ensure_ascii=False,
        sort_keys=True,
    )


def _markdown_actions(
    title: str,
    actions: list[RoadmapAction],
) -> list[str]:
    """Render one roadmap horizon as Markdown lines."""

    lines = [f"### {title}", ""]
    if not actions:
        lines.extend(["No actions generated for this horizon.", ""])
        return lines

    for action in actions:
        lines.extend(
            [
                f"- **{action.priority.value}**: {action.action}",
                f"  - Owner role: {action.owner_role}",
                f"  - Completion: {action.completion_criterion}",
                "  - Source rules: " + ", ".join(action.source_rule_ids),
            ]
        )
    lines.append("")
    return lines


def report_to_markdown(report: ReportSnapshot) -> str:
    """Render a deterministic human-readable executive report."""

    score = report.score_result
    decision = report.decision_result
    gpu = report.gpu_planning_result
    roadmap = report.roadmap_result

    lines = [
        "# PARA-GIP Executive Readiness Report",
        "",
        f"- Report ID: `{report.report_id}`",
        f"- Assessment ID: `{report.assessment_id}`",
        f"- Assessment version: `{report.assessment_version}`",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        "",
        "## Executive Summary",
        "",
        f"- Overall readiness score: **{score.overall_score:.1f}/100**",
        f"- Score-band classification: **{score.score_band_classification.value}**",
        f"- Final classification: **{score.final_classification.value}**",
        f"- Decision status: **{decision.status.value}**",
        f"- Recommended next stage: **{decision.recommended_next_stage}**",
        f"- Evidence Confidence: **{report.evidence_confidence.level.value}**",
        f"- GPU Planning Confidence: **{gpu.planning_confidence.level.value}**",
        "",
        "## Decision Rationale",
        "",
        decision.rationale,
        "",
        "## Domain Scores",
        "",
        "| Domain | Earned | Available | Percentage |",
        "|---|---:|---:|---:|",
    ]

    for domain in score.domain_scores:
        lines.append(
            f"| {domain.domain_name} | {domain.earned_points:.1f} | "
            f"{domain.maximum_points:.1f} | {domain.percentage:.1f}% |"
        )

    lines.extend(["", "## Critical Findings", ""])
    if report.critical_findings:
        for finding in report.critical_findings:
            lines.extend(
                [
                    f"### {finding.name}",
                    "",
                    f"- Rule: `{finding.rule_id}`",
                    f"- Severity: **{finding.severity.value}**",
                    f"- Rationale: {finding.rationale}",
                    f"- Corrective action: {finding.corrective_action}",
                    "",
                ]
            )
    else:
        lines.extend(["No triggered critical-stop findings.", ""])

    lines.extend(
        [
            "## GPU Infrastructure Planning",
            "",
            f"- Infrastructure tier: **{gpu.infrastructure_tier}**",
            f"- GPU memory class: **{gpu.gpu_memory_class}**",
            f"- Deployment pattern: **{gpu.deployment_pattern}**",
            "- Planning estimate: **Not a product recommendation or performance guarantee**",
            "",
            "### Material Assumptions",
            "",
        ]
    )
    lines.extend(f"- {assumption}" for assumption in gpu.material_assumptions)
    lines.extend(["", "## Adoption Roadmap", ""])
    lines.extend(
        _markdown_actions(
            "7-Day Action Plan",
            roadmap.seven_day_action_plan,
        )
    )
    lines.extend(
        _markdown_actions(
            "30-Day Pilot Plan",
            roadmap.thirty_day_pilot_plan,
        )
    )
    lines.extend(
        _markdown_actions(
            "90-Day Scale Plan",
            roadmap.ninety_day_scale_plan,
        )
    )

    if report.optional_narrative:
        lines.extend(
            [
                "## Optional AI-Generated Narrative",
                "",
                "> This narrative is informational and does not modify deterministic results.",
                "",
                report.optional_narrative,
                "",
            ]
        )

    lines.extend(
        [
            "## Rule-Set Versions",
            "",
        ]
    )
    for name, version in sorted(report.rule_set_versions.items()):
        lines.append(f"- `{name}`: `{version}`")

    lines.extend(
        [
            "",
            "## Important Limitations",
            "",
            "- This report is a planning aid, not an automatic deployment or investment approval.",
            "- GPU outputs are neutral planning estimates and require measured benchmarking.",
            "- Formal architecture, security, privacy, compliance, and operational reviews remain necessary.",
            "",
        ]
    )
    return "\n".join(lines)


def _safe_output_path(
    output_path: str | Path,
    *,
    expected_suffix: str,
) -> Path:
    """Validate and normalize an export path."""

    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != expected_suffix:
        raise ReportingError(
            f"output file must use the {expected_suffix} extension"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_json_report(
    report: ReportSnapshot,
    output_path: str | Path,
    *,
    indent: int = 2,
) -> Path:
    """Write the structured report to a UTF-8 JSON file."""

    path = _safe_output_path(output_path, expected_suffix=".json")
    path.write_text(report_to_json(report, indent=indent), encoding="utf-8")
    return path


def write_markdown_report(
    report: ReportSnapshot,
    output_path: str | Path,
) -> Path:
    """Write the human-readable report to a UTF-8 Markdown file."""

    path = _safe_output_path(output_path, expected_suffix=".md")
    path.write_text(report_to_markdown(report), encoding="utf-8")
    return path


__all__ = [
    "ReportingError",
    "create_report_snapshot",
    "report_to_json",
    "report_to_markdown",
    "write_json_report",
    "write_markdown_report",
]
