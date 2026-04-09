"""Scenario-pack loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.schema_models import ScenarioBinding, SchemaValidationError


REQUIRED_SCENARIO_FILES = [
    "scenario_binding.json",
    "scenario_actions.json",
    "scenario_events.json",
    "scenario_glossary.json",
    "scenario_background.json",
]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_scenario_packs(
    data_dir: str,
    ontology: Dict[str, Dict[str, Any]] | None = None,
    legacy_cases: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Dict[str, Any]]:
    scenarios_dir = Path(data_dir) / "scenarios"
    packs: Dict[str, Dict[str, Any]] = {}
    if not scenarios_dir.exists():
        return packs
    for scenario_dir in scenarios_dir.iterdir():
        if not scenario_dir.is_dir():
            continue
        pack = load_scenario_pack(data_dir, scenario_dir.name, ontology=ontology, legacy_cases=legacy_cases)
        packs[pack["scenario_id"]] = pack
    return packs


def load_scenario_pack(
    data_dir: str,
    scenario_id: str,
    ontology: Dict[str, Dict[str, Any]] | None = None,
    legacy_cases: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    legacy_cases = legacy_cases or {}
    scenario_dir = Path(data_dir) / "scenarios" / scenario_id
    if not scenario_dir.exists():
        raise SchemaValidationError(f"Scenario pack {scenario_id!r} does not exist")
    files = {name: _load_json(scenario_dir / name) for name in REQUIRED_SCENARIO_FILES}
    binding = ScenarioBinding.from_dict(files["scenario_binding.json"]).data
    _validate_binding_keys(binding, ontology or {})

    background = _resolve_legacy_section(files["scenario_background.json"], legacy_cases.get(scenario_id, {}))
    actions = _resolve_legacy_section(files["scenario_actions.json"], legacy_cases.get(scenario_id, {}))
    events = _resolve_legacy_section(files["scenario_events.json"], legacy_cases.get(scenario_id, {}))
    glossary = files["scenario_glossary.json"]

    case_metadata = dict(background.get("case_metadata", {}))
    if "title" not in case_metadata:
        case_metadata["title"] = scenario_id.replace("_", " ").title()
    case_metadata.setdefault("summary", "")
    case_metadata.setdefault("player_role", "You are coordinating crisis response.")
    case_metadata.setdefault("goal_text", "Goal: stabilize the situation.")
    pack = {
        "scenario_id": binding["scenario_id"],
        "scenario_version": binding["scenario_version"],
        "setting_profile": binding["setting_profile"],
        "binding": binding,
        "case_metadata": case_metadata,
        "actors": list(background.get("actors", [])),
        "institutions": list(background.get("institutions", [])),
        "groups": list(background.get("groups", [])),
        "resources": list(background.get("resources", [])),
        "indicators": list(background.get("indicators", [])),
        "policy_domains": list(background.get("policy_domains", [])),
        "policy_options": list(actions.get("policy_options", [])),
        "events_and_reports": list(events.get("events_and_reports", [])),
        "glossary_entries": list(glossary.get("entries", [])),
        "background_notes": list(glossary.get("background_notes", [])),
        "teaching_signals": dict(background.get("teaching_signals", {})),
        "historical_notes": dict(background.get("historical_notes", {})),
        "world_state": dict(background.get("world_state", {})),
        "ui_text": dict(binding.get("ui_text", {})),
        "legacy_case": legacy_cases.get(scenario_id),
        "historical_case_id": scenario_id,
    }
    return pack


def _resolve_legacy_section(section_payload: Dict[str, Any], legacy_case: Dict[str, Any]) -> Dict[str, Any]:
    if section_payload.get("inherit_legacy_case"):
        merged = dict(section_payload)
        merged.pop("inherit_legacy_case", None)
        for key, value in legacy_case.items():
            merged.setdefault(key, value)
        return merged
    return section_payload


def _validate_binding_keys(binding: Dict[str, Any], ontology: Dict[str, Dict[str, Any]]) -> None:
    systems = ontology.get("systems", {})
    services = ontology.get("services", {})
    resources = ontology.get("resources", {})
    risks = ontology.get("risks", {})
    for system_key in binding.get("systems", {}):
        if systems and system_key not in systems:
            raise SchemaValidationError(f"ScenarioBinding[{binding['scenario_id']}] system {system_key!r} is not canonical")
    for service_key in binding.get("services", {}):
        if services and service_key not in services:
            raise SchemaValidationError(
                f"ScenarioBinding[{binding['scenario_id']}] service {service_key!r} is not canonical"
            )
    for resource_key in binding.get("resources", {}):
        if resources and resource_key not in resources:
            raise SchemaValidationError(
                f"ScenarioBinding[{binding['scenario_id']}] resource {resource_key!r} is not canonical"
            )
    for risk_key in binding.get("risks", {}):
        if risks and risk_key not in risks:
            raise SchemaValidationError(f"ScenarioBinding[{binding['scenario_id']}] risk {risk_key!r} is not canonical")
