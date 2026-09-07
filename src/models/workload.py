"""GPU workload planning data models for PARA-GIP.

The models in this module capture declared model, workload, deployment,
and benchmark inputs. Infrastructure recommendations and GPU Planning
Confidence are calculated by deterministic services, not by these models.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, field_validator, model_validator

from .assessment import DataSensitivity, DeploymentBoundary, StrictModel


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None


class ModelLicenseStatus(StrEnum):
    UNKNOWN = "unknown"
    IDENTIFIED = "identified"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class PrecisionType(StrEnum):
    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"
    OTHER = "other"


class ActivityType(StrEnum):
    INFERENCE = "inference"
    FINE_TUNING = "fine_tuning"


class ServingPattern(StrEnum):
    SINGLE_MODEL = "single_model"
    MULTI_MODEL = "multi_model"


class RAGUsage(StrEnum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class AvailabilityTarget(StrEnum):
    DEVELOPMENT = "development"
    BUSINESS_HOURS = "business_hours"
    TWENTY_FOUR_SEVEN = "24x7"


class BenchmarkStatus(StrEnum):
    NOT_PLANNED = "not_planned"
    PLANNED = "planned"
    COMPLETED = "completed"
    REVIEWED = "reviewed"


class ModelProfile(StrictModel):
    """Declared model identity, licence, and numerical-format assumptions."""

    family: NonEmptyText
    version: NonEmptyText
    parameter_count_billions: float = Field(gt=0)
    license_status: ModelLicenseStatus
    precision_or_quantization: PrecisionType
    context_length: int = Field(gt=0)
    alternative_precision: OptionalText = None

    @model_validator(mode="after")
    def other_precision_requires_description(self) -> ModelProfile:
        if (
            self.precision_or_quantization is PrecisionType.OTHER
            and not self.alternative_precision
        ):
            raise ValueError(
                "alternative_precision is required when precision is 'other'"
            )
        return self


class PerformanceTargets(StrictModel):
    """Measurable workload performance and quality objectives."""

    concurrency: int = Field(gt=0)
    average_input_tokens: int = Field(ge=0)
    average_output_tokens: int = Field(ge=0)
    latency_target_ms: float = Field(gt=0)
    throughput_target: float = Field(gt=0)
    throughput_unit: NonEmptyText
    availability_target: AvailabilityTarget
    quality_target: NonEmptyText

    @model_validator(mode="after")
    def token_volume_must_be_nonzero(self) -> PerformanceTargets:
        if self.average_input_tokens + self.average_output_tokens == 0:
            raise ValueError(
                "average input and output tokens cannot both be zero"
            )
        return self


class BenchmarkEvidence(StrictModel):
    """Metadata and measured results from a controlled workload benchmark."""

    status: BenchmarkStatus = BenchmarkStatus.NOT_PLANNED
    benchmark_name: OptionalText = None
    measured_at: datetime | None = None
    model_version: OptionalText = None
    hardware_description: OptionalText = None
    measured_latency_ms: float | None = Field(default=None, gt=0)
    measured_throughput: float | None = Field(default=None, gt=0)
    throughput_unit: OptionalText = None
    measured_gpu_utilization_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    measured_peak_vram_gb: float | None = Field(default=None, gt=0)
    quality_result: OptionalText = None
    reviewed_by: OptionalText = None

    @field_validator("measured_at")
    @classmethod
    def measured_timestamp_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("measured_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def benchmark_status_consistency(self) -> BenchmarkEvidence:
        measured_values = (
            self.measured_latency_ms,
            self.measured_throughput,
            self.measured_gpu_utilization_percent,
            self.measured_peak_vram_gb,
        )

        if self.status in {BenchmarkStatus.COMPLETED, BenchmarkStatus.REVIEWED}:
            if not self.benchmark_name or self.measured_at is None:
                raise ValueError(
                    "completed or reviewed benchmarks require a name and measured_at"
                )
            if all(value is None for value in measured_values):
                raise ValueError(
                    "completed or reviewed benchmarks require measured results"
                )

        if self.status is BenchmarkStatus.REVIEWED and not self.reviewed_by:
            raise ValueError(
                "reviewed_by is required when benchmark status is 'reviewed'"
            )

        if self.measured_throughput is not None and not self.throughput_unit:
            raise ValueError(
                "throughput_unit is required when measured_throughput is provided"
            )

        return self


class WorkloadProfile(StrictModel):
    """Complete set of declared inputs for responsible GPU planning."""

    workload_id: UUID = Field(default_factory=uuid4)
    model: ModelProfile
    targets: PerformanceTargets
    deployment_boundary: DeploymentBoundary
    data_sensitivity: DataSensitivity
    rag_usage: RAGUsage
    activity_type: ActivityType
    serving_pattern: ServingPattern
    scale_requirement: NonEmptyText = "bounded"
    benchmark_evidence: BenchmarkEvidence = Field(
        default_factory=BenchmarkEvidence
    )
    material_assumptions: list[NonEmptyText] = Field(default_factory=list)
    notes: OptionalText = None

    @field_validator("material_assumptions")
    @classmethod
    def assumptions_must_be_unique(cls, values: list[str]) -> list[str]:
        normalized = [value.casefold() for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("material assumptions must be unique")
        return values

    @model_validator(mode="after")
    def context_must_cover_expected_tokens(self) -> WorkloadProfile:
        expected_tokens = (
            self.targets.average_input_tokens
            + self.targets.average_output_tokens
        )
        if expected_tokens > self.model.context_length:
            raise ValueError(
                "average input and output tokens exceed model context length"
            )
        return self

    @model_validator(mode="after")
    def restricted_data_requires_private_boundary(self) -> WorkloadProfile:
        permitted_boundaries = {
            DeploymentBoundary.ON_PREMISES,
            DeploymentBoundary.SOVEREIGN_CLOUD,
            DeploymentBoundary.PRIVATE_CLOUD,
        }
        if (
            self.data_sensitivity is DataSensitivity.RESTRICTED
            and self.deployment_boundary not in permitted_boundaries
        ):
            raise ValueError(
                "restricted data requires an on-premises, sovereign-cloud, "
                "or private-cloud deployment boundary"
            )
        return self

    @property
    def benchmark_available(self) -> bool:
        """Return whether completed or reviewed benchmark evidence exists."""

        return self.benchmark_evidence.status in {
            BenchmarkStatus.COMPLETED,
            BenchmarkStatus.REVIEWED,
        }

    def model_dump_for_json(self) -> dict:
        """Return a JSON-compatible workload record."""

        return self.model_dump(mode="json")
