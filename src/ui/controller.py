"""Thin controller that connects the PySide6 GUI to the simulation engine."""

from src.modifiers import can_select_policy
from src.ui.formatters import (
    case_title_text,
    current_problem_text,
    goal_progress_text,
    has_turn_result,
    mission_text,
    policy_summary,
    policy_title,
    player_role_text,
    recommendation_sentence,
    risk_label,
    skill_tag_lines,
    top_risk,
)


class UIController:
    def __init__(self, engine, ui):
        self.engine = engine
        self.ui = ui
        self.last_result = None
        self.journal_entries = []
        self.ui.action_panel.submit_button.clicked.connect(self.run_turn)
        self.ui.action_panel.actions_changed.connect(self.refresh_action_context)
        self.refresh(initial=True)

    def _apply_header(self, forecast):
        current_turn = self.engine.state["telemetry"].get("turn", 1)
        self.ui.title_label.setText(f"{case_title_text(forecast)} | Turn {current_turn}")
        self.ui.role_label.setText(player_role_text(forecast))
        self.ui.status_label.setText("Urgent issue: " + current_problem_text(forecast))
        self.ui.goal_label.setText(mission_text(forecast))
        self.ui.progress_label.setText(goal_progress_text(self.engine.state, forecast))
        self.ui.skills_label.setText("GED skills: " + ", ".join(skill_tag_lines(forecast)))

    def refresh_action_context(self):
        self.ui.action_panel.set_context(
            self.engine.scenario["unit_costs"],
            self.engine.scenario["available_emergency_budget"],
        )
        forecast = self.engine.build_forecast(self.engine.state)
        resolved_view = forecast.get("resolved_view", {})
        self.ui.action_panel.set_copy(
            resolved_view.get("action_text", {}),
            resolved_view.get("resources", {}),
        )
        policy_options = []
        for policy in self.engine.policies_data["policies"]:
            can_use, reason = can_select_policy(self.engine.state, policy)
            title = f"{policy_title(policy['policy_id'])} (${policy['cost']:.0f})"
            if not can_use:
                title += " - unavailable"
            policy_options.append(
                {
                    "policy_id": policy["policy_id"],
                    "title": title,
                    "cost": float(policy["cost"]),
                    "summary": policy_summary(policy) if can_use else f"Unavailable: {reason}",
                }
            )
        self.ui.action_panel.set_policy_options(policy_options)
        top = top_risk(forecast)
        resources = resolved_view.get("resources", {})
        energy_desc = resources.get("electricity", {}).get("description", "Helps protect the main operating system.")
        water_desc = resources.get("water", {}).get("description", "Helps protect water service.")
        food_desc = resources.get("food", {}).get("description", "Helps protect food supply.")
        fuel_desc = resources.get("fuel", {}).get("description", "Helps support the main operating system.")
        materials_desc = resources.get("materials", {}).get("description", "Helps repairs and reduces system losses.")
        self.ui.action_panel.energy_help.setText(
            f"Cost: ${self.engine.scenario['unit_costs']['energy']:.0f} per unit\n{energy_desc}"
        )
        self.ui.action_panel.water_help.setText(
            f"Cost: ${self.engine.scenario['unit_costs']['water']:.0f} per unit\n{water_desc}"
        )
        self.ui.action_panel.food_help.setText(
            f"Cost: ${self.engine.scenario['unit_costs']['food']:.0f} per unit\n{food_desc}"
        )
        self.ui.action_panel.fuel_help.setText(
            f"Cost: ${self.engine.scenario['unit_costs']['fuel']:.0f} per unit\n{fuel_desc}"
        )
        self.ui.action_panel.materials_help.setText(
            f"Cost: ${self.engine.scenario['unit_costs']['materials']:.0f} per unit\n{materials_desc}"
        )
        if top:
            self.ui.action_panel.set_recommendation(recommendation_sentence(forecast))
        else:
            self.ui.action_panel.set_recommendation("Keep core supplies balanced.")
        self.ui.action_panel.prompt_label.setText(
            "1. Read the urgent problem.\n"
            "2. Choose supplies and a priority.\n"
            "3. Add a policy only if the tradeoff is worth it."
        )
        emergency_total = (
            self.ui.action_panel.energy_input.value() * self.engine.scenario["unit_costs"]["energy"]
            + self.ui.action_panel.water_input.value() * self.engine.scenario["unit_costs"]["water"]
            + self.ui.action_panel.food_input.value() * self.engine.scenario["unit_costs"]["food"]
            + self.ui.action_panel.fuel_input.value() * self.engine.scenario["unit_costs"]["fuel"]
            + self.ui.action_panel.materials_input.value() * self.engine.scenario["unit_costs"]["materials"]
        )
        selected_policy = self.ui.action_panel.selected_policy()
        benefit = recommendation_sentence(forecast)
        remaining_risk = risk_label(top["issue_id"], forecast) if top else "No major remaining risk"
        commit_lines = [
            f"You are spending ${emergency_total:.0f} in emergency supplies.",
            f"Policy spend from town budget: ${float(selected_policy['cost']) if selected_policy else 0.0:.0f}.",
            f"Likely benefit: {benefit}",
            f"Main remaining risk: {remaining_risk}.",
        ]
        self.ui.action_panel.set_commit_summary(commit_lines)

    def refresh(self, initial=False):
        forecast = self.engine.build_forecast(self.engine.state)
        self.ui.dashboard.update(self.engine.state, forecast)
        self.ui.forecast.update(forecast, self.last_result)
        self.ui.support_rail.update(forecast, self.engine.state, self.last_result)
        self.ui.log.title.setText(forecast.get("resolved_view", {}).get("panel_text", {}).get("review_label", "Journal"))
        self._apply_header(forecast)
        self.refresh_action_context()
        if initial:
            self.journal_entries = [self.engine.build_startup_journal()]
            self.ui.log.set_entries(self.journal_entries)
        self._apply_view_mode()

    def _apply_view_mode(self):
        has_result = has_turn_result(self.last_result)
        self.ui.forecast.set_post_turn_mode(has_result)
        self.ui.log.set_compact_mode(not has_result)
        self.ui.body_splitter.setSizes([680, 140] if not has_result else [560, 260])
        self.ui.right_splitter.setSizes([520, 180] if not has_result else [460, 220])

    def run_turn(self):
        actions = self.ui.action_panel.get_actions()
        result = self.engine.step(actions)
        self.last_result = result
        self.ui.dashboard.update(result["state"], result["forecast"])
        self.ui.forecast.update(result["forecast"], result)
        self.ui.support_rail.update(result["forecast"], result["state"], result)
        self.ui.log.title.setText(result["forecast"].get("resolved_view", {}).get("panel_text", {}).get("review_label", "Journal"))
        self._apply_header(result["forecast"])
        self.ui.action_panel.reset_inputs()
        self.refresh_action_context()
        self.journal_entries.append(result["journal"])
        self.ui.log.set_entries(self.journal_entries)
        self._apply_view_mode()
