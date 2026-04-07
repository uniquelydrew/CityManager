"""Prompt-building and validation helpers for the CLI challenges."""

from typing import Any, Dict, List, Tuple

from src.reports import issue_label


def math_prompt(scenario: Dict[str, Any], risk_ranking: List[Dict[str, Any]]) -> str:
    """Build the constrained allocation prompt."""
    unit_costs = scenario["unit_costs"]
    top = issue_label(risk_ranking[0]["issue_id"])
    second = issue_label(risk_ranking[1]["issue_id"]) if len(risk_ranking) > 1 else top
    return (
        "Allocate the emergency budget across energy, water, and food purchases.\n"
        f"Available emergency budget: {scenario['available_emergency_budget']:.2f}\n"
        f"Unit costs -> energy: {unit_costs['energy']:.2f}, water: {unit_costs['water']:.2f}, food: {unit_costs['food']:.2f}\n"
        f"Top risks -> {top}, {second}"
    )


def validate_allocation(
    allocation: Dict[str, float],
    scenario: Dict[str, Any],
    risk_ranking: List[Dict[str, Any]],
) -> Tuple[bool, float]:
    """Validate emergency allocation total cost and rough relevance."""
    unit_costs = scenario["unit_costs"]
    total_cost = (
        allocation["energy_amount"] * unit_costs["energy"]
        + allocation["water_amount"] * unit_costs["water"]
        + allocation["food_amount"] * unit_costs["food"]
    )
    valid_budget = total_cost <= scenario["available_emergency_budget"] + 1e-9
    top_two = {risk_ranking[0]["issue_id"]}
    if len(risk_ranking) > 1:
        top_two.add(risk_ranking[1]["issue_id"])
    relevant = (
        ("energy_instability" in top_two and allocation["energy_amount"] > 0)
        or ("water_shortage" in top_two and allocation["water_amount"] > 0)
        or ("food_collapse" in top_two and allocation["food_amount"] > 0)
        or total_cost == 0.0
    )
    return valid_budget and relevant, total_cost


def science_prompt(state: Dict[str, Any], context: Dict[str, Any], required_generation: float) -> str:
    """Build the explicit energy-generation reasoning prompt."""
    recommended_reserve = context["pump_threshold"] + context["constants"]["science_safety_margin"]
    return (
        f"Current energy: {state['resources']['energy']:.1f}\n"
        f"Effective demand: {context['effective_energy_demand']:.1f}\n"
        f"Pump threshold: {context['pump_threshold']:.1f}\n"
        f"Recommended reserve after demand: {recommended_reserve:.1f}\n"
        f"Required additional generation: {required_generation:.1f}\n"
        "Enter the additional generation needed to protect the water system."
    )


def required_generation(current_energy: float, effective_demand: float, pump_threshold: float, safety_margin: float) -> float:
    """Return the additional generation needed to protect the post-demand reserve."""
    required_reserve = pump_threshold + safety_margin
    return max(0.0, required_reserve + effective_demand - current_energy)


def validate_science_generation(answer: float, required_amount: float) -> bool:
    """Return True when the science answer meets or exceeds the required generation."""
    return answer + 1e-9 >= required_amount


def social_prompt(available_policies: List[Dict[str, Any]], budget: float) -> List[str]:
    """Return formatted policy option lines."""
    lines = [f"Budget remaining for policy selection: ${budget:.2f}"]
    for policy in available_policies:
        lines.append(
            f"{policy['label']}) {policy['policy_id']} [{policy['kind']}] cost=${policy['cost']:.2f}"
        )
    return lines


def validate_rla_answers(primary: str, secondary: str, risk_ranking: List[Dict[str, Any]]) -> bool:
    """Validate primary and secondary risk interpretation."""
    expected_primary = risk_ranking[0]["issue_id"]
    expected_secondary = risk_ranking[1]["issue_id"] if len(risk_ranking) > 1 else expected_primary
    return primary == expected_primary and secondary == expected_secondary
