from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui.formatters import (
    advanced_model_lines,
    case_background_lines,
    glossary_entries,
    skill_support_lines,
    systems_reference_lines,
)


class SupportRail(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.title = QLabel("Help and Reference")
        self.title.setWordWrap(True)

        self.tabs = QTabWidget()

        self.quick_help = QWidget()
        quick_layout = QVBoxLayout(self.quick_help)
        quick_layout.setContentsMargins(0, 0, 0, 0)
        quick_layout.setSpacing(6)
        self.glossary_search = QLineEdit()
        self.glossary_search.setPlaceholderText("Search terms used in this scenario")
        self.glossary_list = QListWidget()
        self.glossary_detail = QPlainTextEdit()
        self.glossary_detail.setReadOnly(True)
        self.glossary_detail.setMinimumHeight(120)
        quick_layout.addWidget(QLabel("Quick Explain"))
        quick_layout.addWidget(self.glossary_search)
        quick_layout.addWidget(self.glossary_list)
        quick_layout.addWidget(self.glossary_detail)

        self.background = QPlainTextEdit()
        self.background.setReadOnly(True)

        self.systems = QPlainTextEdit()
        self.systems.setReadOnly(True)

        self.skills = QPlainTextEdit()
        self.skills.setReadOnly(True)

        self.advanced = QWidget()
        advanced_layout = QVBoxLayout(self.advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(6)
        self.advanced_toggle = QCheckBox("Show advanced model detail")
        self.advanced_text = QPlainTextEdit()
        self.advanced_text.setReadOnly(True)
        self.advanced_text.setVisible(False)
        advanced_layout.addWidget(self.advanced_toggle)
        advanced_layout.addWidget(self.advanced_text)

        self.tabs.addTab(self.quick_help, "Glossary")
        self.tabs.addTab(self.background, "Background")
        self.tabs.addTab(self.systems, "Systems")
        self.tabs.addTab(self.skills, "GED Skills")
        self.tabs.addTab(self.advanced, "Advanced")

        layout.addWidget(self.title)
        layout.addWidget(self.tabs)

        self._glossary_items: List[Dict[str, str]] = []
        self.glossary_search.textChanged.connect(self._populate_glossary)
        self.glossary_list.currentItemChanged.connect(self._show_glossary_detail)
        self.advanced_toggle.toggled.connect(self.advanced_text.setVisible)

    def update(self, forecast: Dict, state: Dict, result: Dict | None = None) -> None:
        overlay_text = forecast.get("resolved_view", {}).get("overlay_text", {})
        self.title.setText(forecast.get("resolved_view", {}).get("action_text", {}).get("inspect_label", "Help and Reference"))
        self.tabs.setTabText(0, overlay_text.get("glossary_tab", "Glossary"))
        self.tabs.setTabText(1, overlay_text.get("background_tab", "Background"))
        self.tabs.setTabText(2, overlay_text.get("systems_tab", "Systems"))
        self.tabs.setTabText(3, overlay_text.get("skills_tab", "GED Skills"))
        self.tabs.setTabText(4, overlay_text.get("advanced_tab", "Advanced"))
        self._glossary_items = glossary_entries(forecast)
        self._populate_glossary(self.glossary_search.text())
        self.background.setPlainText("\n".join(case_background_lines(forecast)))
        self.systems.setPlainText("\n".join(systems_reference_lines(forecast, state)))
        self.skills.setPlainText("\n".join(skill_support_lines(forecast)))
        self.advanced_text.setPlainText("\n".join(advanced_model_lines(forecast, state, result)))

    def _populate_glossary(self, query: str) -> None:
        current_term = self.glossary_list.currentItem().text() if self.glossary_list.currentItem() else None
        self.glossary_list.blockSignals(True)
        self.glossary_list.clear()
        query = query.strip().lower()
        filtered = [
            entry for entry in self._glossary_items
            if not query or query in entry["term"].lower() or query in entry["definition"].lower()
        ]
        for entry in filtered:
            item = QListWidgetItem(entry["term"])
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.glossary_list.addItem(item)
        self.glossary_list.blockSignals(False)

        if self.glossary_list.count() == 0:
            self.glossary_detail.setPlainText("No matching glossary entry.")
            return

        target_index = 0
        if current_term:
            for index in range(self.glossary_list.count()):
                if self.glossary_list.item(index).text() == current_term:
                    target_index = index
                    break
        self.glossary_list.setCurrentRow(target_index)
        self._show_glossary_detail(self.glossary_list.currentItem(), None)

    def _show_glossary_detail(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if not current:
            self.glossary_detail.setPlainText("Select a term to read a plain-language explanation.")
            return
        entry = current.data(Qt.ItemDataRole.UserRole) or {}
        detail_lines = [
            entry.get("term", ""),
            "",
            entry.get("definition", ""),
        ]
        why_it_matters = entry.get("why_it_matters")
        if why_it_matters:
            detail_lines.extend(["", "Why it matters here:", why_it_matters])
        related = entry.get("related")
        if related:
            detail_lines.extend(["", "Related terms:", ", ".join(related)])
        self.glossary_detail.setPlainText("\n".join(detail_lines))
