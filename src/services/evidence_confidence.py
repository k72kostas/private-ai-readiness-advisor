"""Deterministic Evidence Confidence service for PARA-GIP.

The service evaluates evidence metadata independently from readiness scoring.
It uses the configured evidence-status credits, confidence bands, and
high-maturity warning rule. It never modifies readiness scores,
classifications, or critical-stop findings.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Mapping

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.assessment import Assessment, EvidenceStatus
from src.models.results import ConfidenceLevel, ConfidenceResult


class EvidenceConfidenceError(ValueError):
    """Raised when Evidence Confidence cannot be evaluated safely."""


_CONFIDENCE_BY_NAME = {
    "Low": ConfidenceLevel.LOW,
    "Medium": ConfidenceLevel.MEDIUM,
    "High": ConfidenceLevel.HIGH,
}


def _plain_value(value: Any) -> Any:
    """Return an enum value or the original ordinary value."""

    return value.value if isinstance(value, Enum) else value


def _decimal(value: Any) -> Decimal:
    """Convert configured numbers without binary floating-point noise."""

    return Decimal(str(value))


def _classify_score(
    score: Decimal,
    confidence_levels: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> ConfidenceLevel:
    """Map an internal score to one configured confidence level."""

    for item in confidence_levels:
        minimum = _decimal(item["minimum_score"])
        maximum = _decimal(item["maximum_score"])
        if minimum <= score <= maximum:
            name = item["name"]
            try:
                return _CONFIDENCE_BY_NAME[name]
            except KeyError as exc:
                raise EvidenceConfidenceError(
                    f"unsupported Evidence Confidence level: {name}"
                ) from exc

    raise EvidenceConfidenceError(
        f"evidence score {score} is outside configured confidence bands"
    )


def _evidence_status_credit(
    status: EvidenceStatus,
    configured_credits: Mapping[str, Any],
) -> Decimal:
    """Return the configured credit for one evidence status."""

    status_value = str(_plain_value(status))
    if status_value not in configured_credits:
        raise EvidenceConfidenceError(
            f"unsupported evidence status: {status_value}"
        )
    return _decimal(configured_credits[status_value])


def calculate_evidence_confidence(
    assessment: Assessment,
    configuration: ConfigurationBundle | None = None,
) -> ConfidenceResult:
    """Calculate Evidence Confidence from assessment evidence metadata.

    Version 1 uses the configured evidence-status credit for each answered
    question and averages those credits. High-maturity responses with absent
    or self-declared evidence are highlighted separately. This result is
    independent from readiness scoring.
    """

    bundle = configuration or load_configuration_bundle()
    rules = bundle.evidence_confidence_rules

    credits = rules.get("evidence_status_credits")
    levels = rules.get("confidence_levels")
    warning_rule = rules.get("high_maturity_without_evidence")

    if not isinstance(credits, Mapping):
        raise EvidenceConfidenceError(
            "evidence_status_credits must be a mapping"
        )
    if not isinstance(levels, (list, tuple)) or not levels:
        raise EvidenceConfidenceError(
            "confidence_levels must be a non-empty list"
        )
    if not isinstance(warning_rule, Mapping):
        raise EvidenceConfidenceError(
            "high_maturity_without_evidence must be a mapping"
        )

    responses = assessment.responses
    applied_rule_ids: list[str] = [rules["calculation"]["rule_id"]]
    highlighted_question_ids: list[str] = []
    missing_evidence: list[str] = []

    if responses:
        status_scores = [
            _evidence_status_credit(response.evidence_status, credits)
            for response in responses
        ]
        score = sum(status_scores, Decimal("0")) / Decimal(len(status_scores))
    else:
        score = Decimal("0")
        missing_evidence.append("No assessment responses are available.")

    score = score.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    level = _classify_score(score, levels)

    warning_maturity_levels = {
        int(value) for value in warning_rule["maturity_levels"]
    }
    warning_statuses = {
        str(value) for value in warning_rule["evidence_statuses"]
    }

    for response in responses:
        status_value = str(_plain_value(response.evidence_status))

        if status_value == EvidenceStatus.NONE.value:
            missing_evidence.append(
                f"{response.question_id}: supporting evidence is missing."
            )

        if (
            response.maturity_level in warning_maturity_levels
            and status_value in warning_statuses
        ):
            highlighted_question_ids.append(response.question_id)

    if highlighted_question_ids:
        applied_rule_ids.append(warning_rule["rule_id"])

    status_counts: dict[str, int] = {}
    for response in responses:
        status_value = str(_plain_value(response.evidence_status))
        status_counts[status_value] = status_counts.get(status_value, 0) + 1

    reasons = [
        f"Evidence Confidence is {level.value} with a score of {score}.",
        (
            f"The score averages configured evidence-status credits across "
            f"{len(responses)} answered questions."
        ),
    ]

    if status_counts:
        distribution = ", ".join(
            f"{status}={count}"
            for status, count in sorted(status_counts.items())
        )
        reasons.append(f"Evidence status distribution: {distribution}.")

    if highlighted_question_ids:
        reasons.append(
            "High-maturity responses with insufficient evidence were highlighted."
        )

    separation = rules.get("separation_rules", {})
    if any(
        bool(separation.get(field, True))
        for field in (
            "modify_readiness_score",
            "modify_readiness_classification",
            "modify_critical_stops",
        )
    ):
        raise EvidenceConfidenceError(
            "Evidence Confidence separation rules must prohibit modifying "
            "readiness and critical-stop results"
        )

    return ConfidenceResult(
        confidence_type="evidence",
        level=level,
        score=float(score),
        reasons=reasons,
        missing_inputs_or_evidence=list(dict.fromkeys(missing_evidence)),
        highlighted_question_ids=sorted(set(highlighted_question_ids)),
        applied_rule_ids=list(dict.fromkeys(applied_rule_ids)),
        rule_set_version=str(rules["rule_set_version"]),
    )


__all__ = [
    "EvidenceConfidenceError",
    "calculate_evidence_confidence",
]
