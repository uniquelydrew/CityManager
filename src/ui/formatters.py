"""Player-facing formatting helpers for the PySide6 GUI."""

from __future__ import annotations

from typing import Any, Dict, List

from src.resource_utils import stock

PLAYER_RISK_LABELS = {
    "energy_instability": "Power generation risk",
    "budget_erosion": "Budget under strain",
    "food_collapse": "Food supply risk",
    "water_shortage": "Water delivery risk",
    "unrest_spike": "Workforce strain risk",
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
        "water": resource_status(stock(state["resources"], "water"), thresholds["water"]),
        "energy": resource_status(stock(state["resources"], "energy"), thresholds["energy"]),
        "food": resource_status(stock(state["resources"], "food"), thresholds["food"]),
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
        return "If fuel or power runs short, water pumps and town services may fail next turn."
    if issue_id == "water_shortage":
        return "If water delivery falls, food production and public health may also drop."
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
        return "Try buying emergency energy or fuel first to protect water service."
    if issue_id == "water_shortage":
        return "Try buying emergency water or materials so pumps and pipes can keep running."
    if issue_id == "food_collapse":
        return "Try buying emergency food and keeping water above the warning line."
    if issue_id == "budget_erosion":
        return "Spend carefully this turn and focus only on the most urgent shortage."
    if issue_id == "unrest_spike":
        return "Protect core services first so health and community stability can recover."
    return "Focus on the strongest warning first."


def system_links(forecast: Dict[str, Any]) -> List[str]:
    links = [
        "Fuel and workers affect power generation.",
        "Power and materials affect water delivery.",
        "Water, power, and workers affect food supply.",
        "Health and unrest affect workforce and town income.",
    ]
    top = top_risk(forecast)
    if top and top["issue_id"] == "budget_erosion":
        links.append("A weak budget can limit future energy recovery.")
    return links[:4]


def _resource_after_value(forecast: Dict[str, Any], key: str) -> float | None:
    resource_flow = forecast.get("resource_flow_projection", {}).get(key, {})
    if resource_flow:
        return resource_flow.get("projected_end", resource_flow.get("start"))
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
        start = forecast.get("resource_flow_projection", {}).get(key, {}).get("start")
        end = _resource_after_value(forecast, key)
        if start is None or end is None:
            continue
        status = resource_status(float(end), thresholds[key])
        lines.append(f"{key.title()}: {start:.1f} -> {end:.1f} | {status}")
    budget_start = forecast.get("resource_flow_projection", {}).get("budget", {}).get("start")
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


def resource_flow_lines(forecast: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for key in ["energy", "water", "food"]:
        flow = forecast.get("resource_flow_projection", {}).get(key, {})
        if not flow:
            continue
        lines.append(
            f"{key.title()}: start {flow.get('start', 0):.1f}, "
            f"+{flow.get('projected_production', 0):.1f} produced, "
            f"+{flow.get('projected_imports', 0):.1f} imported, "
            f"-{flow.get('projected_consumption', 0):.1f} used, "
            f"-{flow.get('projected_losses', 0):.1f} lost, "
            f"end {flow.get('projected_end', 0):.1f}"
        )
    return lines or ["No resource flow forecast is available."]


def supply_change_lines(forecast: Dict[str, Any]) -> List[str]:
    lines = list(forecast.get("constraint_preview", []))[:3]
    if not lines:
        lines = ["Supplies are not showing a major bottleneck right now."]
    return lines


def supporting_resource_lines(state: Dict[str, Any]) -> List[str]:
    resources = state["resources"]
    return [
        f"Fuel: {stock(resources, 'fuel'):.0f}",
        f"Materials: {stock(resources, 'materials'):.0f}",
        f"Workforce: {stock(resources, 'workforce_capacity'):.0f}",
    ]


def improvement_lines(forecast: Dict[str, Any]) -> List[str]:
    top = top_risk(forecast)
    if not top:
        return ["Balanced choices will help the town stay stable."]
    issue_id = top["issue_id"]
    if issue_id == "energy_instability":
        return [
            "Buying emergency energy or fuel can help keep power above the danger line.",
            "Protecting power also helps protect water service.",
        ]
    if issue_id == "water_shortage":
        return [
            "Protecting energy can reduce water loss from pump trouble.",
            "Materials can also help reduce leaks and keep water moving.",
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
        return "Short-term help: adds emergency fuel this turn."
    if policy_id == "food_relief_convoy":
        return "Short-term help: adds emergency food this turn."
    if policy_id == "fuel_contract":
        return "Long-term help: expands fuel access and lowers import cost."
    if policy_id == "maintenance_depot":
        return "Long-term help: reduces leakage and material loss."
    if policy_id == "workforce_training":
        return "Long-term help: improves workforce recovery."
    if policy_id == "cold_storage_upgrade":
        return "Long-term help: reduces food spoilage and improves storage."
    if policy_id == "pipe_replacement_program":
        return "Long-term help: improves water delivery capacity."
    if policy_id == "substation_upgrade":
        return "Long-term help: improves grid efficiency and pump support."
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
    allocation = actions.get("resource_purchases", actions.get("emergency_allocation", {}))
    selected_policy_id = actions.get("selected_policy_id")
    priority = actions.get("allocation_priority")
    chosen = []
    if allocation.get("energy", allocation.get("energy_amount", 0)) > 0:
        chosen.append("emergency energy")
    if allocation.get("water", allocation.get("water_amount", 0)) > 0:
        chosen.append("emergency water")
    if allocation.get("food", allocation.get("food_amount", 0)) > 0:
        chosen.append("emergency food")
    if allocation.get("fuel", 0) > 0:
        chosen.append("emergency fuel")
    if allocation.get("materials", 0) > 0:
        chosen.append("emergency materials")
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
    if priority:
        lines.append(f"Priority: You focused on {priority.replace('_', ' ')}.")
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
