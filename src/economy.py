"""Economy helpers for the deterministic town recovery simulation."""

from typing import Dict, Tuple


def calculate_net(income: float, expenses: float, adjustment: float) -> float:
    """Compute the net result of the economy after an adjustment."""
    return income - expenses + adjustment


def update_budget(budget: float, income: float, expenses: float, adjustment: float) -> Tuple[float, float]:
    """Update the budget based on income, expenses, and an adjustment."""
    net = calculate_net(income, expenses, adjustment)
    return budget + net, net


def is_budget_positive(budget: float) -> bool:
    """Check whether the budget remains non-negative."""
    return budget >= 0


def apply_service_penalty(expenses: float, service_penalty: float) -> float:
    """Return expenses after unrest-driven penalties are applied."""
    return expenses + service_penalty


def apply_income_penalty(income: float, penalty: float) -> float:
    """Return income after a population or labor penalty is applied."""
    return max(0.0, income - penalty)


def compute_effective_income(base_income: float, health: float, unrest: float, tax_base: float) -> float:
    """Return current income based on population health, unrest, and tax base."""
    return max(0.0, base_income * health * max(0.0, 1.0 - unrest) * tax_base)


def compute_operating_result(economy: Dict[str, float]) -> float:
    """Compute the operating result from an economy dictionary."""
    expenses = apply_service_penalty(
        economy.get("expenses", 0.0),
        economy.get("service_penalty", 0.0),
    )
    return economy.get("income", 0.0) - expenses
