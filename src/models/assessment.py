"""Core assessment data models for PARA-GIP.

These models represent user-supplied assessment data only. Deterministic
scores, classifications, critical stops, confidence results, decisions,
and roadmap actions belong to separate result models and services.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None


class AssessmentStatus(StrEnum):
    """Lifecycle status of an assessment session."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DeploymentBoundary(StrEnum):
    """Approved deployment-boundary vocabulary for Version 1."""

    ON_PREMISES = "on_premises"
    SOVEREIGN_CLOUD = "sovereign_cloud"
    PRIVATE_CLOUD = "private_cloud"
    HYBRID = "hybrid"


class DataSensitivity(StrEnum):
    """Data-sensitivity vocabulary used by conditional governance gates."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class EvidenceStatus(StrEnum):
    """Evidence status accepted by the assessment catalog."""

    NONE = "none"
    SELF_DECLARED = "self_declared"
    PARTIALLY_SUPPORTED = "partially_supported"
    DOCUMENTED = "documented"
    REVIEWED = "reviewed"


class EvidenceType(StrEnum):
    """Non-sensitive evidence-reference categories."""

    POLICY = "policy"
    PROCEDURE = "procedure"
    ARCHITECTURE = "architecture"
    APPROVAL = "approval"
    INVENTORY = "inventory"
    ASSESSMENT = "assessment"
    BENCHMARK = "benchmark"
    TRAINING_RECORD = "training_record"
    OTHER = "other"


class TargetStage(StrEnum):
    """Stage the organization wants the assessment to evaluate."""

    DISCOVERY = "discovery"
    FOUNDATION = "foundation"
    CONTROLLED_PROTOTYPE = "controlled_prototype"
    BENCHMARKED_PILOT = "benchmarked_pilot"
    PRODUCTION_ASSESSMENT = "production_assessment"


class StrictModel(BaseModel):
    """Shared strict and serialization-safe Pydantic configuration."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )


class OrganizationProfile(StrictModel):
    """Minimum organization context required by the assessment."""

    size_band: NonEmptyText
    industry: NonEmptyText
    deployment_boundary: DeploymentBoundary
    data_sensitivity: DataSensitivity


class EvidenceReference(StrictModel):
    """Metadata-only reference to supporting evidence.

    Version 1 stores a non-sensitive reference, not the confidential document
    itself.
    """

    evidence_type: EvidenceType
    title: NonEmptyText
    reference: NonEmptyText
    evidence_date: date | None = None
    reviewer_status: EvidenceStatus = EvidenceStatus.NONE
    reviewer_alias: OptionalText = None

    @model_validator(mode="after")
    def reviewer_required_for_reviewed_evidence(self) -> EvidenceReference:
        """Require reviewer metadata when evidence is marked reviewed."""

        if self.reviewer_status is EvidenceStatus.REVIEWED and not self.reviewer_alias:
            raise ValueError(
                "reviewer_alias is required when reviewer_status is 'reviewed'"
            )
        return self


class AssessmentResponse(StrictModel):
    """A raw answer to one configured readiness question."""

    question_id: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=8,
            pattern=r"^[A-Z]{2}[1-9][0-9]*$",
        ),
    ]
    maturity_level: int = Field(ge=0, le=4)
    evidence_status: EvidenceStatus = EvidenceStatus.NONE
    evidence_note: OptionalText = None
    evidence_references: list[EvidenceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_consistency(self) -> AssessmentResponse:
        """Keep evidence status, notes, and references logically consistent."""

        if self.evidence_status is EvidenceStatus.NONE and self.evidence_references:
            raise ValueError(
                "evidence_references must be empty when evidence_status is 'none'"
            )

        if self.maturity_level in {3, 4} and not self.evidence_note:
            raise ValueError(
                "evidence_note is required for maturity levels 3 and 4"
            )

        if self.evidence_status in {
            EvidenceStatus.DOCUMENTED,
            EvidenceStatus.REVIEWED,
        } and not self.evidence_references:
            raise ValueError(
                "at least one evidence reference is required for documented or reviewed evidence"
            )

        return self


class Assessment(StrictModel):
    """Versioned assessment session containing raw, reproducible inputs."""

    assessment_id: UUID = Field(default_factory=uuid4)
    status: AssessmentStatus = AssessmentStatus.DRAFT
    assessment_version: NonEmptyText = "1.0"
    rule_set_version: NonEmptyText = "1.0"
    owner_alias: NonEmptyText
    organization_profile: OrganizationProfile
    target_stage: TargetStage = TargetStage.DISCOVERY
    responses: list[AssessmentResponse] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime) -> datetime:
        """Reject ambiguous timestamps without timezone information."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_assessment_integrity(self) -> Assessment:
        """Reject duplicate answers and invalid lifecycle timestamps."""

        question_ids = [response.question_id for response in self.responses]
        duplicate_ids = sorted(
            question_id
            for question_id in set(question_ids)
            if question_ids.count(question_id) > 1
        )

        if duplicate_ids:
            raise ValueError(
                f"duplicate assessment responses: {', '.join(duplicate_ids)}"
            )

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")

        if self.status is AssessmentStatus.COMPLETED and not self.responses:
            raise ValueError("a completed assessment must contain responses")

        return self

    def response_by_question_id(self) -> dict[str, AssessmentResponse]:
        """Return responses indexed by configured question identifier."""

        return {response.question_id: response for response in self.responses}

    def model_dump_for_json(self) -> dict:
        """Return a JSON-compatible deterministic assessment record."""

        return self.model_dump(mode="json")
