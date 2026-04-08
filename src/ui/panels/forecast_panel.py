from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QSizePolicy, QSplitter, QVBoxLayout, QWidget

from src.ui.formatters import (
    affected_group_lines,
    consequence_sentence,
    historical_situation_text,
    improvement_lines,
    outlook_lines,
    political_constraint_lines,
    resource_flow_lines,
    system_pressure_lines,
    top_risk_cards,
    urgent_problem_sentence,
)


class ForecastPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.splitter = QSplitter(Qt.Orientation.Vertical)

        self.problem = self._make_card("Historical Situation", 90)
        self.goal = self._make_card("What Happens Next", 140)
        self.flow = self._make_card("Power and Supply Flow", 140)
        self.links = self._make_card("Who Is Affected", 120)
        self.improves = self._make_card("Political Constraints", 110)
        self.pressures = self._make_card("System Pressures", 110)
        self.risks = self._make_card("Urgent Problems and Responses", 150)

        for card in [self.problem, self.goal, self.flow, self.links, self.improves, self.pressures, self.risks]:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            container_layout.addWidget(card["label"])
            container_layout.addWidget(card["body"])
            self.splitter.addWidget(container)
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

    def update(self, forecast):
        self.problem["body"].setPlainText(
            historical_situation_text(forecast) + "\n" + urgent_problem_sentence(forecast)
        )
        self.goal["body"].setPlainText(
            "\n".join(outlook_lines(forecast)) or "No next-turn forecast is available."
        )
        self.flow["body"].setPlainText("\n".join(resource_flow_lines(forecast)))
        self.links["body"].setPlainText("\n".join(affected_group_lines(forecast)))
        self.improves["body"].setPlainText("\n".join(political_constraint_lines(forecast)))
        self.pressures["body"].setPlainText("\n".join(system_pressure_lines(forecast)))
        self.risks["body"].setPlainText(
            "\n\n".join(top_risk_cards(forecast) + ["\n".join(improvement_lines(forecast))])
        )
