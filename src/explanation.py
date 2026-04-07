"""Structured explanation helpers for direct, dependency, modifier, and recovery effects."""

from typing import Any, Dict, List


def empty_outcome() -> Dict[str, Any]:
    """Return the default explanation structure."""
    return {
        "direct_effects": [],
        "dependency_effects": [],
        "modifier_effects": [],
        "recovery_effects": [],
        "population_effects": [],
        "economy_effects": [],
        "risk_changes": [],
        "remaining_risks": [],
        "outcome_chain": [],
        "base_projection": {},
        "propagated_projection": {},
        "modifier_projection": {},
        "recovery_projection": {},
        "resource_flow_projection": {},
        "constraint_preview": [],
    }


def record(sectioned: Dict[str, Any], section: str, message: str) -> None:
    """Append a message to a section and the ordered cause chain."""
    sectioned[section].append(message)
    sectioned["outcome_chain"].append(message)
