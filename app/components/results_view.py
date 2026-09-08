"""Result dashboard and in-memory report downloads."""
import json
import streamlit as st
from src.services.reporting import report_to_json, report_to_markdown


def render_results(result) -> None:
    score=result.score_result; decision=result.decision_result; gpu=result.gpu_planning_result
    st.header("Assessment result")
    c1,c2,c3=st.columns(3)
    c1.metric("Overall readiness", f"{score.overall_score:.1f}/100")
    c2.metric("Final classification", score.final_classification.value)
    c3.metric("Decision status", decision.status.value)
    c1,c2,c3=st.columns(3)
    c1.metric("Evidence Confidence", result.evidence_confidence.level.value)
    c2.metric("GPU Planning Confidence", gpu.planning_confidence.level.value)
    c3.metric("Critical stops", len(result.critical_findings))
    (st.error if result.deployment_blocked else st.info)(decision.rationale)
    with st.expander("Domain scores", expanded=True):
        st.dataframe([{"Domain":d.domain_name,"Earned":d.earned_points,"Available":d.maximum_points,"Percentage":d.percentage} for d in score.domain_scores], hide_index=True, use_container_width=True)
    with st.expander("Critical findings", expanded=result.deployment_blocked):
        if not result.critical_findings: st.success("No configured critical-stop conditions were triggered.")
        for f in result.critical_findings:
            st.markdown(f"**{f.name}** (`{f.rule_id}`)"); st.write(f.rationale); st.write("Corrective action:",f.corrective_action)
    with st.expander("GPU infrastructure planning", expanded=True):
        st.write("**Infrastructure tier:**",gpu.infrastructure_tier); st.write("**GPU memory class:**",gpu.gpu_memory_class); st.write("**Deployment pattern:**",gpu.deployment_pattern)
        st.write("**Estimated model runtime memory:**",gpu.planning_estimates.get("estimated_model_runtime_memory_gb"),"GB")
        st.caption("Planning estimate only, not a product recommendation or performance guarantee.")
    st.subheader("Adoption roadmap")
    tabs=st.tabs(["7-day plan","30-day plan","90-day plan"])
    plans=[result.roadmap_result.seven_day_action_plan,result.roadmap_result.thirty_day_pilot_plan,result.roadmap_result.ninety_day_scale_plan]
    for tab,actions in zip(tabs,plans,strict=True):
        with tab:
            if not actions: st.info("No actions generated for this horizon.")
            for a in actions:
                st.markdown(f"**{a.priority.value}: {a.action}**"); st.write("Owner role:",a.owner_role); st.write("Completion:",a.completion_criterion); st.caption("Source rules: "+", ".join(a.source_rule_ids)); st.divider()
    json_text=report_to_json(result.report_snapshot); markdown=report_to_markdown(result.report_snapshot)
    c1,c2=st.columns(2)
    c1.download_button("Download structured JSON",json_text,"para-gip-readiness-report.json","application/json",use_container_width=True)
    c2.download_button("Download Markdown report",markdown,"para-gip-readiness-report.md","text/markdown",use_container_width=True)
    with st.expander("Deterministic result JSON"): st.json(json.loads(json_text))
