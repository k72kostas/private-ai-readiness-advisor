"""Validation tests for the PARA-GIP critical-stop rule configuration."""

from pathlib import Path

import pytest
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPOSITORY_ROOT / "config" / "assessment_questions.yaml"
CRITICAL_STOPS_PATH = REPOSITORY_ROOT / "config" / "critical_stops.yaml"

EXPECTED_RULE_IDS = {
    "CS-NO-DEFINED-USE-CASE",
    "CS-NO-ACCOUNTABLE-OWNER",
    "CS-DATA-BOUNDARY-NOT-APPROVED",
    "CS-NO-ACCESS-CONTROL-DESIGN",
    "CS-UNKNOWN-MODEL-OR-DATA-LICENSE",
    "CS-NO-HUMAN-OVERSIGHT",
    "CS-NO-PRODUCTION-BENCHMARK",
    "CS-PROHIBITED-OR-UNACCEPTABLE-USE",
}

EXPECTED_SOURCE_QUESTIONS = {
    "CS-NO-DEFINED-USE-CASE": {"BV2"},
    "CS-NO-ACCOUNTABLE-OWNER": {"BV5", "GV1"},
    "CS-DATA-BOUNDARY-NOT-APPROVED": {"DR3"},
    "CS-NO-ACCESS-CONTROL-DESIGN": {"SP1"},
    "CS-UNKNOWN-MODEL-OR-DATA-LICENSE": {"GV3", "GP1"},
    "CS-NO-HUMAN-OVERSIGHT": {"GV4"},
    "CS-NO-PRODUCTION-BENCHMARK": {"GP5"},
    "CS-PROHIBITED-OR-UNACCEPTABLE-USE": set(),
}

REQUIRED_TOP_LEVEL_SECTIONS = {
    "schema_version",
    "rule_set_version",
    "rule_set_name",
    "description",
    "dependencies",
    "evaluation",
    "severity_levels",
    "rules",
    "output",
    "validation",
}

REQUIRED_RULE_FIELDS = {
    "rule_id",
    "name",
    "severity",
    "source_questions",
    "trigger",
    "rationale",
    "corrective_action",
}

ALLOWED_TRIGGER_OPERATORS = {
    "maturity_level_equals",
    "any_maturity_level_equals",
    "maturity_level_below",
    "condition_match",
}

ALLOWED_CONDITION_OPERATORS = {
    "equals",
    "in",
}

REQUIRED_OUTPUT_FIELDS = {
    "triggered",
    "rule_id",
    "name",
    "severity",
    "source_questions",
    "rationale",
    "corrective_action",
    "blocking_decision_status",
    "rule_set_version",
}


@pytest.fixture(scope="module")
def critical_stops() -> dict:
    """Load and return the critical-stop configuration."""

    assert CRITICAL_STOPS_PATH.exists(), (
        f"Critical-stop configuration not found at {CRITICAL_STOPS_PATH}"
    )

    with CRITICAL_STOPS_PATH.open("r", encoding="utf-8") as yaml_file:
        loaded = yaml.safe_load(yaml_file)

    assert isinstance(loaded, dict), "The YAML root must be a mapping."
    return loaded


@pytest.fixture(scope="module")
def assessment_catalog() -> dict:
    """Load the assessment catalog for cross-reference validation."""

    assert CATALOG_PATH.exists(), (
        f"Assessment catalog not found at {CATALOG_PATH}"
    )

    with CATALOG_PATH.open("r", encoding="utf-8") as yaml_file:
        loaded = yaml.safe_load(yaml_file)

    assert isinstance(loaded, dict), "The assessment YAML root must be a mapping."
    return loaded


@pytest.fixture(scope="module")
def rules(critical_stops: dict) -> list[dict]:
    """Return the configured critical-stop rules."""

    configured_rules = critical_stops.get("rules")
    assert isinstance(configured_rules, list), "The 'rules' property must be a list."
    return configured_rules


@pytest.fixture(scope="module")
def question_ids(assessment_catalog: dict) -> set[str]:
    """Return all assessment question identifiers."""

    return {
        question["id"]
        for domain in assessment_catalog["domains"]
        for question in domain["questions"]
    }


def test_required_top_level_sections_exist(critical_stops: dict) -> None:
    """Every required critical-stop configuration section must exist."""

    missing = REQUIRED_TOP_LEVEL_SECTIONS - set(critical_stops)
    assert not missing, f"Missing top-level sections: {sorted(missing)}"


def test_rule_set_metadata(critical_stops: dict) -> None:
    """The file must identify the Version 1 critical-stop rule set."""

    assert critical_stops["schema_version"] == "1.0"
    assert critical_stops["rule_set_version"] == "1.0"
    assert critical_stops["rule_set_name"] == (
        "PARA-GIP Critical Stop and Governance Rules"
    )
    assert critical_stops["dependencies"]["assessment_catalog"] == (
        "assessment_questions.yaml"
    )
    assert critical_stops["dependencies"]["scoring_rules"] == (
        "scoring_rules.yaml"
    )


def test_exactly_eight_rules(rules: list[dict]) -> None:
    """The rule set must contain the eight approved stop categories."""

    assert len(rules) == 8


def test_rule_ids_are_unique_and_complete(rules: list[dict]) -> None:
    """Critical-stop identifiers must be unique and approved."""

    rule_ids = [rule["rule_id"] for rule in rules]
    assert len(rule_ids) == len(set(rule_ids))
    assert set(rule_ids) == EXPECTED_RULE_IDS


def test_rule_ids_use_cs_prefix(rules: list[dict]) -> None:
    """Every critical-stop identifier must use the CS- prefix."""

    assert all(rule["rule_id"].startswith("CS-") for rule in rules)


def test_rules_have_required_fields(rules: list[dict]) -> None:
    """Every rule must include its minimum explainable configuration."""

    for rule in rules:
        missing = REQUIRED_RULE_FIELDS - set(rule)
        assert not missing, (
            f"Rule {rule.get('rule_id', '<unknown>')} is missing: "
            f"{sorted(missing)}"
        )


def test_rule_text_is_present(rules: list[dict]) -> None:
    """Names, rationales, and corrective actions must be readable."""

    for rule in rules:
        for field in ("name", "rationale", "corrective_action"):
            value = rule[field]
            assert isinstance(value, str) and value.strip(), (
                f"Rule {rule['rule_id']} has an empty {field}."
            )


def test_all_rules_are_blocking(rules: list[dict]) -> None:
    """Every Version 1 critical stop must use blocking severity."""

    assert all(rule["severity"] == "blocking" for rule in rules)


def test_severity_levels_are_consistent(critical_stops: dict) -> None:
    """Configured severities must match the severity vocabulary."""

    assert critical_stops["severity_levels"] == ["blocking"]


def test_source_question_mapping(rules: list[dict]) -> None:
    """Each stop must reference its approved assessment questions."""

    actual = {
        rule["rule_id"]: set(rule["source_questions"])
        for rule in rules
    }
    assert actual == EXPECTED_SOURCE_QUESTIONS


def test_source_questions_exist_in_catalog(
    rules: list[dict],
    question_ids: set[str],
) -> None:
    """Every referenced source question must exist in the catalog."""

    referenced = {
        question_id
        for rule in rules
        for question_id in rule["source_questions"]
    }
    unknown = referenced - question_ids
    assert not unknown, f"Unknown source questions: {sorted(unknown)}"


def test_trigger_operators_are_supported(rules: list[dict]) -> None:
    """Every trigger must use a supported deterministic operator."""

    for rule in rules:
        trigger = rule["trigger"]
        assert trigger["operator"] in ALLOWED_TRIGGER_OPERATORS, rule["rule_id"]


def test_maturity_triggers_have_valid_values(rules: list[dict]) -> None:
    """Maturity-based trigger values must remain within levels 0 to 4."""

    maturity_operators = {
        "maturity_level_equals",
        "any_maturity_level_equals",
        "maturity_level_below",
    }

    for rule in rules:
        trigger = rule["trigger"]
        if trigger["operator"] in maturity_operators:
            assert isinstance(trigger.get("value"), int), rule["rule_id"]
            assert 0 <= trigger["value"] <= 4, rule["rule_id"]


def test_condition_match_has_conditions(rules: list[dict]) -> None:
    """A condition-match trigger must include at least one condition."""

    for rule in rules:
        if rule["trigger"]["operator"] == "condition_match":
            assert isinstance(rule.get("conditions"), list)
            assert rule["conditions"], rule["rule_id"]


def test_conditions_are_well_formed(rules: list[dict]) -> None:
    """Conditional rules must define valid fields and operators."""

    for rule in rules:
        for condition in rule.get("conditions", []):
            assert isinstance(condition.get("field"), str)
            assert condition["field"].strip()
            assert condition.get("operator") in ALLOWED_CONDITION_OPERATORS

            if condition["operator"] == "in":
                assert isinstance(condition.get("values"), list)
                assert condition["values"]

            if condition["operator"] == "equals":
                assert "value" in condition


def test_data_boundary_rule_is_conditional(rules: list[dict]) -> None:
    """The data-boundary stop must apply to confidential or restricted data."""

    rule = next(
        item for item in rules
        if item["rule_id"] == "CS-DATA-BOUNDARY-NOT-APPROVED"
    )
    condition = rule["conditions"][0]

    assert condition["field"] == "organization_profile.data_sensitivity"
    assert condition["operator"] == "in"
    assert set(condition["values"]) == {"confidential", "restricted"}
    assert rule["trigger"] == {
        "operator": "maturity_level_below",
        "value": 3,
    }


def test_human_oversight_rule_is_conditional(rules: list[dict]) -> None:
    """Human-oversight blocking must apply to consequential outputs."""

    rule = next(
        item for item in rules
        if item["rule_id"] == "CS-NO-HUMAN-OVERSIGHT"
    )
    condition = rule["conditions"][0]

    assert condition == {
        "field": "use_case.consequential_output",
        "operator": "equals",
        "value": True,
    }
    assert rule["trigger"] == {
        "operator": "maturity_level_below",
        "value": 3,
    }


def test_production_benchmark_rule_is_scoped(rules: list[dict]) -> None:
    """Benchmark blocking must apply only to production assessment claims."""

    rule = next(
        item for item in rules
        if item["rule_id"] == "CS-NO-PRODUCTION-BENCHMARK"
    )
    condition = rule["conditions"][0]

    assert condition == {
        "field": "assessment.target_stage",
        "operator": "equals",
        "value": "production_assessment",
    }
    assert rule["trigger"] == {
        "operator": "maturity_level_below",
        "value": 3,
    }


def test_prohibited_use_rule_is_condition_only(rules: list[dict]) -> None:
    """Prohibited-use blocking must not require a question response."""

    rule = next(
        item for item in rules
        if item["rule_id"] == "CS-PROHIBITED-OR-UNACCEPTABLE-USE"
    )

    assert rule["source_questions"] == []
    assert rule["trigger"] == {"operator": "condition_match"}
    assert rule["conditions"][0] == {
        "field": "use_case.acceptability_status",
        "operator": "equals",
        "value": "prohibited",
    }


def test_score_preservation_and_decision_override(
    critical_stops: dict,
) -> None:
    """Critical stops must preserve score and block deployment."""

    evaluation = critical_stops["evaluation"]

    assert evaluation["preserve_numerical_score"] is True
    assert evaluation["blocking_decision_status"] == "Deployment Blocked"
    assert evaluation["evaluate_before_decision_engine"] is True


def test_explainability_controls_enabled(critical_stops: dict) -> None:
    """Stop results must include rule IDs and corrective actions."""

    evaluation = critical_stops["evaluation"]

    assert evaluation["include_rule_ids_in_output"] is True
    assert evaluation["include_corrective_actions_in_output"] is True


def test_output_fields_are_complete(critical_stops: dict) -> None:
    """Critical-stop output must contain all traceability fields."""

    assert set(critical_stops["output"]["include"]) == REQUIRED_OUTPUT_FIELDS


def test_validation_controls_are_enabled(critical_stops: dict) -> None:
    """Rule-integrity validation controls must be enabled."""

    validation = critical_stops["validation"]

    assert validation["reject_duplicate_rule_ids"] is True
    assert validation["reject_unknown_question_ids"] is True
    assert validation["require_rationale"] is True
    assert validation["require_corrective_action"] is True
    assert validation["require_blocking_severity"] is True
