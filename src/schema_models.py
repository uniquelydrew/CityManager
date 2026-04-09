"""Typed validation helpers for canonical ontology and scenario-pack data.

The repo stays JSON-backed at runtime, but these models give us one Python
validation layer for loaders, tests, and future schema export.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping


class SchemaValidationError(ValueError):
    """Raised when JSON-backed ontology or scenario content is invalid."""


def _require_keys(data: Mapping[str, Any], keys: Iterable[str], label: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise SchemaValidationError(f"{label} missing required keys: {missing}")


def _require_mapping(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaValidationError(f"{label} must be an object")
    return dict(value)


def _require_list(value: Any, label: str) -> List[Any]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{label} must be a list")
    return list(value)


@dataclass(frozen=True)
class CanonicalSystem:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalSystem":
        payload = _require_mapping(data, "CanonicalSystem")
        _require_keys(
            payload,
            [
                "key",
                "version",
                "category",
                "kind",
                "default_range",
                "normalization",
                "alert_thresholds",
                "state_labels",
                "dependencies",
                "dependent_services",
                "failure_modes",
                "recovery_modes",
                "pedagogy_tags",
                "debug_description",
            ],
            f"CanonicalSystem[{payload.get('key', '<unknown>')}]",
        )
        _require_mapping(payload["default_range"], "CanonicalSystem.default_range")
        _require_mapping(payload["normalization"], "CanonicalSystem.normalization")
        _require_mapping(payload["alert_thresholds"], "CanonicalSystem.alert_thresholds")
        _require_mapping(payload["state_labels"], "CanonicalSystem.state_labels")
        _require_list(payload["dependencies"], "CanonicalSystem.dependencies")
        _require_list(payload["dependent_services"], "CanonicalSystem.dependent_services")
        return cls(payload)


@dataclass(frozen=True)
class CanonicalService:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalService":
        payload = _require_mapping(data, "CanonicalService")
        _require_keys(
            payload,
            [
                "key",
                "version",
                "description",
                "driven_by_systems",
                "affected_actor_groups",
                "failure_consequences",
                "presentation_priority",
            ],
            f"CanonicalService[{payload.get('key', '<unknown>')}]",
        )
        return cls(payload)


@dataclass(frozen=True)
class CanonicalResource:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalResource":
        payload = _require_mapping(data, "CanonicalResource")
        _require_keys(
            payload,
            [
                "key",
                "version",
                "category",
                "kind",
                "default_unit_type",
                "contributes_to_systems",
                "substitutes_for",
                "scarcity_behavior",
                "debug_description",
            ],
            f"CanonicalResource[{payload.get('key', '<unknown>')}]",
        )
        _require_mapping(payload["scarcity_behavior"], "CanonicalResource.scarcity_behavior")
        return cls(payload)


@dataclass(frozen=True)
class CanonicalActorGroup:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalActorGroup":
        payload = _require_mapping(data, "CanonicalActorGroup")
        _require_keys(
            payload,
            ["key", "version", "class", "sensitivities", "trust_links", "debug_description"],
            f"CanonicalActorGroup[{payload.get('key', '<unknown>')}]",
        )
        _require_mapping(payload["sensitivities"], "CanonicalActorGroup.sensitivities")
        _require_mapping(payload["trust_links"], "CanonicalActorGroup.trust_links")
        return cls(payload)


@dataclass(frozen=True)
class CanonicalRisk:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalRisk":
        payload = _require_mapping(data, "CanonicalRisk")
        _require_keys(
            payload,
            [
                "key",
                "version",
                "primary_systems",
                "dependent_services",
                "timeline_class",
                "severity_model",
                "consequence_chain",
                "mitigation_actions",
                "debug_description",
            ],
            f"CanonicalRisk[{payload.get('key', '<unknown>')}]",
        )
        return cls(payload)


@dataclass(frozen=True)
class CanonicalConsequence:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CanonicalConsequence":
        payload = _require_mapping(data, "CanonicalConsequence")
        _require_keys(
            payload,
            [
                "key",
                "version",
                "affects_systems",
                "affects_actor_groups",
                "affects_services",
                "narrative_class",
                "debug_description",
            ],
            f"CanonicalConsequence[{payload.get('key', '<unknown>')}]",
        )
        return cls(payload)


@dataclass(frozen=True)
class ScenarioBinding:
    data: Dict[str, Any]

    @property
    def scenario_id(self) -> str:
        return str(self.data["scenario_id"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScenarioBinding":
        payload = _require_mapping(data, "ScenarioBinding")
        _require_keys(
            payload,
            [
                "scenario_id",
                "scenario_version",
                "setting_profile",
                "systems",
                "services",
                "resources",
                "risks",
                "actor_groups",
                "ui_text",
            ],
            f"ScenarioBinding[{payload.get('scenario_id', '<unknown>')}]",
        )
        for system_key, system_binding in payload["systems"].items():
            mapping = _require_mapping(system_binding, f"ScenarioBinding.systems[{system_key}]")
            _require_keys(
                mapping,
                [
                    "label",
                    "description",
                    "display_unit",
                    "display_style",
                    "state_words",
                    "risk_labels",
                    "glossary",
                    "tutorial",
                    "aliases",
                ],
                f"ScenarioBinding.systems[{system_key}]",
            )
        for service_key, service_binding in payload["services"].items():
            mapping = _require_mapping(service_binding, f"ScenarioBinding.services[{service_key}]")
            _require_keys(
                mapping,
                ["label", "description", "failure_text", "glossary"],
                f"ScenarioBinding.services[{service_key}]",
            )
        for risk_key, risk_binding in payload["risks"].items():
            mapping = _require_mapping(risk_binding, f"ScenarioBinding.risks[{risk_key}]")
            _require_keys(
                mapping,
                ["label", "summary", "if_ignored", "mitigation_hint"],
                f"ScenarioBinding.risks[{risk_key}]",
            )
        ui_text = _require_mapping(payload["ui_text"], "ScenarioBinding.ui_text")
        _require_keys(ui_text, ["panels", "actions", "overlays"], "ScenarioBinding.ui_text")
        return cls(payload)


@dataclass(frozen=True)
class PresentationProfile:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PresentationProfile":
        payload = _require_mapping(data, "PresentationProfile")
        _require_keys(
            payload,
            ["key", "description", "text_policy", "panel_visibility"],
            f"PresentationProfile[{payload.get('key', '<unknown>')}]",
        )
        return cls(payload)


@dataclass(frozen=True)
class ActionDefinition:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ActionDefinition":
        payload = _require_mapping(data, "ActionDefinition")
        _require_keys(
            payload,
            ["key", "version", "category", "costs", "effects", "prerequisites", "risk_modifiers", "presentation", "pedagogy"],
            f"ActionDefinition[{payload.get('key', '<unknown>')}]",
        )
        return cls(payload)


@dataclass(frozen=True)
class EventDefinition:
    data: Dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.data["key"])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EventDefinition":
        payload = _require_mapping(data, "EventDefinition")
        _require_keys(
            payload,
            ["key", "version", "triggers", "effects", "risk_changes", "narrative_payload"],
            f"EventDefinition[{payload.get('key', '<unknown>')}]",
        )
        return cls(payload)


def export_json_schemas() -> Dict[str, Dict[str, Any]]:
    """Return lightweight JSON-Schema-like metadata for authoring tools."""
    return {
        "CanonicalSystem": {
            "type": "object",
            "required": [
                "key",
                "version",
                "category",
                "kind",
                "default_range",
                "normalization",
                "alert_thresholds",
                "state_labels",
                "dependencies",
                "dependent_services",
                "failure_modes",
                "recovery_modes",
                "pedagogy_tags",
                "debug_description",
            ],
        },
        "CanonicalService": {
            "type": "object",
            "required": [
                "key",
                "version",
                "description",
                "driven_by_systems",
                "affected_actor_groups",
                "failure_consequences",
                "presentation_priority",
            ],
        },
        "CanonicalResource": {
            "type": "object",
            "required": [
                "key",
                "version",
                "category",
                "kind",
                "default_unit_type",
                "contributes_to_systems",
                "substitutes_for",
                "scarcity_behavior",
                "debug_description",
            ],
        },
        "CanonicalActorGroup": {
            "type": "object",
            "required": ["key", "version", "class", "sensitivities", "trust_links", "debug_description"],
        },
        "CanonicalRisk": {
            "type": "object",
            "required": [
                "key",
                "version",
                "primary_systems",
                "dependent_services",
                "timeline_class",
                "severity_model",
                "consequence_chain",
                "mitigation_actions",
                "debug_description",
            ],
        },
        "CanonicalConsequence": {
            "type": "object",
            "required": [
                "key",
                "version",
                "affects_systems",
                "affects_actor_groups",
                "affects_services",
                "narrative_class",
                "debug_description",
            ],
        },
        "ScenarioBinding": {
            "type": "object",
            "required": [
                "scenario_id",
                "scenario_version",
                "setting_profile",
                "systems",
                "services",
                "resources",
                "risks",
                "actor_groups",
                "ui_text",
            ],
        },
        "PresentationProfile": {
            "type": "object",
            "required": ["key", "description", "text_policy", "panel_visibility"],
        },
        "ActionDefinition": {
            "type": "object",
            "required": ["key", "version", "category", "costs", "effects", "prerequisites", "risk_modifiers", "presentation", "pedagogy"],
        },
        "EventDefinition": {
            "type": "object",
            "required": ["key", "version", "triggers", "effects", "risk_changes", "narrative_payload"],
        },
    }
