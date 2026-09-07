"""Validation tests for the PARA-GIP assessment question catalog."""

from pathlib import Path

import pytest
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPOSITORY_ROOT / "config" / "assessment_questions.yaml"

EXPECTED_DOMAIN_IDS = {
    "BV",
    "DR",
    "SP",
    "GV",
    "IP",
    "GP",
    "PO",
}

EXPECTED_DOMAIN_WEIGHTS = {
    "BV": 15,
    "DR": 15,
    "SP": 15,
    "GV": 15,
    "IP": 15,
    "GP": 15,
    "PO": 10,
}

EXPECTED_MATURITY_LEVELS = {
    0: 0,
    1: 25,
    2: 50,
    3: 75,
    4: 100,
}

EXPECTED_CRITICAL_STOP_RULES = {
    "CS-NO-DEFINED-USE-CASE",
    "CS-NO-ACCOUNTABLE-OWNER",
    "CS-DATA-BOUNDARY-NOT-APPROVED",
    "CS-NO-ACCESS-CONTROL-DESIGN",
    "CS-UNKNOWN-MODEL-OR-DATA-LICENSE",
    "CS-NO-HUMAN-OVERSIGHT",
    "CS-NO-PRODUCTION-BENCHMARK",
}

REQUIRED_QUESTION_FIELDS = {
    "id",
    "text",
    "max_points",
    "required",
    "critical_gate",
    "evidence_examples",
}


@pytest.fixture(scope="module")
def catalog() -> dict:
    """Load and return the assessment catalog."""

    assert CATALOG_PATH.exists(), (
        f"Assessment catalog was not found at {CATALOG_PATH}"
    )

    with CATALOG_PATH.open("r", encoding="utf-8") as yaml_file:
        loaded_catalog = yaml.safe_load(yaml_file)

    assert isinstance(loaded_catalog, dict), (
        "The YAML root must be a mapping."
    )

    return loaded_catalog


@pytest.fixture(scope="module")
def domains(catalog: dict) -> list"""Return the configured readiness domains."""

    configured_domains = catalog.get("domains")

    assert isinstance(configured_domains, list), (
        "The 'domains' property must be a list."
    )

    return configured_domains


@pytest.fixture(scope="module")
def questions(domains: list[dict]) -> list"""Return all questions across all domains."""

    return [
        question
        for domain in domains
        for question in domain.get("questions", [])
    ]


def test_catalog_metadata(catalog: dict) -> None:
    """Catalog metadata must identify the Version 1 assessment."""

    assert catalog["schema_version"] == "1.0"
    assert catalog["catalog_version"] == "1.0"
    assert catalog["catalog_name"] == (
        "PARA-GIP Private AI Readiness Assessment"
    )
    assert catalog["domain_count"] == 7
    assert catalog["question_count"] == 35
    assert catalog["total_points"] == 100


def test_catalog_contains_seven_domains(domains: list[dict]) -> None:
    """The catalog must contain exactly seven readiness domains."""

    assert len(domains) == 7


def test_domain_ids_are_unique_and_complete(
    domains: list[dict],
) -> None:
    """Domain identifiers must be unique and match the approved model."""

    domain_ids = [domain["id"] for domain in domains]

    assert len(domain_ids) == len(set(domain_ids))
    assert set(domain_ids) == EXPECTED_DOMAIN_IDS


def test_domain_display_order_is_complete(
    domains: list[dict],
) -> None:
    """Domain display order must contain every value from 1 through 7."""

    display_orders = [domain["display_order"] for domain in domains]

    assert sorted(display_orders) == list(range(1, 8))


def test_domain_weights_match_approved_model(
    domains: list[dict],
) -> None:
    """Each domain must use its approved readiness weight."""

    actual_weights = {
        domain["id"]: domain["weight"]
        for domain in domains
    }

    assert actual_weights == EXPECTED_DOMAIN_WEIGHTS


def test_domain_weights_total_one_hundred(
    domains: list[dict],
) -> None:
    """The seven domain weights must total 100 points."""

    assert sum(domain["weight"] for domain in domains) == 100


def test_each_domain_has_required_properties(
    domains: list[dict],
) -> None:
    """Every domain must define its identity and question collection."""

    required_fields = {
        "id",
        "name",
        "weight",
        "display_order",
        "primary_question",
        "questions",
    }

    for domain in domains:
        missing_fields = required_fields - set(domain)

        assert not missing_fields, (
            f"Domain {domain.get('id', '<unknown>')} is missing "
            f"fields: {sorted(missing_fields)}"
        )

        assert domain["name"].strip()
        assert domain["primary_question"].strip()
        assert isinstance(domain["questions"], list)


def test_each_domain_contains_five_questions(
    domains: list[dict],
) -> None:
    """Each approved readiness domain must contain five questions."""

    for domain in domains:
        assert len(domain["questions"]) == 5, (
            f"Domain {domain['id']} contains "
            f"{len(domain['questions'])} questions instead of 5."
        )


def test_catalog_contains_thirty_five_questions(
    catalog: dict,
    questions: list[dict],
) -> None:
    """The actual question count must match the catalog metadata."""

    assert len(questions) == 35
    assert len(questions) == catalog["question_count"]


def test_question_ids_are_unique(
    questions: list[dict],
) -> None:
    """Every assessment question must have a unique identifier."""

    question_ids = [question["id"] for question in questions]

    duplicates = {
        question_id
        for question_id in question_ids
        if question_ids.count(question_id) > 1
    }

    assert not duplicates, (
        f"Duplicate question identifiers found: {sorted(duplicates)}"
    )


def test_question_ids_match_domain_prefix(
    domains: list[dict],
) -> None:
    """Question identifiers must begin with their domain identifier."""

    for domain in domains:
        domain_id = domain["id"]

        for question in domain["questions"]:
            assert question["id"].startswith(domain_id), (
                f"Question {question['id']} does not match "
                f"domain {domain_id}."
            )


def test_question_ids_follow_expected_sequence(
    domains: list[dict],
) -> None:
    """Each domain must contain identifiers numbered 1 through 5."""

    for domain in domains:
        expected_ids = {
            f"{domain['id']}{number}"
            for number in range(1, 6)
        }
        actual_ids = {
            question["id"]
            for question in domain["questions"]
        }

        assert actual_ids == expected_ids, (
            f"Unexpected question IDs in domain {domain['id']}: "
            f"{sorted(actual_ids)}"
        )


def test_questions_have_required_fields(
    questions: list[dict],
) -> None:
    """Every question must contain the minimum configuration fields."""

    for question in questions:
        missing_fields = REQUIRED_QUESTION_FIELDS - set(question)

        assert not missing_fields, (
            f"Question {question.get('id', '<unknown>')} is missing "
            f"fields: {sorted(missing_fields)}"
        )


def test_question_content_is_valid(
    questions: list[dict],
) -> None:
    """Question text, flags, points, and evidence examples must be valid."""

    for question in questions:
        assert isinstance(question["text"], str)
        assert question["text"].strip()

        assert isinstance(question["max_points"], int)
        assert question["max_points"] > 0

        assert isinstance(question["required"], bool)
        assert isinstance(question["critical_gate"], bool)

        assert isinstance(question["evidence_examples"], list)
        assert question["evidence_examples"], (
            f"Question {question['id']} has no evidence examples."
        )

        assert all(
            isinstance(example, str) and example.strip()
            for example in question["evidence_examples"]
        )


def test_question_points_match_domain_weights(
    domains: list[dict],
) -> None:
    """Question maximum points must equal the corresponding domain weight."""

    for domain in domains:
        question_points = sum(
            question["max_points"]
            for question in domain["questions"]
        )

        assert question_points == domain["weight"], (
            f"Domain {domain['id']} has question points totaling "
            f"{question_points}, but its configured weight is "
            f"{domain['weight']}."
        )


def test_question_points_total_one_hundred(
    catalog: dict,
    questions: list[dict],
) -> None:
    """All question maximum points must total 100."""

    actual_total = sum(
        question["max_points"]
        for question in questions
    )

    assert actual_total == 100
    assert actual_total == catalog["total_points"]


def test_maturity_levels_are_complete(
    catalog: dict,
) -> None:
    """The maturity scale must contain levels 0 through 4."""

    maturity_levels = catalog["scoring"]["maturity_levels"]

    actual_levels = {
        item["level"]: item["credit_percentage"]
        for item in maturity_levels
    }

    assert actual_levels == EXPECTED_MATURITY_LEVELS


def test_maturity_level_labels_are_present(
    catalog: dict,
) -> None:
    """Each maturity level must contain a readable label."""

    maturity_levels = catalog["scoring"]["maturity_levels"]

    for maturity_level in maturity_levels:
        assert isinstance(maturity_level["label"], str)
        assert maturity_level["label"].strip()


def test_evidence_statuses_are_unique(
    catalog: dict,
) -> None:
    """Supported evidence statuses must be non-empty and unique."""

    statuses = catalog["evidence"]["supported_statuses"]

    assert statuses
    assert len(statuses) == len(set(statuses))

    assert all(
        isinstance(status, str) and status.strip()
        for status in statuses
    )


def test_evidence_notes_required_for_high_scores(
    catalog: dict,
) -> None:
    """Maturity levels 3 and 4 must require an evidence note."""

    assert catalog["evidence"]["note_required_for_levels"] == [3, 4]


def test_confidential_upload_is_not_required(
    catalog: dict,
) -> None:
    """Version 1 must not require confidential-document uploads."""

    assert (
        catalog["evidence"][
            "confidential_document_upload_required"
        ]
        is False
    )


def test_critical_gates_have_gate_metadata(
    questions: list[dict],
) -> None:
    """Every critical gate must specify a rule or a scoped condition."""

    for question in questions:
        if not question["critical_gate"]:
            continue

        has_stop_rule = bool(question.get("critical_stop_rule"))
        has_gate_scope = bool(question.get("gate_scope"))
        has_gate_condition = bool(question.get("gate_condition"))

        assert (
            has_stop_rule
            or has_gate_scope
            or has_gate_condition
        ), (
            f"Critical gate {question['id']} does not define a "
            "critical-stop rule, gate scope, or gate condition."
        )


def test_critical_stop_rule_names_are_valid(
    questions: list[dict],
) -> None:
    """Question-level critical-stop references must use approved IDs."""

    referenced_rules = {
        question["critical_stop_rule"]
        for question in questions
        if "critical_stop_rule" in question
    }

    unknown_rules = referenced_rules - EXPECTED_CRITICAL_STOP_RULES

    assert not unknown_rules, (
        f"Unknown critical-stop rule references: "
        f"{sorted(unknown_rules)}"
    )


def test_critical_stop_rule_format(
    questions: list[dict],
) -> None:
    """Critical-stop identifiers must follow the CS-* convention."""

    for question in questions:
        rule_id = question.get("critical_stop_rule")

        if rule_id is not None:
            assert rule_id.startswith("CS-"), (
                f"Question {question['id']} references invalid "
                f"rule identifier {rule_id}."
            )


def test_gate_conditions_are_well_formed(
    questions: list[dict],
) -> None:
    """Conditional gates must provide a field, operator, and values."""

    for question in questions:
        condition = question.get("gate_condition")

        if condition is None:
            continue

        assert condition.get("field")
        assert condition.get("operator") == "in"

        values = condition.get("values")
        assert isinstance(values, list)
        assert values


def test_production_scoped_gates_are_expected(
    questions: list[dict],
) -> None:
    """Only approved questions may act as production-assessment gates."""

    production_gate_ids = {
        question["id"]
        for question in questions
        if question.get("gate_scope") == "production_assessment"
    }

    assert production_gate_ids == {"IP4", "GP5"}