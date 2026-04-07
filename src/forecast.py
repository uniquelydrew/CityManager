"""Forecast generation helpers for no-action and action-aware projections."""

from typing import Any, Callable, Dict, Tuple


def build_forecast(
    state: Dict[str, Any],
    simulator: Callable[[Dict[str, Any], Dict[str, Any], bool], Tuple[Dict[str, Any], Dict[str, Any]]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a no-action forecast using the shared simulator."""
    no_action = {
        "resource_purchases": {
            "energy": 0.0,
            "water": 0.0,
            "food": 0.0,
            "fuel": 0.0,
            "materials": 0.0,
        },
        "allocation_priority": "balance_services",
        "selected_policy_id": None,
        "risk_assessment": {"primary_risk": "", "secondary_risk": ""},
        "parsed_report_issue": {"primary_issue": "", "secondary_issue": ""},
        "science_generation_answer": 0.0,
        "emergency_total_cost": 0.0,
    }
    projected_state, outcome = simulator(state, no_action, True)
    return {
        "base_projection": outcome.get("base_projection", {}),
        "propagated_projection": outcome.get("propagated_projection", {}),
        "modifier_projection": outcome.get("modifier_projection", {}),
        "recovery_projection": outcome.get("recovery_projection", {}),
        "resource_flow_projection": outcome.get("resource_flow_projection", {}),
        "risk_ranking": projected_state["telemetry"]["last_risk_ranking"],
        "causal_chains": outcome["outcome_chain"],
        "projected_state": projected_state,
        "report_text": "",
        "context": context,
        "risk_changes": outcome["risk_changes"],
        "constraint_preview": outcome.get("constraint_preview", []),
    }
