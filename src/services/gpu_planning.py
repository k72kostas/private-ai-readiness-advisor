"""Deterministic GPU infrastructure planning service for PARA-GIP.

This service converts declared model and workload assumptions into neutral
planning outputs. It does not recommend a GPU product, make a purchasing
decision, or guarantee performance. All estimates require benchmarking.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Mapping

from src.config_loader import ConfigurationBundle, load_configuration_bundle
from src.models.results import ConfidenceLevel, ConfidenceResult, GPUPlanningResult
from src.models.workload import BenchmarkStatus, PrecisionType, WorkloadProfile


class GPUPlanningError(ValueError):
    """Raised when GPU planning cannot be completed safely."""


_CONFIDENCE_BY_ID = {
    "GPU-CONFIDENCE-LOW": ConfidenceLevel.LOW,
    "GPU-CONFIDENCE-MEDIUM": ConfidenceLevel.MEDIUM,
    "GPU-CONFIDENCE-HIGH": ConfidenceLevel.HIGH,
}


def _plain_value(value: Any) -> Any:
    """Return an enum value or the original value."""

    return value.value if isinstance(value, Enum) else value


def _decimal(value: Any) -> Decimal:
    """Convert values to Decimal without binary floating-point noise."""

    return Decimal(str(value))


def _round(value: Decimal, places: int = 2) -> float:
    """Round a planning value using half-up rounding."""

    quantum = Decimal("1").scaleb(-places)
    return float(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _model_memory_estimate(
    workload: WorkloadProfile,
    memory_rules: Mapping[str, Any],
) -> tuple[Decimal, list[str]]:
    """Estimate model-weight memory plus configured runtime overhead."""

    precision = _plain_value(workload.model.precision_or_quantization)
    bytes_by_precision = memory_rules["precision_bytes_per_parameter"]

    if precision == PrecisionType.OTHER.value:
        raise GPUPlanningError(
            "memory estimation is unavailable for a custom precision; "
            "add an explicit configured bytes-per-parameter value"
        )
    if precision not in bytes_by_precision:
        raise GPUPlanningError(f"unsupported precision: {precision}")

    parameters_billions = _decimal(workload.model.parameter_count_billions)
    bytes_per_parameter = _decimal(bytes_by_precision[precision])
    overhead = _decimal(memory_rules["default_runtime_overhead_factor"])

    estimated_gb = parameters_billions * bytes_per_parameter * overhead
    assumptions = [
        f"Model parameter count: {parameters_billions} billion.",
        f"Precision assumption: {precision} at {bytes_per_parameter} bytes per parameter.",
        f"Configured runtime overhead factor: {overhead}.",
        "Estimate covers model-weight memory plus a fixed planning overhead.",
        "Context, KV cache, batching, concurrency, framework, and serving overhead require validation.",
    ]
    return estimated_gb, assumptions


def _select_memory_class(
    estimated_vram_gb: Decimal,
    memory_classes: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Select the configured neutral GPU memory class."""

    for memory_class in memory_classes:
        minimum = _decimal(memory_class["minimum_vram_gb"])
        maximum_value = memory_class.get("maximum_vram_gb")
        maximum = None if maximum_value is None else _decimal(maximum_value)
        if estimated_vram_gb >= minimum and (
            maximum is None or estimated_vram_gb <= maximum
        ):
            return memory_class

    raise GPUPlanningError(
        f"estimated memory {estimated_vram_gb} GB does not match a configured class"
    )


def _workload_definition_complete(workload: WorkloadProfile) -> bool:
    """Return whether material model and workload inputs are present."""

    return bool(
        workload.model.family
        and workload.model.version
        and workload.model.license_status.value != "unknown"
        and workload.targets.concurrency > 0
        and workload.targets.latency_target_ms > 0
        and workload.targets.throughput_target > 0
        and workload.targets.quality_target
    )


def _operational_targets_defined(workload: WorkloadProfile) -> bool:
    """Return whether measurable operating targets are configured."""

    return bool(
        workload.targets.availability_target
        and workload.targets.latency_target_ms > 0
        and workload.targets.throughput_target > 0
        and workload.targets.quality_target
    )


def _select_infrastructure_tier(
    workload: WorkloadProfile,
    rules: Mapping[str, Any],
) -> tuple[Mapping[str, Any], str]:
    """Select an infrastructure planning tier using configured conditions."""

    complete = _workload_definition_complete(workload)
    benchmark = workload.benchmark_available
    operational = _operational_targets_defined(workload)
    formal_reviews = benchmark and operational

    facts = {
        "workload_definition_complete": complete,
        "benchmark_evidence": benchmark,
        "operational_targets_defined": operational,
        "formal_reviews_required": formal_reviews,
    }
    tiers = {item["id"]: item for item in rules["infrastructure_tiers"]}

    matching: list[tuple[Mapping[str, Any], str]] = []
    for rule in rules["infrastructure_tier_rules"]:
        conditions = rule["when"]
        if all(facts.get(key) == value for key, value in conditions.items()):
            matching.append((tiers[rule["target_tier"]], rule["rule_id"]))

    if not matching:
        raise GPUPlanningError("no infrastructure tier rule matched the workload")

    return matching[-1]


def _select_deployment_pattern(
    workload: WorkloadProfile,
    rules: Mapping[str, Any],
) -> tuple[Mapping[str, Any], list[str]]:
    """Select the highest-precedence matching deployment pattern."""

    facts = {
        "serving_pattern": _plain_value(workload.serving_pattern),
        "scale_requirement": workload.scale_requirement,
        "deployment_boundary": _plain_value(workload.deployment_boundary),
        "data_sensitivity": _plain_value(workload.data_sensitivity),
    }
    patterns = {item["id"]: item for item in rules["deployment_patterns"]}
    matches: list[tuple[Mapping[str, Any], str]] = []

    for rule in rules["deployment_pattern_rules"]:
        matched = True
        for key, expected in rule["when"].items():
            actual = facts.get(key)
            if isinstance(expected, (list, tuple)):
                matched = matched and actual in expected
            else:
                matched = matched and actual == expected
        if matched:
            matches.append((patterns[rule["target_pattern"]], rule["rule_id"]))

    if not matches:
        raise GPUPlanningError("no deployment pattern rule matched the workload")

    selected_pattern, _ = matches[-1]
    return selected_pattern, [rule_id for _, rule_id in matches]


def _planning_confidence(
    workload: WorkloadProfile,
    rules: Mapping[str, Any],
) -> ConfidenceResult:
    """Calculate GPU Planning Confidence from completeness and benchmarks."""

    complete = _workload_definition_complete(workload)
    benchmark = workload.benchmark_available
    reviewed = workload.benchmark_evidence.status is BenchmarkStatus.REVIEWED
    relevant = benchmark and bool(workload.benchmark_evidence.model_version)

    if not complete:
        confidence_id = "GPU-CONFIDENCE-LOW"
        rule_id = "GP-CONFIDENCE-001"
        reasons = ["Material model or workload inputs are incomplete."]
    elif benchmark and relevant and reviewed:
        confidence_id = "GPU-CONFIDENCE-HIGH"
        rule_id = "GP-CONFIDENCE-003"
        reasons = ["Relevant benchmark evidence is complete and reviewed."]
    else:
        confidence_id = "GPU-CONFIDENCE-MEDIUM"
        rule_id = "GP-CONFIDENCE-002"
        reasons = [
            "Workload assumptions are defined, but reviewed relevant benchmark evidence is unavailable."
        ]

    applied_rule_ids = [rule_id]
    if not benchmark:
        cap = rules["planning_confidence"]["maximum_without_benchmark"]
        maximum = _CONFIDENCE_BY_ID[cap["maximum_level"]]
        selected = _CONFIDENCE_BY_ID[confidence_id]
        rank = {ConfidenceLevel.LOW: 0, ConfidenceLevel.MEDIUM: 1, ConfidenceLevel.HIGH: 2}
        if rank[selected] > rank[maximum]:
            selected = maximum
        applied_rule_ids.append(cap["rule_id"])
        reasons.append("Without benchmark evidence, confidence cannot exceed Medium.")
    else:
        selected = _CONFIDENCE_BY_ID[confidence_id]

    missing: list[str] = []
    if workload.model.license_status.value == "unknown":
        missing.append("Reviewed model licence status")
    if not benchmark:
        missing.append("Measured workload benchmark evidence")
    elif not relevant:
        missing.append("Benchmark model-version relevance")
    elif not reviewed:
        missing.append("Benchmark review approval")

    return ConfidenceResult(
        confidence_type="gpu_planning",
        level=selected,
        score=None,
        reasons=reasons,
        missing_inputs_or_evidence=missing,
        highlighted_question_ids=[],
        applied_rule_ids=applied_rule_ids,
        rule_set_version=str(rules["rule_set_version"]),
    )


def plan_gpu_infrastructure(
    workload: WorkloadProfile,
    configuration: ConfigurationBundle | None = None,
) -> GPUPlanningResult:
    """Generate neutral GPU infrastructure planning guidance."""

    bundle = configuration or load_configuration_bundle()
    rules = bundle.gpu_planning_rules
    safeguards = rules["safeguards"]

    prohibited_flags = (
        "recommend_specific_gpu_product",
        "make_purchase_recommendation",
        "guarantee_performance",
        "treat_estimates_as_benchmarks",
    )
    if any(bool(safeguards.get(flag, True)) for flag in prohibited_flags):
        raise GPUPlanningError("GPU planning safeguards are not safely configured")

    estimate, calculated_assumptions = _model_memory_estimate(
        workload, rules["memory_estimation"]
    )
    memory_class = _select_memory_class(estimate, rules["gpu_memory_classes"])
    tier, tier_rule_id = _select_infrastructure_tier(workload, rules)
    pattern, pattern_rule_ids = _select_deployment_pattern(workload, rules)
    confidence = _planning_confidence(workload, rules)

    assumptions = list(
        dict.fromkeys([*workload.material_assumptions, *calculated_assumptions])
    )
    benchmark_action = (
        "Validate the planning estimate with a controlled benchmark that measures "
        "latency, throughput, quality, peak VRAM, and GPU utilization."
    )

    return GPUPlanningResult(
        infrastructure_tier=tier["name"],
        gpu_memory_class=memory_class["name"],
        deployment_pattern=pattern["name"],
        planning_confidence=confidence,
        material_assumptions=assumptions,
        planning_estimates={
            "estimated_model_runtime_memory_gb": _round(estimate),
            "estimate_label": rules["memory_estimation"]["estimate_label"],
            "precision": _plain_value(workload.model.precision_or_quantization),
            "runtime_overhead_factor": float(
                rules["memory_estimation"]["default_runtime_overhead_factor"]
            ),
        },
        missing_inputs=confidence.missing_inputs_or_evidence,
        recommended_benchmark_action=benchmark_action,
        applied_rule_ids=list(
            dict.fromkeys(
                [
                    rules["memory_estimation"]["rule_id"],
                    tier_rule_id,
                    *pattern_rule_ids,
                    *confidence.applied_rule_ids,
                ]
            )
        ),
        rule_set_version=str(rules["rule_set_version"]),
    )


__all__ = ["GPUPlanningError", "plan_gpu_infrastructure"]
