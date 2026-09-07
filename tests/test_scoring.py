"""Validation tests for the PARA-GIP readiness scoring rules."""

from decimal import Decimal
from pathlib import Path

import pytest
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCORING_RULES_PATH = REPOSITORY_ROOT / "config" / "scoring_rules.yaml"

EXPECTED_CLASSIFICATION_IDS = {
    "CLASS-DISCOVERY",
    "CLASS-FOUNDATION",
    "CLASS-CONTROLLED-PROTOTYPE",
    "CLASS-BENCHMARKED-PILOT",
    "CLASS-PRODUCTION-ASSESSMENT",
}

EXPECTED_CLASSIFICATION_NAMES = [
    "Discovery Required",
    "Foundation Required",
    "Ready for Controlled Prototype",
    "Ready for Benchmarked Pilot",
    "Candidate for Production Assessment",
]

EXPECTED_MATURITY_FACTORS = {
    0: Decimal("0.00"),
    1: Decimal("0.25"),
    2: Decimal("0.50"),
    3: Decimal("0.75"),
    4: Decimal("1.00"),
}

EXPECTED_MINIMUM_DOMAIN_RULES = {
    "CLASS-CONTROLLED-PROTOTYPE": (40, "CLASS-FOUNDATION"),
    "CLASS-BENCHMARKED-PILOT": (60, "CLASS-CONTROLLED-PROTOTYPE"),
    "CLASS-PRODUCTION-ASSESSMENT": (75, "CLASS-BENCHMARKED-PILOT"),
}

REQUIRED_TOP_LEVEL_SECTIONS = {
    "schema_version",
    "rule_set_version",
    "rule_set_name",
    "dependencies",
    "score_range",
    "maturity_credit_factors",
    "calculation",
    "precision",
    "classifications",
    "minimum_domain_rules",
    "classification_processing",
    "output",
    "validation",
}

REQUIRED_CALCULATION_RULES = {
    "question_score",
    "domain_score",
    "domain_percentage",
    "overall_score",
}

REQUIRED_OUTPUT_FIELDS = {
    "question_scores",
    "domain_scores",
    "domain_percentages",
    "overall_score",
    "score_band_classification",
    "final_classification",
    "applied_caps",
    "calculation_explanation",
    "applied_rule_ids",
    "rule_set_version",
}


def as_decimal(value: object) -> Decimal:
    """Convert a YAML numeric value to Decimal without binary-float noise."""

    return Decimal(str(value))


@pytest.fixture(scope="module")
def rules() -> dict:
    """Load and return the readiness scoring rules."""

    assert SCORING_RULES_PATH.exists(), (
        f"Scoring rules were not found at {SCORING_RULES_PATH}"
    )

    with SCORING_RULES_PATH.open("r", encoding="utf-8") as yaml_file:
        loaded_rules = yaml.safe_load(yaml_file)

    assert isinstance(loaded_rules, dict), "The YAML root must be a mapping."

    return loaded_rules


@pytest.fixture(scope="module")
def classifications(rules: dict) -> list[dict]:
    """Return the configured readiness classifications."""

    configured_classifications = rules.get("classifications")

    assert isinstance(configured_classifications, list), (
        "The 'classifications' property must be a list."
    )

    return configured_classifications


def test_required_top_level_sections_exist(rules: dict) -> None:
    """The rule file must include every required configuration section."""

    missing_sections = REQUIRED_TOP_LEVEL_SECTIONS - set(rules)

    assert not missing_sections, (
        f"Missing top-level sections: {sorted(missing_sections)}"
    )


def test_rule_set_metadata(rules: dict) -> None:
    """The file must identify the Version 1 PARA-GIP scoring rule set."""

    assert rules["schema_version"] == "1.0"
    assert rules["rule_set_version"] == "1.0"
    assert rules["rule_set_name"] == (
        "PARA-GIP Readiness Scoring and Classification Rules"
    )
    assert rules["dependencies"]["assessment_catalog"] == (
        "assessment_questions.yaml"
    )


def test_score_range_is_zero_to_one_hundred(rules: dict) -> None:
    """The configured readiness-score range must be 0 through 100."""

    assert rules["score_range"] == {"minimum": 0, "maximum": 100}


def test_maturity_credit_factors_are_complete(rules: dict) -> None:
    """Maturity levels 0 through 4 must map to the approved credit factors."""

    actual_factors = {
        int(level): as_decimal(value)
        for level, value in rules["maturity_credit_factors"].items()
    }

    assert actual_factors == EXPECTED_MATURITY_FACTORS


def test_maturity_credit_factors_are_monotonic(rules: dict) -> None:
    """Higher maturity levels must never earn less credit."""

    factors = [
        as_decimal(rules["maturity_credit_factors"][level])
        for level in range(5)
    ]

    assert factors == sorted(factors)
    assert len(factors) == len(set(factors))


def test_calculation_rules_are_complete(rules: dict) -> None:
    """All four deterministic score calculations must be configured."""

    calculation = rules["calculation"]

    assert set(calculation) == REQUIRED_CALCULATION_RULES

    for calculation_name, calculation_rule in calculation.items():
        assert calculation_rule.get("rule_id"), calculation_name
        assert calculation_rule.get("formula"), calculation_name
        assert calculation_rule.get("description"), calculation_name


def test_calculation_rule_ids_are_unique(rules: dict) -> None:
    """Calculation rule identifiers must be unique."""

    rule_ids = [
        calculation_rule["rule_id"]
        for calculation_rule in rules["calculation"].values()
    ]

    assert len(rule_ids) == len(set(rule_ids))


def test_precision_configuration(rules: dict) -> None:
    """Internal precision must exceed display precision."""

    precision = rules["precision"]

    assert precision["internal_decimal_places"] > (
        precision["display_decimal_places"]
    )
    assert precision["rounding_method"] == "half_up"
    assert precision["apply_classification_before_display_rounding"] is True


def test_exactly_five_classifications(
    classifications: list[dict],
) -> None:
    """The rule set must contain exactly five readiness classifications."""

    assert len(classifications) == 5


def test_classification_ids_are_unique_and_complete(
    classifications: list[dict],
) -> None:
    """Classification identifiers must be unique and approved."""

    classification_ids = [item["id"] for item in classifications]

    assert len(classification_ids) == len(set(classification_ids))
    assert set(classification_ids) == EXPECTED_CLASSIFICATION_IDS


def test_classification_names_and_order(
    classifications: list[dict],
) -> None:
    """Classification names must follow the approved maturity order."""

    actual_names = [item["name"] for item in classifications]

    assert actual_names == EXPECTED_CLASSIFICATION_NAMES


def test_classification_ranges_are_ordered(
    classifications: list[dict],
) -> None:
    """Each classification minimum must be below its maximum."""

    previous_minimum = None

    for item in classifications:
        minimum = as_decimal(item["minimum_score"])
        maximum = as_decimal(item["maximum_score"])

        assert minimum <= maximum, item["id"]

        if previous_minimum is not None:
            assert minimum > previous_minimum, item["id"]

        previous_minimum = minimum


def test_classification_ranges_cover_score_range(
    rules: dict,
    classifications: list[dict],
) -> None:
    """Classification thresholds must cover the configured score range."""

    assert as_decimal(classifications[0]["minimum_score"]) == as_decimal(
        rules["score_range"]["minimum"]
    )
    assert as_decimal(classifications[-1]["maximum_score"]) == as_decimal(
        rules["score_range"]["maximum"]
    )

    expected_minimums = [
        Decimal("0"),
        Decimal("40"),
        Decimal("60"),
        Decimal("75"),
        Decimal("90"),
    ]
    expected_maximums = [
        Decimal("39.9999"),
        Decimal("59.9999"),
        Decimal("74.9999"),
        Decimal("89.9999"),
        Decimal("100"),
    ]

    assert [
        as_decimal(item["minimum_score"])
        for item in classifications
    ] == expected_minimums
    assert [
        as_decimal(item["maximum_score"])
        for item in classifications
    ] == expected_maximums


def test_display_ranges_match_approved_integer_bands(
    classifications: list[dict],
) -> None:
    """Displayed score ranges must match the approved integer bands."""

    actual_ranges = [
        (item["display_minimum"], item["display_maximum"])
        for item in classifications
    ]

    assert actual_ranges == [
        (0, 39),
        (40, 59),
        (60, 74),
        (75, 89),
        (90, 100),
    ]


def test_classification_routes_are_present(
    classifications: list[dict],
) -> None:
    """Every classification must include a non-empty recommended route."""

    for item in classifications:
        assert isinstance(item["route"], str)
        assert item["route"].strip(), item["id"]


def test_minimum_domain_rules_are_complete(rules: dict) -> None:
    """The three approved minimum-domain safeguards must be configured."""

    configured_rules = rules["minimum_domain_rules"]

    assert len(configured_rules) == 3

    actual_rules = {
        item["target_classification"]: (
            item["required_domain_percentage"],
            item["failure_cap"],
        )
        for item in configured_rules
    }

    assert actual_rules == EXPECTED_MINIMUM_DOMAIN_RULES


def test_minimum_domain_rule_ids_are_unique(rules: dict) -> None:
    """Minimum-domain safeguard identifiers must be unique."""

    rule_ids = [
        item["rule_id"]
        for item in rules["minimum_domain_rules"]
    ]

    assert len(rule_ids) == len(set(rule_ids))


def test_minimum_domain_rules_reference_valid_classifications(
    rules: dict,
    classifications: list[dict],
) -> None:
    """Safeguard targets and caps must reference defined classifications."""

    classification_ids = {item["id"] for item in classifications}

    for item in rules["minimum_domain_rules"]:
        assert item["target_classification"] in classification_ids
        assert item["failure_cap"] in classification_ids
        assert isinstance(item["explanation"], str)
        assert item["explanation"].strip()


def test_classification_processing_sequence(rules: dict) -> None:
    """Classification must use internal values before display rounding."""

    expected_sequence = [
        "calculate_question_scores",
        "calculate_domain_scores",
        "calculate_domain_percentages",
        "calculate_overall_score",
        "assign_score_band_classification",
        "apply_minimum_domain_rules",
        "retain_internal_precision",
        "round_values_for_display",
    ]

    processing = rules["classification_processing"]

    assert processing["sequence"] == expected_sequence
    assert processing["preserve_uncapped_classification"] is True
    assert processing["preserve_applied_caps"] is True
    assert processing["preserve_rule_ids"] is True


def test_output_fields_are_complete(rules: dict) -> None:
    """Scoring output must expose values needed for explainability."""

    configured_output_fields = set(rules["output"]["include"])

    assert configured_output_fields == REQUIRED_OUTPUT_FIELDS


def test_validation_controls(rules: dict) -> None:
    """Input and score-integrity validation controls must be enabled."""

    validation = rules["validation"]

    assert validation["require_all_questions_answered"] is True
    assert validation["reject_unknown_question_ids"] is True
    assert validation["reject_duplicate_question_ids"] is True
    assert validation["reject_maturity_levels_outside_range"] is True
    assert validation["verify_domain_weights_total"] == 100
    assert validation["verify_score_range"] is True


def test_all_rule_ids_are_unique(rules: dict) -> None:
    """All scoring-related rule identifiers must be globally unique."""

    rule_ids = [
        item["rule_id"]
        for item in rules["calculation"].values()
    ]
    rule_ids.extend(
        item["rule_id"]
        for item in rules["minimum_domain_rules"]
    )
    rule_ids.append(rules["classification_processing"]["rule_id"])

    assert len(rule_ids) == len(set(rule_ids))


def test_all_rule_ids_use_sc_prefix(rules: dict) -> None:
    """Scoring rule identifiers must follow the SC-* convention."""

    rule_ids = [
        item["rule_id"]
        for item in rules["calculation"].values()
    ]
    rule_ids.extend(
        item["rule_id"]
        for item in rules["minimum_domain_rules"]
    )
    rule_ids.append(rules["classification_processing"]["rule_id"])

    assert all(rule_id.startswith("SC-") for rule_id in rule_ids)
