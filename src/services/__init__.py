"""Public deterministic service interface for PARA-GIP."""

from .scoring import ScoringError, calculate_readiness_score


__all__ = [
    "ScoringError",
    "calculate_readiness_score",
]