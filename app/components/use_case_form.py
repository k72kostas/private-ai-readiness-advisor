"""AI Use Case Discovery form and model builder."""
from typing import Any, Mapping
import streamlit as st
from src.models import ComplexityAssessment, PilotBoundary, SuccessMetric, UseCase
from .helpers import enum_label, lines


def render_use_case_form() -> dict[str, Any]:
    st.subheader("2. AI Use Case Discovery")
    st.caption("Define a bounded, owned, measurable pilot use case before infrastructure decisions.")
    left, right = st.columns(2)
    with left:
        name = st.text_input("Use-case name", placeholder="Internal Knowledge Assistant")
        problem_statement = st.text_area("Business problem", height=110)
        category = st.selectbox("Use-case category", ["knowledge_assistant", "document_processing", "summarization", "content_generation", "code_assistant", "analytics", "customer_service", "operations", "other"], format_func=enum_label)
    with right:
        process_owner = st.text_input("Process owner")
        business_sponsor = st.text_input("Business sponsor")
        acceptability_status = st.selectbox("Acceptability status", ["not_reviewed", "acceptable", "acceptable_with_conditions", "prohibited"], format_func=enum_label)
        consequential_output = st.checkbox("The use case produces consequential output")
    a, b = st.columns(2)
    with a:
        intended_users = st.text_area("Intended users, one per line")
        beneficiaries = st.text_area("Beneficiaries, one per line")
    with b:
        expected_benefits = st.text_area("Expected benefits, one per line")
        suggested = st.text_area("Suggested pilot starting point")
    st.markdown("#### Measurable success criterion")
    a, b = st.columns(2)
    with a:
        metric_name = st.text_input("Metric name")
        metric_baseline = st.text_input("Current baseline")
        metric_target = st.text_input("Target")
    with b:
        metric_unit = st.text_input("Metric unit")
        metric_direction = st.selectbox("Improvement direction", ["increase", "decrease", "maintain"], format_func=enum_label)
        measurement_method = st.text_input("Measurement method")
    st.markdown("#### Pilot boundary")
    a, b = st.columns(2)
    with a:
        in_scope = st.text_area("In scope, one per line")
        out_of_scope = st.text_area("Out of scope, one per line")
        pilot_users = st.text_area("Pilot users, one per line")
    with b:
        permitted_data = st.text_area("Permitted pilot data, one per line")
        prohibited_data = st.text_area("Prohibited pilot data, one per line")
        exit_condition = st.text_input("Pilot duration or exit condition")
    st.markdown("#### Initial complexity assessment")
    cols = st.columns(4)
    data_complexity = cols[0].slider("Data", 0, 4, 2)
    integration_complexity = cols[1].slider("Integration", 0, 4, 2)
    risk_complexity = cols[2].slider("Risk", 0, 4, 2)
    operations_complexity = cols[3].slider("Operations", 0, 4, 2)
    return {"name": name, "problem_statement": problem_statement, "category": category, "process_owner": process_owner, "business_sponsor": business_sponsor, "acceptability_status": acceptability_status, "consequential_output": consequential_output, "intended_users": lines(intended_users), "beneficiaries": lines(beneficiaries), "expected_benefits": lines(expected_benefits), "suggested_pilot_starting_point": suggested.strip() or None, "metric_name": metric_name, "metric_baseline": metric_baseline.strip() or None, "metric_target": metric_target, "metric_unit": metric_unit.strip() or None, "metric_direction": metric_direction, "measurement_method": measurement_method, "in_scope": lines(in_scope), "out_of_scope": lines(out_of_scope), "pilot_users": lines(pilot_users), "permitted_data": lines(permitted_data), "prohibited_data": lines(prohibited_data), "exit_condition": exit_condition, "data_complexity": data_complexity, "integration_complexity": integration_complexity, "risk_complexity": risk_complexity, "operations_complexity": operations_complexity}


def build_use_case(data: Mapping[str, Any]) -> UseCase:
    return UseCase(name=data["name"], problem_statement=data["problem_statement"], category=data["category"], intended_users=data["intended_users"], beneficiaries=data["beneficiaries"], process_owner=data["process_owner"], business_sponsor=data["business_sponsor"], expected_benefits=data["expected_benefits"], success_metrics=[SuccessMetric(name=data["metric_name"], baseline=data["metric_baseline"], target=data["metric_target"], unit=data["metric_unit"], direction=data["metric_direction"], measurement_method=data["measurement_method"])], pilot_boundary=PilotBoundary(in_scope=data["in_scope"], out_of_scope=data["out_of_scope"], intended_users=data["pilot_users"], permitted_data=data["permitted_data"], prohibited_data=data["prohibited_data"], duration_or_exit_condition=data["exit_condition"]), complexity=ComplexityAssessment(data=data["data_complexity"], integration=data["integration_complexity"], risk=data["risk_complexity"], operations=data["operations_complexity"]), suggested_pilot_starting_point=data["suggested_pilot_starting_point"], acceptability_status=data["acceptability_status"], consequential_output=data["consequential_output"])
