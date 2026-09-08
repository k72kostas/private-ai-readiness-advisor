"""Streamlit application entry point for PARA-GIP Version 1."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import streamlit as st


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.config_loader import ConfigurationError, load_configuration_bundle
from src.models import (
    Assessment,
    AssessmentResponse,
    ModelProfile,
    OrganizationProfile,
    PerformanceTargets,
    WorkloadProfile,
)
from src.services import (
    AssessmentPipelineError,
    run_assessment_pipeline,
)
from src.services.reporting import report_to_json, report_to_markdown


st.set_page_config(
    page_title="PARA-GIP",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)


MATURITY_LABELS = {
    0: "0 · Not started or unknown",
    1: "1 · Informal or discussed",
    2: "2 · Partially defined",
    3: "3 · Implemented for the pilot",
    4: "4 · Documented, measured, and repeatable",
}

EVIDENCE_LABELS = {
    "none": "None",
    "self_declared": "Self-declared",
    "partially_supported": "Partially supported",
    "documented": "Documented",
    "reviewed": "Reviewed",
}


def _initialize_state() -> None:
    """Initialize application state used across Streamlit reruns."""

    st.session_state.setdefault("pipeline_result", None)
    st.session_state.setdefault("assessment_submitted", False)


@st.cache_resource
def _configuration_bundle():
    """Load the immutable configuration bundle once per app process."""

    return load_configuration_bundle()


def _enum_label(value: str) -> str:
    """Convert a machine-readable enumeration to a UI label."""

    return value.replace("_", " ").title()


def _render_sidebar() -> None:
    """Render application identity, scope, and safety guidance."""

    with st.sidebar:
        st.title("PARA-GIP")
        st.caption("Private AI Readiness Advisor & GPU Infrastructure Planner")
        st.info(
            "Version 1 provides deterministic readiness, governance, "
            "GPU-planning, decision, roadmap, and reporting guidance."
        )
        st.warning(
            "Do not enter personal, restricted, confidential, credential, "
            "or secret information into this demonstration interface."
        )
        st.markdown("### Important boundaries")
        st.markdown(
            "- Planning aid, not deployment approval\n"
            "- No specific GPU product recommendation\n"
            "- No guaranteed performance or production sizing\n"
            "- Formal reviews and measured benchmarks remain necessary"
        )


def _organization_section() -> dict[str, str]:
    """Render and return organization-level inputs."""

    st.subheader("1. Organization context")
    column_one, column_two = st.columns(2)

    with column_one:
        owner_alias = st.text_input(
            "Assessment owner alias",
            placeholder="assessment-owner",
        )
        size_band = st.selectbox(
            "Organization size band",
            options=["small", "medium", "large", "enterprise"],
            format_func=_enum_label,
        )
        industry = st.text_input(
            "Industry",
            placeholder="Technology, energy, government, education...",
        )

    with column_two:
        deployment_boundary = st.selectbox(
            "Deployment boundary",
            options=[
                "on_premises",
                "private_cloud",
                "sovereign_cloud",
                "hybrid",
            ],
            format_func=_enum_label,
        )
        data_sensitivity = st.selectbox(
            "Highest data sensitivity",
            options=["public", "internal", "confidential", "restricted"],
            format_func=_enum_label,
        )
        target_stage = st.selectbox(
            "Target assessment stage",
            options=[
                "discovery",
                "foundation",
                "controlled_prototype",
                "benchmarked_pilot",
                "production_assessment",
            ],
            format_func=_enum_label,
        )

    return {
        "owner_alias": owner_alias,
        "size_band": size_band,
        "industry": industry,
        "deployment_boundary": deployment_boundary,
        "data_sensitivity": data_sensitivity,
        "target_stage": target_stage,
    }


def _assessment_section(catalog: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Render configured readiness questions and return raw responses."""

    st.subheader("2. Private AI readiness assessment")
    st.caption(
        "Questions and maximum points are loaded from "
        "config/assessment_questions.yaml."
    )

    responses: list[dict[str, Any]] = []
    for domain in catalog["domains"]:
        with st.expander(
            f"{domain['name']} · {domain['weight']} points",
            expanded=False,
        ):
            st.caption(domain["primary_question"])

            for question in domain["questions"]:
                st.markdown(f"**{question['id']} · {question['text']}**")
                maturity_column, evidence_column = st.columns(2)

                with maturity_column:
                    maturity_level = st.select_slider(
                        "Maturity level",
                        options=list(MATURITY_LABELS),
                        value=0,
                        format_func=lambda value: MATURITY_LABELS[value],
                        key=f"maturity_{question['id']}",
                    )

                with evidence_column:
                    evidence_status = st.selectbox(
                        "Evidence status",
                        options=list(EVIDENCE_LABELS),
                        format_func=lambda value: EVIDENCE_LABELS[value],
                        key=f"evidence_{question['id']}",
                    )

                evidence_note = st.text_area(
                    "Evidence note",
                    placeholder=(
                        "Required for maturity levels 3 and 4. Do not include "
                        "confidential content."
                    ),
                    key=f"note_{question['id']}",
                    height=80,
                )

                responses.append(
                    {
                        "question_id": question["id"],
                        "maturity_level": maturity_level,
                        "evidence_status": evidence_status,
                        "evidence_note": evidence_note.strip() or None,
                    }
                )
                st.divider()

    return responses


def _workload_section(deployment_boundary: str, data_sensitivity: str) -> dict[str, Any]:
    """Render model and workload assumptions used by GPU planning."""

    st.subheader("3. Model and workload assumptions")
    st.caption(
        "All infrastructure outputs are neutral planning estimates and require "
        "measured validation."
    )

    model_column, workload_column = st.columns(2)

    with model_column:
        st.markdown("#### Model")
        model_family = st.text_input("Model family", value="Candidate model")
        model_version = st.text_input("Model version", value="Initial candidate")
        parameter_count = st.number_input(
            "Parameter count, billions",
            min_value=0.1,
            value=8.0,
            step=0.1,
        )
        license_status = st.selectbox(
            "Model licence status",
            options=["unknown", "identified", "reviewed", "approved"],
            format_func=_enum_label,
        )
        precision = st.selectbox(
            "Precision or quantization",
            options=["fp32", "fp16", "bf16", "int8", "int4"],
            index=4,
            format_func=str.upper,
        )
        context_length = st.number_input(
            "Context length, tokens",
            min_value=1,
            value=8192,
            step=512,
        )

    with workload_column:
        st.markdown("#### Workload")
        concurrency = st.number_input(
            "Expected concurrency",
            min_value=1,
            value=10,
        )
        input_tokens = st.number_input(
            "Average input tokens",
            min_value=0,
            value=1000,
            step=100,
        )
        output_tokens = st.number_input(
            "Average output tokens",
            min_value=0,
            value=500,
            step=100,
        )
        latency_target = st.number_input(
            "Latency target, milliseconds",
            min_value=1.0,
            value=3000.0,
            step=100.0,
        )
        throughput_target = st.number_input(
            "Throughput target",
            min_value=0.1,
            value=5.0,
            step=0.1,
        )
        throughput_unit = st.text_input(
            "Throughput unit",
            value="requests_per_second",
        )
        availability_target = st.selectbox(
            "Availability target",
            options=["development", "business_hours", "24x7"],
            format_func=_enum_label,
        )
        quality_target = st.text_input(
            "Quality target",
            value="Meet pilot acceptance criteria",
        )

    option_column, assumption_column = st.columns(2)
    with option_column:
        rag_usage = st.selectbox(
            "RAG usage",
            options=["none", "optional", "required"],
            format_func=_enum_label,
        )
        activity_type = st.selectbox(
            "Activity type",
            options=["inference", "fine_tuning"],
            format_func=_enum_label,
        )
        serving_pattern = st.selectbox(
            "Serving pattern",
            options=["single_model", "multi_model"],
            format_func=_enum_label,
        )
        scale_requirement = st.selectbox(
            "Scale requirement",
            options=["bounded", "scalable"],
            format_func=_enum_label,
        )

    with assumption_column:
        material_assumptions = st.text_area(
            "Material assumptions, one per line",
            value=(
                "No measured benchmark is currently available\n"
                "Concurrency is an initial planning estimate"
            ),
            height=140,
        )

    return {
        "model_family": model_family,
        "model_version": model_version,
        "parameter_count": parameter_count,
        "license_status": license_status,
        "precision": precision,
        "context_length": context_length,
        "concurrency": concurrency,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_target": latency_target,
        "throughput_target": throughput_target,
        "throughput_unit": throughput_unit,
        "availability_target": availability_target,
        "quality_target": quality_target,
        "rag_usage": rag_usage,
        "activity_type": activity_type,
        "serving_pattern": serving_pattern,
        "scale_requirement": scale_requirement,
        "deployment_boundary": deployment_boundary,
        "data_sensitivity": data_sensitivity,
        "material_assumptions": [
            value.strip()
            for value in material_assumptions.splitlines()
            if value.strip()
        ],
    }


def _build_inputs(
    organization: Mapping[str, Any],
    responses: list[Mapping[str, Any]],
    workload_data: Mapping[str, Any],
) -> tuple[Assessment, WorkloadProfile]:
    """Create validated domain models from submitted UI values."""

    assessment = Assessment(
        owner_alias=organization["owner_alias"],
        organization_profile=OrganizationProfile(
            size_band=organization["size_band"],
            industry=organization["industry"],
            deployment_boundary=organization["deployment_boundary"],
            data_sensitivity=organization["data_sensitivity"],
        ),
        target_stage=organization["target_stage"],
        responses=[AssessmentResponse(**response) for response in responses],
    )

    workload = WorkloadProfile(
        model=ModelProfile(
            family=workload_data["model_family"],
            version=workload_data["model_version"],
            parameter_count_billions=workload_data["parameter_count"],
            license_status=workload_data["license_status"],
            precision_or_quantization=workload_data["precision"],
            context_length=workload_data["context_length"],
        ),
        targets=PerformanceTargets(
            concurrency=workload_data["concurrency"],
            average_input_tokens=workload_data["input_tokens"],
            average_output_tokens=workload_data["output_tokens"],
            latency_target_ms=workload_data["latency_target"],
            throughput_target=workload_data["throughput_target"],
            throughput_unit=workload_data["throughput_unit"],
            availability_target=workload_data["availability_target"],
            quality_target=workload_data["quality_target"],
        ),
        deployment_boundary=workload_data["deployment_boundary"],
        data_sensitivity=workload_data["data_sensitivity"],
        rag_usage=workload_data["rag_usage"],
        activity_type=workload_data["activity_type"],
        serving_pattern=workload_data["serving_pattern"],
        scale_requirement=workload_data["scale_requirement"],
        material_assumptions=workload_data["material_assumptions"],
    )
    return assessment, workload


def _render_results(result: Any) -> None:
    """Render deterministic pipeline results and download controls."""

    score = result.score_result
    decision = result.decision_result
    gpu = result.gpu_planning_result

    st.header("Assessment result")
    score_column, classification_column, decision_column = st.columns(3)
    score_column.metric("Overall readiness", f"{score.overall_score:.1f}/100")
    classification_column.metric(
        "Final classification",
        score.final_classification.value,
    )
    decision_column.metric("Decision status", decision.status.value)

    confidence_one, confidence_two, blocker_column = st.columns(3)
    confidence_one.metric(
        "Evidence Confidence",
        result.evidence_confidence.level.value,
    )
    confidence_two.metric(
        "GPU Planning Confidence",
        gpu.planning_confidence.level.value,
    )
    blocker_column.metric(
        "Critical stops",
        len(result.critical_findings),
    )

    if result.deployment_blocked:
        st.error(
            "Deployment is blocked. The numerical score remains visible, "
            "but the triggered critical stops must be remediated."
        )
    elif decision.status.value == "Proceed with Conditions":
        st.warning(decision.rationale)
    else:
        st.info(decision.rationale)

    with st.expander("Domain scores", expanded=True):
        st.dataframe(
            [
                {
                    "Domain": domain.domain_name,
                    "Earned points": domain.earned_points,
                    "Available points": domain.maximum_points,
                    "Percentage": domain.percentage,
                }
                for domain in score.domain_scores
            ],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("Critical findings", expanded=result.deployment_blocked):
        if not result.critical_findings:
            st.success("No configured critical-stop conditions were triggered.")
        for finding in result.critical_findings:
            st.markdown(f"**{finding.name}** (`{finding.rule_id}`)")
            st.write(finding.rationale)
            st.write("Corrective action:", finding.corrective_action)

    with st.expander("GPU infrastructure planning", expanded=True):
        st.write("**Infrastructure tier:**", gpu.infrastructure_tier)
        st.write("**GPU memory class:**", gpu.gpu_memory_class)
        st.write("**Deployment pattern:**", gpu.deployment_pattern)
        st.write(
            "**Estimated model runtime memory:**",
            gpu.planning_estimates.get("estimated_model_runtime_memory_gb"),
            "GB",
        )
        st.caption(
            "This is a planning estimate, not a product recommendation or "
            "performance guarantee."
        )
        st.markdown("**Material assumptions**")
        for assumption in gpu.material_assumptions:
            st.write("-", assumption)

    st.subheader("Adoption roadmap")
    roadmap = result.roadmap_result
    roadmap_tabs = st.tabs(["7-day plan", "30-day plan", "90-day plan"])
    plans = [
        roadmap.seven_day_action_plan,
        roadmap.thirty_day_pilot_plan,
        roadmap.ninety_day_scale_plan,
    ]
    for tab, actions in zip(roadmap_tabs, plans, strict=True):
        with tab:
            if not actions:
                st.info("No actions generated for this horizon.")
            for action in actions:
                st.markdown(f"**{action.priority.value}: {action.action}**")
                st.write("Owner role:", action.owner_role)
                st.write("Completion:", action.completion_criterion)
                st.caption("Source rules: " + ", ".join(action.source_rule_ids))
                st.divider()

    json_text = report_to_json(result.report_snapshot)
    markdown_text = report_to_markdown(result.report_snapshot)
    download_one, download_two = st.columns(2)
    with download_one:
        st.download_button(
            "Download structured JSON",
            data=json_text,
            file_name="para-gip-readiness-report.json",
            mime="application/json",
            use_container_width=True,
        )
    with download_two:
        st.download_button(
            "Download Markdown report",
            data=markdown_text,
            file_name="para-gip-readiness-report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with st.expander("Deterministic result JSON"):
        st.json(json.loads(json_text))


def main() -> None:
    """Render and run the PARA-GIP Streamlit application."""

    _initialize_state()
    _render_sidebar()

    st.title("Private AI Readiness Advisor & GPU Infrastructure Planner")
    st.write(
        "Assess Private AI readiness, identify deployment blockers, evaluate "
        "evidence and GPU-planning confidence, and generate a traceable roadmap."
    )

    try:
        bundle = _configuration_bundle()
    except ConfigurationError as error:
        st.error(f"Configuration could not be loaded: {error}")
        st.stop()

    with st.form("assessment_form"):
        organization = _organization_section()
        responses = _assessment_section(bundle.assessment_catalog)
        workload_data = _workload_section(
            organization["deployment_boundary"],
            organization["data_sensitivity"],
        )
        submitted = st.form_submit_button(
            "Calculate readiness and generate roadmap",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        try:
            assessment, workload = _build_inputs(
                organization,
                responses,
                workload_data,
            )
            st.session_state.pipeline_result = run_assessment_pipeline(
                assessment=assessment,
                workload=workload,
                configuration=bundle,
            )
            st.session_state.assessment_submitted = True
        except Exception as error:
            st.session_state.pipeline_result = None
            st.session_state.assessment_submitted = False
            st.error(f"Assessment could not be completed: {error}")

    if st.session_state.pipeline_result is not None:
        _render_results(st.session_state.pipeline_result)
    elif st.session_state.assessment_submitted:
        st.warning("No pipeline result is available.")


if __name__ == "__main__":
    main()
