"""End-to-end deterministic assessment pipeline for PARA-GIP.

The pipeline coordinates configuration loading, readiness scoring, critical
stop evaluation, Evidence Confidence, GPU planning, decision evaluation,
roadmap generation, and report assembly. It contains no scoring or governance
rules of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.assessment import Assessment
from src.models.results import (
    ConfidenceResult,
    CriticalFinding,
    DecisionResult,
    GPUPlanningResult,
    ReportSnapshot,
    RoadmapResult,
    ScoreResult,
)
from src.models.use_case import UseCase
from src.models.workload import WorkloadProfile
from src.services.critical_stops import evaluate_critical_stops
from src.services.decision import evaluate_decision
from src.services.evidence_confidence import calculate_evidence_confidence
from src.services.gpu_planning import plan_gpu_infrastructure
from src.services.reporting import (
    create_report_snapshot,
    write_json_report,
    write_markdown_report,
)
from src.services.roadmap import generate_roadmap
from src.services.scoring import calculate_readiness_score


class AssessmentPipelineError(RuntimeError):
    """Raised when the assessment pipeline receives inconsistent inputs."""


@dataclass(frozen=True, slots=True)
class AssessmentPipelineResult:
    """Complete deterministic result set from one pipeline execution."""

    score_result: ScoreResult
    critical_findings: tuple[CriticalFinding, ...]
    evidence_confidence: ConfidenceResult
    gpu_planning_result: GPUPlanningResult
    decision_result: DecisionResult
    roadmap_result: RoadmapResult
    report_snapshot: ReportSnapshot

    @property
    def deployment_blocked(self) -> bool:
        """Return whether the decision contains triggered blockers."""

        return bool(self.decision_result.triggered_critical_stops)

    def model_dump_for_json(self) -> dict:
        """Return every pipeline output as JSON-compatible data."""

        return {
            "score_result": self.score_result.model_dump(mode="json"),
            "critical_findings": [
                finding.model_dump(mode="json")
                for finding in self.critical_findings
            ],
            "evidence_confidence": self.evidence_confidence.model_dump(
                mode="json"
            ),
            "gpu_planning_result": self.gpu_planning_result.model_dump(
                mode="json"
            ),
            "decision_result": self.decision_result.model_dump(mode="json"),
            "roadmap_result": self.roadmap_result.model_dump(mode="json"),
            "report_snapshot": self.report_snapshot.model_dump_for_json(),
        }


@dataclass(frozen=True, slots=True)
class AssessmentExportResult:
    """Paths written for one completed pipeline result."""

    json_path: Path
    markdown_path: Path


def _validate_pipeline_inputs(
    assessment: Assessment,
    workload: WorkloadProfile,
) -> None:
    """Validate input relationships required by the orchestration layer."""

    if (
        workload.deployment_boundary
        != assessment.organization_profile.deployment_boundary
    ):
        raise AssessmentPipelineError(
            "assessment and workload deployment boundaries must match"
        )

    if (
        workload.data_sensitivity
        != assessment.organization_profile.data_sensitivity
    ):
        raise AssessmentPipelineError(
            "assessment and workload data sensitivity must match"
        )


def run_assessment_pipeline(
    assessment: Assessment,
    workload: WorkloadProfile,
    *,
    use_case: UseCase | None = None,
    unresolved_governance_findings: list[str] | None = None,
    optional_narrative: str | None = None,
    configuration: ConfigurationBundle | None = None,
) -> AssessmentPipelineResult:
    """Execute the complete deterministic PARA-GIP assessment workflow.

    Args:
        assessment: Versioned organizational readiness assessment.
        workload: Model, workload, deployment, and benchmark assumptions.
        use_case: Optional use-case context for conditional critical stops.
        unresolved_governance_findings: Optional unresolved findings that are
            not already represented as critical stops.
        optional_narrative: Optional informational narrative stored separately
            from deterministic outputs.
        configuration: Optional preloaded configuration bundle.

    Returns:
        All intermediate service results and the final report snapshot.
    """

    _validate_pipeline_inputs(assessment, workload)
    bundle = configuration or load_configuration_bundle()
    governance_findings = unresolved_governance_findings or []

    score_result = calculate_readiness_score(
        assessment,
        configuration=bundle,
    )

    critical_findings = evaluate_critical_stops(
        assessment=assessment,
        use_case=use_case,
        configuration=bundle,
    )

    evidence_confidence = calculate_evidence_confidence(
        assessment,
        configuration=bundle,
    )

    gpu_planning_result = plan_gpu_infrastructure(
        workload,
        configuration=bundle,
    )

    decision_result = evaluate_decision(
        score_result=score_result,
        critical_findings=critical_findings,
        evidence_confidence=evidence_confidence,
        gpu_planning_result=gpu_planning_result,
        unresolved_governance_findings=bool(governance_findings),
        benchmark_evidence_available=workload.benchmark_available,
        configuration=bundle,
    )

    roadmap_result = generate_roadmap(
        score_result=score_result,
        critical_findings=critical_findings,
        evidence_confidence=evidence_confidence,
        gpu_planning_result=gpu_planning_result,
        decision_result=decision_result,
        unresolved_governance_findings=governance_findings,
        configuration=bundle,
    )

    report_snapshot = create_report_snapshot(
        assessment=assessment,
        score_result=score_result,
        critical_findings=critical_findings,
        evidence_confidence=evidence_confidence,
        gpu_planning_result=gpu_planning_result,
        decision_result=decision_result,
        roadmap_result=roadmap_result,
        optional_narrative=optional_narrative,
        configuration=bundle,
    )

    return AssessmentPipelineResult(
        score_result=score_result,
        critical_findings=tuple(critical_findings),
        evidence_confidence=evidence_confidence,
        gpu_planning_result=gpu_planning_result,
        decision_result=decision_result,
        roadmap_result=roadmap_result,
        report_snapshot=report_snapshot,
    )


def export_assessment_pipeline_result(
    result: AssessmentPipelineResult,
    output_directory: str | Path = "reports/generated",
    *,
    file_stem: str | None = None,
) -> AssessmentExportResult:
    """Write JSON and Markdown exports for a completed pipeline result."""

    directory = Path(output_directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)

    stem = file_stem or f"assessment-{result.report_snapshot.assessment_id}"
    stem = stem.strip()
    if not stem or stem in {".", ".."}:
        raise AssessmentPipelineError("file_stem must be non-empty")
    if Path(stem).name != stem:
        raise AssessmentPipelineError(
            "file_stem must not contain directory components"
        )

    json_path = write_json_report(
        result.report_snapshot,
        directory / f"{stem}.json",
    )
    markdown_path = write_markdown_report(
        result.report_snapshot,
        directory / f"{stem}.md",
    )

    return AssessmentExportResult(
        json_path=json_path,
        markdown_path=markdown_path,
    )


__all__ = [
    "AssessmentExportResult",
    "AssessmentPipelineError",
    "AssessmentPipelineResult",
    "export_assessment_pipeline_result",
    "run_assessment_pipeline",
]
