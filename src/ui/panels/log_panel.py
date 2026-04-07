from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget


class LogPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("What You Learned")
        self.subtitle = QLabel("Each turn, this panel explains what you chose, what changed, and what to focus on next.")
        self.subtitle.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(220)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.log)

    def append(self, text):
        self.log.appendPlainText(text)
