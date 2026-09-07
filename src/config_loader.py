"""Central YAML configuration loader for PARA-GIP.

The loader reads the complete Version 1 configuration set, performs common
structural checks, validates declared file dependencies, and returns an
immutable configuration bundle for deterministic services.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

import yaml


DEFAULT_CONFIG_DIRECTORY = Path(__file__).resolve().parents[1] / "config"

CONFIG_FILES: Mapping[str, str] = MappingProxyType(
    {
        "assessment_catalog": "assessment_questions.yaml",
        "scoring_rules": "scoring_rules.yaml",
        "critical_stop_rules": "critical_stops.yaml",
        "evidence_confidence_rules": "evidence_confidence_rules.yaml",
        "gpu_planning_rules": "gpu_planning_rules.yaml",
        "roadmap_rules": "roadmap_rules.yaml",
        "decision_rules": "decision_rules.yaml",
    }
)


class ConfigurationError(RuntimeError):
    """Base exception for PARA-GIP configuration failures."""


class ConfigurationFileNotFoundError(ConfigurationError):
    """Raised when a required configuration file is missing."""


class ConfigurationParseError(ConfigurationError):
    """Raised when a YAML file cannot be parsed."""


class ConfigurationValidationError(ConfigurationError):
    """Raised when parsed configuration violates baseline integrity rules."""


@dataclass(frozen=True, slots=True)
class ConfigurationBundle:
    """Immutable container for the loaded Version 1 configuration set."""

    config_directory: Path
    assessment_catalog: Mapping[str, Any]
    scoring_rules: Mapping[str, Any]
    critical_stop_rules: Mapping[str, Any]
    evidence_confidence_rules: Mapping[str, Any]
    gpu_planning_rules: Mapping[str, Any]
    roadmap_rules: Mapping[str, Any]
    decision_rules: Mapping[str, Any]

    def get(self, config_name: str) -> Mapping[str, Any]:
        """Return one named configuration mapping."""

        if config_name not in CONFIG_FILES:
            valid_names = ", ".join(sorted(CONFIG_FILES))
            raise KeyError(
                f"unknown configuration '{config_name}'; expected one of: "
                f"{valid_names}"
            )
        return getattr(self, config_name)

    def versions(self) -> dict[str, str]:
        """Return rule-set or catalog versions for audit records."""

        result: dict[str, str] = {}
        for name in CONFIG_FILES:
            configuration = self.get(name)
            version = configuration.get(
                "rule_set_version",
                configuration.get("catalog_version"),
            )
            if version is not None:
                result[name] = str(version)
        return result

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Return a defensive mutable copy suitable for serialization."""

        return {
            name: deepcopy(dict(self.get(name)))
            for name in CONFIG_FILES
        }


def _freeze(value: Any) -> Any:
    """Recursively convert dictionaries to read-only mappings."""

    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Load one UTF-8 YAML file and require a mapping at its root."""

    if not path.is_file():
        raise ConfigurationFileNotFoundError(
            f"required configuration file not found: {path}"
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"unable to read configuration file {path}: {exc}"
        ) from exc

    if not raw_text.strip():
        raise ConfigurationValidationError(
            f"configuration file is empty: {path}"
        )

    try:
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigurationParseError(
            f"invalid YAML in {path}: {exc}"
        ) from exc

    if not isinstance(loaded, dict):
        raise ConfigurationValidationError(
            f"configuration root must be a mapping: {path}"
        )

    return loaded


def _require_keys(
    configuration: Mapping[str, Any],
    required_keys: Iterable[str],
    *,
    config_name: str,
) -> None:
    """Require top-level keys in one configuration mapping."""

    missing = sorted(set(required_keys) - set(configuration))
    if missing:
        raise ConfigurationValidationError(
            f"{config_name} is missing required keys: {', '.join(missing)}"
        )


def _require_version(
    configuration: Mapping[str, Any],
    *,
    config_name: str,
) -> None:
    """Require schema and catalog or rule-set version metadata."""

    if str(configuration.get("schema_version", "")).strip() != "1.0":
        raise ConfigurationValidationError(
            f"{config_name} must declare schema_version '1.0'"
        )

    version = configuration.get(
        "rule_set_version",
        configuration.get("catalog_version"),
    )
    if str(version or "").strip() != "1.0":
        raise ConfigurationValidationError(
            f"{config_name} must declare Version 1.0 metadata"
        )


def _require_unique_ids(
    items: Any,
    *,
    config_name: str,
    collection_name: str,
    id_field: str,
) -> None:
    """Ensure a configured collection contains unique non-empty IDs."""

    if not isinstance(items, (list, tuple)):
        raise ConfigurationValidationError(
            f"{config_name}.{collection_name} must be a list"
        )

    identifiers: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ConfigurationValidationError(
                f"{config_name}.{collection_name}[{index}] must be a mapping"
            )
        identifier = item.get(id_field)
        if not isinstance(identifier, str) or not identifier.strip():
            raise ConfigurationValidationError(
                f"{config_name}.{collection_name}[{index}] requires "
                f"a non-empty {id_field}"
            )
        identifiers.append(identifier)

    duplicates = sorted(
        identifier
        for identifier in set(identifiers)
        if identifiers.count(identifier) > 1
    )
    if duplicates:
        raise ConfigurationValidationError(
            f"duplicate IDs in {config_name}.{collection_name}: "
            f"{', '.join(duplicates)}"
        )


def _validate_assessment_catalog(configuration: Mapping[str, Any]) -> None:
    """Validate assessment-catalog counts, IDs, and point totals."""

    _require_keys(
        configuration,
        ("domains", "domain_count", "question_count", "total_points"),
        config_name="assessment_catalog",
    )

    domains = configuration["domains"]
    _require_unique_ids(
        domains,
        config_name="assessment_catalog",
        collection_name="domains",
        id_field="id",
    )

    questions: list[Mapping[str, Any]] = []
    for domain in domains:
        domain_questions = domain.get("questions")
        if not isinstance(domain_questions, (list, tuple)):
            raise ConfigurationValidationError(
                f"domain {domain['id']} questions must be a list"
            )
        questions.extend(domain_questions)

    _require_unique_ids(
        questions,
        config_name="assessment_catalog",
        collection_name="questions",
        id_field="id",
    )

    if len(domains) != configuration["domain_count"]:
        raise ConfigurationValidationError(
            "assessment_catalog domain_count does not match actual domains"
        )
    if len(questions) != configuration["question_count"]:
        raise ConfigurationValidationError(
            "assessment_catalog question_count does not match actual questions"
        )

    try:
        total_points = sum(float(question["max_points"]) for question in questions)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationValidationError(
            "every assessment question requires numeric max_points"
        ) from exc

    if abs(total_points - float(configuration["total_points"])) > 1e-9:
        raise ConfigurationValidationError(
            "assessment_catalog total_points does not match question points"
        )


def _validate_rule_collections(
    configurations: Mapping[str, Mapping[str, Any]],
) -> None:
    """Validate unique rule IDs within the main rule collections."""

    collection_map = {
        "critical_stop_rules": (("rules", "rule_id"),),
        "gpu_planning_rules": (
            ("infrastructure_tier_rules", "rule_id"),
            ("deployment_pattern_rules", "rule_id"),
        ),
        "roadmap_rules": (("roadmap_rules", "rule_id"),),
        "decision_rules": (("rules", "rule_id"),),
    }

    for config_name, collections in collection_map.items():
        configuration = configurations[config_name]
        for collection_name, id_field in collections:
            _require_keys(
                configuration,
                (collection_name,),
                config_name=config_name,
            )
            _require_unique_ids(
                configuration[collection_name],
                config_name=config_name,
                collection_name=collection_name,
                id_field=id_field,
            )

    scoring = configurations["scoring_rules"]
    _require_keys(
        scoring,
        ("calculation", "classifications", "minimum_domain_rules"),
        config_name="scoring_rules",
    )
    _require_unique_ids(
        scoring["classifications"],
        config_name="scoring_rules",
        collection_name="classifications",
        id_field="id",
    )
    _require_unique_ids(
        scoring["minimum_domain_rules"],
        config_name="scoring_rules",
        collection_name="minimum_domain_rules",
        id_field="rule_id",
    )

    calculation = scoring["calculation"]
    if not isinstance(calculation, Mapping):
        raise ConfigurationValidationError(
            "scoring_rules.calculation must be a mapping"
        )
    calculation_rules = list(calculation.values())
    _require_unique_ids(
        calculation_rules,
        config_name="scoring_rules",
        collection_name="calculation",
        id_field="rule_id",
    )


def _validate_declared_dependencies(
    configurations: Mapping[str, Mapping[str, Any]],
) -> None:
    """Ensure declared dependency filenames exist in the loaded set."""

    available_filenames = set(CONFIG_FILES.values())

    for config_name, configuration in configurations.items():
        dependencies = configuration.get("dependencies", {})
        if not isinstance(dependencies, Mapping):
            raise ConfigurationValidationError(
                f"{config_name}.dependencies must be a mapping"
            )

        for dependency_name, filename in dependencies.items():
            if not isinstance(filename, str) or not filename.strip():
                raise ConfigurationValidationError(
                    f"{config_name} dependency {dependency_name} has "
                    "an invalid filename"
                )
            if filename not in available_filenames:
                raise ConfigurationValidationError(
                    f"{config_name} declares unknown dependency file: {filename}"
                )


def validate_configuration_set(
    configurations: Mapping[str, Mapping[str, Any]],
) -> None:
    """Validate the complete loaded configuration set."""

    missing_configurations = sorted(set(CONFIG_FILES) - set(configurations))
    if missing_configurations:
        raise ConfigurationValidationError(
            "missing loaded configurations: "
            + ", ".join(missing_configurations)
        )

    for config_name, configuration in configurations.items():
        _require_version(configuration, config_name=config_name)

    _validate_assessment_catalog(configurations["assessment_catalog"])
    _validate_rule_collections(configurations)
    _validate_declared_dependencies(configurations)


def load_configuration_bundle(
    config_directory: str | Path | None = None,
) -> ConfigurationBundle:
    """Load and validate all PARA-GIP Version 1 YAML configurations.

    Args:
        config_directory: Optional directory override. When omitted, the
            repository-level ``config`` directory is used.

    Returns:
        An immutable :class:`ConfigurationBundle`.

    Raises:
        ConfigurationError: If a file is missing, invalid, or inconsistent.
    """

    directory = Path(config_directory or DEFAULT_CONFIG_DIRECTORY).expanduser()
    directory = directory.resolve()

    loaded: dict[str, dict[str, Any]] = {
        config_name: _load_yaml_mapping(directory / filename)
        for config_name, filename in CONFIG_FILES.items()
    }

    validate_configuration_set(loaded)

    frozen = {name: _freeze(value) for name, value in loaded.items()}

    return ConfigurationBundle(
        config_directory=directory,
        assessment_catalog=frozen["assessment_catalog"],
        scoring_rules=frozen["scoring_rules"],
        critical_stop_rules=frozen["critical_stop_rules"],
        evidence_confidence_rules=frozen["evidence_confidence_rules"],
        gpu_planning_rules=frozen["gpu_planning_rules"],
        roadmap_rules=frozen["roadmap_rules"],
        decision_rules=frozen["decision_rules"],
    )


def load_config(
    config_name: str,
    config_directory: str | Path | None = None,
) -> Mapping[str, Any]:
    """Load the full bundle and return one named configuration."""

    return load_configuration_bundle(config_directory).get(config_name)


__all__ = [
    "CONFIG_FILES",
    "DEFAULT_CONFIG_DIRECTORY",
    "ConfigurationBundle",
    "ConfigurationError",
    "ConfigurationFileNotFoundError",
    "ConfigurationParseError",
    "ConfigurationValidationError",
    "load_config",
    "load_configuration_bundle",
    "validate_configuration_set",
]
