"""Canonical ontology loading and cross-reference validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from src.schema_models import (
    CanonicalActorGroup,
    CanonicalConsequence,
    CanonicalResource,
    CanonicalRisk,
    CanonicalService,
    CanonicalSystem,
    SchemaValidationError,
)


ONTOLOGY_FILENAMES = {
    "systems": "canonical_systems.json",
    "services": "canonical_services.json",
    "resources": "canonical_resources.json",
    "actor_groups": "canonical_actor_groups.json",
    "risks": "canonical_risks.json",
    "consequences": "canonical_consequences.json",
}


@dataclass(frozen=True)
class OntologyRegistry:
    systems: Dict[str, Dict[str, Any]]
    services: Dict[str, Dict[str, Any]]
    resources: Dict[str, Dict[str, Any]]
    actor_groups: Dict[str, Dict[str, Any]]
    risks: Dict[str, Dict[str, Any]]
    consequences: Dict[str, Dict[str, Any]]

    def to_context(self) -> Dict[str, Dict[str, Any]]:
        return {
            "systems": self.systems,
            "services": self.services,
            "resources": self.resources,
            "actor_groups": self.actor_groups,
            "risks": self.risks,
            "consequences": self.consequences,
        }


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_ontology(data_dir: str) -> OntologyRegistry:
    ontology_dir = Path(data_dir) / "ontology"
    systems_payload = _load_json(ontology_dir / ONTOLOGY_FILENAMES["systems"]).get("canonical_systems", [])
    services_payload = _load_json(ontology_dir / ONTOLOGY_FILENAMES["services"]).get("canonical_services", [])
    resources_payload = _load_json(ontology_dir / ONTOLOGY_FILENAMES["resources"]).get("canonical_resources", [])
    actor_groups_payload = _load_json(ontology_dir / ONTOLOGY_FILENAMES["actor_groups"]).get("canonical_actor_groups", [])
    risks_payload = _load_json(ontology_dir / ONTOLOGY_FILENAMES["risks"]).get("canonical_risks", [])
    consequences_payload = _load_json(ontology_dir / ONTOLOGY_FILENAMES["consequences"]).get("canonical_consequences", [])

    systems = {item.key: item.data for item in map(CanonicalSystem.from_dict, systems_payload)}
    services = {item.key: item.data for item in map(CanonicalService.from_dict, services_payload)}
    resources = {item.key: item.data for item in map(CanonicalResource.from_dict, resources_payload)}
    actor_groups = {item.key: item.data for item in map(CanonicalActorGroup.from_dict, actor_groups_payload)}
    risks = {item.key: item.data for item in map(CanonicalRisk.from_dict, risks_payload)}
    consequences = {item.key: item.data for item in map(CanonicalConsequence.from_dict, consequences_payload)}

    registry = OntologyRegistry(
        systems=systems,
        services=services,
        resources=resources,
        actor_groups=actor_groups,
        risks=risks,
        consequences=consequences,
    )
    _validate_cross_references(registry)
    return registry


def _validate_cross_references(registry: OntologyRegistry) -> None:
    for system in registry.systems.values():
        for dependency in system.get("dependencies", []):
            if dependency not in registry.systems and dependency not in registry.resources:
                raise SchemaValidationError(f"CanonicalSystem[{system['key']}] dependency {dependency!r} does not resolve")
        for service_key in system.get("dependent_services", []):
            if service_key not in registry.services:
                raise SchemaValidationError(
                    f"CanonicalSystem[{system['key']}] dependent service {service_key!r} does not resolve"
                )

    for service in registry.services.values():
        for system_key in service.get("driven_by_systems", []):
            if system_key not in registry.systems:
                raise SchemaValidationError(
                    f"CanonicalService[{service['key']}] driven system {system_key!r} does not resolve"
                )
        for actor_group_key in service.get("affected_actor_groups", []):
            if actor_group_key not in registry.actor_groups:
                raise SchemaValidationError(
                    f"CanonicalService[{service['key']}] actor group {actor_group_key!r} does not resolve"
                )
        for consequence_key in service.get("failure_consequences", []):
            if consequence_key not in registry.consequences:
                raise SchemaValidationError(
                    f"CanonicalService[{service['key']}] consequence {consequence_key!r} does not resolve"
                )

    for resource in registry.resources.values():
        for system_key in resource.get("contributes_to_systems", []):
            if system_key not in registry.systems:
                raise SchemaValidationError(
                    f"CanonicalResource[{resource['key']}] system {system_key!r} does not resolve"
                )

    for actor_group in registry.actor_groups.values():
        sensitivities = actor_group.get("sensitivities", {})
        for system_sensitivity in sensitivities.get("systems", []):
            if system_sensitivity["system"] not in registry.systems:
                raise SchemaValidationError(
                    f"CanonicalActorGroup[{actor_group['key']}] system sensitivity {system_sensitivity['system']!r} does not resolve"
                )
        for service_sensitivity in sensitivities.get("services", []):
            if service_sensitivity["service"] not in registry.services:
                raise SchemaValidationError(
                    f"CanonicalActorGroup[{actor_group['key']}] service sensitivity {service_sensitivity['service']!r} does not resolve"
                )

    for risk in registry.risks.values():
        for system_key in risk.get("primary_systems", []):
            if system_key not in registry.systems:
                raise SchemaValidationError(f"CanonicalRisk[{risk['key']}] system {system_key!r} does not resolve")
        for service_key in risk.get("dependent_services", []):
            if service_key not in registry.services:
                raise SchemaValidationError(f"CanonicalRisk[{risk['key']}] service {service_key!r} does not resolve")
        for consequence_key in risk.get("consequence_chain", []):
            if consequence_key not in registry.consequences:
                raise SchemaValidationError(
                    f"CanonicalRisk[{risk['key']}] consequence {consequence_key!r} does not resolve"
                )

    for consequence in registry.consequences.values():
        for system_effect in consequence.get("affects_systems", []):
            if system_effect["system"] not in registry.systems:
                raise SchemaValidationError(
                    f"CanonicalConsequence[{consequence['key']}] system {system_effect['system']!r} does not resolve"
                )
        for actor_effect in consequence.get("affects_actor_groups", []):
            if actor_effect["actor_group"] not in registry.actor_groups:
                raise SchemaValidationError(
                    f"CanonicalConsequence[{consequence['key']}] actor group {actor_effect['actor_group']!r} does not resolve"
                )
        for service_effect in consequence.get("affects_services", []):
            if service_effect["service"] not in registry.services:
                raise SchemaValidationError(
                    f"CanonicalConsequence[{consequence['key']}] service {service_effect['service']!r} does not resolve"
                )
