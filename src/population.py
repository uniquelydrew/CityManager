"""Population helpers for the deterministic town recovery simulation."""

from typing import Dict


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a value between low and high inclusive."""
    return max(low, min(high, value))


def apply_unrest(population: Dict[str, float], unrest_delta: float) -> Dict[str, float]:
    """Return a population dict with unrest adjusted and clamped."""
    updated = dict(population)
    updated["unrest"] = clamp(updated.get("unrest", 0.0) + unrest_delta)
    return updated


def recover_health(population: Dict[str, float], delta: float) -> Dict[str, float]:
    """Return a population dict with health improved by delta."""
    updated = dict(population)
    updated["health"] = clamp(updated.get("health", 0.0) + delta)
    return updated
