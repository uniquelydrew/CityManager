"""Policy and modifier handling for persistent and temporary effects."""

from typing import Any, Dict, List, Tuple


def ensure_modifier_containers(state: Dict[str, Any]) -> None:
    """Ensure modifier containers exist on the world state."""
    state.setdefault("modifiers", {})
    state["modifiers"].setdefault("active_policies", [])
    state["modifiers"].setdefault("temporary_effects", [])
    state["modifiers"].setdefault("persistent_effects", [])


def policy_map(policies_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index policies by policy_id."""
    return {policy["policy_id"]: policy for policy in policies_data.get("policies", [])}


def active_policy_ids(state: Dict[str, Any]) -> List[str]:
    """Return active policy ids in insertion order."""
    ensure_modifier_containers(state)
    return list(state["modifiers"]["active_policies"])


def can_select_policy(state: Dict[str, Any], policy: Dict[str, Any]) -> Tuple[bool, str]:
    """Return whether a policy can be selected this turn."""
    ensure_modifier_containers(state)
    if state["economy"]["budget"] < policy.get("cost", 0.0):
        return False, "Policy is not affordable."
    if (
        policy.get("stacking_mode") == "unique"
        and policy["policy_id"] in state["modifiers"]["active_policies"]
    ):
        return False, "That infrastructure policy is already active."
    return True, ""


def activate_policy(state: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    """Activate a policy on the state in a JSON-compatible way."""
    ensure_modifier_containers(state)
    state["modifiers"]["active_policies"].append(policy["policy_id"])
    if policy.get("kind") == "persistent_infrastructure":
        state["modifiers"]["persistent_effects"].append(
            {
                "modifier_id": policy["policy_id"],
                "source_policy_id": policy["policy_id"],
                "duration_turns": None,
                "stat_deltas": dict(policy.get("persistent_effects", {})),
                "rule_overrides": {},
                "stacking_mode": policy.get("stacking_mode", "unique"),
            }
        )
    else:
        state["modifiers"]["temporary_effects"].append(
            {
                "modifier_id": policy["policy_id"],
                "source_policy_id": policy["policy_id"],
                "duration_turns": int(policy.get("duration_turns", 1)),
                "stat_deltas": dict(policy.get("instant_effects", {})),
                "rule_overrides": {},
                "stacking_mode": policy.get("stacking_mode", "add"),
            }
        )
    return state


def aggregate_modifier_context(state: Dict[str, Any]) -> Dict[str, float]:
    """Aggregate persistent modifier effects into a simple context dictionary."""
    ensure_modifier_containers(state)
    context = {
        "energy_demand_multiplier": 0.0,
        "energy_to_water_multiplier": 0.0,
        "irrigation_threshold_multiplier": 0.0,
        "water_capacity_bonus": 0.0,
        "grid_efficiency_bonus": 0.0,
        "food_yield_bonus": 0.0,
        "fuel_import_bonus": 0.0,
        "fuel_cost_multiplier": 0.0,
        "water_leakage_multiplier": 0.0,
        "food_spoilage_multiplier": 0.0,
        "materials_loss_multiplier": 0.0,
        "workforce_recovery_bonus": 0.0,
        "pump_efficiency_bonus": 0.0,
        "storage_capacity_bonus": 0.0,
    }
    for modifier in state["modifiers"]["persistent_effects"]:
        stat_deltas = modifier.get("stat_deltas", {})
        context["water_capacity_bonus"] += stat_deltas.get("infrastructure.water_capacity", 0.0)
        context["grid_efficiency_bonus"] += stat_deltas.get("infrastructure.grid_efficiency", 0.0)
        context["food_yield_bonus"] += stat_deltas.get("infrastructure.food_yield", 0.0)
        context["energy_to_water_multiplier"] += stat_deltas.get(
            "rule_overrides.energy_to_water_multiplier", 0.0
        )
        context["energy_demand_multiplier"] += stat_deltas.get(
            "rule_overrides.energy_demand_multiplier", 0.0
        )
        context["irrigation_threshold_multiplier"] += stat_deltas.get(
            "rule_overrides.irrigation_threshold_multiplier", 0.0
        )
        context["fuel_import_bonus"] += stat_deltas.get("resource_limits.fuel_import_bonus", 0.0)
        context["fuel_cost_multiplier"] += stat_deltas.get("resource_costs.fuel_cost_multiplier", 0.0)
        context["water_leakage_multiplier"] += stat_deltas.get(
            "rule_overrides.water_leakage_multiplier", 0.0
        )
        context["food_spoilage_multiplier"] += stat_deltas.get(
            "rule_overrides.food_spoilage_multiplier", 0.0
        )
        context["materials_loss_multiplier"] += stat_deltas.get(
            "rule_overrides.materials_loss_multiplier", 0.0
        )
        context["workforce_recovery_bonus"] += stat_deltas.get(
            "rule_overrides.workforce_recovery_bonus", 0.0
        )
        context["pump_efficiency_bonus"] += stat_deltas.get(
            "rule_overrides.pump_efficiency_bonus", 0.0
        )
        context["storage_capacity_bonus"] += stat_deltas.get(
            "resource_limits.storage_capacity_bonus", 0.0
        )
    return context


def decrement_temporary_effects(state: Dict[str, Any]) -> None:
    """Decrement timed modifier durations and remove expired entries."""
    ensure_modifier_containers(state)
    kept: List[Dict[str, Any]] = []
    for effect in state["modifiers"]["temporary_effects"]:
        turns = effect.get("duration_turns")
        if turns is None:
            kept.append(effect)
            continue
        remaining = int(turns) - 1
        if remaining > 0:
            effect["duration_turns"] = remaining
            kept.append(effect)
    state["modifiers"]["temporary_effects"] = kept
