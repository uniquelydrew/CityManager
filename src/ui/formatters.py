"""Player-facing formatting helpers for the PySide6 GUI."""

from __future__ import annotations

from typing import Any, Dict, List

from src.resource_utils import stock
from src.units import format_unit_value

PLAYER_RISK_LABELS = {
    "energy_instability": "Power may fail soon",
    "budget_erosion": "The budget is under pressure",
    "food_collapse": "Food stores are running low",
    "water_shortage": "Water delivery may break down",
    "unrest_spike": "Workforce strain is rising",
    "institutional_breakdown": "Key institutions may jam up",
    "political_stalemate": "Support for strong action is weakening",
    "public_trust_collapse": "Trust in the court is slipping",
}


def _resolved_view(forecast: Dict[str, Any] | None) -> Dict[str, Any]:
    if not forecast:
        return {}
    return forecast.get("resolved_view") or forecast.get("context", {}).get("resolved_view", {}) or {}


def _resolved_risk_view(forecast: Dict[str, Any] | None, issue_id: str) -> Dict[str, Any]:
    return _resolved_view(forecast).get("risks", {}).get(issue_id, {})


def risk_label(issue_id: str, forecast: Dict[str, Any] | None = None) -> str:
    resolved = _resolved_risk_view(forecast, issue_id)
    if resolved.get("display_label"):
        return resolved["display_label"]
    return PLAYER_RISK_LABELS.get(issue_id, issue_id.replace("_", " ").title())


def _resource_definition(context: Dict[str, Any], key: str) -> Dict[str, Any]:
    definitions = context.get("resource_definitions", {})
    if key == "energy":
        return definitions.get("electricity", {})
    if key == "workforce_capacity":
        return definitions.get("labor_hours", {})
    return definitions.get(key, {})


def _case_resource_definition(context: Dict[str, Any], key: str) -> Dict[str, Any]:
    case_resources = context.get("historical_case", {}).get("resources", [])
    resource_type_id = "electricity" if key == "energy" else "labor_hours" if key == "workforce_capacity" else key
    for entry in case_resources:
        if entry.get("resource_type_id") == resource_type_id:
            return entry
    return {}


def resource_label(context: Dict[str, Any], key: str) -> str:
    resolved_resources = context.get("resolved_view", {}).get("resources", {})
    runtime_key = "electricity" if key == "energy" else "labor_hours" if key == "workforce_capacity" else key
    if resolved_resources.get(runtime_key, {}).get("display_label"):
        return resolved_resources[runtime_key]["display_label"]
    case_definition = _case_resource_definition(context, key)
    if case_definition.get("display_name"):
        return case_definition["display_name"]
    definition = _resource_definition(context, key)
    return definition.get("player_label") or definition.get("display_name") or key.replace("_", " ").title()


def resource_value_text(value: float, context: Dict[str, Any], key: str) -> str:
    definition = _resource_definition(context, key)
    unit_id = definition.get("unit_id", "")
    units = context.get("units", {})
    if unit_id and units:
        return format_unit_value(float(value), unit_id, units)
    return f"{float(value):.1f}"


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
    return f"The most urgent problem is {risk_label(risk['issue_id'], forecast).lower()}."


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
    if issue_id == "institutional_breakdown":
        return "If institutions keep weakening, relief and repair efforts may stall."
    if issue_id == "political_stalemate":
        return "If coalition support breaks down, strong policies may become unavailable."
    if issue_id == "public_trust_collapse":
        return "If public trust falls further, backlash and instability may spread quickly."
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
    if issue_id == "institutional_breakdown":
        return "Strengthen transport, distribution, or repair capacity before more systems jam up."
    if issue_id == "political_stalemate":
        return "Choose a policy that can still hold coalition support, not just one that looks efficient."
    if issue_id == "public_trust_collapse":
        return "Protect visible services and frontline groups so public trust can recover."
    return "Focus on the strongest warning first."


def system_links(forecast: Dict[str, Any]) -> List[str]:
    links = [
        "Fuel and workers affect power generation.",
        "Power and materials affect water delivery.",
        "Water, power, and workers affect food supply.",
        "Health and unrest affect workforce and town income.",
        "Trust and coalition support affect which policies can survive politically.",
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
    context = forecast.get("context", {})
    lines: List[str] = []
    for key in ["energy", "water", "food"]:
        start = forecast.get("resource_flow_projection", {}).get(key, {}).get("start")
        end = _resource_after_value(forecast, key)
        if start is None or end is None:
            continue
        status = resource_status(float(end), thresholds[key])
        lines.append(
            f"{resource_label(context, key)}: {resource_value_text(start, context, key)} -> "
            f"{resource_value_text(end, context, key)} | {status}"
        )
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
    context = forecast.get("context", {})
    lines: List[str] = []
    for key in ["energy", "water", "food"]:
        flow = forecast.get("resource_flow_projection", {}).get(key, {})
        if not flow:
            continue
        label = resource_label(context, key)
        lines.append(
            f"{label}: start {resource_value_text(flow.get('start', 0), context, key)}, "
            f"+{resource_value_text(flow.get('projected_production', 0), context, key)} produced, "
            f"+{resource_value_text(flow.get('projected_imports', 0), context, key)} imported, "
            f"-{resource_value_text(flow.get('projected_consumption', 0), context, key)} used, "
            f"-{resource_value_text(flow.get('projected_losses', 0), context, key)} lost, "
            f"end {resource_value_text(flow.get('projected_end', 0), context, key)}"
        )
        allocations = flow.get("projected_flow", {}).get("allocated", {})
        if allocations:
            allocation_parts = ", ".join(f"{name} {value:.1f}" for name, value in allocations.items())
            lines.append(f"  Uses: {allocation_parts}")
        constraint = flow.get("primary_constraint")
        if constraint and constraint != "none":
            lines.append(f"  Bottleneck: {constraint}")
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
    if issue_id == "political_stalemate":
        return [
            "A policy that protects coalition support can unlock stronger actions next turn.",
            "Negotiated relief may matter as much as raw supply purchases.",
        ]
    if issue_id == "institutional_breakdown":
        return [
            "Repair and transport capacity can prevent multiple downstream failures.",
            "Strong institutions make every supply decision work better.",
        ]
    return [recommendation_sentence(forecast)]


def mission_text(forecast: Dict[str, Any]) -> str:
    resolved_header = _resolved_view(forecast).get("header", {})
    authored_goal = resolved_header.get("goal_text")
    if authored_goal:
        return authored_goal
    case_meta = forecast.get("context", {}).get("case_metadata", {})
    title = case_meta.get("title")
    if title:
        return f"Goal: stabilize {title} long enough to avoid cascading civic failure."
    return "Goal: keep the town stable for 2 safe turns."


def safety_text() -> str:
    return "A safe turn means no critical shortages and the budget stays healthy."


def current_problem_text(forecast: Dict[str, Any]) -> str:
    top = top_risk(forecast)
    if not top:
        return "Current urgent problem: none."
    return risk_label(top["issue_id"], forecast)


def player_role_text(forecast: Dict[str, Any]) -> str:
    resolved_header = _resolved_view(forecast).get("header", {})
    authored_role = resolved_header.get("player_role")
    if authored_role:
        return authored_role
    case_meta = forecast.get("context", {}).get("case_metadata", {})
    title = case_meta.get("title", "")
    if title:
        return "You are coordinating emergency city response."
    return "You are guiding the town through an emergency response."


def skill_tag_lines(forecast: Dict[str, Any]) -> List[str]:
    resolved_header = _resolved_view(forecast).get("header", {})
    if resolved_header.get("skill_tags"):
        return [skill.title() for skill in resolved_header["skill_tags"][:4]]
    signals = forecast.get("context", {}).get("historical_case", {}).get("teaching_signals", {})
    skills = signals.get("main_skills", [])
    if not skills:
        return ["Reading", "Civic reasoning", "Systems thinking"]
    return [skill.title() for skill in skills[:4]]


def goal_progress_text(state: Dict[str, Any], forecast: Dict[str, Any]) -> str:
    streak = int(state.get("telemetry", {}).get("stable_turn_streak", 0))
    needed = int(forecast.get("context", {}).get("constants", {}).get("stabilization_turns_required", 2))
    return f"Goal progress: {streak} of {needed} safe turns"


def case_title_text(forecast: Dict[str, Any]) -> str:
    resolved_header = _resolved_view(forecast).get("header", {})
    if resolved_header:
        parts = [resolved_header.get("title", "Town Recovery Simulation")]
        if resolved_header.get("place"):
            parts.append(resolved_header["place"])
        if resolved_header.get("timeframe"):
            parts.append(resolved_header["timeframe"])
        return " | ".join(parts)
    meta = forecast.get("context", {}).get("case_metadata", {})
    title = meta.get("title", "Town Recovery Simulation")
    place = meta.get("place", "")
    timeframe = meta.get("timeframe", "")
    parts = [title]
    if place:
        parts.append(place)
    if timeframe:
        parts.append(timeframe)
    return " | ".join(parts)


def immediate_crisis_lines(forecast: Dict[str, Any]) -> List[str]:
    top = top_risk(forecast)
    if not top:
        return [
            "Town conditions are currently stable.",
            "No immediate crisis is forecast for next turn.",
        ]
    severity_text = "Critical" if top["severity"] >= 0.75 else "Warning" if top["severity"] >= 0.4 else "Manageable"
    resolved_risk = _resolved_risk_view(forecast, top["issue_id"])
    return [
        f"{resolved_risk.get('display_label', title_case_label(top['issue_id']))} - {severity_text}",
        resolved_risk.get("summary") or consequence_sentence(forecast),
        f"If ignored: {resolved_risk.get('if_ignored') or consequence_sentence(forecast)}",
        f"Best first move: {resolved_risk.get('mitigation_hint') or recommendation_sentence(forecast)}",
        f"Why it matters: {top['reason']}",
    ]


def delta_summary_lines(result: Dict[str, Any] | None, forecast: Dict[str, Any]) -> List[str]:
    if not result:
        return [
            "You have not run a turn yet.",
            "Use this panel after each turn to see the biggest interpreted changes.",
        ]
    outcome = result.get("outcome", {})
    for key in ("dependency_effects", "recovery_effects", "economy_effects", "political_effects", "stakeholder_effects"):
        entries = outcome.get(key, [])
        if entries:
            lines = [entry.rstrip(".") + "." for entry in entries[:3]]
            return lines
    return [
        "No major change stood out last turn.",
        recommendation_sentence(forecast),
    ]


def has_turn_result(result: Dict[str, Any] | None) -> bool:
    return bool(result and result.get("outcome"))


def do_nothing_lines(forecast: Dict[str, Any]) -> List[str]:
    top = top_risk(forecast)
    if not top:
        return ["If you do nothing, the town should stay steady next turn."]
    lines = [consequence_sentence(forecast)]
    if top["issue_id"] == "energy_instability":
        lines.append("Water service may become unreliable soon after.")
    elif top["issue_id"] == "water_shortage":
        lines.append("Food supply and health may start to weaken.")
    elif top["issue_id"] == "budget_erosion":
        lines.append("Future emergency choices may become smaller and riskier.")
    elif top["issue_id"] == "political_stalemate":
        lines.append("Important policies may become politically unavailable.")
    return lines


def causal_chain_lines(forecast: Dict[str, Any]) -> List[str]:
    top = top_risk(forecast)
    if not top:
        return ["Core systems are holding together right now."]
    issue_id = top["issue_id"]
    if issue_id == "energy_instability":
        return [
            "Fuel deliveries are constrained or too weak.",
            "Power generation cannot safely cover demand.",
            "Water pumps and essential services are put at risk.",
        ]
    if issue_id == "water_shortage":
        return [
            "Pumps or pipes are under strain.",
            "Water delivery falls below a safe level.",
            "Food, health, and trust may weaken next.",
        ]
    if issue_id == "food_collapse":
        return [
            "Water or power weakness reduces food production.",
            "Food reserves shrink faster than they recover.",
            "Health and workforce strength may fall next.",
        ]
    if issue_id == "political_stalemate":
        return [
            "Support is splitting across key groups.",
            "Harder policies become more costly to pass.",
            "Delayed action can worsen the material crisis.",
        ]
    return system_links(forecast)


def active_policy_text(state: Dict[str, Any]) -> str:
    policies = state.get("modifiers", {}).get("active_policies", [])
    if not policies:
        return "No active town policies."
    return "Active policies: " + ", ".join(policy.replace("_", " ") for policy in policies)


def policy_title(policy_id: str) -> str:
    return policy_id.replace("_", " ").title()


def policy_summary(policy: Dict[str, Any]) -> str:
    policy_id = policy["policy_id"]
    if policy.get("historical_framing"):
        return policy["historical_framing"]
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
    meta = forecast.get("context", {}).get("case_metadata", {})
    return [
        case_title_text(forecast),
        mission_text(forecast),
        meta.get("summary", urgent_problem_sentence(forecast)),
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
    energy_ledger = state.get("telemetry", {}).get("turn_resource_ledger", {}).get("energy", {})
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
    if energy_ledger and (energy_ledger.get("produced", 0.0) > 0 or energy_ledger.get("imported", 0.0) > 0):
        lines.append(
            "Power flow: "
            f"{energy_ledger.get('produced', 0.0):.1f} produced, "
            f"{energy_ledger.get('imported', 0.0):.1f} imported, "
            f"{energy_ledger.get('consumed', 0.0):.1f} used, "
            f"{energy_ledger.get('end', 0.0):.1f} left."
        )
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
    reports = outcome.get("case_reports", [])
    if reports:
        lines.append("Historical note: " + reports[0])
    return lines


def build_startup_journal_entry(forecast: Dict[str, Any]) -> Dict[str, Any]:
    top = top_risk(forecast)
    return {
        "scenario_title": case_title_text(forecast),
        "turn": 0,
        "entry_type": "startup",
        "urgent_issue": risk_label(top["issue_id"]) if top else "No urgent issue",
        "actions_taken": [],
        "policy_selected": None,
        "priority_selected": None,
        "key_changes": [historical_situation_text(forecast)],
        "why_it_changed": causal_chain_lines(forecast)[:2],
        "remaining_risk": risk_label(top["issue_id"]) if top else "No major remaining risk",
        "historical_note": (forecast.get("case_reports") or [{}])[0].get("body") if forecast.get("case_reports") else "",
        "skill_tags": skill_tag_lines(forecast),
        "affected_groups": affected_group_lines(forecast)[:3],
    }


def journal_entry_lines(entry: Dict[str, Any]) -> List[str]:
    lines = [entry.get("scenario_title", "Scenario"), f"Turn {entry.get('turn', 0)}" if entry.get("turn") else "Before the first turn"]
    urgent = entry.get("urgent_issue")
    if urgent:
        lines.append(f"Urgent issue: {urgent}")
    actions = entry.get("actions_taken") or []
    if actions:
        lines.append("Actions taken: " + ", ".join(actions))
    policy = entry.get("policy_selected")
    if policy:
        lines.append(f"Policy: {policy}")
    priority = entry.get("priority_selected")
    if priority:
        lines.append(f"Priority: {priority}")
    key_changes = entry.get("key_changes") or []
    if key_changes:
        lines.append("Key change: " + key_changes[0])
    why = entry.get("why_it_changed") or []
    if why:
        lines.append("Why: " + why[0])
    remaining = entry.get("remaining_risk")
    if remaining:
        lines.append(f"Next thing to watch: {remaining}")
    note = entry.get("historical_note")
    if note:
        lines.append("Historical note: " + note)
    skills = entry.get("skill_tags") or []
    if skills:
        lines.append("GED skills: " + ", ".join(skills))
    return lines


def historical_situation_text(forecast: Dict[str, Any]) -> str:
    resolved_header = _resolved_view(forecast).get("header", {})
    return resolved_header.get("historical_situation") or forecast.get("context", {}).get("case_metadata", {}).get(
        "summary",
        urgent_problem_sentence(forecast),
    )


def case_background_lines(forecast: Dict[str, Any]) -> List[str]:
    resolved = _resolved_view(forecast)
    meta = resolved.get("header", {})
    notes = meta.get("reference_notes", [])
    lines = [
        case_title_text(forecast),
        "",
        historical_situation_text(forecast) or "No background summary is available.",
        "",
        player_role_text(forecast),
    ]
    if notes:
        lines.extend(["", "Historical notes:"])
        lines.extend(f"- {note}" for note in notes[:3])
    return lines


def affected_group_lines(forecast: Dict[str, Any]) -> List[str]:
    return list(forecast.get("affected_groups", [])) or ["No group-specific pressure is dominant right now."]


def political_constraint_lines(forecast: Dict[str, Any]) -> List[str]:
    return list(forecast.get("political_constraints", [])) or ["Political constraints are currently manageable."]


def system_pressure_lines(forecast: Dict[str, Any]) -> List[str]:
    case_reports = forecast.get("case_reports", [])
    lines = list(forecast.get("system_pressures", []))
    if case_reports:
        lines.extend(f"{report['title']}: {report['body']}" for report in case_reports[:2])
    return lines or ["No major historical pressure signal is active right now."]


def systems_reference_lines(forecast: Dict[str, Any], state: Dict[str, Any]) -> List[str]:
    thresholds = threshold_snapshot(forecast)
    resolved = _resolved_view(forecast)
    mechanism_lines = resolved.get("mechanism_lines", [])
    if mechanism_lines:
        lines = ["How this scenario works:"]
        lines.extend(f"- {line}" for line in mechanism_lines[:5])
        lines.extend(
            [
                "",
                "Current safe lines:",
                f"- Power is safer above {thresholds['energy']:.0f}.",
                f"- Water is safer above {thresholds['water']:.0f}.",
                f"- Food is safer above {thresholds['food']:.0f}.",
                f"- Budget is safer above ${thresholds['budget']:.0f}.",
            ]
        )
        return lines
    return [
        "How this scenario works:",
        "- Fuel and workers help produce power.",
        "- Power and materials help keep water moving.",
        "- Water, power, and workers help protect food supply.",
        "- Health and unrest shape workforce strength and town income.",
        "",
        "Current safe lines:",
        f"- Power is safer above {thresholds['energy']:.0f}.",
        f"- Water is safer above {thresholds['water']:.0f}.",
        f"- Food is safer above {thresholds['food']:.0f}.",
        f"- Budget is safer above ${thresholds['budget']:.0f}.",
        "",
        "Current system links:",
        *[f"- {line}" for line in causal_chain_lines(forecast)],
    ]


def skill_support_lines(forecast: Dict[str, Any]) -> List[str]:
    resolved_header = _resolved_view(forecast).get("header", {})
    guidance = resolved_header.get(
        "skill_guidance",
        "This scenario asks you to read the situation, weigh tradeoffs, and explain cause and effect.",
    )
    lines = [
        "GED skills in play:",
        *[f"- {skill.title()}" for skill in skill_tag_lines(forecast)],
        "",
        "Why this matters:",
        guidance,
    ]
    return lines


def glossary_entries(forecast: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolved_entries = _resolved_view(forecast).get("glossary_entries", [])
    if resolved_entries:
        return resolved_entries
    common = [
        {
            "term": "Blockade",
            "definition": "A blockade limits movement of goods and people into an area.",
            "why_it_matters": "This scenario starts with ground routes cut off, so the city depends on emergency delivery choices.",
            "related": ["Airlift", "Imports", "Rationing"],
        },
        {
            "term": "Rationing",
            "definition": "Rationing means limiting access so a scarce supply can stretch further.",
            "why_it_matters": "Some policies reduce demand now, but they can also frustrate households or workers.",
            "related": ["Budget", "Public trust"],
        },
        {
            "term": "Coalition support",
            "definition": "Coalition support is the backing a decision-maker has from important groups and institutions.",
            "why_it_matters": "Low coalition support can make strong policies harder to use.",
            "related": ["Political stalemate", "Opposition pressure"],
        },
        {
            "term": "Legitimacy",
            "definition": "Legitimacy is the public sense that leaders and institutions have the right to govern.",
            "why_it_matters": "When legitimacy falls, people are less likely to accept difficult emergency measures.",
            "related": ["Public trust", "Institutions"],
        },
        {
            "term": "kWh",
            "definition": "kWh stands for kilowatt-hour, a common measure of electric energy.",
            "why_it_matters": "The game uses simplified power units to show whether enough energy exists to keep services running.",
            "related": ["Power", "Pumps"],
        },
        {
            "term": "Infrastructure",
            "definition": "Infrastructure means the physical systems that help a city function, like pipes, pumps, roads, and power lines.",
            "why_it_matters": "When infrastructure is weak, supplies may leak, stall, or fail to reach people.",
            "related": ["Repair materials", "Transport throughput"],
        },
        {
            "term": "Public trust",
            "definition": "Public trust is how much people believe leaders and systems will act fairly and effectively.",
            "why_it_matters": "Low public trust can make every shortage feel worse and increase backlash.",
            "related": ["Legitimacy", "Community unrest"],
        },
        {
            "term": "Transport throughput",
            "definition": "Transport throughput is how much supply a transport system can move in a useful amount of time.",
            "why_it_matters": "Even if supplies exist, weak transport can stop them from reaching homes and services.",
            "related": ["Imports", "Repair backlog"],
        },
    ]
    top = top_risk(forecast)
    if top and top["issue_id"] == "energy_instability":
        common.append(
            {
                "term": "Power generation",
                "definition": "Power generation is the process of creating usable electricity from fuel, equipment, and labor.",
                "why_it_matters": "If generation stays too low, pumps and services can fail next turn.",
                "related": ["Fuel", "Water pumps"],
            }
        )
    return common


def advanced_model_lines(forecast: Dict[str, Any], state: Dict[str, Any], result: Dict[str, Any] | None) -> List[str]:
    lines = ["Advanced model details:", ""]
    for key in ("energy", "water", "food"):
        flow = forecast.get("resource_flow_projection", {}).get(key, {})
        if not flow:
            continue
        lines.append(
            f"{key}: start={flow.get('start', 0):.2f}, produced={flow.get('projected_production', 0):.2f}, "
            f"imported={flow.get('projected_imports', 0):.2f}, consumed={flow.get('projected_consumption', 0):.2f}, "
            f"lost={flow.get('projected_losses', 0):.2f}, end={flow.get('projected_end', 0):.2f}"
        )
        if flow.get("primary_constraint"):
            lines.append(f"  constraint: {flow['primary_constraint']}")
    risks = forecast.get("risk_ranking", [])[:3]
    if risks:
        lines.append("")
        lines.append("Top risk scores:")
        lines.extend(f"- {risk['issue_id']}: {risk['severity']:.2f}" for risk in risks)
    if result:
        outcome = result.get("outcome", {})
        constraints = outcome.get("constraint_preview", [])
        if constraints:
            lines.append("")
            lines.append("Constraint log:")
            lines.extend(f"- {entry}" for entry in constraints[:5])
    return lines
