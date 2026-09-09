"""Reusable factories for PARA-GIP integration scenarios."""

from __future__ import annotations

from typing import Any, Mapping

from src.config_loader import ConfigurationBundle
from src.models import (
    Assessment,
    AssessmentResponse,
    ComplexityAssessment,
    ModelProfile,
    OrganizationProfile,
    PerformanceTargets,
    PilotBoundary,
    SuccessMetric,
    UseCase,
    WorkloadProfile,
)


def build_assessment(
    configuration: ConfigurationBundle,
    *,
    default_maturity: int = 2,
    default_evidence: str = "self_declared",
    response_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    data_sensitivity: str = "internal",
    deployment_boundary: str = "on_premises",
    target_stage: str = "foundation",
) -> Assessment:
    """Build a complete configured assessment with optional overrides."""

    overrides = response_overrides or {}
    responses: list[AssessmentResponse] = []

    for domain in configuration.assessment_catalog["domains"]:
        for question in domain["questions"]:
            question_id = question["id"]
            values: dict[str, Any] = {
                "question_id": question_id,
                "maturity_level": default_maturity,
                "evidence_status": default_evidence,
            }
            values.update(overrides.get(question_id, {}))

            if (
                values["maturity_level"] in {3, 4}
                and not values.get("evidence_note")
            ):
                values["evidence_note"] = (
                    "Integration-test evidence note."
                )

            responses.append(AssessmentResponse(**values))

    return Assessment(
        owner_alias="integration-test-owner",
        organization_profile=OrganizationProfile(
            size_band="medium",
            industry="technology",
            deployment_boundary=deployment_boundary,
            data_sensitivity=data_sensitivity,
        ),
        target_stage=target_stage,
        responses=responses,
    )


def build_use_case(
    *,
    acceptability_status: str = "acceptable",
    consequential_output: bool = False,
) -> UseCase:
    """Build a bounded and measurable baseline use case."""

    return UseCase(
        name="Internal Knowledge Assistant",
        problem_statement=(
            "Employees need faster access to approved internal "
            "information."
        ),
        category="knowledge_assistant",
        intended_users=["Employees"],
        beneficiaries=["Service teams"],
        process_owner="Knowledge Management",
        business_sponsor="Business Sponsor",
        expected_benefits=[
            "Reduce information retrieval time",
        ],
        success_metrics=[
            SuccessMetric(
                name="Information retrieval time",
                baseline="10 minutes",
                target="3 minutes",
                unit="minutes",
                direction="decrease",
                measurement_method="Pilot task timing",
            ),
        ],
        pilot_boundary=PilotBoundary(
            in_scope=["Approved internal document search"],
            out_of_scope=["Automated decisions"],
            intended_users=["Internal pilot group"],
            permitted_data=["Approved internal documents"],
            prohibited_data=["Restricted personal data"],
            duration_or_exit_condition=(
                "Pilot acceptance criteria completed"
            ),
        ),
        complexity=ComplexityAssessment(
            data=2,
            integration=2,
            risk=2,
            operations=2,
        ),
        suggested_pilot_starting_point=(
            "Run a bounded pilot with approved internal documents."
        ),
        acceptability_status=acceptability_status,
        consequential_output=consequential_output,
    )


def build_workload(
    *,
    data_sensitivity: str = "internal",
    deployment_boundary: str = "on_premises",
) -> WorkloadProfile:
    """Build the baseline unbenchmarked 8B INT4 workload."""

    return WorkloadProfile(
        model=ModelProfile(
            family="Llama",
            version="candidate-model",
            parameter_count_billions=8,
            license_status="identified",
            precision_or_quantization="int4",
            context_length=8192,
        ),
        targets=PerformanceTargets(
            concurrency=10,
            average_input_tokens=1000,
            average_output_tokens=500,
            latency_target_ms=3000,
            throughput_target=5,
            throughput_unit="requests_per_second",
            availability_target="development",
            quality_target="Meet pilot acceptance criteria",
        ),
        deployment_boundary=deployment_boundary,
        data_sensitivity=data_sensitivity,
        rag_usage="required",
        activity_type="inference",
        serving_pattern="single_model",
        scale_requirement="bounded",
        material_assumptions=[
            "No measured benchmark is currently available",
            "Concurrency is an initial planning estimate",
        ],
    )
