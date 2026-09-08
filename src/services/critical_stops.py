"""Deterministic critical-stop evaluation service for PARA-GIP.

The service evaluates configured maturity-based and contextual blocking rules
and returns CriticalFinding objects. It never changes readiness scores.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.assessment import Assessment
from src.models.results import CriticalFinding
from src.models.use_case import UseCase


class CriticalStopEvaluationError(ValueError):
    """Raised when a critical-stop rule cannot be evaluated safely."""


def _plain_value(value: Any) -> Any:
    """Convert enum values while leaving ordinary values unchanged."""

    return value.value if isinstance(value, Enum) else value


def _resolve_path(context: Mapping[str, Any], dotted_path: str) -> Any:
    """Resolve a dotted field path from the evaluation context."""

    current: Any = context
    for segment in dotted_path.split("."):
        if isinstance(current, Mapping):
            if segment not in current:
                return None
            current = current[segment]
        else:
            if not hasattr(current, segment):
                return None
            current = getattr(current, segment)
    return _plain_value(current)


def _condition_matches(condition: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    """Evaluate one supported contextual condition."""

    field = condition.get("field")
    operator = condition.get("operator")
    if not isinstance(field, str) or not field:
        raise CriticalStopEvaluationError("condition requires a non-empty field")

    actual = _resolve_path(context, field)

    if operator == "equals":
        return actual == condition.get("value")

    if operator == "in":
        values = condition.get("values")
        if not isinstance(values, (list, tuple)):
            raise CriticalStopEvaluationError(
                f"condition '{field}' with operator 'in' requires values"
            )
        return actual in values

    raise CriticalStopEvaluationError(
        f"unsupported condition operator '{operator}' for '{field}'"
    )


def _conditions_match(rule: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    """Require all configured contextual conditions to match."""

    conditions = rule.get("conditions", ())
    if not isinstance(conditions, (list, tuple)):
        raise CriticalStopEvaluationError(
            f"rule {rule.get('rule_id')} conditions must be a list"
        )
    return all(_condition_matches(condition, context) for condition in conditions)


def _maturity_values(
    source_questions: tuple[str, ...] | list[str],
    response_index: Mapping[str, Any],
) -> list[int]:
    """Return maturity values for a rule's configured source questions."""

    values: list[int] = []
    for question_id in source_questions:
        response = response_index.get(question_id)
        if response is not None:
            values.append(response.maturity_level)
    return values


def _trigger_matches(
    rule: Mapping[str, Any],
    response_index: Mapping[str, Any],
) -> bool:
    """Evaluate one configured deterministic trigger."""

    trigger = rule.get("trigger")
    if not isinstance(trigger, Mapping):
        raise CriticalStopEvaluationError(
            f"rule {rule.get('rule_id')} requires a trigger mapping"
        )

    operator = trigger.get("operator")
    source_questions = rule.get("source_questions", ())
    if not isinstance(source_questions, (list, tuple)):
        raise CriticalStopEvaluationError(
            f"rule {rule.get('rule_id')} source_questions must be a list"
        )

    if operator == "condition_match":
        return True

    values = _maturity_values(source_questions, response_index)
    if len(values) != len(source_questions):
        return False

    threshold = trigger.get("value")
    if not isinstance(threshold, int):
        raise CriticalStopEvaluationError(
            f"rule {rule.get('rule_id')} requires an integer trigger value"
        )

    if operator == "maturity_level_equals":
        return bool(values) and all(value == threshold for value in values)

    if operator == "any_maturity_level_equals":
        return any(value == threshold for value in values)

    if operator == "maturity_level_below":
        return bool(values) and any(value < threshold for value in values)

    raise CriticalStopEvaluationError(
        f"unsupported trigger operator '{operator}' in rule {rule.get('rule_id')}"
    )


def evaluate_critical_stops(
    assessment: Assessment,
    use_case: UseCase | None = None,
    configuration: ConfigurationBundle | None = None,
) -> list[CriticalFinding]:
    """Evaluate all configured blockers and return triggered findings.

    Missing responses do not trigger maturity-based blockers. Assessment
    completeness remains the scoring service's responsibility.
    """

    bundle = configuration or load_configuration_bundle()
    rules = bundle.critical_stop_rules
    response_index = assessment.response_by_question_id()

    context: dict[str, Any] = {
        "assessment": assessment,
        "organization_profile": assessment.organization_profile,
        "organization": assessment.organization_profile,
        "use_case": use_case,
    }

    findings: list[CriticalFinding] = []
    for rule in rules["rules"]:
        if not _conditions_match(rule, context):
            continue
        if not _trigger_matches(rule, response_index):
            continue

        findings.append(
            CriticalFinding(
                rule_id=rule["rule_id"],
                name=rule["name"],
                severity=rule["severity"],
                source_questions=list(rule.get("source_questions", ())),
                rationale=rule["rationale"],
                corrective_action=rule["corrective_action"],
                triggered=True,
            )
        )

    return findings


def has_blocking_findings(findings: list[CriticalFinding]) -> bool:
    """Return whether at least one triggered blocking finding exists."""

    return any(
        finding.triggered and _plain_value(finding.severity) == "blocking"
        for finding in findings
    )


__all__ = [
    "CriticalStopEvaluationError",
    "evaluate_critical_stops",
    "has_blocking_findings",
]
