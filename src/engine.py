"""Logistics-first deterministic simulation for the town recovery scenario."""

from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Dict, List, Tuple

if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.challenges import (
    math_prompt,
    required_generation,
    science_prompt,
    social_prompt,
    validate_allocation,
    validate_rla_answers,
    validate_science_generation,
)
from src.case_loader import load_cases
from src.economy import compute_effective_income, update_budget
from src.explanation import empty_outcome, record
from src.food import effective_irrigation_threshold
from src.forecast import build_forecast as build_forecast_payload
from src.modifiers import (
    activate_policy,
    aggregate_modifier_context,
    can_select_policy,
    decrement_temporary_effects,
    ensure_modifier_containers,
    policy_map,
)
from src.population import apply_unrest, clamp, recover_health
from src.reports import generate_report_text, issue_label
from src.interaction_registry import InteractionRegistry
from src.resource_registry import ResourceRegistry
from src.resource_utils import (
    add_stock,
    allocate,
    build_turn_ledger,
    end_of_turn_ledger,
    ensure_resource_records,
    record_import,
    record_loss,
    record_production,
    reset_turn_metrics,
    resource_record,
    set_stock,
    stock,
)
from src.risk import compute_risk_ranking
from src.units import load_units
from src.verbs import run_allocate, run_consume, run_decay, run_produce, run_repair, run_transform


State = Dict[str, Any]
Actions = Dict[str, Any]
OutcomeReport = Dict[str, Any]


class SimulationEngine:
    """Orchestrates the playable logistics loop for the town recovery scenario."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.scenario = self._load_json("town_recovery_v2.json")
        self.dependency_rules = self._load_json("dependency_rules.json")
        self.base_policies_data = self._load_json("policies.json")
        self.cases = load_cases(data_dir)
        self.active_case = self.cases[self.scenario["active_case_id"]]
        self.policies_data = {
            "policies": list(self.active_case.get("policy_options", []))
            + list(self.base_policies_data.get("policies", []))
        }
        self.resource_registry = ResourceRegistry.load(data_dir)
        self.interaction_registry = InteractionRegistry.load(data_dir)
        self.units = load_units(data_dir)
        self.policy_map = policy_map(self.policies_data)
        self.turns = int(self.scenario.get("turns", 4))
        self.resource_defaults = self._resource_defaults()
        self.state = self._normalize_state(self._load_json("state.json"))
        self.skills_used: Dict[str, bool] = {
            "math": False,
            "science": False,
            "rla": False,
            "social": False,
        }

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.data_dir, filename)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _get_path_value(self, state: Dict[str, Any], path: str, default: float = 0.0) -> Any:
        current: Any = state
        for part in path.split("."):
            if not isinstance(current, dict):
                return default
            current = current.get(part, default)
        return current

    def _set_path_delta(self, state: Dict[str, Any], path: str, delta: float) -> None:
        head, *rest = path.split(".")
        current = state.setdefault(head, {})
        for part in rest[:-1]:
            current = current.setdefault(part, {})
        leaf = rest[-1]
        current[leaf] = float(current.get(leaf, 0.0) + delta)

    def _clamp_indicator(self, section: str, key: str, state: Dict[str, Any]) -> None:
        if section not in state or key not in state[section]:
            return
        state[section][key] = max(0.0, min(1.0, float(state[section][key])))

    def _active_case_policy_ids(self) -> List[str]:
        return [policy["policy_id"] for policy in self.active_case.get("policy_options", [])]

    def _resource_defaults(self) -> Dict[str, Dict[str, float]]:
        limits = self.scenario.get("resource_limits", {})
        base = self.scenario.get("base_production", {})
        initial = self.scenario.get("initial_resources", {})
        defaults: Dict[str, Dict[str, Any]] = {}
        active_ids = set(self.scenario.get("resource_type_ids", []))
        active_ids.update(item["resource_type_id"] for item in self.active_case.get("resources", []))
        legacy_initial = {
            "electricity": initial.get("electricity", initial.get("energy", 40.0)),
            "labor_hours": initial.get("labor_hours", initial.get("workforce_capacity", 75.0)),
        }
        for definition in self.resource_registry.all():
            resource_type_id = definition["resource_type_id"]
            if resource_type_id not in active_ids:
                continue
            runtime_key = self.resource_registry.runtime_key(resource_type_id)
            storage = definition["storage"]
            defaults[runtime_key] = resource_record(
                initial.get(resource_type_id, legacy_initial.get(resource_type_id, definition["defaults"]["base_quantity"])),
                limits.get(storage["capacity_key"], storage["default_capacity"]),
                base.get(resource_type_id, base.get(runtime_key, definition["defaults"]["base_production"])),
                resource_type_id=resource_type_id,
                unit_id=definition["unit_id"],
                category=definition.get("category", ""),
                tags=definition.get("tags", []),
            )
        return defaults

    def _default_state(self) -> Dict[str, Any]:
        case_world = self.active_case.get("world_state", {})
        return {
            "resources": copy.deepcopy(self.resource_defaults),
            "population": {"count": 1000, "health": 0.7, "happiness": 0.6, "unrest": 0.1},
            "economy": {
                "budget": 10000.0,
                "income": 500.0,
                "base_income": 500.0,
                "expenses": 700.0,
                "tax_base": 1.0,
                "service_penalty": 0.0,
            },
            "infrastructure": {
                "water_capacity": 1.0,
                "grid_efficiency": 1.0,
                "food_yield": 1.0,
            },
            "governance": copy.deepcopy(case_world.get("governance", {
                "legitimacy": 0.6,
                "administrative_capacity": 0.6,
                "corruption_friction": 0.2,
                "enforcement_reach": 0.5,
            })),
            "politics": copy.deepcopy(case_world.get("politics", {
                "coalition_stability": 0.6,
                "opposition_pressure": 0.4,
                "elite_resistance": 0.3,
                "faction_support": {},
            })),
            "society": copy.deepcopy(case_world.get("society", {
                "public_trust": 0.6,
                "class_sector_strain": 0.4,
                "displacement": 0.2,
                "labor_unrest": 0.25,
                "mortality_burden": 0.15,
            })),
            "economic_conditions": copy.deepcopy(case_world.get("economic_conditions", {
                "price_pressure": 0.4,
                "wage_pressure": 0.4,
                "revenue_stability": 0.5,
                "debt_pressure": 0.4,
                "trade_dependence": 0.5,
                "import_dependence": 0.5,
            })),
            "services": copy.deepcopy(case_world.get("services", {
                "transport_throughput": 0.5,
                "distribution_capacity": 0.5,
                "repair_backlog": 0.4,
                "hospital_pressure": 0.35,
                "institutional_bottlenecks": 0.45,
            })),
            "modifiers": {
                "active_policies": [],
                "temporary_effects": [],
                "persistent_effects": [],
            },
            "telemetry": {
                "turn": 1,
                "stable_turn_streak": 0,
                "last_risk_ranking": [],
                "last_risk_values": {},
                "last_outcome_chain": [],
                "turn_resource_ledger": {},
                "resource_flow_history": [],
                "turn_constraint_log": [],
                "turn_allocation_snapshot": {},
                "last_case_reports": [],
            },
            "active_case_id": self.active_case["historical_case_id"],
        }

    def _deep_merge(self, default: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = copy.deepcopy(default)
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _normalize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._deep_merge(self._default_state(), state)
        normalized["resources"] = ensure_resource_records(normalized["resources"], self.resource_defaults)
        ensure_modifier_containers(normalized)
        if "base_income" not in normalized["economy"]:
            normalized["economy"]["base_income"] = normalized["economy"]["income"]
        normalized["telemetry"].setdefault("turn_resource_ledger", {})
        normalized["telemetry"].setdefault("resource_flow_history", [])
        normalized["telemetry"].setdefault("turn_constraint_log", [])
        normalized["telemetry"].setdefault("turn_allocation_snapshot", {})
        normalized["telemetry"].setdefault("last_case_reports", [])
        normalized.setdefault("active_case_id", self.active_case["historical_case_id"])
        return normalized

    def clone_state(self, state: State) -> State:
        return copy.deepcopy(self._normalize_state(state))

    def _priority_profiles(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        return {
            "balance_services": {
                "workforce": {"energy": 0.35, "water": 0.35, "food": 0.30},
                "energy": {"pumps": 0.40, "food": 0.30, "civic": 0.30},
                "materials": {"water": 0.45, "energy": 0.30, "food": 0.25},
            },
            "keep_water_running": {
                "workforce": {"energy": 0.25, "water": 0.50, "food": 0.25},
                "energy": {"pumps": 0.55, "food": 0.20, "civic": 0.25},
                "materials": {"water": 0.60, "energy": 0.20, "food": 0.20},
            },
            "protect_food_supply": {
                "workforce": {"energy": 0.20, "water": 0.30, "food": 0.50},
                "energy": {"pumps": 0.30, "food": 0.45, "civic": 0.25},
                "materials": {"water": 0.30, "energy": 0.20, "food": 0.50},
            },
            "stabilize_power": {
                "workforce": {"energy": 0.50, "water": 0.25, "food": 0.25},
                "energy": {"pumps": 0.35, "food": 0.20, "civic": 0.45},
                "materials": {"water": 0.25, "energy": 0.55, "food": 0.20},
            },
        }

    def build_context(self, state: State) -> Dict[str, Any]:
        constants = self.scenario["constants"]
        modifier_context = aggregate_modifier_context(state)
        grid_efficiency = state["infrastructure"]["grid_efficiency"] + modifier_context["grid_efficiency_bonus"]
        water_capacity = max(0.2, state["infrastructure"]["water_capacity"] + modifier_context["water_capacity_bonus"])
        food_yield = state["infrastructure"]["food_yield"] + modifier_context["food_yield_bonus"]
        workforce_record = state["resources"]["workforce_capacity"]
        workforce_base = float(workforce_record.get("baseline_quantity", stock(state["resources"], "workforce_capacity")))
        workforce_available = max(
            0.0,
            min(
                workforce_record["capacity"],
                workforce_base * state["population"]["health"] * max(0.2, 1.0 - state["population"]["unrest"])
                + modifier_context["workforce_recovery_bonus"] * 10.0,
            ),
        )
        effective_demand = max(
            0.0,
            constants["energy_demand"] * (1.0 + modifier_context["energy_demand_multiplier"] - max(0.0, grid_efficiency - 1.0)),
        )
        irrigation_threshold = effective_irrigation_threshold(
            constants["irrigation_threshold"],
            modifier_context["irrigation_threshold_multiplier"],
        )
        return {
            "constants": constants,
            "modifier_context": modifier_context,
            "grid_efficiency": grid_efficiency,
            "water_capacity_multiplier": water_capacity,
            "food_yield": food_yield,
            "effective_energy_demand": effective_demand,
            "pump_threshold": constants["water_pump_threshold"] * water_capacity,
            "irrigation_threshold": irrigation_threshold,
            "workforce_available": workforce_available,
            "resource_limits": self.scenario["resource_limits"],
            "base_production": self.scenario["base_production"],
            "conversion_rates": self.scenario["conversion_rates"],
            "allocation_profiles": self._priority_profiles(),
            "unit_costs": self.scenario["unit_costs"],
            "available_emergency_budget": self.scenario["available_emergency_budget"],
            "resource_definitions": {item["resource_type_id"]: item for item in self.resource_registry.all()},
            "interactions": self.interaction_registry.all(),
            "units": self.units,
            "historical_case": self.active_case,
            "case_metadata": self.active_case.get("case_metadata", {}),
            "actors": self.active_case.get("actors", []),
            "institutions": self.active_case.get("institutions", []),
            "groups": self.active_case.get("groups", []),
            "policy_domains": self.active_case.get("policy_domains", []),
            "indicator_definitions": self.active_case.get("indicators", []),
            "report_definitions": self.active_case.get("events_and_reports", []),
            "historical_notes": self.active_case.get("historical_notes", {}),
        }

    def observe_state(self) -> None:
        res = self.state["resources"]
        pop = self.state["population"]
        econ = self.state["economy"]
        streak = self.state["telemetry"].get("stable_turn_streak", 0)
        print("\n=== Current State ===")
        print(
            "Resources: "
            f"water={stock(res, 'water'):.1f} energy={stock(res, 'energy'):.1f} food={stock(res, 'food'):.1f} "
            f"fuel={stock(res, 'fuel'):.1f} materials={stock(res, 'materials'):.1f} workforce={stock(res, 'workforce_capacity'):.1f}"
        )
        print(
            f"Population: count={int(pop['count'])}, health={pop['health']:.2f}, "
            f"happiness={pop['happiness']:.2f}, unrest={pop['unrest']:.2f}"
        )
        print(
            f"Economy: budget=${econ['budget']:.2f}, income=${econ['income']:.2f}, "
            f"base_income=${econ['base_income']:.2f}, expenses=${econ['expenses']:.2f}, "
            f"service_penalty=${econ['service_penalty']:.2f}"
        )
        active = ", ".join(self.state["modifiers"]["active_policies"]) or "none"
        print(f"Active policies: {active}")
        print(f"Stable turn streak: {streak}")

    def build_forecast(self, state: State) -> Dict[str, Any]:
        context = self.build_context(state)
        forecast = build_forecast_payload(state, self.simulate_turn, context)
        generic_report = generate_report_text(forecast["risk_ranking"])
        forecast["historical_case"] = self.active_case
        forecast["historical_situation"] = self.active_case["case_metadata"]["summary"]
        forecast["affected_groups"] = self._affected_group_lines(forecast["projected_state"])
        forecast["political_constraints"] = self._political_constraint_lines(forecast["projected_state"])
        forecast["system_pressures"] = self._case_pressure_lines(forecast["projected_state"])
        forecast["case_reports"] = list(forecast["projected_state"]["telemetry"].get("last_case_reports", []))
        if forecast["case_reports"]:
            report_intro = " ".join(report["body"] for report in forecast["case_reports"][:2])
            forecast["report_text"] = f"{generic_report} {report_intro}".strip()
        else:
            forecast["report_text"] = generic_report
        return forecast

    def display_forecast(self, forecast: Dict[str, Any]) -> None:
        print("\n=== Forecast Resource Flow ===")
        for resource, values in forecast["resource_flow_projection"].items():
            print(f"- {resource}: {values}")
        print("\n=== Forecast Constraints ===")
        for line in forecast.get("constraint_preview", []):
            print(f"- {line}")
        print("\n=== Forecast Risk Ranking ===")
        for risk in forecast["risk_ranking"][:3]:
            print(
                f"- {issue_label(risk['issue_id'])}: severity {risk['severity']:.2f} because {risk['reason']}"
            )

    def prompt_choice(self, prompt: str, valid_choices: List[str]) -> str:
        while True:
            answer = input(prompt).strip().upper()
            if answer in valid_choices:
                return answer
            print(f"Please enter one of: {', '.join(valid_choices)}")

    def prompt_float(self, prompt: str) -> float:
        while True:
            raw = input(prompt).strip()
            try:
                return float(raw)
            except ValueError:
                print("Please enter a numeric value.")

    def risk_id_from_option(self, option: str) -> str:
        mapping = {
            "A": "water_shortage",
            "B": "energy_instability",
            "C": "food_collapse",
            "D": "budget_erosion",
            "E": "unrest_spike",
        }
        return mapping[option]

    def rla_challenge(self, forecast: Dict[str, Any]) -> Dict[str, str]:
        print("\nRLA Challenge:")
        print(forecast["report_text"])
        print("Identify the primary and secondary issues in order.")
        print("A) Water shortage")
        print("B) Energy instability")
        print("C) Food collapse")
        print("D) Budget erosion")
        print("E) Unrest spike")
        primary = self.prompt_choice("Primary issue: ", ["A", "B", "C", "D", "E"])
        secondary = self.prompt_choice("Secondary issue: ", ["A", "B", "C", "D", "E"])
        answers = {
            "primary_issue": self.risk_id_from_option(primary),
            "secondary_issue": self.risk_id_from_option(secondary),
        }
        if validate_rla_answers(answers["primary_issue"], answers["secondary_issue"], forecast["risk_ranking"]):
            self.skills_used["rla"] = True
            print("Correct. You identified the top two signals in the report.")
        else:
            print("Not quite. The report mixes multiple signals, and the order matters.")
        return answers

    def math_challenge(self, forecast: Dict[str, Any]) -> Dict[str, Any]:
        print("\nMath Challenge:")
        print(math_prompt(self.scenario, forecast["risk_ranking"]))
        purchases = {
            "energy": self.prompt_float("Emergency energy to buy: "),
            "water": self.prompt_float("Emergency water to buy: "),
            "food": self.prompt_float("Emergency food to buy: "),
            "fuel": self.prompt_float("Emergency fuel to buy: "),
            "materials": self.prompt_float("Emergency materials to buy: "),
        }
        valid, total_cost = validate_allocation(purchases, self.scenario, forecast["risk_ranking"])
        if valid:
            self.skills_used["math"] = True
            print(f"Valid allocation. Total emergency cost is ${total_cost:.2f}.")
        else:
            print(f"Invalid allocation. Total emergency cost is ${total_cost:.2f}.")
        return {"resource_purchases": purchases, "total_cost": total_cost}

    def science_challenge(self, forecast: Dict[str, Any]) -> float:
        context = forecast["context"]
        current_energy = stock(self.state["resources"], "energy")
        required_amount = required_generation(
            current_energy,
            context["effective_energy_demand"],
            context["pump_threshold"],
            context["constants"]["science_safety_margin"],
        )
        print("\nScience Challenge:")
        print(science_prompt(self.state, context, required_amount))
        answer = self.prompt_float("Additional generation needed: ")
        if validate_science_generation(answer, required_amount):
            self.skills_used["science"] = True
            print("Correct. That generation target protects the post-demand reserve.")
        else:
            print(f"Insufficient. You needed at least {required_amount:.1f}.")
        return answer

    def social_challenge(self, forecast: Dict[str, Any], spent: float) -> Tuple[str | None, str]:
        print("\nSocial Studies Challenge:")
        available = list(self.policies_data["policies"])
        for line in social_prompt(available, self.state["economy"]["budget"] - spent):
            print(line)
        valid_policy_labels = [policy["label"] for policy in available]
        choice = self.prompt_choice(
            f"Choose a policy ({'/'.join(valid_policy_labels)}): ",
            valid_policy_labels,
        )
        preset = self.prompt_choice(
            "Choose an allocation priority: A) Keep Water Running B) Protect Food Supply C) Stabilize Power D) Balance Services ",
            ["A", "B", "C", "D"],
        )
        priority_map = {
            "A": "keep_water_running",
            "B": "protect_food_supply",
            "C": "stabilize_power",
            "D": "balance_services",
        }
        policy = next(policy for policy in available if policy["label"] == choice)
        can_use, reason = can_select_policy(self.state, policy)
        if can_use:
            self.skills_used["social"] = True
            print("Good policy choice.")
            return policy["policy_id"], priority_map[preset]
        print(reason or "That choice is unavailable.")
        return None, priority_map[preset]

    def collect_player_actions(self, forecast: Dict[str, Any]) -> Actions:
        parsed_report_issue = self.rla_challenge(forecast)
        purchase_bundle = self.math_challenge(forecast)
        science_generation_answer = self.science_challenge(forecast)
        selected_policy_id, allocation_priority = self.social_challenge(forecast, purchase_bundle["total_cost"])
        return {
            "resource_purchases": purchase_bundle["resource_purchases"],
            "allocation_priority": allocation_priority,
            "selected_policy_id": selected_policy_id,
            "risk_assessment": {
                "primary_risk": parsed_report_issue["primary_issue"],
                "secondary_risk": parsed_report_issue["secondary_issue"],
            },
            "parsed_report_issue": parsed_report_issue,
            "science_generation_answer": science_generation_answer,
            "emergency_total_cost": purchase_bundle["total_cost"],
        }

    def format_explanation_text(self, outcome_report: OutcomeReport) -> str:
        sections = [
            "direct_effects",
            "dependency_effects",
            "modifier_effects",
            "recovery_effects",
            "population_effects",
            "economy_effects",
            "political_effects",
            "stakeholder_effects",
            "institution_effects",
            "case_reports",
            "risk_changes",
            "remaining_risks",
        ]
        lines: List[str] = []
        for heading in sections:
            lines.append(f"{heading.replace('_', ' ').title()}:")
            entries = outcome_report.get(heading, [])
            if entries:
                lines.extend(f"- {entry}" for entry in entries)
            else:
                lines.append("- none")
        return "\n".join(lines)

    def _resource_purchases_from_gui(self, actions: Dict[str, float]) -> Dict[str, float]:
        return {
            "energy": float(actions.get("energy", 0.0)),
            "water": float(actions.get("water", 0.0)),
            "food": float(actions.get("food", 0.0)),
            "fuel": float(actions.get("fuel", 0.0)),
            "materials": float(actions.get("materials", 0.0)),
        }

    def step(self, actions: Dict[str, float]) -> Dict[str, Any]:
        forecast = self.build_forecast(self.state)
        context = forecast["context"]
        top_primary = forecast["risk_ranking"][0]["issue_id"]
        top_secondary = forecast["risk_ranking"][1]["issue_id"] if len(forecast["risk_ranking"]) > 1 else top_primary
        resource_purchases = self._resource_purchases_from_gui(actions)
        _, total_cost = validate_allocation(resource_purchases, self.scenario, forecast["risk_ranking"])
        full_actions = {
            "resource_purchases": resource_purchases,
            "allocation_priority": actions.get("allocation_priority", "balance_services"),
            "selected_policy_id": actions.get("policy_id"),
            "risk_assessment": {"primary_risk": top_primary, "secondary_risk": top_secondary},
            "parsed_report_issue": {"primary_issue": top_primary, "secondary_issue": top_secondary},
            "science_generation_answer": required_generation(
                stock(self.state["resources"], "energy"),
                context["effective_energy_demand"],
                context["pump_threshold"],
                context["constants"]["science_safety_margin"],
            ),
            "emergency_total_cost": total_cost,
        }
        self.state, outcome = self.simulate_turn(self.state, full_actions)
        self.last_forecast = self.build_forecast(self.state)
        self.last_outcome = outcome
        top_risks = self.last_forecast["risk_ranking"][:3]
        return {
            "state": self.state,
            "forecast": self.last_forecast,
            "outcome": outcome,
            "actions": full_actions,
            "top_risks": top_risks,
            "top_risk": top_risks[0] if top_risks else None,
            "turn": self.state["telemetry"].get("turn", 1),
            "stable_turn_streak": self.state["telemetry"].get("stable_turn_streak", 0),
            "explanation": self.format_explanation_text(outcome),
        }

    def _risk_change_lines(self, previous: Dict[str, float], current: List[Dict[str, Any]]) -> List[str]:
        lines: List[str] = []
        for risk in current[:3]:
            prior = previous.get(risk["issue_id"])
            if prior is None:
                lines.append(f"{issue_label(risk['issue_id'])} is now {risk['severity']:.2f}.")
                continue
            delta = risk["severity"] - prior
            if abs(delta) < 1e-9:
                direction = "held steady"
            elif delta < 0:
                direction = f"fell from {prior:.2f} to {risk['severity']:.2f}"
            else:
                direction = f"rose from {prior:.2f} to {risk['severity']:.2f}"
            lines.append(f"{issue_label(risk['issue_id'])} {direction}.")
        return lines

    def _evaluate_report_trigger(
        self,
        trigger: Dict[str, Any],
        state: Dict[str, Any],
        risk_ranking: List[Dict[str, Any]],
        selected_policy_id: str | None,
    ) -> bool:
        trigger_type = trigger.get("type", "always")
        if trigger_type == "always":
            return True
        if trigger_type == "indicator_below":
            return float(self._get_path_value(state, trigger["path"], 1.0)) <= float(trigger["value"])
        if trigger_type == "indicator_above":
            return float(self._get_path_value(state, trigger["path"], 0.0)) >= float(trigger["value"])
        if trigger_type == "policy_selected":
            return selected_policy_id == trigger.get("policy_id")
        if trigger_type == "risk_top":
            return bool(risk_ranking) and risk_ranking[0]["issue_id"] == trigger.get("issue_id")
        return False

    def _trigger_case_reports(
        self,
        state: Dict[str, Any],
        risk_ranking: List[Dict[str, Any]],
        selected_policy_id: str | None,
    ) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []
        for report in self.active_case.get("events_and_reports", []):
            if self._evaluate_report_trigger(report.get("trigger", {}), state, risk_ranking, selected_policy_id):
                reports.append(report)
        return reports

    def _case_pressure_lines(self, state: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        if state["services"]["transport_throughput"] < 0.5:
            lines.append("Transport throughput is too weak to reliably move relief and repairs.")
        if state["society"]["public_trust"] < 0.5:
            lines.append("Public trust is slipping, so even useful policies may trigger backlash.")
        if state["politics"]["coalition_stability"] < 0.5:
            lines.append("Coalition support is fragile, limiting which policies can survive politically.")
        if state["services"]["hospital_pressure"] > 0.5:
            lines.append("Hospitals are under visible pressure and may need priority support.")
        return lines or ["The case's civic pressures are tense but still manageable."]

    def _affected_group_lines(self, state: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        for group in self.active_case.get("groups", [])[:3]:
            pressure = group.get("main_pressure", "service instability")
            lines.append(f"{group['display_name']} are facing {pressure}.")
        return lines

    def _political_constraint_lines(self, state: Dict[str, Any]) -> List[str]:
        politics = state["politics"]
        lines: List[str] = []
        if politics["opposition_pressure"] > 0.5:
            lines.append("Opposition pressure is high, so disruptive policies will be politically costly.")
        if politics["elite_resistance"] > 0.5:
            lines.append("Elite resistance is high, which can slow fiscal or industrial measures.")
        faction_support = politics.get("faction_support", {})
        weakest = sorted(faction_support.items(), key=lambda item: item[1])[:2]
        for actor_id, support in weakest:
            actor = next((a for a in self.active_case.get("actors", []) if a["actor_id"] == actor_id), None)
            if actor:
                lines.append(f"{actor['display_name']} support is only {support:.2f}.")
        return lines or ["No acute political constraint is dominating the turn."]

    def _apply_case_indicator_effects(self, state: Dict[str, Any], indicator_effects: Dict[str, float], outcome: OutcomeReport) -> None:
        for path, delta in indicator_effects.items():
            self._set_path_delta(state, path, delta)
            section, key = path.split(".", 1)
            if "." not in key:
                self._clamp_indicator(section, key, state)
            if section in {"governance", "politics", "society", "economic_conditions", "services"}:
                label = key.replace("_", " ")
                bucket = "political_effects" if section in {"governance", "politics"} else "institution_effects"
                record(outcome, bucket, f"{label.title()} changed by {delta:+.2f}.")

    def _apply_actor_effects(self, state: Dict[str, Any], actor_effects: Dict[str, float], outcome: OutcomeReport) -> None:
        supports = state["politics"].setdefault("faction_support", {})
        for actor_id, delta in actor_effects.items():
            supports[actor_id] = max(0.0, min(1.0, float(supports.get(actor_id, 0.5) + delta)))
            actor = next((item for item in self.active_case.get("actors", []) if item["actor_id"] == actor_id), None)
            name = actor["display_name"] if actor else actor_id.replace("_", " ")
            record(outcome, "stakeholder_effects", f"{name} support changed by {delta:+.2f}.")

    def _apply_case_dynamics(
        self,
        state: Dict[str, Any],
        outcome: OutcomeReport,
        resource_gaps: Dict[str, float],
        selected_policy_id: str | None,
    ) -> None:
        society = state["society"]
        governance = state["governance"]
        politics = state["politics"]
        services = state["services"]
        economic_conditions = state["economic_conditions"]

        if resource_gaps["energy"] > 0:
            governance["legitimacy"] -= 0.04
            services["transport_throughput"] -= 0.03
            politics["opposition_pressure"] += 0.05
            record(outcome, "political_effects", "Power shortfalls weakened legitimacy and raised opposition pressure.")
        if resource_gaps["water"] > 0 or resource_gaps["food"] > 0:
            society["public_trust"] -= 0.05
            society["class_sector_strain"] += 0.05
            services["hospital_pressure"] += 0.04
            record(outcome, "stakeholder_effects", "Households and frontline institutions felt rising strain from shortages.")
        if state["economy"]["budget"] < self.scenario["constants"]["safe_budget_threshold"]:
            politics["coalition_stability"] -= 0.04
            economic_conditions["debt_pressure"] += 0.04
            services["institutional_bottlenecks"] += 0.03
            record(outcome, "political_effects", "Budget strain reduced coalition stability and increased debt pressure.")
        if society["labor_unrest"] > 0.4:
            politics["opposition_pressure"] += 0.03
            services["distribution_capacity"] -= 0.02
            record(outcome, "institution_effects", "Labor unrest slowed distribution and increased political friction.")
        if selected_policy_id:
            policy = self.policy_map[selected_policy_id]
            self._apply_actor_effects(state, policy.get("actor_effects", {}), outcome)
            self._apply_case_indicator_effects(state, policy.get("indicator_effects", {}), outcome)

        for section in ("governance", "politics", "society", "economic_conditions", "services"):
            for key in state[section]:
                if isinstance(state[section][key], (int, float)):
                    state[section][key] = max(0.0, min(1.0, float(state[section][key])))

    def _apply_policy(
        self,
        state: State,
        selected_policy_id: str | None,
        outcome: OutcomeReport,
        direct_adjustment: float,
        forecast_mode: bool,
    ) -> float:
        if not selected_policy_id:
            return direct_adjustment
        policy = self.policy_map[selected_policy_id]
        can_use, reason = can_select_policy(state, policy)
        if not can_use:
            if not forecast_mode:
                record(outcome, "modifier_effects", reason)
            return direct_adjustment
        activate_policy(state, policy)
        direct_adjustment -= float(policy.get("cost", 0.0))
        for path, delta in policy.get("instant_effects", {}).items():
            if path.startswith("resources."):
                key = path.split(".", 1)[1]
                record_import(state["resources"], key, float(delta))
            else:
                self._set_path_delta(state, path, float(delta))
        framing = policy.get("historical_framing")
        if framing:
            record(outcome, "modifier_effects", framing)
        record(outcome, "modifier_effects", f"Selected policy {selected_policy_id} for ${policy['cost']:.2f}.")
        return direct_adjustment

    def _apply_imports(self, resources: Dict[str, Any], purchases: Dict[str, float], outcome: OutcomeReport) -> None:
        added_parts: List[str] = []
        for name, amount in purchases.items():
            if amount > 0:
                record_import(resources, name, float(amount))
                added_parts.append(f"+{amount:.1f} {name}")
        if added_parts:
            record(outcome, "direct_effects", "Emergency imports added " + ", ".join(added_parts) + ".")
        else:
            record(outcome, "direct_effects", "No emergency resource imports were purchased this turn.")

    def _apply_start_snapshot(self, resources: Dict[str, Any], outcome: OutcomeReport) -> None:
        for name, record_data in resources.items():
            record_data["start"] = record_data["stock"]
            outcome["resource_flow_projection"][name] = {"start": record_data["stock"]}

    def _allocate_by_priority(
        self,
        resources: Dict[str, Any],
        context: Dict[str, Any],
        priority: str,
        outcome: OutcomeReport,
    ) -> Dict[str, Any]:
        profile = context["allocation_profiles"].get(priority, context["allocation_profiles"]["balance_services"])
        allocation_snapshot: Dict[str, Any] = {"priority": priority}

        workforce_available = context["workforce_available"]
        set_stock(resources, "workforce_capacity", workforce_available)
        resources["workforce_capacity"]["start"] = workforce_available
        for target, share in profile["workforce"].items():
            amount = workforce_available * share
            allocated = allocate(resources, "workforce_capacity", target, amount)
            allocation_snapshot[f"workforce_{target}"] = allocated

        energy_available = stock(resources, "energy")
        for target, share in profile["energy"].items():
            allocated = allocate(resources, "energy", target, energy_available * share)
            allocation_snapshot[f"energy_{target}"] = allocated

        materials_available = stock(resources, "materials")
        for target, share in profile["materials"].items():
            allocated = allocate(resources, "materials", target, materials_available * share)
            allocation_snapshot[f"materials_{target}"] = allocated

        record(outcome, "modifier_effects", f"Resource priority for this turn: {priority.replace('_', ' ')}.")
        return allocation_snapshot

    def _run_logistics(
        self,
        new_state: State,
        context: Dict[str, Any],
        allocation_priority: str,
        outcome: OutcomeReport,
    ) -> Tuple[Dict[str, Any], Dict[str, bool], List[str]]:
        resources = new_state["resources"]
        population = new_state["population"]
        economy = new_state["economy"]
        constants = context["constants"]
        modifier_context = context["modifier_context"]
        constraint_log: List[str] = []
        recovery_flags = {
            "energy_recovery": False,
            "water_recovery": False,
            "food_recovery": False,
            "population_recovery": False,
            "income_recovery": False,
        }

        allocation_snapshot: Dict[str, Any] = {"priority": allocation_priority}
        new_state["telemetry"]["turn_allocation_snapshot"] = allocation_snapshot
        resources["workforce_capacity"]["start"] = context["workforce_available"]
        set_stock(resources, "workforce_capacity", context["workforce_available"])
        labor_allocation = next(
            item for item in self.interaction_registry.by_verb("allocate") if item["interaction_id"] == "allocate_labor"
        )
        allocations = run_allocate(resources, labor_allocation, context, allocation_priority, outcome)
        for target, amount in allocations.items():
            allocation_snapshot[f"workforce_{target}"] = amount

        run_transform(
            resources,
            next(item for item in self.interaction_registry.by_verb("transform") if item["interaction_id"] == "fuel_to_electricity"),
            context,
            outcome,
            constraint_log,
        )
        for interaction_id, prefix in (
            ("allocate_electricity", "energy"),
            ("allocate_materials", "materials"),
        ):
            interaction = next(
                item for item in self.interaction_registry.by_verb("allocate") if item["interaction_id"] == interaction_id
            )
            allocations = run_allocate(resources, interaction, context, allocation_priority, outcome)
            for target, amount in allocations.items():
                allocation_snapshot[f"{prefix}_{target}"] = amount
        water_result = run_produce(
            resources,
            next(item for item in self.interaction_registry.by_verb("produce") if item["interaction_id"] == "electricity_materials_labor_to_water"),
            context,
            outcome,
            constraint_log,
        )
        outcome.setdefault("_verb_cache", {})["water_produced"] = water_result.get("produced", 0.0)
        food_result = run_produce(
            resources,
            next(item for item in self.interaction_registry.by_verb("produce") if item["interaction_id"] == "water_electricity_labor_to_food"),
            context,
            outcome,
            constraint_log,
        )
        service_result = run_consume(
            resources,
            next(item for item in self.interaction_registry.by_verb("consume") if item["interaction_id"] == "civic_service_energy"),
            context,
            outcome,
            constraint_log,
        )
        run_consume(
            resources,
            next(item for item in self.interaction_registry.by_verb("consume") if item["interaction_id"] == "household_water"),
            context,
            outcome,
            constraint_log,
        )
        run_consume(
            resources,
            next(item for item in self.interaction_registry.by_verb("consume") if item["interaction_id"] == "household_food"),
            context,
            outcome,
            constraint_log,
        )
        repair_result = run_repair(
            resources,
            next(item for item in self.interaction_registry.by_verb("repair") if item["interaction_id"] == "materials_maintenance"),
            context,
            outcome,
        )
        for interaction in self.interaction_registry.by_verb("decay"):
            decay_result = run_decay(resources, interaction, context, outcome)
            if interaction["interaction_id"] == "water_decay" and decay_result["lost"] > 0:
                record(outcome, "dependency_effects", f"Water leakage drained {decay_result['lost']:.1f} water.")
            if interaction["interaction_id"] == "food_decay" and decay_result["lost"] > 0:
                record(outcome, "dependency_effects", f"Food spoilage wasted {decay_result['lost']:.1f} food.")

        for name, record_data in resources.items():
            cap_bonus = modifier_context["storage_capacity_bonus"] if name in {"water", "food", "fuel"} else 0.0
            effective_capacity = record_data["capacity"] * (1.0 + cap_bonus)
            if stock(resources, name) > effective_capacity:
                overflow = stock(resources, name) - effective_capacity
                record_loss(resources, name, overflow)
                constraint_log.append(f"{name.title()} overflow caused {overflow:.1f} waste.")

        unmet_water = max(0.0, constants["water_consumption"] - resources["water"]["allocated"].get("households", 0.0))
        unmet_food = max(0.0, constants["food_consumption"] - resources["food"]["allocated"].get("households", 0.0))
        if unmet_water > 0:
            population["health"] = clamp(population["health"] - constants["water_health_penalty"])
            population["happiness"] = clamp(population["happiness"] - 0.05)
            record(outcome, "population_effects", f"Water shortages reduced health by {constants['water_health_penalty']:.2f}.")
        if unmet_food > 0:
            population["health"] = clamp(population["health"] - constants["food_to_health_penalty"])
            population["happiness"] = clamp(population["happiness"] - 0.05)
            record(outcome, "population_effects", f"Food insecurity reduced health by {constants['food_to_health_penalty']:.2f}.")
        energy_service_gap = service_result.get("gap", 0.0)
        if energy_service_gap > 0:
            population["happiness"] = clamp(population["happiness"] - 0.04)
            record(outcome, "dependency_effects", "Power shortages disrupted services across town.")
        elif stock(resources, "energy") > constants["energy_recovery_surplus_threshold"]:
            recovery_flags["energy_recovery"] = True
            water_bonus = constants["water_recovery_bonus"]
            record_production(resources, "water", water_bonus)
            record(outcome, "recovery_effects", f"Energy surplus improved pumping efficiency, restoring +{water_bonus:.1f} water.")

        if stock(resources, "water") > context["irrigation_threshold"]:
            recovery_flags["water_recovery"] = True
            food_bonus = constants["food_recovery_bonus"]
            record_production(resources, "food", food_bonus)
            record(outcome, "recovery_effects", f"Healthy water reserves improved agriculture, restoring +{food_bonus:.1f} food.")

        if stock(resources, "food") > constants["food_security_threshold"]:
            updated = recover_health(population, constants["health_recovery_bonus"])
            population["health"] = updated["health"]
            recovery_flags["food_recovery"] = True
            record(outcome, "recovery_effects", f"Food security supported a modest health recovery of +{constants['health_recovery_bonus']:.2f}.")

        if population["happiness"] < 0.55:
            updated = apply_unrest(population, constants["happiness_to_unrest_penalty"])
            population["unrest"] = updated["unrest"]
            record(outcome, "population_effects", f"Low happiness increased unrest by {constants['happiness_to_unrest_penalty']:.2f}.")
        elif population["unrest"] > 0.0:
            population["unrest"] = clamp(population["unrest"] - 0.05)
            recovery_flags["population_recovery"] = True
            record(outcome, "recovery_effects", "Steadier conditions reduced unrest by 0.05.")

        economy["income"] = compute_effective_income(
            economy["base_income"],
            population["health"],
            population["unrest"],
            economy["tax_base"],
        )
        if population["health"] < constants["labor_threshold"] or population["unrest"] > constants["unrest_threshold"]:
            economy["income"] = max(0.0, economy["income"] - constants["health_to_income_penalty"])
            record(outcome, "economy_effects", f"Population stress reduced next-turn income by ${constants['health_to_income_penalty']:.2f}.")
        else:
            economy["income"] += constants["income_recovery_bonus"]
            recovery_flags["income_recovery"] = True
            record(outcome, "recovery_effects", f"Stable health and unrest improved revenue by +${constants['income_recovery_bonus']:.2f}.")

        if population["unrest"] > constants["unrest_threshold"]:
            economy["service_penalty"] = constants["unrest_to_budget_penalty"]
            record(outcome, "economy_effects", f"Unrest added a ${constants['unrest_to_budget_penalty']:.2f} service penalty for the next turn.")
        else:
            economy["service_penalty"] = 0.0

        outcome.pop("_verb_cache", None)
        return allocation_snapshot, recovery_flags, constraint_log

    def simulate_turn(self, state: State, actions: Actions, forecast_mode: bool = False) -> Tuple[State, OutcomeReport]:
        new_state = self.clone_state(state)
        ensure_modifier_containers(new_state)
        outcome = empty_outcome()
        resources = new_state["resources"]
        population = new_state["population"]
        economy = new_state["economy"]
        constants = self.scenario["constants"]

        reset_turn_metrics(resources)
        self._apply_start_snapshot(resources, outcome)
        previous_risk_values = dict(new_state["telemetry"].get("last_risk_values", {}))

        if stock(resources, "energy") <= 0:
            record_import(resources, "energy", constants["base_energy_recovery"])
            record(outcome, "recovery_effects", f"Base grid recovery restored {constants['base_energy_recovery']:.1f} energy before planning.")

        context = self.build_context(new_state)
        resource_purchases = actions.get("resource_purchases")
        if resource_purchases is None:
            legacy = actions.get("emergency_allocation", {})
            resource_purchases = {
                "energy": float(legacy.get("energy_amount", 0.0)),
                "water": float(legacy.get("water_amount", 0.0)),
                "food": float(legacy.get("food_amount", 0.0)),
                "fuel": 0.0,
                "materials": 0.0,
            }
        risk_basis = new_state["telemetry"].get("last_risk_ranking") or [
            {"issue_id": "energy_instability"},
            {"issue_id": "water_shortage"},
            {"issue_id": "food_collapse"},
        ]
        _, total_cost = validate_allocation(resource_purchases, self.scenario, risk_basis)
        self._apply_imports(resources, resource_purchases, outcome)
        direct_adjustment = -total_cost
        direct_adjustment = self._apply_policy(new_state, actions.get("selected_policy_id"), outcome, direct_adjustment, forecast_mode)

        context = self.build_context(new_state)
        allocation_priority = actions.get("allocation_priority", "balance_services")
        allocation_snapshot, recovery_flags, constraint_log = self._run_logistics(
            new_state,
            context,
            allocation_priority,
            outcome,
        )

        expenses_for_turn = economy["expenses"] + economy.get("service_penalty", 0.0)
        new_budget, net = update_budget(economy["budget"], economy["income"], expenses_for_turn, direct_adjustment)
        economy["budget"] = new_budget
        record(outcome, "economy_effects", f"Operations and imports changed the budget by {net:+.2f}, leaving ${economy['budget']:.2f}.")

        resource_gaps = {
            "energy": max(0.0, context["effective_energy_demand"] - resources["energy"]["allocated"].get("service_demand", 0.0)),
            "water": max(0.0, constants["water_consumption"] - resources["water"]["allocated"].get("households", 0.0)),
            "food": max(0.0, constants["food_consumption"] - resources["food"]["allocated"].get("households", 0.0)),
        }
        self._apply_case_dynamics(new_state, outcome, resource_gaps, actions.get("selected_policy_id"))

        outcome["base_projection"]["budget"] = {"start": state["economy"]["budget"], "after_operations": economy["budget"]}
        outcome["resource_flow_projection"]["budget"] = {
            "start": state["economy"]["budget"],
            "projected_consumption": expenses_for_turn,
            "projected_imports": -direct_adjustment,
            "projected_end": economy["budget"],
            "primary_constraint": "budget strain" if economy["budget"] < constants["safe_budget_threshold"] else "none",
        }

        ledger = end_of_turn_ledger(resources)
        new_state["telemetry"]["turn_resource_ledger"] = ledger
        history = list(new_state["telemetry"].get("resource_flow_history", []))
        history.append({"turn": new_state["telemetry"].get("turn", 1), "ledger": ledger})
        new_state["telemetry"]["resource_flow_history"] = history[-8:]
        new_state["telemetry"]["turn_constraint_log"] = list(constraint_log)
        new_state["telemetry"]["turn_allocation_snapshot"] = allocation_snapshot
        set_stock(resources, "workforce_capacity", context["workforce_available"])
        outcome["constraint_preview"] = constraint_log

        for name, entry in ledger.items():
            outcome["resource_flow_projection"].setdefault(name, {})
            outcome["resource_flow_projection"][name].update(
                {
                    "resource_type_id": entry["resource_type_id"],
                    "unit_id": entry["unit_id"],
                    "start_quantity": entry["start_quantity"],
                    "projected_production": entry["produced"],
                    "projected_imports": entry["imported"],
                    "projected_consumption": entry["consumed"],
                    "projected_losses": entry["lost"],
                    "projected_flow": entry["projected_flow"],
                    "projected_end_quantity": entry["end_quantity"],
                    "projected_end": entry["end"],
                    "primary_constraint": entry["constraint"] or "none",
                }
            )
            if entry["constraint"]:
                record(outcome, "dependency_effects", entry["constraint"])

        risk_ranking = compute_risk_ranking(
            new_state,
            context,
            outcome["outcome_chain"],
            recovery_flags,
            ledger,
            constraint_log,
        )
        case_reports = self._trigger_case_reports(new_state, risk_ranking, actions.get("selected_policy_id"))
        new_state["telemetry"]["last_case_reports"] = case_reports
        outcome["case_reports"] = []
        for report_item in case_reports:
            record(outcome, "case_reports", f"{report_item['title']}: {report_item['body']}")
        current_risk_values = {risk["issue_id"]: risk["severity"] for risk in risk_ranking}
        new_state["telemetry"]["last_risk_ranking"] = risk_ranking
        new_state["telemetry"]["last_risk_values"] = current_risk_values
        new_state["telemetry"]["last_outcome_chain"] = list(outcome["outcome_chain"])
        new_state["telemetry"]["turn"] = new_state["telemetry"].get("turn", 1) + (0 if forecast_mode else 1)
        outcome["risk_changes"] = self._risk_change_lines(previous_risk_values, risk_ranking)
        outcome["remaining_risks"] = [
            f"{issue_label(risk['issue_id'])}: {risk['severity']:.2f} ({risk['reason']})"
            for risk in risk_ranking[:3]
        ]
        outcome["historical_situation"] = self.active_case["case_metadata"]["summary"]
        outcome["political_constraints"] = self._political_constraint_lines(new_state)
        outcome["stakeholder_snapshot"] = self._affected_group_lines(new_state)
        outcome["system_pressures"] = self._case_pressure_lines(new_state)

        stable = (
            stock(resources, "energy") >= constants["safe_energy_threshold"]
            and stock(resources, "water") >= constants["safe_water_threshold"]
            and stock(resources, "food") >= constants["safe_food_threshold"]
            and population["health"] >= constants["safe_health_threshold"]
            and economy["budget"] >= constants["safe_budget_threshold"]
        )
        new_state["telemetry"]["stable_turn_streak"] = (
            new_state["telemetry"].get("stable_turn_streak", 0) + 1 if stable else 0
        )
        decrement_temporary_effects(new_state)
        return new_state, outcome

    def explain_outcome(self, outcome_report: OutcomeReport) -> None:
        print("\n=== Outcome Explanation ===")
        for heading in [
            "direct_effects",
            "dependency_effects",
            "modifier_effects",
            "recovery_effects",
            "population_effects",
            "economy_effects",
            "political_effects",
            "stakeholder_effects",
            "institution_effects",
            "case_reports",
            "risk_changes",
            "remaining_risks",
        ]:
            print(f"{heading.replace('_', ' ').title()}:")
            lines = outcome_report.get(heading, [])
            if lines:
                for line in lines:
                    print(f"- {line}")
            else:
                print("- none")

    def evaluate_end_state(self, turn: int) -> bool:
        resources = self.state["resources"]
        population = self.state["population"]
        economy = self.state["economy"]
        constants = self.scenario["constants"]
        if stock(resources, "water") <= 0 or stock(resources, "food") <= 0:
            print("\nCritical resources have collapsed. The town fails.")
            return False
        if population["health"] <= 0.3:
            print("\nPublic health has deteriorated beyond recovery. The town fails.")
            return False
        if economy["budget"] < 0 or economy["service_penalty"] > 150:
            print("\nEconomic instability has pushed the town into collapse.")
            return False
        if self.state["telemetry"].get("stable_turn_streak", 0) >= constants["stabilization_turns_required"]:
            print("\nYou held all major systems above the safety thresholds long enough to stabilize the town.")
            return False
        if turn == self.turns:
            print("\nThe forecast window ended.")
            return False
        return True

    def run(self) -> None:
        print("Welcome to the Town Recovery Simulation!")
        print("Each turn, study the coupled forecast, interpret the report, then act under logistics constraints.")
        for turn in range(1, self.turns + 1):
            print(f"\n--- Turn {turn} ---")
            self.observe_state()
            forecast = self.build_forecast(self.state)
            self.display_forecast(forecast)
            actions = self.collect_player_actions(forecast)
            self.state, outcome = self.simulate_turn(self.state, actions)
            self.explain_outcome(outcome)
            self.observe_state()
            if not self.evaluate_end_state(turn):
                break


def main() -> None:
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    SimulationEngine(base_dir).run()


if __name__ == "__main__":
    main()
