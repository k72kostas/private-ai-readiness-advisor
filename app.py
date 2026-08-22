import json
import streamlit as st
from src.models import AssessmentInput
from src.assessment import assess
from src.llm import executive_summary

st.set_page_config(page_title="Private AI Readiness Advisor", page_icon="🟢", layout="wide")
st.title("Private AI Readiness Advisor")
st.caption("Open-source planning assistant for responsible enterprise AI pilots")
with st.sidebar:
    st.header("Project")
    st.write("Built for transparent, reproducible AI infrastructure planning.")
    use_ai=st.toggle("Generate AI narrative", value=False)

with st.form("assessment"):
    a,b,c=st.columns(3)
    org=a.number_input("Organization size",1,1000000,2000)
    users=b.number_input("Expected concurrent users",1,100000,50)
    workload=c.selectbox("Primary workload",["Knowledge assistant","Document summarization","Code assistant","Training content"])
    deployment=a.selectbox("Deployment boundary",["On-premises","Sovereign cloud","Public cloud","Hybrid"])
    sensitivity=b.selectbox("Data sensitivity",["Public","Internal","Confidential","Restricted"])
    availability=c.selectbox("Availability target",["Development","Business hours","24x7"])
    model=a.slider("Model size, billions of parameters",1,400,8)
    tokens=b.number_input("Average tokens per request",64,32768,1024)
    submitted=st.form_submit_button("Generate readiness plan",type="primary",use_container_width=True)

if submitted:
    inp=AssessmentInput(organization_size=org,concurrent_users=users,workload=workload,deployment=deployment,sensitivity=sensitivity,availability=availability,model_size_b=model,avg_tokens_per_request=tokens)
    result=assess(inp)
    x,y,z=st.columns(3)
    x.metric("Readiness score",f"{result.readiness_score}/100")
    y.metric("Status",result.maturity)
    z.metric("Estimated VRAM",f"{result.estimated_vram_gb} GB")
    st.info(result.disclaimer)
    left,right=st.columns(2)
    with left:
        st.subheader("Suggested prototype tier")
        st.write(result.gpu_tier)
        st.subheader("Reference architecture")
        for item in result.architecture: st.write("• "+item)
    with right:
        st.subheader("Risks")
        for item in result.risks: st.warning(item)
        st.subheader("Next steps")
        for item in result.next_steps: st.write("✓ "+item)
    payload={"inputs":inp.model_dump(),"result":result.model_dump()}
    if use_ai:
        st.subheader("AI-generated executive summary")
        with st.spinner("Generating..."):
            try: st.write(executive_summary(payload))
            except Exception as e: st.error(f"Narrative generation failed: {e}")
    st.download_button("Download JSON report",json.dumps(payload,indent=2),"readiness-report.json","application/json")
