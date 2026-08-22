import os
from openai import OpenAI

def executive_summary(payload: dict) -> str:
    base_url=os.getenv("NIM_BASE_URL")
    model=os.getenv("NIM_MODEL")
    if not base_url or not model:
        return "AI narrative disabled. Configure NIM_BASE_URL and NIM_MODEL to use an OpenAI-compatible NVIDIA NIM endpoint."
    client=OpenAI(base_url=base_url, api_key=os.getenv("NIM_API_KEY","not-required"))
    prompt=("Write a concise enterprise AI-readiness summary. Clearly distinguish facts, assumptions, risks, and next actions. "
            "Do not claim vendor certification or guaranteed capacity. Data: "+str(payload))
    r=client.chat.completions.create(model=model,messages=[{"role":"user","content":prompt}],temperature=0.2,max_tokens=450)
    return r.choices[0].message.content
