from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.engine import SimulationEngine
from src.ui.controller import UIController
from src.ui.panels.action_panel import ActionPanel
from src.ui.panels.forecast_panel import ForecastPanel
from src.ui.panels.log_panel import LogPanel
from src.ui.panels.system_dashboard import SystemDashboard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Town Recovery Simulation")
        self.resize(1280, 860)

        self.central = QWidget()
        self.setCentralWidget(self.central)

        self.root_layout = QVBoxLayout(self.central)
        self.root_layout.setContentsMargins(8, 8, 8, 8)
        self.root_layout.setSpacing(8)

        self._build_top_bar()
        self._build_body()
        self._assemble_panels()

        data_dir = str(Path(__file__).resolve().parents[2] / "data")
        self.engine = SimulationEngine(data_dir)
        self.controller = UIController(self.engine, self)

    def _build_top_bar(self):
        self.top_bar = QHBoxLayout()
        self.title_label = QLabel("Town Recovery Simulation")
        self.goal_label = QLabel("Goal: keep the town stable for 2 safe turns.")
        self.goal_note_label = QLabel(
            "A safe turn means no critical shortages and the budget stays healthy."
        )
        self.status_label = QLabel("Current urgent problem: loading...")
        for label in [self.goal_label, self.goal_note_label, self.status_label]:
            label.setWordWrap(True)
        self.header_text = QVBoxLayout()
        self.header_text.addWidget(self.title_label)
        self.header_text.addWidget(self.goal_label)
        self.header_text.addWidget(self.goal_note_label)
        self.top_bar.addLayout(self.header_text)
        self.top_bar.addStretch(1)
        self.top_bar.addWidget(self.status_label)
        self.root_layout.addLayout(self.top_bar)

    def _build_body(self):
        self.body_splitter = QSplitter(Qt.Orientation.Vertical)
        self.root_layout.addWidget(self.body_splitter, 1)

        self.left_panel = QFrame()
        self.center_panel = QFrame()
        self.right_panel = QFrame()
        self.bottom_panel = QFrame()

        self.top_content = QWidget()
        self.top_grid = QGridLayout(self.top_content)
        self.top_grid.setContentsMargins(0, 0, 0, 0)
        self.top_grid.setHorizontalSpacing(12)
        self.top_grid.setVerticalSpacing(12)
        self.top_grid.addWidget(self.left_panel, 0, 0)
        self.top_grid.addWidget(self.center_panel, 0, 1)
        self.top_grid.addWidget(self.right_panel, 0, 2)
        self.top_grid.setColumnStretch(0, 2)
        self.top_grid.setColumnStretch(1, 4)
        self.top_grid.setColumnStretch(2, 2)
        self.top_grid.setRowStretch(0, 1)

        self.body_splitter.addWidget(self.top_content)
        self.body_splitter.addWidget(self.bottom_panel)
        self.body_splitter.setStretchFactor(0, 4)
        self.body_splitter.setStretchFactor(1, 2)
        self.body_splitter.setChildrenCollapsible(False)
        self.bottom_panel.setMinimumHeight(220)

    def _assemble_panels(self):
        self.dashboard = SystemDashboard()
        self.forecast = ForecastPanel()
        self.action_panel = ActionPanel()
        self.log = LogPanel()

        self.left_panel.setLayout(QVBoxLayout())
        self.left_panel.layout().setContentsMargins(0, 0, 0, 0)
        self.left_panel.layout().addWidget(self.dashboard)

        self.center_panel.setLayout(QVBoxLayout())
        self.center_panel.layout().setContentsMargins(0, 0, 0, 0)
        self.center_panel.layout().addWidget(self.forecast)

        self.right_scroll = QScrollArea()
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.right_scroll.setWidget(self.action_panel)
        self.right_panel.setLayout(QVBoxLayout())
        self.right_panel.layout().setContentsMargins(0, 0, 0, 0)
        self.right_panel.layout().addWidget(self.right_scroll)

        self.bottom_panel.setLayout(QVBoxLayout())
        self.bottom_panel.layout().setContentsMargins(0, 0, 0, 0)
        self.bottom_panel.layout().addWidget(self.log)

        self._apply_responsive_layout()

    def _apply_responsive_layout(self):
        width = self.width()
        self.top_grid.removeWidget(self.left_panel)
        self.top_grid.removeWidget(self.center_panel)
        self.top_grid.removeWidget(self.right_panel)

        if width < 1150:
            self.top_grid.addWidget(self.left_panel, 0, 0, 1, 2)
            self.top_grid.addWidget(self.center_panel, 1, 0, 1, 2)
            self.top_grid.addWidget(self.right_panel, 2, 0, 1, 2)
            self.top_grid.setColumnStretch(0, 1)
            self.top_grid.setColumnStretch(1, 1)
        else:
            self.top_grid.addWidget(self.left_panel, 0, 0)
            self.top_grid.addWidget(self.center_panel, 0, 1)
            self.top_grid.addWidget(self.right_panel, 0, 2)
            self.top_grid.setColumnStretch(0, 2)
            self.top_grid.setColumnStretch(1, 4)
            self.top_grid.setColumnStretch(2, 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()


def launch_gui():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
