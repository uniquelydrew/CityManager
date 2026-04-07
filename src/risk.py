"""Risk scoring and ranking for the Phase 3 simulation."""

from typing import Any, Dict, List


RISK_PRIORITY = {
    "food_collapse": 0,
    "water_shortage": 1,
    "energy_instability": 2,
    "budget_erosion": 3,
    "unrest_spike": 4,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _has_chain(causal_chains: List[str], needle: str) -> bool:
    return any(needle in chain.lower() for chain in causal_chains)


def _resource_pressure(value: float, threshold: float) -> float:
    return max(0.0, (threshold - value) / max(threshold, 1.0))


def compute_risk_ranking(
    state: Dict[str, Any],
    context: Dict[str, Any],
    causal_chains: List[str],
    recovery_flags: Dict[str, bool] | None = None,
) -> List[Dict[str, Any]]:
    """Compute ranked issue severities with deterministic ordering."""
    recovery_flags = recovery_flags or {}
    resources = state["resources"]
    population = state["population"]
    economy = state["economy"]
    constants = context["constants"]
    energy_demand = context["effective_energy_demand"]

    food_pressure = _resource_pressure(resources["food"], constants["food_security_threshold"])
    water_pressure = _resource_pressure(resources["water"], context["irrigation_threshold"])
    energy_pressure = _resource_pressure(resources["energy"], context["pump_threshold"])
    budget_pressure = _resource_pressure(economy["budget"], constants["safe_budget_threshold"])
    unrest_pressure = _clamp01(
        population.get("unrest", 0.0) / max(constants["unrest_threshold"], 0.01)
        + _resource_pressure(population["health"], constants["labor_threshold"])
    )

    ranking = [
        {
            "issue_id": "food_collapse",
            "severity": _clamp01(
                food_pressure
                + (0.15 if _has_chain(causal_chains, "food") else 0.0)
                - (0.10 if recovery_flags.get("food_recovery") else 0.0)
            ),
            "reason": "food reserves reflect threshold pressure plus irrigation-linked dependency stress",
        },
        {
            "issue_id": "water_shortage",
            "severity": _clamp01(
                water_pressure
                + (0.15 if _has_chain(causal_chains, "water") else 0.0)
                - (0.10 if recovery_flags.get("water_recovery") else 0.0)
            ),
            "reason": "water risk depends on stock level and exposure to energy-linked pumping failure",
        },
        {
            "issue_id": "energy_instability",
            "severity": _clamp01(
                energy_pressure
                + max(0.0, (energy_demand - resources["energy"]) / max(energy_demand, 1.0)) * 0.5
                - (0.15 if recovery_flags.get("energy_recovery") else 0.0)
            ),
            "reason": "energy severity reflects reserve shortfall against demand and the pump threshold",
        },
        {
            "issue_id": "budget_erosion",
            "severity": _clamp01(
                max(0.0, (economy["expenses"] + economy.get("service_penalty", 0.0) - economy["income"]) / 500.0)
                + budget_pressure * 0.5
                - (0.10 if recovery_flags.get("income_recovery") else 0.0)
            ),
            "reason": "budget pressure combines operating losses, service penalties, and procurement strain",
        },
        {
            "issue_id": "unrest_spike",
            "severity": _clamp01(
                unrest_pressure - (0.10 if recovery_flags.get("population_recovery") else 0.0)
            ),
            "reason": "unrest risk follows health strain, unhappiness, and existing civic instability",
        },
    ]
    ranking.sort(key=lambda item: (-item["severity"], RISK_PRIORITY[item["issue_id"]]))
    return ranking
