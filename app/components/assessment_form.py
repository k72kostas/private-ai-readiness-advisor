"""Configuration-driven readiness-assessment form."""
from typing import Any, Mapping
import streamlit as st

MATURITY = {0:"0 · Not started or unknown",1:"1 · Informal or discussed",2:"2 · Partially defined",3:"3 · Implemented for the pilot",4:"4 · Documented, measured, and repeatable"}
EVIDENCE = {"none":"None","self_declared":"Self-declared","partially_supported":"Partially supported","documented":"Documented","reviewed":"Reviewed"}


def render_assessment_form(catalog: Mapping[str, Any]) -> list[dict[str, Any]]:
    st.subheader("3. Private AI readiness assessment")
    responses=[]
    for domain in catalog["domains"]:
        with st.expander(f"{domain['name']} · {domain['weight']} points"):
            st.caption(domain.get("primary_question", ""))
            for q in domain["questions"]:
                st.markdown(f"**{q['id']} · {q['text']}**")
                c1,c2=st.columns(2)
                maturity=c1.select_slider("Maturity level", options=list(MATURITY), value=0, format_func=lambda v: MATURITY[v], key=f"maturity_{q['id']}")
                evidence=c2.selectbox("Evidence status", list(EVIDENCE), format_func=lambda v:EVIDENCE[v], key=f"evidence_{q['id']}")
                note=st.text_area("Evidence note", key=f"note_{q['id']}", help="Required for maturity levels 3 and 4. Do not include confidential content.")
                responses.append({"question_id":q["id"],"maturity_level":maturity,"evidence_status":evidence,"evidence_note":note.strip() or None})
                st.divider()
    return responses
