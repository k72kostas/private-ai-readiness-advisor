"""AI use-case discovery data models for PARA-GIP.

These models capture the business problem, ownership, expected value,
success measures, complexity inputs, pilot boundaries, and suitability
inputs. Classification and recommendations remain service responsibilities.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, field_validator, model_validator

from .assessment import StrictModel


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None


class UseCaseCategory(StrEnum):
    """High-level enterprise AI use-case categories."""

    KNOWLEDGE_ASSISTANT = "knowledge_assistant"
    DOCUMENT_PROCESSING = "document_processing"
    SUMMARIZATION = "summarization"
    CONTENT_GENERATION = "content_generation"
    CODE_ASSISTANT = "code_assistant"
    ANALYTICS = "analytics"
    CUSTOMER_SERVICE = "customer_service"
    OPERATIONS = "operations"
    OTHER = "other"


class ComplexityLevel(StrEnum):
    """Transparent use-case complexity vocabulary."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ComplexityFactor(StrEnum):
    """Factors considered by the deterministic complexity service."""

    DATA = "data"
    INTEGRATION = "integration"
    RISK = "risk"
    OPERATIONS = "operations"


class PilotSuitability(StrEnum):
    """Pilot-suitability result vocabulary."""

    NOT_DEFINED = "not_defined"
    NOT_SUITABLE = "not_suitable"
    SUITABLE_WITH_CONDITIONS = "suitable_with_conditions"
    SUITABLE = "suitable"


class AcceptabilityStatus(StrEnum):
    """Organizational acceptability status used by governance rules."""

    NOT_REVIEWED = "not_reviewed"
    ACCEPTABLE = "acceptable"
    ACCEPTABLE_WITH_CONDITIONS = "acceptable_with_conditions"
    PROHIBITED = "prohibited"


class MetricDirection(StrEnum):
    """Direction that represents improvement for a success metric."""

    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"


class ComplexityAssessment(StrictModel):
    """Declared complexity inputs with a deterministic result and rationale."""

    data: int = Field(ge=0, le=4)
    integration: int = Field(ge=0, le=4)
    risk: int = Field(ge=0, le=4)
    operations: int = Field(ge=0, le=4)
    level: ComplexityLevel | None = None
    rationale: OptionalText = None
    applied_rule_ids: list[NonEmptyText] = Field(default_factory=list)

    @model_validator(mode="after")
    def calculated_result_requires_traceability(self) -> ComplexityAssessment:
        """Require rationale and rule IDs when a calculated level is stored."""

        if self.level is not None and not self.rationale:
            raise ValueError("rationale is required when complexity level is set")
        if self.level is not None and not self.applied_rule_ids:
            raise ValueError("applied_rule_ids are required when complexity level is set")
        return self


class SuccessMetric(StrictModel):
    """A measurable pilot success criterion."""

    name: NonEmptyText
    baseline: OptionalText = None
    target: NonEmptyText
    unit: OptionalText = None
    direction: MetricDirection
    measurement_method: NonEmptyText


class PilotBoundary(StrictModel):
    """Explicit boundary for a controlled pilot."""

    in_scope: list[NonEmptyText] = Field(min_length=1)
    out_of_scope: list[NonEmptyText] = Field(default_factory=list)
    intended_users: list[NonEmptyText] = Field(min_length=1)
    permitted_data: list[NonEmptyText] = Field(min_length=1)
    prohibited_data: list[NonEmptyText] = Field(default_factory=list)
    duration_or_exit_condition: NonEmptyText

    @field_validator(
        "in_scope",
        "out_of_scope",
        "intended_users",
        "permitted_data",
        "prohibited_data",
    )
    @classmethod
    def list_values_must_be_unique(cls, values: list[str]) -> list[str]:
        """Reject duplicate values within pilot-boundary lists."""

        normalized = [value.casefold() for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("pilot-boundary list values must be unique")
        return values


class UseCase(StrictModel):
    """Business and pilot context for one proposed Private AI use case."""

    use_case_id: UUID = Field(default_factory=uuid4)
    name: NonEmptyText
    problem_statement: NonEmptyText
    category: UseCaseCategory
    intended_users: list[NonEmptyText] = Field(min_length=1)
    beneficiaries: list[NonEmptyText] = Field(min_length=1)
    process_owner: NonEmptyText
    business_sponsor: NonEmptyText
    expected_benefits: list[NonEmptyText] = Field(min_length=1)
    success_metrics: list[SuccessMetric] = Field(min_length=1)
    pilot_boundary: PilotBoundary
    complexity: ComplexityAssessment
    pilot_suitability: PilotSuitability = PilotSuitability.NOT_DEFINED
    pilot_suitability_rationale: OptionalText = None
    suggested_pilot_starting_point: OptionalText = None
    acceptability_status: AcceptabilityStatus = AcceptabilityStatus.NOT_REVIEWED
    consequential_output: bool = False

    @field_validator("intended_users", "beneficiaries", "expected_benefits")
    @classmethod
    def use_case_lists_must_be_unique(cls, values: list[str]) -> list[str]:
        """Reject duplicate user, beneficiary, and benefit entries."""

        normalized = [value.casefold() for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("use-case list values must be unique")
        return values

    @model_validator(mode="after")
    def pilot_suitability_requires_rationale(self) -> UseCase:
        """Require an explanation for every evaluated suitability result."""

        if (
            self.pilot_suitability is not PilotSuitability.NOT_DEFINED
            and not self.pilot_suitability_rationale
        ):
            raise ValueError(
                "pilot_suitability_rationale is required when suitability is evaluated"
            )
        return self

    @model_validator(mode="after")
    def prohibited_use_cannot_be_pilot_suitable(self) -> UseCase:
        """Prevent contradictory acceptability and pilot-suitability states."""

        suitable_states = {
            PilotSuitability.SUITABLE,
            PilotSuitability.SUITABLE_WITH_CONDITIONS,
        }
        if (
            self.acceptability_status is AcceptabilityStatus.PROHIBITED
            and self.pilot_suitability in suitable_states
        ):
            raise ValueError(
                "a prohibited use case cannot be marked suitable for a pilot"
            )
        return self

    def model_dump_for_json(self) -> dict:
        """Return a JSON-compatible use-case record."""

        return self.model_dump(mode="json")
