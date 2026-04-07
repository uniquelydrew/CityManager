from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from src.ui.formatters import active_policy_text, state_status_snapshot, title_case_label


class SystemDashboard(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.title = QLabel("Town Status")
        self.water = self._make_bar("Water")
        self.energy = self._make_bar("Energy")
        self.food = self._make_bar("Food")
        self.health = self._make_bar("Health")
        self.budget = QLabel("Budget: $0.00")
        self.turn = QLabel("Turn: 1")
        self.streak = QLabel("Goal progress: 0 of 2 safe turns")
        self.active_policies = QLabel("No active town policies.")
        self.active_policies.setWordWrap(True)
        self.status_summary = QLabel("Most urgent problem: none")
        self.status_summary.setWordWrap(True)

        layout.addWidget(self.title)
        for item in [self.water, self.energy, self.food, self.health]:
            layout.addWidget(item["label"])
            layout.addWidget(item["bar"])
        layout.addWidget(self.budget)
        layout.addWidget(self.turn)
        layout.addWidget(self.streak)
        layout.addWidget(self.active_policies)
        layout.addWidget(self.status_summary)
        layout.addStretch(1)

    def _make_bar(self, name):
        label = QLabel(f"{name}:")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setFormat("%v")
        return {"label": label, "bar": bar}

    def update(self, state, forecast):
        statuses = state_status_snapshot(state, forecast)
        self.water["bar"].setValue(int(max(0, min(100, state["resources"]["water"]))))
        self.energy["bar"].setValue(int(max(0, min(100, state["resources"]["energy"]))))
        self.food["bar"].setValue(int(max(0, min(100, state["resources"]["food"]))))
        self.health["bar"].setValue(int(max(0, min(100, state["population"]["health"] * 100))))
        self.water["label"].setText(f"Water: {state['resources']['water']:.0f} | {statuses['water']}")
        self.energy["label"].setText(f"Energy: {state['resources']['energy']:.0f} | {statuses['energy']}")
        self.food["label"].setText(f"Food: {state['resources']['food']:.0f} | {statuses['food']}")
        self.health["label"].setText(
            f"Health: {state['population']['health'] * 100:.0f} | {statuses['health']}"
        )
        self.budget.setText(f"Budget: ${state['economy']['budget']:.2f}")
        self.turn.setText(f"Turn: {state['telemetry'].get('turn', 1)}")
        self.streak.setText(
            f"Goal progress: {state['telemetry'].get('stable_turn_streak', 0)} of 2 safe turns"
        )
        self.active_policies.setText(active_policy_text(state))
        if forecast["risk_ranking"]:
            top = forecast["risk_ranking"][0]
            self.status_summary.setText(
                f"Most urgent problem: {title_case_label(top['issue_id'])}"
            )
        else:
            self.status_summary.setText("Most urgent problem: none")
