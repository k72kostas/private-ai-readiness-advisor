from src.models import AssessmentInput
from src.assessment import assess

def test_assessment_bounds():
    x=AssessmentInput(organization_size=2000,concurrent_users=50,workload="Knowledge assistant",deployment="On-premises",sensitivity="Internal",availability="Development",model_size_b=8,avg_tokens_per_request=1024)
    r=assess(x)
    assert 0 <= r.readiness_score <= 100
    assert r.estimated_vram_gb > 0
    assert "Planning estimate" in r.disclaimer
