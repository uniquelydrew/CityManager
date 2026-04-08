from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from src.resource_utils import stock
from src.ui.formatters import active_policy_text, case_title_text, state_status_snapshot, title_case_label


class SystemDashboard(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.title = QLabel("Town Status")
        self.case_title = QLabel("Historical Case")
        self.water = self._make_bar("Water")
        self.energy = self._make_bar("Energy")
        self.food = self._make_bar("Food")
        self.health = self._make_bar("Health")
        self.budget = QLabel("Budget: $0.00")
        self.turn = QLabel("Turn: 1")
        self.streak = QLabel("Goal progress: 0 of 2 safe turns")
        self.supporting = QLabel("Fuel: 0 | Materials: 0 | Workforce: 0")
        self.supporting.setWordWrap(True)
        self.active_policies = QLabel("No active town policies.")
        self.active_policies.setWordWrap(True)
        self.civic_status = QLabel("Legitimacy: 0.00 | Trust: 0.00 | Coalition: 0.00")
        self.civic_status.setWordWrap(True)
        self.status_summary = QLabel("Most urgent problem: none")
        self.status_summary.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.case_title)
        for item in [self.water, self.energy, self.food, self.health]:
            layout.addWidget(item["label"])
            layout.addWidget(item["bar"])
        layout.addWidget(self.budget)
        layout.addWidget(self.turn)
        layout.addWidget(self.streak)
        layout.addWidget(self.supporting)
        layout.addWidget(self.active_policies)
        layout.addWidget(self.civic_status)
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
        self.case_title.setText(case_title_text(forecast))
        self.water["bar"].setValue(int(max(0, min(100, stock(state["resources"], "water")))))
        self.energy["bar"].setValue(int(max(0, min(100, stock(state["resources"], "energy")))))
        self.food["bar"].setValue(int(max(0, min(100, stock(state["resources"], "food")))))
        self.health["bar"].setValue(int(max(0, min(100, state["population"]["health"] * 100))))
        self.water["label"].setText(f"Water: {stock(state['resources'], 'water'):.0f} | {statuses['water']}")
        self.energy["label"].setText(f"Energy: {stock(state['resources'], 'energy'):.0f} | {statuses['energy']}")
        self.food["label"].setText(f"Food: {stock(state['resources'], 'food'):.0f} | {statuses['food']}")
        self.health["label"].setText(
            f"Health: {state['population']['health'] * 100:.0f} | {statuses['health']}"
        )
        self.budget.setText(f"Budget: ${state['economy']['budget']:.2f}")
        self.turn.setText(f"Turn: {state['telemetry'].get('turn', 1)}")
        self.streak.setText(
            f"Goal progress: {state['telemetry'].get('stable_turn_streak', 0)} of 2 safe turns"
        )
        self.supporting.setText(
            f"Fuel: {stock(state['resources'], 'fuel'):.0f} | "
            f"Materials: {stock(state['resources'], 'materials'):.0f} | "
            f"Workforce: {stock(state['resources'], 'workforce_capacity'):.0f}"
        )
        self.active_policies.setText(active_policy_text(state))
        self.civic_status.setText(
            f"Legitimacy: {state['governance']['legitimacy']:.2f} | "
            f"Trust: {state['society']['public_trust']:.2f} | "
            f"Coalition: {state['politics']['coalition_stability']:.2f}"
        )
        if forecast["risk_ranking"]:
            top = forecast["risk_ranking"][0]
            self.status_summary.setText(
                f"Most urgent problem: {title_case_label(top['issue_id'])}"
            )
        else:
            self.status_summary.setText("Most urgent problem: none")
