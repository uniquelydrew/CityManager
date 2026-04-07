"""Player-facing formatting helpers for the PySide6 GUI."""

from __future__ import annotations

from typing import Any, Dict, List


PLAYER_RISK_LABELS = {
    "energy_instability": "Power shortage risk",
    "budget_erosion": "Budget under strain",
    "food_collapse": "Food supply risk",
    "water_shortage": "Water shortage risk",
    "unrest_spike": "Community unrest risk",
}


def risk_label(issue_id: str) -> str:
    return PLAYER_RISK_LABELS.get(issue_id, issue_id.replace("_", " ").title())


def title_case_label(issue_id: str) -> str:
    text = risk_label(issue_id)
    return text[:1].upper() + text[1:]


def resource_status(value: float, safe_threshold: float) -> str:
    if value < safe_threshold * 0.7:
        return "Critical"
    if value < safe_threshold:
        return "Warning"
    return "Safe"


def budget_status(value: float, safe_threshold: float) -> str:
    if value < safe_threshold * 0.8:
        return "Critical"
    if value < safe_threshold:
        return "Warning"
    return "Safe"


def top_risk(forecast: Dict[str, Any]) -> Dict[str, Any] | None:
    risks = forecast.get("risk_ranking", [])
    return risks[0] if risks else None


def threshold_snapshot(forecast: Dict[str, Any]) -> Dict[str, float]:
    constants = forecast.get("context", {}).get("constants", {})
    return {
        "water": float(constants.get("safe_water_threshold", 30.0)),
        "energy": float(constants.get("safe_energy_threshold", 25.0)),
        "food": float(constants.get("safe_food_threshold", 30.0)),
        "health": float(constants.get("safe_health_threshold", 0.7)) * 100.0,
        "budget": float(constants.get("safe_budget_threshold", 9000.0)),
    }


def state_status_snapshot(state: Dict[str, Any], forecast: Dict[str, Any]) -> Dict[str, str]:
    thresholds = threshold_snapshot(forecast)
    return {
        "water": resource_status(float(state["resources"]["water"]), thresholds["water"]),
        "energy": resource_status(float(state["resources"]["energy"]), thresholds["energy"]),
        "food": resource_status(float(state["resources"]["food"]), thresholds["food"]),
        "health": resource_status(float(state["population"]["health"] * 100.0), thresholds["health"]),
        "budget": budget_status(float(state["economy"]["budget"]), thresholds["budget"]),
    }


def urgent_problem_sentence(forecast: Dict[str, Any]) -> str:
    risk = top_risk(forecast)
    if not risk:
        return "The town is stable right now."
    return f"The most urgent problem is {risk_label(risk['issue_id']).lower()}."


def consequence_sentence(forecast: Dict[str, Any]) -> str:
    top = top_risk(forecast)
    if not top:
        return "If nothing changes, the town should stay steady next turn."
    issue_id = top["issue_id"]
    if issue_id == "energy_instability":
        return "If power drops too low, water pumps may fail next turn."
    if issue_id == "water_shortage":
        return "If water runs low, food production may also fall."
    if issue_id == "food_collapse":
        return "If food runs low, town health may get worse."
    if issue_id == "budget_erosion":
        return "If the budget keeps shrinking, emergency response will get harder."
    if issue_id == "unrest_spike":
        return "If community strain grows, services and income may suffer."
    return "If nothing changes, one of the town's key systems may get worse next turn."


def recommendation_sentence(forecast: Dict[str, Any]) -> str:
    top = top_risk(forecast)
    if not top:
        return "You can keep supplies balanced and avoid overspending."
    issue_id = top["issue_id"]
    if issue_id == "energy_instability":
        return "Try buying emergency energy first to protect water service."
    if issue_id == "water_shortage":
        return "Try buying emergency water or protecting energy so pumps can keep running."
    if issue_id == "food_collapse":
        return "Try buying emergency food and keeping water above the warning line."
    if issue_id == "budget_erosion":
        return "Spend carefully this turn and focus only on the most urgent shortage."
    if issue_id == "unrest_spike":
        return "Protect core services first so health and community stability can recover."
    return "Focus on the strongest warning first."


def system_links(forecast: Dict[str, Any]) -> List[str]:
    links = [
        "Power affects water pumps.",
        "Water affects food supply.",
        "Food affects health.",
        "Health and unrest affect town income.",
    ]
    top = top_risk(forecast)
    if top and top["issue_id"] == "budget_erosion":
        links.append("A weak budget can limit future energy recovery.")
    return links[:4]


def _resource_after_value(forecast: Dict[str, Any], key: str) -> float | None:
    base = forecast.get("base_projection", {}).get(key, {})
    if key == "budget":
        return base.get("after_operations", base.get("start"))
    value = base.get("after_consumption", base.get("start"))
    for section in ["propagated_projection", "modifier_projection", "recovery_projection"]:
        if key in forecast.get(section, {}):
            inner = forecast[section][key]
            for field in ["after_dependencies", "after_modifiers", "after_recovery"]:
                if field in inner:
                    value = inner[field]
    return value


def outlook_lines(forecast: Dict[str, Any]) -> List[str]:
    thresholds = threshold_snapshot(forecast)
    lines: List[str] = []
    for key in ["energy", "water", "food"]:
        start = forecast.get("base_projection", {}).get(key, {}).get("start")
        end = _resource_after_value(forecast, key)
        if start is None or end is None:
            continue
        status = resource_status(float(end), thresholds[key])
        lines.append(f"{key.title()}: {start:.1f} -> {end:.1f} | {status}")
    budget_start = forecast.get("base_projection", {}).get("budget", {}).get("start")
    budget_end = _resource_after_value(forecast, "budget")
    if budget_start is not None and budget_end is not None:
        status = budget_status(float(budget_end), thresholds["budget"])
        lines.append(f"Budget: ${budget_start:.0f} -> ${budget_end:.0f} | {status}")
    return lines


def top_risk_cards(forecast: Dict[str, Any]) -> List[str]:
    cards = []
    for risk in forecast.get("risk_ranking", [])[:2]:
        cards.append(
            f"{title_case_label(risk['issue_id'])} | Urgency {risk['severity']:.2f}\n"
            f"{consequence_sentence({'risk_ranking': [risk]})}"
        )
    return cards or ["No urgent problems are forecast right now."]


def improvement_lines(forecast: Dict[str, Any]) -> List[str]:
    top = top_risk(forecast)
    if not top:
        return ["Balanced choices will help the town stay stable."]
    issue_id = top["issue_id"]
    if issue_id == "energy_instability":
        return [
            "Buying emergency energy can help keep power above the danger line.",
            "Protecting power also helps protect water service.",
        ]
    if issue_id == "water_shortage":
        return [
            "Protecting energy can reduce water loss from pump trouble.",
            "Emergency water can buy time while the pumps stay online.",
        ]
    if issue_id == "food_collapse":
        return [
            "Emergency food helps right away.",
            "Protecting water also helps food production recover.",
        ]
    if issue_id == "budget_erosion":
        return [
            "Smaller, targeted purchases can protect the budget.",
            "A safer budget keeps future emergency options open.",
        ]
    return [recommendation_sentence(forecast)]


def mission_text(forecast: Dict[str, Any]) -> str:
    return "Goal: keep the town stable for 2 safe turns."


def safety_text() -> str:
    return "A safe turn means no critical shortages and the budget stays healthy."


def current_problem_text(forecast: Dict[str, Any]) -> str:
    top = top_risk(forecast)
    if not top:
        return "Current urgent problem: none."
    return f"Current urgent problem: {risk_label(top['issue_id'])}."


def active_policy_text(state: Dict[str, Any]) -> str:
    policies = state.get("modifiers", {}).get("active_policies", [])
    if not policies:
        return "No active town policies."
    return "Active policies: " + ", ".join(policy.replace("_", " ") for policy in policies)


def policy_title(policy_id: str) -> str:
    return policy_id.replace("_", " ").title()


def policy_summary(policy: Dict[str, Any]) -> str:
    policy_id = policy["policy_id"]
    if policy_id == "water_emergency_crews":
        return "Short-term help: adds emergency water this turn."
    if policy_id == "grid_fuel_delivery":
        return "Short-term help: adds emergency energy this turn."
    if policy_id == "food_relief_convoy":
        return "Short-term help: adds emergency food this turn."
    if policy_id == "pump_repair_program":
        return "Long-term help: improves water system reliability."
    if policy_id == "grid_maintenance":
        return "Long-term help: lowers future energy demand."
    if policy_id == "irrigation_upgrade":
        return "Long-term help: improves future food production."
    return "Town policy support."


def tutor_startup_lines(forecast: Dict[str, Any]) -> List[str]:
    return [
        mission_text(forecast),
        urgent_problem_sentence(forecast),
        consequence_sentence(forecast),
        recommendation_sentence(forecast),
    ]


def tutor_turn_lines(result: Dict[str, Any]) -> List[str]:
    state = result["state"]
    outcome = result.get("outcome", {})
    actions = result.get("actions", {})
    turn = state.get("telemetry", {}).get("turn", 1) - 1
    allocation = actions.get("emergency_allocation", {})
    selected_policy_id = actions.get("selected_policy_id")
    chosen = []
    if allocation.get("energy_amount", 0) > 0:
        chosen.append("emergency energy")
    if allocation.get("water_amount", 0) > 0:
        chosen.append("emergency water")
    if allocation.get("food_amount", 0) > 0:
        chosen.append("emergency food")
    dependency = outcome.get("dependency_effects", [])
    recovery = outcome.get("recovery_effects", [])
    remaining = outcome.get("remaining_risks", [])
    lines = [f"Turn {turn}"]
    if chosen:
        if len(chosen) == 1:
            choice_text = chosen[0]
        elif len(chosen) == 2:
            choice_text = f"{chosen[0]} and {chosen[1]}"
        else:
            choice_text = f"{chosen[0]}, {chosen[1]}, and {chosen[2]}"
        lines.append(f"What you chose: You bought {choice_text}.")
    else:
        lines.append("What you chose: You saved your emergency budget this turn.")
    if selected_policy_id:
        lines.append(f"Policy: You also chose {policy_title(selected_policy_id).lower()}.")
    if dependency:
        lines.append("What changed: " + dependency[0])
    elif recovery:
        lines.append("What changed: " + recovery[0])
    if len(dependency) > 1:
        lines.append("Why it changed: " + dependency[1])
    elif recovery:
        lines.append("Why it changed: " + recovery[0])
    if remaining:
        lines.append("What to focus on next: " + remaining[0].split(":", 1)[0] + ".")
    return lines
