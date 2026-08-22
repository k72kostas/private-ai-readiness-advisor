from pydantic import BaseModel, Field
from typing import Literal

class AssessmentInput(BaseModel):
    organization_size: int = Field(ge=1, le=1000000)
    concurrent_users: int = Field(ge=1, le=100000)
    workload: Literal["Knowledge assistant", "Document summarization", "Code assistant", "Training content"]
    deployment: Literal["On-premises", "Sovereign cloud", "Public cloud", "Hybrid"]
    sensitivity: Literal["Public", "Internal", "Confidential", "Restricted"]
    availability: Literal["Development", "Business hours", "24x7"]
    model_size_b: int = Field(ge=1, le=400)
    avg_tokens_per_request: int = Field(ge=64, le=32768)

class AssessmentResult(BaseModel):
    readiness_score: int
    maturity: str
    estimated_vram_gb: float
    gpu_tier: str
    architecture: list[str]
    risks: list[str]
    next_steps: list[str]
    disclaimer: str
