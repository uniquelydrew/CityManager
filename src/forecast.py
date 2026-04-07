"""Forecast generation helpers for no-action and action-aware projections."""

from typing import Any, Callable, Dict, Tuple


def build_forecast(
    state: Dict[str, Any],
    simulator: Callable[[Dict[str, Any], Dict[str, Any], bool], Tuple[Dict[str, Any], Dict[str, Any]]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a no-action forecast using the shared simulator."""
    no_action = {
        "emergency_allocation": {
            "energy_amount": 0.0,
            "water_amount": 0.0,
            "food_amount": 0.0,
            "total_cost": 0.0
        },
        "selected_policy_id": None,
        "risk_assessment": {"primary_risk": "", "secondary_risk": ""},
        "parsed_report_issue": {"primary_issue": "", "secondary_issue": ""},
        "science_generation_answer": 0.0
    }
    projected_state, outcome = simulator(state, no_action, True)
    return {
        "base_projection": outcome["base_projection"],
        "propagated_projection": outcome["propagated_projection"],
        "modifier_projection": outcome["modifier_projection"],
        "recovery_projection": outcome["recovery_projection"],
        "risk_ranking": projected_state["telemetry"]["last_risk_ranking"],
        "causal_chains": outcome["outcome_chain"],
        "projected_state": projected_state,
        "report_text": "",
        "context": context,
        "risk_changes": outcome["risk_changes"]
    }
