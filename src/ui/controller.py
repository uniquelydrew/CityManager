"""Thin controller that connects the PySide6 GUI to the simulation engine."""

from src.modifiers import can_select_policy
from src.ui.formatters import (
    current_problem_text,
    mission_text,
    policy_summary,
    policy_title,
    recommendation_sentence,
    top_risk,
    tutor_startup_lines,
    tutor_turn_lines,
)


class UIController:
    def __init__(self, engine, ui):
        self.engine = engine
        self.ui = ui
        self.ui.action_panel.submit_button.clicked.connect(self.run_turn)
        self.ui.action_panel.actions_changed.connect(self.refresh_action_context)
        self.refresh(initial=True)

    def _apply_header(self, forecast):
        self.ui.goal_label.setText(mission_text(forecast))
        self.ui.status_label.setText(current_problem_text(forecast))

    def _startup_message(self, forecast):
        return "\n".join(tutor_startup_lines(forecast))

    def format_turn_summary(self, result):
        return "\n".join(tutor_turn_lines(result))

    def refresh_action_context(self):
        self.ui.action_panel.set_context(
            self.engine.scenario["unit_costs"],
            self.engine.scenario["available_emergency_budget"],
        )
        forecast = self.engine.build_forecast(self.engine.state)
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
        if top:
            label = top["issue_id"]
            if label == "energy_instability":
                self.ui.action_panel.energy_help.setText(
                    f"Cost: ${self.engine.scenario['unit_costs']['energy']:.0f} per unit\n"
                    "Best first move for the current power risk."
                )
            if label == "water_shortage":
                self.ui.action_panel.water_help.setText(
                    f"Cost: ${self.engine.scenario['unit_costs']['water']:.0f} per unit\n"
                    "Helps protect homes while you stabilize pumps."
                )
            if label == "food_collapse":
                self.ui.action_panel.food_help.setText(
                    f"Cost: ${self.engine.scenario['unit_costs']['food']:.0f} per unit\n"
                    "Best first move for the current food risk."
                )
        self.ui.action_panel.prompt_label.setText(
            "Step 1: Read the urgent problem\n"
            "Step 2: Choose emergency supplies\n"
            "Step 3: Choose a policy if you want one\n"
            "Step 4: Run the turn\n\n"
            + recommendation_sentence(forecast)
        )

    def refresh(self, initial=False):
        forecast = self.engine.build_forecast(self.engine.state)
        self.ui.dashboard.update(self.engine.state, forecast)
        self.ui.forecast.update(forecast)
        self._apply_header(forecast)
        self.refresh_action_context()
        if initial:
            self.ui.log.append(self._startup_message(forecast))

    def run_turn(self):
        actions = self.ui.action_panel.get_actions()
        result = self.engine.step(actions)
        self.ui.dashboard.update(result["state"], result["forecast"])
        self.ui.forecast.update(result["forecast"])
        self._apply_header(result["forecast"])
        self.ui.action_panel.reset_inputs()
        self.refresh_action_context()
        self.ui.log.append(self.format_turn_summary(result))
