from .models import AssessmentInput, AssessmentResult

def assess(x: AssessmentInput) -> AssessmentResult:
    score = 35
    score += 10 if x.deployment in {"On-premises", "Hybrid"} else 6
    score += 10 if x.sensitivity in {"Public", "Internal"} else 4
    score += 8 if x.availability != "24x7" else 3
    score += 12 if x.concurrent_users <= 100 else 6 if x.concurrent_users <= 500 else 2
    score += 10 if x.model_size_b <= 14 else 5 if x.model_size_b <= 70 else 1
    score = min(score, 100)
    maturity = "Ready for pilot" if score >= 70 else "Preparation required" if score >= 50 else "Discovery required"

    # Approximate weight memory at 4-bit plus 35% runtime overhead.
    vram = round(x.model_size_b * 0.5 * 1.35, 1)
    if vram <= 24: tier = "Single 24 GB class GPU for prototype"
    elif vram <= 48: tier = "Single 48 GB class GPU or equivalent"
    elif vram <= 96: tier = "80-96 GB class GPU or multi-GPU configuration"
    else: tier = "Multi-GPU configuration; benchmark required"

    architecture = [
        "Streamlit assessment interface",
        "Policy and validation layer",
        "Open model served through an OpenAI-compatible NVIDIA NIM endpoint",
        "Optional vector database for approved enterprise knowledge",
        "Telemetry, audit logging, and human review before production use",
    ]
    risks=[]
    if x.sensitivity in {"Confidential", "Restricted"}: risks.append("Sensitive data requires access controls, retention rules, and approved deployment boundaries.")
    if x.availability == "24x7": risks.append("High availability, failover, capacity testing, and operational ownership are not yet validated.")
    if x.concurrent_users > 100: risks.append("Concurrency assumptions require load testing with the selected model and hardware.")
    if x.model_size_b > 70: risks.append("Large model memory and latency may materially increase infrastructure requirements.")
    risks.append("Model accuracy, prompt injection, unsafe output, and licensing must be evaluated before production use.")
    next_steps=[
        "Select one measurable pilot use case and success metric.",
        "Choose an openly licensed model and verify its license for the intended use.",
        "Run latency, throughput, quality, and GPU utilization benchmarks.",
        "Document data classification, access control, audit, and human-approval requirements.",
        "Publish reproducible test data, assumptions, limitations, and results.",
    ]
    return AssessmentResult(readiness_score=score,maturity=maturity,estimated_vram_gb=vram,gpu_tier=tier,architecture=architecture,risks=risks,next_steps=next_steps,disclaimer="Planning estimate only. It is not an NVIDIA, VMware, Broadcom, or hardware-vendor sizing recommendation. Validate with benchmarks and official product guidance.")
