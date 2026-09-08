"""Organization-context form component."""
from typing import Any
import streamlit as st
from .helpers import enum_label


def render_organization_form() -> dict[str, Any]:
    st.subheader("1. Organization context")
    left, right = st.columns(2)
    with left:
        owner_alias = st.text_input("Assessment owner alias", placeholder="assessment-owner")
        size_band = st.selectbox("Organization size band", ["small", "medium", "large", "enterprise"], format_func=enum_label)
        industry = st.text_input("Industry", placeholder="Technology, energy, government...")
    with right:
        deployment_boundary = st.selectbox("Deployment boundary", ["on_premises", "private_cloud", "sovereign_cloud", "hybrid"], format_func=enum_label)
        data_sensitivity = st.selectbox("Highest data sensitivity", ["public", "internal", "confidential", "restricted"], format_func=enum_label)
        target_stage = st.selectbox("Target assessment stage", ["discovery", "foundation", "controlled_prototype", "benchmarked_pilot", "production_assessment"], format_func=enum_label)
    return {"owner_alias": owner_alias, "size_band": size_band, "industry": industry, "deployment_boundary": deployment_boundary, "data_sensitivity": data_sensitivity, "target_stage": target_stage}
