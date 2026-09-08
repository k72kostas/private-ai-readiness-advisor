"""Public deterministic service interface for PARA-GIP."""

from .critical_stops import (
    CriticalStopEvaluationError,
    evaluate_critical_stops,
    has_blocking_findings,
)
from .scoring import (
    ScoringError,
    calculate_readiness_score,
)


__all__ = [
    "CriticalStopEvaluationError",
    "ScoringError",
    "calculate_readiness_score",
    "evaluate_critical_stops",
    "has_blocking_findings",
]