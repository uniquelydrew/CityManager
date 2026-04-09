"""Risk scoring and ranking for the Phase 3 simulation."""

from typing import Any, Dict, List

from src.resource_utils import stock


RISK_PRIORITY = {
    "food_collapse": 0,
    "water_shortage": 1,
    "energy_instability": 2,
    "budget_erosion": 3,
    "unrest_spike": 4,
    "institutional_breakdown": 5,
    "political_stalemate": 6,
    "public_trust_collapse": 7,
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
    ledger: Dict[str, Any] | None = None,
    constraint_log: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Compute ranked issue severities with deterministic ordering."""
    recovery_flags = recovery_flags or {}
    ledger = ledger or {}
    constraint_log = constraint_log or []
    resources = state["resources"]
    population = state["population"]
    economy = state["economy"]
    governance = state.get("governance", {})
    politics = state.get("politics", {})
    society = state.get("society", {})
    services = state.get("services", {})
    economic_conditions = state.get("economic_conditions", {})
    constants = context["constants"]
    energy_demand = context["effective_energy_demand"]

    food_pressure = _resource_pressure(stock(resources, "food"), constants["food_security_threshold"])
    water_pressure = _resource_pressure(stock(resources, "water"), context["irrigation_threshold"])
    energy_pressure = _resource_pressure(stock(resources, "energy"), context["pump_threshold"])
    budget_pressure = _resource_pressure(economy["budget"], constants["safe_budget_threshold"])
    unrest_pressure = _clamp01(
        population.get("unrest", 0.0) / max(constants["unrest_threshold"], 0.01)
        + _resource_pressure(population["health"], constants["labor_threshold"])
    )
    fuel_pressure = _resource_pressure(stock(resources, "fuel"), constants.get("fuel_risk_threshold", 12.0))
    materials_pressure = _resource_pressure(stock(resources, "materials"), constants.get("materials_risk_threshold", 8.0))
    workforce_pressure = _resource_pressure(stock(resources, "workforce_capacity"), constants.get("workforce_risk_threshold", 45.0))
    energy_constraint = 0.15 if any("fuel" in item.lower() or "energy" in item.lower() or "operating capacity" in item.lower() for item in constraint_log) else 0.0
    water_constraint = 0.15 if any("water delivery" in item.lower() or "water" in item.lower() for item in constraint_log) else 0.0
    food_constraint = 0.15 if any("food production" in item.lower() for item in constraint_log) else 0.0
    budget_constraint = 0.10 if economy.get("service_penalty", 0.0) > 0 else 0.0
    unrest_constraint = 0.10 if workforce_pressure > 0.0 else 0.0
    institutional_pressure = _clamp01(
        _resource_pressure(services.get("transport_throughput", 1.0), 0.55)
        + services.get("repair_backlog", 0.0) * 0.4
        + services.get("institutional_bottlenecks", 0.0) * 0.5
        + _resource_pressure(governance.get("administrative_capacity", 1.0), 0.55)
    )
    political_pressure = _clamp01(
        _resource_pressure(politics.get("coalition_stability", 1.0), 0.55)
        + politics.get("opposition_pressure", 0.0) * 0.5
        + politics.get("elite_resistance", 0.0) * 0.35
    )
    trust_pressure = _clamp01(
        _resource_pressure(society.get("public_trust", 1.0), 0.55)
        + society.get("class_sector_strain", 0.0) * 0.35
        + society.get("labor_unrest", 0.0) * 0.4
    )

    ranking = [
        {
            "issue_id": "food_collapse",
            "severity": _clamp01(
                food_pressure
                + food_constraint
                + materials_pressure * 0.10
                + (0.15 if _has_chain(causal_chains, "food") else 0.0)
                - (0.10 if recovery_flags.get("food_recovery") else 0.0)
            ),
            "reason": "food supply is shaped by stock level plus water, energy, and workforce limits",
        },
        {
            "issue_id": "water_shortage",
            "severity": _clamp01(
                water_pressure
                + water_constraint
                + materials_pressure * 0.15
                + (0.15 if _has_chain(causal_chains, "water") else 0.0)
                - (0.10 if recovery_flags.get("water_recovery") else 0.0)
            ),
            "reason": "water service depends on reserves, pump power, repair materials, and workforce",
        },
        {
            "issue_id": "energy_instability",
            "severity": _clamp01(
                energy_pressure
                + energy_constraint
                + fuel_pressure * 0.35
                + workforce_pressure * 0.15
                + max(0.0, (energy_demand - stock(resources, "energy")) / max(energy_demand, 1.0)) * 0.5
                - (0.15 if recovery_flags.get("energy_recovery") else 0.0)
            ),
            "reason": "energy risk reflects reserves plus fuel and workforce bottlenecks",
        },
        {
            "issue_id": "budget_erosion",
            "severity": _clamp01(
                max(0.0, (economy["expenses"] + economy.get("service_penalty", 0.0) - economy["income"]) / 500.0)
                + budget_constraint
                + budget_pressure * 0.5
                - (0.10 if recovery_flags.get("income_recovery") else 0.0)
            ),
            "reason": "budget pressure combines operating losses, service penalties, imports, and procurement strain",
        },
        {
            "issue_id": "unrest_spike",
            "severity": _clamp01(
                unrest_constraint
                + unrest_pressure
                - (0.10 if recovery_flags.get("population_recovery") else 0.0)
            ),
            "reason": "community strain follows health loss, low service quality, and workforce stress",
        },
        {
            "issue_id": "institutional_breakdown",
            "severity": _clamp01(
                institutional_pressure
                + (0.10 if any("throughput" in item.lower() or "distribution" in item.lower() for item in constraint_log) else 0.0)
            ),
            "reason": "institutional pressure reflects transport, distribution, repair backlog, and administrative weakness",
        },
        {
            "issue_id": "political_stalemate",
            "severity": _clamp01(
                political_pressure
                + max(0.0, economic_conditions.get("debt_pressure", 0.0) - 0.5) * 0.2
            ),
            "reason": "political pressure reflects weak coalition support, opposition pressure, and elite resistance",
        },
        {
            "issue_id": "public_trust_collapse",
            "severity": _clamp01(
                trust_pressure
                + max(0.0, services.get("hospital_pressure", 0.0) - 0.4) * 0.2
            ),
            "reason": "public trust pressure rises when shortages, labor conflict, and visible service strain reach households",
        },
    ]
    ranking.sort(key=lambda item: (-item["severity"], RISK_PRIORITY[item["issue_id"]]))
    return ranking
