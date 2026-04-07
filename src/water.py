"""Water system rules for pump thresholds, penalties, and recovery."""


def effective_water_penalty(base_penalty: float, multiplier: float) -> float:
    """Return the water penalty after applying a rule multiplier."""
    return max(0.0, base_penalty * (1.0 + multiplier))


def effective_water_capacity(base_capacity: float, infrastructure_bonus: float) -> float:
    """Return effective water capacity multiplier."""
    return max(0.1, base_capacity + infrastructure_bonus)


def recovery_bonus(energy_after_demand: float, surplus_threshold: float, bonus: float) -> float:
    """Return the deterministic water recovery bonus when energy is comfortably above demand."""
    if energy_after_demand > surplus_threshold:
        return bonus
    return 0.0
