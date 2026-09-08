"""GPU workload-input form and model builder."""
from typing import Any, Mapping
import streamlit as st
from src.models import ModelProfile, PerformanceTargets, WorkloadProfile
from .helpers import enum_label, lines


def render_workload_form(deployment_boundary: str, data_sensitivity: str) -> dict[str, Any]:
    st.subheader("4. Model and workload assumptions")
    st.caption("Outputs are neutral planning estimates and require measured validation.")
    left,right=st.columns(2)
    with left:
        family=st.text_input("Model family", value="Candidate model")
        version=st.text_input("Model version", value="Initial candidate")
        parameters=st.number_input("Parameter count, billions", min_value=0.1, value=8.0, step=0.1)
        license_status=st.selectbox("Model licence status", ["unknown","identified","reviewed","approved"], format_func=enum_label)
        precision=st.selectbox("Precision or quantization", ["fp32","fp16","bf16","int8","int4"], index=4, format_func=str.upper)
        context=st.number_input("Context length, tokens", min_value=1, value=8192, step=512)
    with right:
        concurrency=st.number_input("Expected concurrency", min_value=1, value=10)
        input_tokens=st.number_input("Average input tokens", min_value=0, value=1000, step=100)
        output_tokens=st.number_input("Average output tokens", min_value=0, value=500, step=100)
        latency=st.number_input("Latency target, ms", min_value=1.0, value=3000.0, step=100.0)
        throughput=st.number_input("Throughput target", min_value=0.1, value=5.0, step=0.1)
        throughput_unit=st.text_input("Throughput unit", value="requests_per_second")
        availability=st.selectbox("Availability target", ["development","business_hours","24x7"], format_func=enum_label)
        quality=st.text_input("Quality target", value="Meet pilot acceptance criteria")
    c1,c2=st.columns(2)
    with c1:
        rag=st.selectbox("RAG usage", ["none","optional","required"], format_func=enum_label)
        activity=st.selectbox("Activity type", ["inference","fine_tuning"], format_func=enum_label)
        serving=st.selectbox("Serving pattern", ["single_model","multi_model"], format_func=enum_label)
        scale=st.selectbox("Scale requirement", ["bounded","scalable"], format_func=enum_label)
    with c2:
        assumptions=st.text_area("Material assumptions, one per line", value="No measured benchmark is currently available\nConcurrency is an initial planning estimate", height=140)
    return {"family":family,"version":version,"parameters":parameters,"license_status":license_status,"precision":precision,"context":context,"concurrency":concurrency,"input_tokens":input_tokens,"output_tokens":output_tokens,"latency":latency,"throughput":throughput,"throughput_unit":throughput_unit,"availability":availability,"quality":quality,"rag":rag,"activity":activity,"serving":serving,"scale":scale,"deployment_boundary":deployment_boundary,"data_sensitivity":data_sensitivity,"assumptions":lines(assumptions)}


def build_workload(data: Mapping[str, Any]) -> WorkloadProfile:
    return WorkloadProfile(model=ModelProfile(family=data["family"],version=data["version"],parameter_count_billions=data["parameters"],license_status=data["license_status"],precision_or_quantization=data["precision"],context_length=data["context"]), targets=PerformanceTargets(concurrency=data["concurrency"],average_input_tokens=data["input_tokens"],average_output_tokens=data["output_tokens"],latency_target_ms=data["latency"],throughput_target=data["throughput"],throughput_unit=data["throughput_unit"],availability_target=data["availability"],quality_target=data["quality"]), deployment_boundary=data["deployment_boundary"],data_sensitivity=data["data_sensitivity"],rag_usage=data["rag"],activity_type=data["activity"],serving_pattern=data["serving"],scale_requirement=data["scale"],material_assumptions=data["assumptions"])
