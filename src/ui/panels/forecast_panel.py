from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QSizePolicy, QSplitter, QVBoxLayout, QWidget

from src.ui.formatters import (
    affected_group_lines,
    causal_chain_lines,
    delta_summary_lines,
    do_nothing_lines,
    immediate_crisis_lines,
    outlook_lines,
    political_constraint_lines,
    system_pressure_lines,
)


class ForecastPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.problem = self._make_card("Immediate Crisis", 150)
        self.delta = self._make_card("What Changed Since Last Turn", 100)
        self.goal = self._make_card("What Happens Next", 130)
        self.consequence = self._make_card("If You Do Nothing", 90)
        self.links = self._make_card("Who Is Affected", 120)
        self.causes = self._make_card("Why This Is Happening", 110)
        self.pressures = self._make_card("Political and System Pressures", 120)

        self.card_containers = {}
        for name, card in [
            ("problem", self.problem),
            ("delta", self.delta),
            ("goal", self.goal),
            ("consequence", self.consequence),
            ("links", self.links),
            ("causes", self.causes),
            ("pressures", self.pressures),
        ]:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            container_layout.addWidget(card["label"])
            container_layout.addWidget(card["body"])
            self.splitter.addWidget(container)
            self.card_containers[name] = container
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 2)
        self.splitter.setStretchFactor(3, 2)
        self.splitter.setStretchFactor(4, 2)
        self.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.splitter)

    def _make_card(self, title, min_height):
        label = QLabel(title)
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setMinimumHeight(min_height)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.setMaximumBlockCount(200)
        return {"label": label, "body": body}

    def set_post_turn_mode(self, has_result):
        self.card_containers["delta"].setVisible(has_result)
        self.delta["label"].setVisible(has_result)
        self.delta["body"].setVisible(has_result)
        self.problem["body"].setMinimumHeight(150 if not has_result else 120)

    def update(self, forecast, result=None):
        panel_text = forecast.get("resolved_view", {}).get("panel_text", {})
        self.problem["label"].setText(panel_text.get("current_problem_label", "Immediate Crisis"))
        self.delta["label"].setText(panel_text.get("what_changed_label", "What Changed Since Last Turn"))
        self.goal["label"].setText(panel_text.get("what_happens_next_label", "What Happens Next"))
        self.consequence["label"].setText(panel_text.get("if_you_do_nothing_label", "If You Do Nothing"))
        self.links["label"].setText(panel_text.get("who_is_affected_label", "Who Is Affected"))
        self.causes["label"].setText(panel_text.get("why_this_is_happening_label", "Why This Is Happening"))
        self.pressures["label"].setText(panel_text.get("system_pressures_label", "Political and System Pressures"))
        self.problem["body"].setPlainText(
            "\n".join(immediate_crisis_lines(forecast))
        )
        self.delta["body"].setPlainText(
            "\n".join(delta_summary_lines(result, forecast))
        )
        self.goal["body"].setPlainText(
            "\n".join(outlook_lines(forecast)) or "No next-turn forecast is available."
        )
        self.consequence["body"].setPlainText("\n".join(do_nothing_lines(forecast)))
        self.links["body"].setPlainText("\n".join(affected_group_lines(forecast)))
        self.causes["body"].setPlainText(
            "\n".join(causal_chain_lines(forecast))
        )
        self.pressures["body"].setPlainText("\n".join(system_pressure_lines(forecast)))
        self.pressures["body"].appendPlainText("")
        self.pressures["body"].appendPlainText("\n".join(political_constraint_lines(forecast)))
