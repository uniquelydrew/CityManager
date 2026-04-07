"""Phase 3 predictive CLI simulation for the town recovery scenario."""

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
from src.economy import compute_effective_income, update_budget
from src.energy import capped_energy_purchase, effective_energy_demand
from src.explanation import empty_outcome, record
from src.food import effective_irrigation_threshold, food_output_bonus, recovery_bonus as food_recovery_bonus
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
from src.risk import compute_risk_ranking
from src.water import effective_water_capacity, effective_water_penalty, recovery_bonus as water_recovery_bonus


State = Dict[str, Any]
Actions = Dict[str, Any]
OutcomeReport = Dict[str, Any]


class SimulationEngine:
    """Orchestrates the gameplay loop for the town recovery Phase 3 scenario."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self.scenario = self._load_json("town_recovery_v2.json")
        self.dependency_rules = self._load_json("dependency_rules.json")
        self.policies_data = self._load_json("policies.json")
        self.policy_map = policy_map(self.policies_data)
        self.turns = int(self.scenario.get("turns", 4))
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

    def _default_state(self) -> Dict[str, Any]:
        return {
            "resources": {"water": 50.0, "energy": 40.0, "food": 60.0},
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
            },
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
        ensure_modifier_containers(normalized)
        if "base_income" not in normalized["economy"]:
            normalized["economy"]["base_income"] = normalized["economy"]["income"]
        return normalized

    def clone_state(self, state: State) -> State:
        return copy.deepcopy(self._normalize_state(state))

    def build_context(self, state: State) -> Dict[str, Any]:
        constants = self.scenario["constants"]
        modifier_context = aggregate_modifier_context(state)
        grid_efficiency = state["infrastructure"]["grid_efficiency"] + modifier_context["grid_efficiency_bonus"]
        water_capacity = effective_water_capacity(
            state["infrastructure"]["water_capacity"],
            modifier_context["water_capacity_bonus"],
        )
        food_yield = state["infrastructure"]["food_yield"] + modifier_context["food_yield_bonus"]
        effective_demand = effective_energy_demand(
            constants["energy_demand"],
            grid_efficiency,
            modifier_context["energy_demand_multiplier"],
        )
        irrigation_threshold = effective_irrigation_threshold(
            constants["irrigation_threshold"],
            modifier_context["irrigation_threshold_multiplier"],
        )
        return {
            "constants": constants,
            "effective_energy_demand": effective_demand,
            "pump_threshold": constants["water_pump_threshold"] * water_capacity,
            "irrigation_threshold": irrigation_threshold,
            "grid_efficiency": grid_efficiency,
            "water_capacity": water_capacity,
            "food_yield": food_yield,
            "modifier_context": modifier_context,
        }

    def observe_state(self) -> None:
        res = self.state["resources"]
        pop = self.state["population"]
        econ = self.state["economy"]
        infra = self.state["infrastructure"]
        streak = self.state["telemetry"].get("stable_turn_streak", 0)
        print("\n=== Current State ===")
        print(f"Water: {res['water']:.1f}  Energy: {res['energy']:.1f}  Food: {res['food']:.1f}")
        print(
            f"Population: count={int(pop['count'])}, health={pop['health']:.2f}, "
            f"happiness={pop['happiness']:.2f}, unrest={pop['unrest']:.2f}"
        )
        print(
            f"Economy: budget=${econ['budget']:.2f}, income=${econ['income']:.2f}, "
            f"base_income=${econ['base_income']:.2f}, expenses=${econ['expenses']:.2f}, "
            f"service_penalty=${econ['service_penalty']:.2f}"
        )
        print(
            f"Infrastructure: water_capacity={infra['water_capacity']:.2f}, "
            f"grid_efficiency={infra['grid_efficiency']:.2f}, food_yield={infra['food_yield']:.2f}"
        )
        active = ", ".join(self.state["modifiers"]["active_policies"]) or "none"
        print(f"Active policies: {active}")
        print(f"Stable turn streak: {streak}")

    def build_forecast(self, state: State) -> Dict[str, Any]:
        context = self.build_context(state)
        forecast = build_forecast_payload(state, self.simulate_turn, context)
        forecast["report_text"] = generate_report_text(forecast["risk_ranking"])
        return forecast

    def display_forecast(self, forecast: Dict[str, Any]) -> None:
        print("\n=== Forecast Base Changes ===")
        for system, values in forecast["base_projection"].items():
            print(f"- {system}: {values}")
        print("\n=== Forecast Dependency Changes ===")
        for system, values in forecast["propagated_projection"].items():
            print(f"- {system}: {values}")
        print("\n=== Forecast Modifier Changes ===")
        for system, values in forecast["modifier_projection"].items():
            print(f"- {system}: {values}")
        print("\n=== Forecast Recovery Changes ===")
        for system, values in forecast["recovery_projection"].items():
            print(f"- {system}: {values}")
        print("\n=== Forecast Risk Ranking ===")
        for risk in forecast["risk_ranking"][:3]:
            print(
                f"- {issue_label(risk['issue_id'])}: severity {risk['severity']:.2f} "
                f"because {risk['reason']}"
            )
        if forecast.get("risk_changes"):
            print("\n=== Forecast Risk Movement ===")
            for line in forecast["risk_changes"]:
                print(f"- {line}")

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
        if validate_rla_answers(
            answers["primary_issue"],
            answers["secondary_issue"],
            forecast["risk_ranking"],
        ):
            self.skills_used["rla"] = True
            print("Correct. You identified the top two signals in the report.")
        else:
            print("Not quite. The report mixes multiple signals, and the order matters.")
        return answers

    def math_challenge(self, forecast: Dict[str, Any]) -> Dict[str, float]:
        print("\nMath Challenge:")
        print(math_prompt(self.scenario, forecast["risk_ranking"]))
        allocation = {
            "energy_amount": self.prompt_float("Energy units to buy: "),
            "water_amount": self.prompt_float("Water units to buy: "),
            "food_amount": self.prompt_float("Food units to buy: "),
        }
        valid, total_cost = validate_allocation(allocation, self.scenario, forecast["risk_ranking"])
        allocation["total_cost"] = total_cost
        if valid:
            self.skills_used["math"] = True
            print(f"Valid allocation. Total emergency cost is ${total_cost:.2f}.")
        else:
            print(
                f"Invalid allocation. Total emergency cost is ${total_cost:.2f}, "
                "and it must stay within budget while helping top risks."
            )
        return allocation

    def science_challenge(self, forecast: Dict[str, Any]) -> float:
        context = forecast["context"]
        current_energy = self.state["resources"]["energy"]
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
            print(
                f"Insufficient. You needed at least {required_amount:.1f} additional generation "
                "to protect the water system."
            )
        return answer

    def social_challenge(self, forecast: Dict[str, Any], spent: float) -> str:
        print("\nSocial Studies Challenge:")
        available = [policy for policy in self.policies_data["policies"]]
        for line in social_prompt(available, self.state["economy"]["budget"] - spent):
            print(line)
        choice = self.prompt_choice("Choose a policy (A-F): ", [policy["label"] for policy in available])
        policy = next(policy for policy in available if policy["label"] == choice)
        can_use, reason = can_select_policy(self.state, policy)
        top_two = {forecast["risk_ranking"][0]["issue_id"], forecast["risk_ranking"][1]["issue_id"]}
        improves_future = (
            policy["policy_id"] in {"pump_repair_program", "grid_maintenance", "irrigation_upgrade"}
            or (policy["policy_id"] == "water_emergency_crews" and "water_shortage" in top_two)
            or (policy["policy_id"] == "grid_fuel_delivery" and "energy_instability" in top_two)
            or (policy["policy_id"] == "food_relief_convoy" and "food_collapse" in top_two)
        )
        if can_use and improves_future:
            self.skills_used["social"] = True
            print("Good policy choice. It addresses a current or future bottleneck.")
        else:
            print(reason or "That policy is legal, but it does not address the strongest tradeoff well.")
        return policy["policy_id"]

    def collect_player_actions(self, forecast: Dict[str, Any]) -> Actions:
        parsed_report_issue = self.rla_challenge(forecast)
        emergency_allocation = self.math_challenge(forecast)
        science_generation_answer = self.science_challenge(forecast)
        selected_policy_id = self.social_challenge(forecast, emergency_allocation["total_cost"])
        return {
            "emergency_allocation": emergency_allocation,
            "selected_policy_id": selected_policy_id,
            "risk_assessment": {
                "primary_risk": parsed_report_issue["primary_issue"],
                "secondary_risk": parsed_report_issue["secondary_issue"],
            },
            "parsed_report_issue": parsed_report_issue,
            "science_generation_answer": science_generation_answer,
        }

    def _auto_policy_for_gui(self, forecast: Dict[str, Any], spent: float) -> str | None:
        """Pick a deterministic policy for the GUI adapter."""
        remaining_budget = self.state["economy"]["budget"] - spent
        top_risks = [risk["issue_id"] for risk in forecast["risk_ranking"][:2]]
        preferred_order = []
        if "energy_instability" in top_risks:
            preferred_order.extend(["grid_maintenance", "grid_fuel_delivery"])
        if "water_shortage" in top_risks:
            preferred_order.extend(["pump_repair_program", "water_emergency_crews"])
        if "food_collapse" in top_risks:
            preferred_order.extend(["irrigation_upgrade", "food_relief_convoy"])
        if "budget_erosion" in top_risks:
            preferred_order.extend(["grid_maintenance"])
        seen: set[str] = set()
        for policy_id in preferred_order:
            if policy_id in seen:
                continue
            seen.add(policy_id)
            policy = self.policy_map[policy_id]
            if policy["cost"] > remaining_budget:
                continue
            can_use, _ = can_select_policy(self.state, policy)
            if can_use:
                return policy_id
        return None

    def format_explanation_text(self, outcome_report: OutcomeReport) -> str:
        """Flatten the structured outcome into readable multiline text."""
        sections = [
            "direct_effects",
            "dependency_effects",
            "modifier_effects",
            "recovery_effects",
            "population_effects",
            "economy_effects",
            "risk_changes",
            "remaining_risks",
        ]
        lines: List[str] = []
        for heading in sections:
            title = heading.replace("_", " ").title()
            lines.append(f"{title}:")
            entries = outcome_report.get(heading, [])
            if entries:
                lines.extend(f"- {entry}" for entry in entries)
            else:
                lines.append("- none")
        return "\n".join(lines)

    def step(self, actions: Dict[str, float]) -> Dict[str, Any]:
        """GUI adapter that advances one deterministic turn without duplicating logic."""
        forecast = self.build_forecast(self.state)
        context = forecast["context"]
        top_primary = forecast["risk_ranking"][0]["issue_id"]
        top_secondary = forecast["risk_ranking"][1]["issue_id"] if len(forecast["risk_ranking"]) > 1 else top_primary
        emergency_allocation = {
            "energy_amount": float(actions.get("energy", 0.0)),
            "water_amount": float(actions.get("water", 0.0)),
            "food_amount": float(actions.get("food", 0.0)),
        }
        _, total_cost = validate_allocation(emergency_allocation, self.scenario, forecast["risk_ranking"])
        emergency_allocation["total_cost"] = total_cost
        science_generation_answer = required_generation(
            self.state["resources"]["energy"],
            context["effective_energy_demand"],
            context["pump_threshold"],
            context["constants"]["science_safety_margin"],
        )
        selected_policy_id = actions.get("policy_id")
        if selected_policy_id is None:
            selected_policy_id = self._auto_policy_for_gui(forecast, total_cost)
        full_actions = {
            "emergency_allocation": emergency_allocation,
            "selected_policy_id": selected_policy_id,
            "risk_assessment": {
                "primary_risk": top_primary,
                "secondary_risk": top_secondary,
            },
            "parsed_report_issue": {
                "primary_issue": top_primary,
                "secondary_issue": top_secondary,
            },
            "science_generation_answer": science_generation_answer,
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

    def simulate_turn(self, state: State, actions: Actions, forecast_mode: bool = False) -> Tuple[State, OutcomeReport]:
        new_state = self.clone_state(state)
        ensure_modifier_containers(new_state)
        outcome = empty_outcome()
        resources = new_state["resources"]
        population = new_state["population"]
        economy = new_state["economy"]
        infrastructure = new_state["infrastructure"]
        constants = self.scenario["constants"]

        outcome["base_projection"] = {
            "water": {"start": resources["water"]},
            "energy": {"start": resources["energy"]},
            "food": {"start": resources["food"]},
            "budget": {"start": economy["budget"]},
        }
        recovery_flags = {
            "energy_recovery": False,
            "water_recovery": False,
            "food_recovery": False,
            "population_recovery": False,
            "income_recovery": False,
        }

        if resources["energy"] <= 0:
            resources["energy"] += constants["base_energy_recovery"]
            recovery_flags["energy_recovery"] = True
            record(
                outcome,
                "recovery_effects",
                f"Base grid recovery restored {constants['base_energy_recovery']:.1f} energy before purchases.",
            )

        context = self.build_context(new_state)
        allocation = actions.get("emergency_allocation", {})
        total_cost = float(allocation.get("total_cost", 0.0))
        procurement_penalty = (
            constants["procurement_penalty"]
            if economy["budget"] < constants["energy_procurement_threshold"]
            else 0.0
        )
        purchased_energy, capped_amount = capped_energy_purchase(
            float(allocation.get("energy_amount", 0.0)),
            self.scenario["available_emergency_budget"],
            self.scenario["unit_costs"]["energy"],
            procurement_penalty,
        )
        resources["energy"] += purchased_energy
        resources["water"] += float(allocation.get("water_amount", 0.0))
        resources["food"] += float(allocation.get("food_amount", 0.0))
        direct_adjustment = -total_cost
        record(
            outcome,
            "direct_effects",
            f"Emergency budget purchased +{purchased_energy:.1f} energy, +{allocation.get('water_amount', 0.0):.1f} water, and +{allocation.get('food_amount', 0.0):.1f} food.",
        )
        if capped_amount > 0:
            record(
                outcome,
                "economy_effects",
                f"Energy procurement constraints reduced the requested purchase by {capped_amount:.1f} units.",
            )
            outcome["modifier_projection"]["energy_procurement_cap"] = {"capped_amount": capped_amount}

        selected_policy_id = actions.get("selected_policy_id")
        if selected_policy_id:
            policy = self.policy_map[selected_policy_id]
            can_use, reason = can_select_policy(new_state, policy)
            if can_use:
                activate_policy(new_state, policy)
                direct_adjustment -= float(policy.get("cost", 0.0))
                for path, delta in policy.get("instant_effects", {}).items():
                    head, key = path.split(".")
                    new_state[head][key] += delta
                record(
                    outcome,
                    "modifier_effects",
                    f"Selected policy {selected_policy_id} for ${policy['cost']:.2f}.",
                )
            elif not forecast_mode:
                record(outcome, "modifier_effects", reason)

        modifier_context = aggregate_modifier_context(new_state)
        context = self.build_context(new_state)
        effective_demand = context["effective_energy_demand"]
        if modifier_context["energy_demand_multiplier"] != 0.0:
            record(
                outcome,
                "modifier_effects",
                f"Active grid modifiers changed effective energy demand to {effective_demand:.1f}.",
            )

        resources["energy"] = max(0.0, resources["energy"] - effective_demand)
        resources["water"] = max(0.0, resources["water"] - constants["water_consumption"])
        resources["food"] = max(0.0, resources["food"] - constants["food_consumption"])
        outcome["base_projection"]["energy"]["after_consumption"] = resources["energy"]
        outcome["base_projection"]["water"]["after_consumption"] = resources["water"]
        outcome["base_projection"]["food"]["after_consumption"] = resources["food"]

        expenses_for_turn = economy["expenses"] + economy.get("service_penalty", 0.0)
        new_budget, net = update_budget(
            economy["budget"],
            economy["income"],
            expenses_for_turn,
            direct_adjustment,
        )
        economy["budget"] = new_budget
        outcome["base_projection"]["budget"]["after_operations"] = economy["budget"]
        record(
            outcome,
            "economy_effects",
            f"Operations and purchases changed the budget by {net:+.2f}, leaving ${economy['budget']:.2f}.",
        )

        pump_penalty = effective_water_penalty(
            constants["energy_to_water_penalty"],
            modifier_context["energy_to_water_multiplier"],
        )
        if resources["energy"] < context["pump_threshold"]:
            resources["water"] = max(0.0, resources["water"] - pump_penalty)
            record(
                outcome,
                "dependency_effects",
                f"Energy fell below the pump threshold, reducing water by {pump_penalty:.1f}.",
            )
        else:
            record(
                outcome,
                "dependency_effects",
                "Energy remained above the pump threshold, so the water pumping penalty did not trigger.",
            )
        outcome["propagated_projection"]["water"] = {"after_dependencies": resources["water"]}

        if resources["water"] < context["irrigation_threshold"]:
            resources["food"] = max(0.0, resources["food"] - constants["water_to_food_penalty"])
            record(
                outcome,
                "dependency_effects",
                f"Water fell below the irrigation threshold, reducing food by {constants['water_to_food_penalty']:.1f}.",
            )
        else:
            record(
                outcome,
                "dependency_effects",
                "Water stayed above the irrigation threshold, preventing an extra food penalty.",
            )
        outcome["propagated_projection"]["food"] = {"after_dependencies": resources["food"]}

        if context["food_yield"] > 1.0:
            bonus = food_output_bonus(constants["food_consumption"], context["food_yield"])
            resources["food"] += bonus
            infrastructure["food_yield"] = context["food_yield"]
            record(
                outcome,
                "modifier_effects",
                f"Persistent yield improvements added {bonus:.1f} food after dependency checks.",
            )
            outcome["modifier_projection"]["food"] = {"after_modifiers": resources["food"]}

        if resources["food"] < constants["food_security_threshold"]:
            population["health"] = clamp(population["health"] - constants["food_to_health_penalty"])
            population["happiness"] = clamp(population["happiness"] - 0.05)
            record(
                outcome,
                "population_effects",
                f"Food insecurity reduced health by {constants['food_to_health_penalty']:.2f}.",
            )
        elif resources["food"] > constants["food_security_threshold"]:
            updated = recover_health(population, constants["health_recovery_bonus"])
            population["health"] = updated["health"]
            recovery_flags["population_recovery"] = True
            record(
                outcome,
                "recovery_effects",
                f"Food security supported a modest health recovery of +{constants['health_recovery_bonus']:.2f}.",
            )

        if population["happiness"] < 0.55:
            updated = apply_unrest(population, constants["happiness_to_unrest_penalty"])
            population["unrest"] = updated["unrest"]
            record(
                outcome,
                "population_effects",
                f"Low happiness increased unrest by {constants['happiness_to_unrest_penalty']:.2f}.",
            )
        elif population["unrest"] > 0.0:
            population["unrest"] = clamp(population["unrest"] - 0.05)
            recovery_flags["population_recovery"] = True
            record(
                outcome,
                "recovery_effects",
                "Steadier conditions reduced unrest by 0.05.",
            )

        water_bonus = water_recovery_bonus(
            resources["energy"],
            constants["energy_recovery_surplus_threshold"],
            constants["water_recovery_bonus"],
        )
        if water_bonus > 0:
            resources["water"] += water_bonus
            recovery_flags["water_recovery"] = True
            record(
                outcome,
                "recovery_effects",
                f"Energy surplus improved pumping efficiency, restoring +{water_bonus:.1f} water.",
            )

        food_bonus = food_recovery_bonus(
            resources["water"],
            context["irrigation_threshold"],
            constants["food_recovery_bonus"],
        )
        if food_bonus > 0:
            resources["food"] += food_bonus
            recovery_flags["food_recovery"] = True
            record(
                outcome,
                "recovery_effects",
                f"Healthy water reserves improved agriculture, restoring +{food_bonus:.1f} food.",
            )
        outcome["recovery_projection"]["water"] = {"after_recovery": resources["water"]}
        outcome["recovery_projection"]["food"] = {"after_recovery": resources["food"]}

        economy["income"] = compute_effective_income(
            economy["base_income"],
            population["health"],
            population["unrest"],
            economy["tax_base"],
        )
        if (
            population["health"] < constants["labor_threshold"]
            or population["unrest"] > constants["unrest_threshold"]
        ):
            economy["income"] = max(
                0.0, economy["income"] - constants["health_to_income_penalty"]
            )
            record(
                outcome,
                "economy_effects",
                f"Population stress reduced next-turn income by ${constants['health_to_income_penalty']:.2f}.",
            )
        elif population["health"] >= constants["labor_threshold"] and population["unrest"] <= constants["unrest_threshold"]:
            economy["income"] += constants["income_recovery_bonus"]
            recovery_flags["income_recovery"] = True
            record(
                outcome,
                "recovery_effects",
                f"Stable health and unrest improved revenue by +${constants['income_recovery_bonus']:.2f}.",
            )

        if population["unrest"] > constants["unrest_threshold"]:
            economy["service_penalty"] = constants["unrest_to_budget_penalty"]
            record(
                outcome,
                "economy_effects",
                f"Unrest added a ${constants['unrest_to_budget_penalty']:.2f} service penalty for the next turn.",
            )
        else:
            if economy["service_penalty"] > 0:
                record(
                    outcome,
                    "recovery_effects",
                    "Lower unrest cleared the service penalty for the next turn.",
                )
            economy["service_penalty"] = 0.0

        previous_risk_values = dict(new_state["telemetry"].get("last_risk_values", {}))
        risk_ranking = compute_risk_ranking(
            new_state,
            context,
            outcome["outcome_chain"],
            recovery_flags,
        )
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

        epsilon = 1e-6
        stable = (
            resources["energy"] + epsilon >= constants["safe_energy_threshold"]
            and resources["water"] + epsilon >= constants["safe_water_threshold"]
            and resources["food"] + epsilon >= constants["safe_food_threshold"]
            and population["health"] + epsilon >= constants["safe_health_threshold"]
            and economy["budget"] + epsilon >= constants["safe_budget_threshold"]
        )
        if stable:
            new_state["telemetry"]["stable_turn_streak"] = new_state["telemetry"].get("stable_turn_streak", 0) + 1
        else:
            new_state["telemetry"]["stable_turn_streak"] = 0

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
            "risk_changes",
            "remaining_risks",
        ]:
            title = heading.replace("_", " ").title()
            print(f"{title}:")
            lines = outcome_report.get(heading, [])
            if not lines:
                print("- none")
            else:
                for line in lines:
                    print(f"- {line}")

    def evaluate_end_state(self, turn: int) -> bool:
        resources = self.state["resources"]
        population = self.state["population"]
        economy = self.state["economy"]
        constants = self.scenario["constants"]
        if resources["water"] <= 0 or resources["food"] <= 0:
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
            if all(self.skills_used.values()):
                print("\nThe forecast window ended with every skill used, but the town is not fully stabilized yet.")
            else:
                print("\nThe slice ended, but not every skill was applied successfully.")
            return False
        return True

    def run(self) -> None:
        print("Welcome to the Town Recovery Simulation!")
        print("Each turn, study the coupled forecast, interpret the report, then act under constraints.")
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
