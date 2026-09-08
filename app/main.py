"""Streamlit entry point for the modular PARA-GIP application."""
from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
from pydantic import ValidationError

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from src.config_loader import ConfigurationError, load_configuration_bundle
from src.models import Assessment, AssessmentResponse, OrganizationProfile
from src.services import AssessmentPipelineError, run_assessment_pipeline
from app.components.assessment_form import render_assessment_form
from app.components.organization_form import render_organization_form
from app.components.results_view import render_results
from app.components.use_case_form import build_use_case, render_use_case_form
from app.components.workload_form import build_workload, render_workload_form

st.set_page_config(page_title="PARA-GIP",page_icon="🧭",layout="wide",initial_sidebar_state="expanded")

@st.cache_resource
def configuration(): return load_configuration_bundle()

def sidebar():
    with st.sidebar:
        st.title("PARA-GIP"); st.caption("Private AI Readiness Advisor & GPU Infrastructure Planner")
        st.warning("Do not enter personal, restricted, confidential, credential, or secret information.")
        st.markdown("- Planning aid, not deployment approval\n- No specific GPU product recommendation\n- Formal reviews and benchmarks remain necessary")

def show_validation(error: ValidationError):
    st.error("Some required fields are incomplete or inconsistent.")
    for item in error.errors():
        location=" → ".join(str(p) for p in item["loc"])
        st.write(f"- **{location}:** {item['msg']}")

def main():
    sidebar(); st.title("Private AI Readiness Advisor & GPU Infrastructure Planner")
    st.write("Assess readiness, blockers, evidence, GPU planning, decision status, and adoption roadmap.")
    try: bundle=configuration()
    except ConfigurationError as error: st.error(f"Configuration could not be loaded: {error}"); st.stop()
    with st.form("assessment_form"):
        org=render_organization_form(); use_data=render_use_case_form(); responses=render_assessment_form(bundle.assessment_catalog)
        workload_data=render_workload_form(org["deployment_boundary"],org["data_sensitivity"])
        submitted=st.form_submit_button("Calculate readiness and generate roadmap",type="primary",use_container_width=True)
    if submitted:
        try:
            assessment=Assessment(owner_alias=org["owner_alias"],organization_profile=OrganizationProfile(size_band=org["size_band"],industry=org["industry"],deployment_boundary=org["deployment_boundary"],data_sensitivity=org["data_sensitivity"]),target_stage=org["target_stage"],responses=[AssessmentResponse(**r) for r in responses])
            result=run_assessment_pipeline(assessment=assessment,workload=build_workload(workload_data),use_case=build_use_case(use_data),configuration=bundle)
            st.session_state["pipeline_result"]=result
        except ValidationError as error: show_validation(error)
        except AssessmentPipelineError as error: st.error(f"Pipeline validation failed: {error}")
        except Exception as error: st.error(f"Assessment could not be completed: {error}")
    if st.session_state.get("pipeline_result") is not None: render_results(st.session_state["pipeline_result"])

if __name__ == "__main__": main()
