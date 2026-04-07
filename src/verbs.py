"""Deterministic verb executors for registry-driven resource interactions."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.explanation import record
from src.resource_utils import (
    add_constraint,
    allocate,
    record_flow,
    record_loss,
    record_production,
    stock,
)


State = Dict[str, Any]
OutcomeReport = Dict[str, Any]


def _runtime_name(resource_id: str) -> str:
    return {
        "electricity": "energy",
        "labor_hours": "workforce_capacity",
    }.get(resource_id, resource_id)


def _record_fact(outcome: OutcomeReport, interaction: Dict[str, Any], constraint: str, delta: Dict[str, float]) -> None:
    outcome.setdefault("explanation_facts", []).append(
        {
            "verb": interaction["verb"],
            "inputs": list(interaction.get("inputs", [])),
            "outputs": list(interaction.get("outputs", [])),
            "constraint": constraint,
            "delta": delta,
            "source_interaction_id": interaction["interaction_id"],
        }
    )
    outcome.setdefault("interaction_ledger", []).append(
        {
            "interaction_id": interaction["interaction_id"],
            "verb": interaction["verb"],
            "constraint": constraint,
            "delta": delta,
        }
    )


def run_allocate(
    resources: Dict[str, Any],
    interaction: Dict[str, Any],
    context: Dict[str, Any],
    priority: str,
    outcome: OutcomeReport,
) -> Dict[str, float]:
    profile_key = interaction["constraints"]["profile_key"]
    profile = context["allocation_profiles"].get(priority, context["allocation_profiles"]["balance_services"])
    shares = profile[profile_key]
    source_name = _runtime_name(interaction["inputs"][0])

    available = stock(resources, source_name)
    allocations: Dict[str, float] = {}
    for target, share in shares.items():
        amount = allocate(resources, source_name, target, available * share)
        allocations[target] = amount
    _record_fact(outcome, interaction, "", allocations)
    return allocations


def run_transform(
    resources: Dict[str, Any],
    interaction: Dict[str, Any],
    context: Dict[str, Any],
    outcome: OutcomeReport,
    constraint_log: List[str],
) -> Dict[str, float]:
    coeffs = interaction["coefficients"]
    conversion = context["conversion_rates"]
    base_production = context["base_production"]
    workforce_name = _runtime_name("labor_hours")
    output_name = _runtime_name(interaction["outputs"][0])
    fuel_name = _runtime_name(interaction["inputs"][0])

    workforce_key = coeffs["workforce_input_key"]
    workforce_amount = resources[workforce_name]["allocated"].get(workforce_key, 0.0)
    desired_output = min(
        base_production[coeffs["base_output_key"]] * max(0.5, context["grid_efficiency"]),
        workforce_amount * conversion[coeffs["workforce_ratio_key"]],
    )
    fuel_needed = desired_output / max(conversion[coeffs["fuel_ratio_key"]], 1e-9)
    fuel_used = min(stock(resources, fuel_name), fuel_needed)
    if fuel_used < fuel_needed:
        constraint = interaction["constraints"]["constraint_message"]
        add_constraint(resources, output_name, constraint)
        constraint_log.append(constraint)
    produced = min(desired_output, fuel_used * conversion[coeffs["fuel_ratio_key"]])
    if fuel_used > 0:
        allocate(resources, fuel_name, interaction["interaction_id"], fuel_used)
        record_flow(resources, fuel_name, "transformed_out", fuel_used)
    if produced > 0:
        record_production(resources, output_name, produced)
        record_flow(resources, output_name, "transformed_in", produced)
    _record_fact(outcome, interaction, resources[output_name].get("constraint", ""), {"produced": produced, "fuel_used": fuel_used})
    return {"produced": produced, "fuel_used": fuel_used}


def run_produce(
    resources: Dict[str, Any],
    interaction: Dict[str, Any],
    context: Dict[str, Any],
    outcome: OutcomeReport,
    constraint_log: List[str],
) -> Dict[str, float]:
    coeffs = interaction["coefficients"]
    conversion = context["conversion_rates"]
    base_production = context["base_production"]
    modifier_context = context["modifier_context"]
    output_name = _runtime_name(interaction["outputs"][0])

    if output_name == "water":
        workforce_amount = resources["workforce_capacity"]["allocated"].get(coeffs["workforce_input_key"], 0.0)
        materials_amount = resources["materials"]["allocated"].get("water", 0.0)
        energy_amount = resources["energy"]["allocated"].get(coeffs["energy_allocated_key"], 0.0)
        water_capacity = base_production[coeffs["base_output_key"]] * context["water_capacity_multiplier"]
        pump_supply = energy_amount * (conversion[coeffs["energy_ratio_key"]] + modifier_context["pump_efficiency_bonus"])
        material_support = materials_amount * conversion[coeffs["materials_ratio_key"]]
        workforce_cap = workforce_amount * conversion[coeffs["workforce_ratio_key"]]
        produced = min(water_capacity + material_support, pump_supply, workforce_cap)
        if produced < water_capacity:
            constraint = interaction["constraints"]["constraint_message"]
            add_constraint(resources, output_name, constraint)
            constraint_log.append(constraint)
        record_production(resources, output_name, produced)
        _record_fact(outcome, interaction, resources[output_name].get("constraint", ""), {"produced": produced})
        return {"produced": produced}

    if output_name == "food":
        workforce_amount = resources["workforce_capacity"]["allocated"].get(coeffs["workforce_input_key"], 0.0)
        energy_amount = resources["energy"]["allocated"].get(coeffs["energy_input_key"], 0.0)
        actual_water = outcome.setdefault("_verb_cache", {}).get("water_produced", 0.0)
        irrigation_water = min(stock(resources, "water"), actual_water * conversion[coeffs["water_ratio_key"]])
        food_capacity = base_production[coeffs["base_output_key"]] * max(0.5, context["food_yield"])
        workforce_cap = workforce_amount * conversion[coeffs["workforce_ratio_key"]]
        energy_cap = energy_amount * conversion[coeffs["energy_ratio_key"]]
        water_cap = irrigation_water * conversion[coeffs["water_ratio_key"]]
        produced = min(food_capacity, workforce_cap, energy_cap, water_cap)
        if produced < food_capacity:
            constraint = interaction["constraints"]["constraint_message"]
            add_constraint(resources, output_name, constraint)
            constraint_log.append(constraint)
        used_water = min(stock(resources, "water"), produced / max(conversion[coeffs["water_ratio_key"]], 1e-9))
        allocate(resources, "water", "food_production", used_water)
        record_flow(resources, "water", "transformed_out", used_water)
        record_production(resources, output_name, produced)
        record_flow(resources, output_name, "transformed_in", produced)
        _record_fact(outcome, interaction, resources[output_name].get("constraint", ""), {"produced": produced, "water_used": used_water})
        return {"produced": produced, "water_used": used_water}

    return {"produced": 0.0}


def run_consume(
    resources: Dict[str, Any],
    interaction: Dict[str, Any],
    context: Dict[str, Any],
    outcome: OutcomeReport,
    constraint_log: List[str],
) -> Dict[str, float]:
    coeffs = interaction["coefficients"]
    input_name = _runtime_name(interaction["inputs"][0])
    if interaction["interaction_id"] == "civic_service_energy":
        civic_energy = resources[input_name]["allocated"].get(coeffs["allocation_key"], 0.0)
        service_need = max(0.0, context["effective_energy_demand"] - civic_energy)
        used = allocate(resources, input_name, "service_demand", min(stock(resources, input_name), service_need))
        gap = max(0.0, service_need - used)
        if gap > 0:
            constraint = interaction["constraints"]["gap_message"].format(gap=gap)
            constraint_log.append(constraint)
            add_constraint(resources, input_name, constraint)
        _record_fact(outcome, interaction, resources[input_name].get("constraint", ""), {"used": used, "gap": gap})
        return {"used": used, "gap": gap}

    demand = context["constants"][coeffs["demand_constant_key"]]
    used = allocate(resources, input_name, interaction["outputs"][0], min(stock(resources, input_name), demand))
    _record_fact(outcome, interaction, "", {"used": used, "demand": demand})
    return {"used": used, "demand": demand}


def run_repair(resources: Dict[str, Any], interaction: Dict[str, Any], context: Dict[str, Any], outcome: OutcomeReport) -> Dict[str, float]:
    coeffs = interaction["coefficients"]
    demand = context["constants"][coeffs["demand_constant_key"]]
    used = allocate(resources, "materials", "maintenance", min(stock(resources, "materials"), demand))
    _record_fact(outcome, interaction, "", {"used": used})
    return {"used": used}


def run_decay(resources: Dict[str, Any], interaction: Dict[str, Any], context: Dict[str, Any], outcome: OutcomeReport) -> Dict[str, float]:
    coeffs = interaction["coefficients"]
    constants = context["constants"]
    modifier_context = context["modifier_context"]
    resource_name = _runtime_name(interaction["inputs"][0])
    loss_rate = constants[coeffs["loss_rate_key"]]
    multiplier = 1.0 + modifier_context.get(coeffs.get("loss_multiplier_key", ""), 0.0)
    if coeffs.get("support_resource"):
        support_available = resources[coeffs["support_resource"]]["allocated"].get("maintenance", 0.0)
        multiplier -= support_available * coeffs.get("support_effect_per_unit", 0.0)
    loss_amount = stock(resources, resource_name) * max(0.0, loss_rate * multiplier)
    lost = record_loss(resources, resource_name, loss_amount)
    _record_fact(outcome, interaction, "", {"lost": lost})
    return {"lost": lost}
