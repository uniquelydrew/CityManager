"""Energy helpers for the deterministic town recovery simulation."""

from typing import Tuple


def is_supply_sufficient(supply: float, consumption: float) -> bool:
    """Return True when supply meets or exceeds consumption."""
    return supply >= consumption


def required_additional_supply(supply: float, consumption: float) -> float:
    """Return the non-negative additional supply required to meet consumption."""
    if supply >= consumption:
        return 0.0
    return consumption - supply


def update_energy(supply: float, consumption: float, additional: float) -> Tuple[float, float]:
    """Update energy after consumption and additional supply."""
    updated = supply + additional - consumption
    if updated < 0:
        return 0.0, updated - supply
    return updated, updated - supply


def effective_energy_demand(base_demand: float, grid_efficiency: float, demand_multiplier: float) -> float:
    """Compute effective energy demand after infrastructure modifiers."""
    efficiency_discount = max(0.0, grid_efficiency - 1.0)
    demand = base_demand * (1.0 + demand_multiplier - efficiency_discount)
    return max(0.0, demand)


def capped_energy_purchase(desired_units: float, budget: float, unit_cost: float, cap_penalty: float) -> Tuple[float, float]:
    """Return affordable energy purchases and the visibly capped amount."""
    affordable_units = budget / unit_cost if unit_cost > 0 else 0.0
    max_units = max(0.0, affordable_units - cap_penalty)
    purchased = max(0.0, min(desired_units, max_units))
    capped_amount = max(0.0, desired_units - purchased)
    return purchased, capped_amount
