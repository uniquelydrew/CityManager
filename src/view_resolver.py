"""Resolve scenario-bound player-facing view models from canonical state."""

from __future__ import annotations

from typing import Any, Dict, List

from src.resource_utils import stock


def _system_value(system_key: str, state: Dict[str, Any]) -> float:
    resources = state.get("resources", {})
    if system_key == "energy":
        return float(stock(resources, "energy"))
    if system_key == "water":
        return float(stock(resources, "water"))
    if system_key == "food":
        return float(stock(resources, "food"))
    if system_key == "health":
        return float(state.get("population", {}).get("health", 0.0))
    if system_key == "workforce":
        return float(stock(resources, "workforce_capacity"))
    if system_key == "logistics":
        return float(state.get("services", {}).get("transport_throughput", 0.0))
    if system_key == "infrastructure":
        infrastructure = state.get("infrastructure", {})
        return float(
            (
                infrastructure.get("water_capacity", 0.0)
                + infrastructure.get("grid_efficiency", 0.0)
                + infrastructure.get("food_yield", 0.0)
            )
            / 3.0
        )
    if system_key == "treasury":
        return float(state.get("economy", {}).get("budget", 0.0))
    if system_key == "trust":
        return float(state.get("society", {}).get("public_trust", 0.0))
    if system_key == "legitimacy":
        return float(state.get("governance", {}).get("legitimacy", 0.0))
    if system_key == "order":
        unrest = float(state.get("population", {}).get("unrest", 0.0))
        return max(0.0, 1.0 - unrest)
    return 0.0


def _state_word(system: Dict[str, Any], binding: Dict[str, Any], value: float) -> str:
    thresholds = system.get("alert_thresholds", {})
    state_words = binding.get("state_words", {})
    critical = thresholds.get("critical")
    warning = thresholds.get("warning")
    stable = thresholds.get("stable")
    if critical is not None and value <= critical:
        return state_words.get("critical", "Critical")
    if warning is not None and value <= warning:
        return state_words.get("warning", "Warning")
    if stable is not None and value >= stable:
        return state_words.get("stable", "Stable")
    return state_words.get("warning", "Warning")


def _display_value(binding: Dict[str, Any], value: float) -> str:
    display_unit = binding.get("display_unit", {})
    mode = display_unit.get("mode", "hidden")
    precision = int(display_unit.get("precision") or 0)
    if mode == "hidden":
        return ""
    if mode == "normalized":
        if 0.0 <= value <= 1.0:
            return f"{value * 100:.{precision}f}"
        return f"{value:.{precision}f}"
    unit_label = display_unit.get("unit_label")
    if unit_label:
        return f"{value:.{precision}f} {unit_label}"
    return f"{value:.{precision}f}"


def _resolved_glossary_entries(scenario_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    binding = scenario_pack["binding"]
    entries: List[Dict[str, Any]] = []
    for system_key, system_binding in binding.get("systems", {}).items():
        glossary = system_binding.get("glossary", {})
        entries.append(
            {
                "term": system_binding.get("label", system_key.replace("_", " ").title()),
                "definition": glossary.get("quick_explain", system_binding.get("description", "")),
                "why_it_matters": glossary.get("why_it_matters", ""),
                "related": list(system_binding.get("aliases", [])),
                "canonical_key": system_key,
            }
        )
    for service_key, service_binding in binding.get("services", {}).items():
        glossary = service_binding.get("glossary", {})
        entries.append(
            {
                "term": service_binding.get("label", service_key.replace("_", " ").title()),
                "definition": glossary.get("quick_explain", service_binding.get("description", "")),
                "why_it_matters": glossary.get("why_it_matters", ""),
                "related": [],
                "canonical_key": service_key,
            }
        )
    entries.extend(scenario_pack.get("glossary_entries", []))
    return entries


def resolve_view_model(
    ontology: Dict[str, Dict[str, Any]],
    scenario_pack: Dict[str, Any],
    presentation_profile: Dict[str, Any],
    state: Dict[str, Any],
    forecast: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    binding = scenario_pack["binding"]
    systems: Dict[str, Dict[str, Any]] = {}
    for system_key, system_binding in binding.get("systems", {}).items():
        canonical_system = ontology["systems"].get(system_key, {})
        value = _system_value(system_key, state)
        systems[system_key] = {
            "key": system_key,
            "canonical_label": system_key.replace("_", " ").title(),
            "display_label": system_binding.get("label", system_key.replace("_", " ").title()),
            "short_label": system_binding.get("short_label") or system_binding.get("label"),
            "display_value": _display_value(system_binding, value),
            "normalized_value": value,
            "state_word": _state_word(canonical_system, system_binding, value),
            "description": system_binding.get("description", ""),
            "mechanism_label": system_binding.get("mechanism_label"),
            "mechanism_description": system_binding.get("mechanism_description"),
            "quick_explain": system_binding.get("glossary", {}).get("quick_explain", ""),
            "why_it_matters": system_binding.get("glossary", {}).get("why_it_matters", ""),
            "aliases": list(system_binding.get("aliases", [])),
            "tutorial_hint": system_binding.get("tutorial", {}).get("player_hint"),
        }

    resolved_risks: Dict[str, Dict[str, Any]] = {}
    for risk_key, risk_binding in binding.get("risks", {}).items():
        canonical_risk = ontology["risks"].get(risk_key, {})
        resolved_risks[risk_key] = {
            "key": risk_key,
            "display_label": risk_binding.get("label", risk_key.replace("_", " ").title()),
            "summary": risk_binding.get("summary", ""),
            "if_ignored": risk_binding.get("if_ignored", ""),
            "mitigation_hint": risk_binding.get("mitigation_hint"),
            "affected_systems": list(canonical_risk.get("primary_systems", [])),
            "affected_services": list(canonical_risk.get("dependent_services", [])),
        }

    resolved_resources = {
        resource_key: {
            "display_label": resource_binding.get("label", resource_key.replace("_", " ").title()),
            "description": resource_binding.get("description", ""),
            "display_unit": dict(resource_binding.get("display_unit", {})),
            "aliases": list(resource_binding.get("aliases", [])),
        }
        for resource_key, resource_binding in binding.get("resources", {}).items()
    }

    mechanism_lines = []
    for system_key, system_binding in binding.get("systems", {}).items():
        mechanism_label = system_binding.get("mechanism_label")
        mechanism_description = system_binding.get("mechanism_description")
        if mechanism_label and mechanism_description:
            mechanism_lines.append(
                f"{system_binding.get('label', system_key.title())}: {mechanism_label} — {mechanism_description}"
            )

    risks_for_forecast = []
    if forecast:
        for risk in forecast.get("risk_ranking", []):
            resolved = dict(resolved_risks.get(risk["issue_id"], {}))
            if resolved:
                resolved["severity"] = risk.get("severity", 0.0)
                resolved["reason"] = risk.get("reason", "")
                risks_for_forecast.append(resolved)

    return {
        "scenario_id": scenario_pack["scenario_id"],
        "scenario_version": scenario_pack["scenario_version"],
        "presentation_profile_key": presentation_profile["key"],
        "presentation_profile": presentation_profile,
        "header": {
            "title": scenario_pack.get("case_metadata", {}).get("title", "Town Recovery Simulation"),
            "place": scenario_pack.get("case_metadata", {}).get("place", ""),
            "timeframe": scenario_pack.get("case_metadata", {}).get("timeframe", ""),
            "player_role": scenario_pack.get("case_metadata", {}).get("player_role", ""),
            "goal_text": scenario_pack.get("case_metadata", {}).get("goal_text", ""),
            "historical_situation": scenario_pack.get("case_metadata", {}).get("summary", ""),
            "reference_notes": list(scenario_pack.get("case_metadata", {}).get("reference_notes", [])),
            "skill_tags": list(scenario_pack.get("teaching_signals", {}).get("main_skills", [])),
            "skill_guidance": scenario_pack.get("teaching_signals", {}).get("guidance", ""),
        },
        "panel_text": dict(binding.get("ui_text", {}).get("panels", {})),
        "overlay_text": dict(binding.get("ui_text", {}).get("overlays", {})),
        "action_text": dict(binding.get("ui_text", {}).get("actions", {})),
        "systems": systems,
        "resources": resolved_resources,
        "risks": resolved_risks,
        "risk_views": risks_for_forecast,
        "actor_groups": dict(binding.get("actor_groups", {})),
        "glossary_entries": _resolved_glossary_entries(scenario_pack),
        "mechanism_lines": mechanism_lines,
        "background_notes": list(scenario_pack.get("background_notes", [])),
    }
