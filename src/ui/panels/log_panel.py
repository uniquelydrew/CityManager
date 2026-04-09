from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from src.ui.formatters import journal_entry_lines


class LogPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("Journal")
        self.subtitle = QLabel(
            "This journal keeps a running record of what happened, why it happened, and what to watch next."
        )
        self.subtitle.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.log)
        self.entries = []

    def set_compact_mode(self, compact: bool):
        self.log.setMinimumHeight(120 if compact else 220)

    def set_entries(self, entries):
        self.entries = list(entries)
        rendered = []
        for entry in self.entries:
            rendered.append("\n".join(journal_entry_lines(entry)))
        self.log.setPlainText("\n\n".join(rendered))
