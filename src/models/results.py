"""Deterministic output models for PARA-GIP.

These contracts hold calculated scoring, governance, confidence, decision,
roadmap, GPU planning, and report results. They remain separate from raw
assessment, use-case, and workload inputs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, field_validator, model_validator

from .assessment import StrictModel


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReadinessClassification(StrEnum):
    DISCOVERY_REQUIRED = "Discovery Required"
    FOUNDATION_REQUIRED = "Foundation Required"
    CONTROLLED_PROTOTYPE = "Ready for Controlled Prototype"
    BENCHMARKED_PILOT = "Ready for Benchmarked Pilot"
    PRODUCTION_ASSESSMENT = "Candidate for Production Assessment"


class ConfidenceLevel(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class DecisionStatus(StrEnum):
    DISCOVERY_REQUIRED = "Discovery Required"
    FOUNDATION_REQUIRED = "Foundation Required"
    CONTROLLED_PROTOTYPE = "Ready for Controlled Prototype"
    BENCHMARKED_PILOT = "Ready for Benchmarked Pilot"
    PRODUCTION_ASSESSMENT = "Candidate for Production Assessment"
    PROCEED_WITH_CONDITIONS = "Proceed with Conditions"
    GOVERNANCE_REVIEW_REQUIRED = "Governance Review Required"
    DEPLOYMENT_BLOCKED = "Deployment Blocked"


class CriticalSeverity(StrEnum):
    BLOCKING = "blocking"


class RoadmapHorizon(StrEnum):
    SEVEN_DAY = "HORIZON-7-DAY"
    THIRTY_DAY = "HORIZON-30-DAY"
    NINETY_DAY = "HORIZON-90-DAY"


class RoadmapPriority(StrEnum):
    PRIORITY_1 = "PRIORITY-1"
    PRIORITY_2 = "PRIORITY-2"
    PRIORITY_3 = "PRIORITY-3"
    PRIORITY_4 = "PRIORITY-4"
    PRIORITY_5 = "PRIORITY-5"


class QuestionScore(StrictModel):
    question_id: NonEmptyText
    maturity_level: int = Field(ge=0, le=4)
    maximum_points: float = Field(ge=0)
    earned_points: float = Field(ge=0)
    applied_rule_ids: list[NonEmptyText] = Field(min_length=1)

    @model_validator(mode="after")
    def earned_points_cannot_exceed_maximum(self) -> QuestionScore:
        if self.earned_points > self.maximum_points:
            raise ValueError("earned_points cannot exceed maximum_points")
        return self


class DomainScore(StrictModel):
    domain_id: NonEmptyText
    domain_name: NonEmptyText
    maximum_points: float = Field(gt=0)
    earned_points: float = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    applied_rule_ids: list[NonEmptyText] = Field(min_length=1)

    @model_validator(mode="after")
    def domain_points_are_valid(self) -> DomainScore:
        if self.earned_points > self.maximum_points:
            raise ValueError("earned_points cannot exceed maximum_points")
        return self


class ClassificationCap(StrictModel):
    rule_id: NonEmptyText
    target_classification: ReadinessClassification
    capped_to: ReadinessClassification
    affected_domains: list[NonEmptyText] = Field(min_length=1)
    rationale: NonEmptyText


class ScoreResult(StrictModel):
    assessment_id: UUID
    assessment_version: NonEmptyText
    rule_set_version: NonEmptyText
    question_scores: list[QuestionScore] = Field(min_length=1)
    domain_scores: list[DomainScore] = Field(min_length=1)
    overall_score: float = Field(ge=0, le=100)
    score_band_classification: ReadinessClassification
    final_classification: ReadinessClassification
    applied_caps: list[ClassificationCap] = Field(default_factory=list)
    calculation_explanation: NonEmptyText
    applied_rule_ids: list[NonEmptyText] = Field(min_length=1)

    @field_validator("domain_scores")
    @classmethod
    def domain_ids_must_be_unique(cls, values: list[DomainScore]) -> list[DomainScore]:
        ids = [value.domain_id for value in values]
        if len(ids) != len(set(ids)):
            raise ValueError("domain score identifiers must be unique")
        return values


class CriticalFinding(StrictModel):
    rule_id: NonEmptyText
    name: NonEmptyText
    severity: CriticalSeverity = CriticalSeverity.BLOCKING
    source_questions: list[NonEmptyText] = Field(default_factory=list)
    rationale: NonEmptyText
    corrective_action: NonEmptyText
    triggered: bool = True


class ConfidenceResult(StrictModel):
    confidence_type: NonEmptyText
    level: ConfidenceLevel
    score: float | None = Field(default=None, ge=0, le=100)
    reasons: list[NonEmptyText] = Field(min_length=1)
    missing_inputs_or_evidence: list[NonEmptyText] = Field(default_factory=list)
    highlighted_question_ids: list[NonEmptyText] = Field(default_factory=list)
    applied_rule_ids: list[NonEmptyText] = Field(min_length=1)
    rule_set_version: NonEmptyText


class GPUPlanningResult(StrictModel):
    infrastructure_tier: NonEmptyText
    gpu_memory_class: NonEmptyText
    deployment_pattern: NonEmptyText
    planning_confidence: ConfidenceResult
    material_assumptions: list[NonEmptyText] = Field(min_length=1)
    planning_estimates: dict[str, Any] = Field(default_factory=dict)
    missing_inputs: list[NonEmptyText] = Field(default_factory=list)
    recommended_benchmark_action: NonEmptyText
    applied_rule_ids: list[NonEmptyText] = Field(min_length=1)
    rule_set_version: NonEmptyText

    @model_validator(mode="after")
    def confidence_type_must_be_gpu(self) -> GPUPlanningResult:
        if self.planning_confidence.confidence_type != "gpu_planning":
            raise ValueError("planning_confidence must have type 'gpu_planning'")
        return self


class DecisionResult(StrictModel):
    status_id: NonEmptyText
    status: DecisionStatus
    recommended_next_stage: NonEmptyText
    rationale: NonEmptyText
    overall_score: float = Field(ge=0, le=100)
    score_band_classification: ReadinessClassification
    final_classification: ReadinessClassification
    applied_caps: list[ClassificationCap] = Field(default_factory=list)
    triggered_critical_stops: list[CriticalFinding] = Field(default_factory=list)
    evidence_confidence: ConfidenceLevel
    gpu_planning_confidence: ConfidenceLevel
    originating_rule_ids: list[NonEmptyText] = Field(min_length=1)
    rule_set_version: NonEmptyText

    @model_validator(mode="after")
    def blocked_status_requires_critical_stop(self) -> DecisionResult:
        if (
            self.status is DecisionStatus.DEPLOYMENT_BLOCKED
            and not self.triggered_critical_stops
        ):
            raise ValueError(
                "Deployment Blocked requires at least one critical finding"
            )
        return self


class RoadmapAction(StrictModel):
    action_id: UUID = Field(default_factory=uuid4)
    horizon: RoadmapHorizon
    priority: RoadmapPriority
    action: NonEmptyText
    rationale: NonEmptyText
    owner_role: NonEmptyText
    completion_criterion: NonEmptyText
    source_rule_ids: list[NonEmptyText] = Field(min_length=1)


class RoadmapResult(StrictModel):
    priority_improvement_areas: list[NonEmptyText] = Field(default_factory=list)
    recommended_next_actions: list[NonEmptyText] = Field(default_factory=list)
    seven_day_action_plan: list[RoadmapAction] = Field(default_factory=list)
    thirty_day_pilot_plan: list[RoadmapAction] = Field(default_factory=list)
    ninety_day_scale_plan: list[RoadmapAction] = Field(default_factory=list)
    roadmap_rationale: NonEmptyText
    recommended_next_decision: NonEmptyText
    applied_rule_ids: list[NonEmptyText] = Field(min_length=1)
    rule_set_version: NonEmptyText

    @model_validator(mode="after")
    def actions_match_their_horizons(self) -> RoadmapResult:
        mappings = (
            (self.seven_day_action_plan, RoadmapHorizon.SEVEN_DAY),
            (self.thirty_day_pilot_plan, RoadmapHorizon.THIRTY_DAY),
            (self.ninety_day_scale_plan, RoadmapHorizon.NINETY_DAY),
        )
        for actions, expected_horizon in mappings:
            if any(action.horizon is not expected_horizon for action in actions):
                raise ValueError(
                    f"roadmap action does not match {expected_horizon.value}"
                )
        return self


class ReportSnapshot(StrictModel):
    report_id: UUID = Field(default_factory=uuid4)
    assessment_id: UUID
    assessment_version: NonEmptyText
    rule_set_versions: dict[NonEmptyText, NonEmptyText]
    generated_at: datetime
    score_result: ScoreResult
    critical_findings: list[CriticalFinding] = Field(default_factory=list)
    evidence_confidence: ConfidenceResult
    gpu_planning_result: GPUPlanningResult
    decision_result: DecisionResult
    roadmap_result: RoadmapResult
    optional_narrative: str | None = None

    @field_validator("generated_at")
    @classmethod
    def generated_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def assessment_ids_must_match(self) -> ReportSnapshot:
        if self.score_result.assessment_id != self.assessment_id:
            raise ValueError("report and score-result assessment IDs must match")
        return self

    def model_dump_for_json(self) -> dict:
        return self.model_dump(mode="json")
