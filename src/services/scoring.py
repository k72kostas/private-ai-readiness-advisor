"""Deterministic readiness scoring and classification service for PARA-GIP."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.assessment import Assessment
from src.models.results import (
    ClassificationCap,
    DomainScore,
    QuestionScore,
    ReadinessClassification,
    ScoreResult,
)


class ScoringError(ValueError):
    """Raised when assessment responses cannot be scored safely."""


_CLASSIFICATION_BY_ID = {
    "CLASS-DISCOVERY": ReadinessClassification.DISCOVERY_REQUIRED,
    "CLASS-FOUNDATION": ReadinessClassification.FOUNDATION_REQUIRED,
    "CLASS-CONTROLLED-PROTOTYPE": ReadinessClassification.CONTROLLED_PROTOTYPE,
    "CLASS-BENCHMARKED-PILOT": ReadinessClassification.BENCHMARKED_PILOT,
    "CLASS-PRODUCTION-ASSESSMENT": ReadinessClassification.PRODUCTION_ASSESSMENT,
}

_CLASSIFICATION_RANK = {
    ReadinessClassification.DISCOVERY_REQUIRED: 0,
    ReadinessClassification.FOUNDATION_REQUIRED: 1,
    ReadinessClassification.CONTROLLED_PROTOTYPE: 2,
    ReadinessClassification.BENCHMARKED_PILOT: 3,
    ReadinessClassification.PRODUCTION_ASSESSMENT: 4,
}


def _decimal(value: Any) -> Decimal:
    """Convert configuration and input numbers without float artifacts."""

    return Decimal(str(value))


def _round_for_display(value: Decimal, decimal_places: int) -> float:
    """Round a value using the configured half-up presentation rule."""

    quantum = Decimal("1").scaleb(-decimal_places)
    return float(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _catalog_index(catalog: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    """Return question and domain indexes from the configured catalog."""

    questions: dict[str, Mapping[str, Any]] = {}
    domains: dict[str, Mapping[str, Any]] = {}

    for domain in catalog["domains"]:
        domain_id = domain["id"]
        domains[domain_id] = domain
        for question in domain["questions"]:
            questions[question["id"]] = question

    return questions, domains


def _validate_responses(
    assessment: Assessment,
    question_index: Mapping[str, Mapping[str, Any]],
    *,
    require_all: bool,
) -> dict[str, Any]:
    """Validate response IDs and assessment completeness."""

    response_index = assessment.response_by_question_id()
    unknown = sorted(set(response_index) - set(question_index))
    if unknown:
        raise ScoringError(f"unknown assessment question IDs: {', '.join(unknown)}")

    if require_all:
        missing = sorted(set(question_index) - set(response_index))
        if missing:
            raise ScoringError(
                "assessment is incomplete; missing responses: " + ", ".join(missing)
            )

    return response_index


def _classification_for_score(
    score: Decimal,
    classifications: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> tuple[str, ReadinessClassification]:
    """Return configured classification ID and enum for an internal score."""

    for item in classifications:
        minimum = _decimal(item["minimum_score"])
        maximum = _decimal(item["maximum_score"])
        if minimum <= score <= maximum:
            classification_id = item["id"]
            try:
                return classification_id, _CLASSIFICATION_BY_ID[classification_id]
            except KeyError as exc:
                raise ScoringError(
                    f"unsupported classification ID: {classification_id}"
                ) from exc

    raise ScoringError(f"score {score} is outside configured classification bands")


def calculate_readiness_score(
    assessment: Assessment,
    configuration: ConfigurationBundle | None = None,
) -> ScoreResult:
    """Calculate deterministic question, domain, overall, and capped results."""

    bundle = configuration or load_configuration_bundle()
    catalog = bundle.assessment_catalog
    rules = bundle.scoring_rules
    question_index, domain_index = _catalog_index(catalog)

    validation = rules["validation"]
    response_index = _validate_responses(
        assessment,
        question_index,
        require_all=bool(validation["require_all_questions_answered"]),
    )

    maturity_factors = {
        int(level): _decimal(factor)
        for level, factor in rules["maturity_credit_factors"].items()
    }
    internal_places = int(rules["precision"]["internal_decimal_places"])
    display_places = int(rules["precision"]["display_decimal_places"])
    internal_quantum = Decimal("1").scaleb(-internal_places)

    question_results: list[QuestionScore] = []
    domain_results: list[DomainScore] = []
    internal_domain_percentages: dict[str, Decimal] = {}
    overall = Decimal("0")

    for domain in catalog["domains"]:
        domain_id = domain["id"]
        domain_score = Decimal("0")

        for question in domain["questions"]:
            question_id = question["id"]
            response = response_index.get(question_id)
            if response is None:
                continue

            try:
                factor = maturity_factors[response.maturity_level]
            except KeyError as exc:
                raise ScoringError(
                    f"unsupported maturity level for {question_id}: "
                    f"{response.maturity_level}"
                ) from exc

            maximum = _decimal(question["max_points"])
            earned = (maximum * factor).quantize(
                internal_quantum,
                rounding=ROUND_HALF_UP,
            )
            domain_score += earned
            question_results.append(
                QuestionScore(
                    question_id=question_id,
                    maturity_level=response.maturity_level,
                    maximum_points=float(maximum),
                    earned_points=float(earned),
                    applied_rule_ids=["SC-QUESTION-001"],
                )
            )

        domain_maximum = _decimal(domain["weight"])
        domain_score = domain_score.quantize(
            internal_quantum,
            rounding=ROUND_HALF_UP,
        )
        domain_percentage = (
            domain_score / domain_maximum * Decimal("100")
        ).quantize(internal_quantum, rounding=ROUND_HALF_UP)
        internal_domain_percentages[domain_id] = domain_percentage
        overall += domain_score

        domain_results.append(
            DomainScore(
                domain_id=domain_id,
                domain_name=domain["name"],
                maximum_points=float(domain_maximum),
                earned_points=_round_for_display(domain_score, display_places),
                percentage=_round_for_display(domain_percentage, display_places),
                applied_rule_ids=["SC-DOMAIN-001", "SC-DOMAIN-002"],
            )
        )

    overall = overall.quantize(internal_quantum, rounding=ROUND_HALF_UP)
    band_id, band_classification = _classification_for_score(
        overall,
        rules["classifications"],
    )
    final_classification = band_classification
    applied_caps: list[ClassificationCap] = []
    applied_rule_ids = [
        "SC-QUESTION-001",
        "SC-DOMAIN-001",
        "SC-DOMAIN-002",
        "SC-OVERALL-001",
        "SC-CLASSIFICATION-001",
    ]

    for cap_rule in rules["minimum_domain_rules"]:
        target = _CLASSIFICATION_BY_ID[cap_rule["target_classification"]]
        if _CLASSIFICATION_RANK[final_classification] < _CLASSIFICATION_RANK[target]:
            continue

        threshold = _decimal(cap_rule["required_domain_percentage"])
        affected = sorted(
            domain_id
            for domain_id, percentage in internal_domain_percentages.items()
            if percentage < threshold
        )
        if not affected:
            continue

        capped_to = _CLASSIFICATION_BY_ID[cap_rule["failure_cap"]]
        if _CLASSIFICATION_RANK[capped_to] < _CLASSIFICATION_RANK[final_classification]:
            final_classification = capped_to
            applied_caps.append(
                ClassificationCap(
                    rule_id=cap_rule["rule_id"],
                    target_classification=target,
                    capped_to=capped_to,
                    affected_domains=affected,
                    rationale=cap_rule["explanation"],
                )
            )
            applied_rule_ids.append(cap_rule["rule_id"])

    explanation = (
        f"Calculated {len(question_results)} question scores across "
        f"{len(domain_results)} domains. Internal overall score: {overall}. "
        f"Score-band classification: {band_classification.value}. "
        f"Final classification after minimum-domain safeguards: "
        f"{final_classification.value}."
    )

    return ScoreResult(
        assessment_id=assessment.assessment_id,
        assessment_version=assessment.assessment_version,
        rule_set_version=str(rules["rule_set_version"]),
        question_scores=question_results,
        domain_scores=domain_results,
        overall_score=_round_for_display(overall, display_places),
        score_band_classification=band_classification,
        final_classification=final_classification,
        applied_caps=applied_caps,
        calculation_explanation=explanation,
        applied_rule_ids=list(dict.fromkeys(applied_rule_ids)),
    )


__all__ = ["ScoringError", "calculate_readiness_score"]
