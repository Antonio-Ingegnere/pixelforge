from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._edit = QPlainTextEdit()
        self._edit.setReadOnly(True)
        self._edit.setMaximumBlockCount(2000)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self._edit.clear)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(clear_btn)
        layout.addWidget(self._edit)

    def append(self, text: str):
        self._edit.appendPlainText(text)
        self._edit.verticalScrollBar().setValue(
            self._edit.verticalScrollBar().maximum()
        )

    def append_error(self, text: str):
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#ff6b6b"))
        cursor.insertText(f"ERROR: {text}\n", fmt)
        self._edit.setTextCursor(cursor)
        self._edit.verticalScrollBar().setValue(
            self._edit.verticalScrollBar().maximum()
        )

    def append_ok(self, text: str):
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#6bffb8"))
        cursor.insertText(f"{text}\n", fmt)
        self._edit.setTextCursor(cursor)
        self._edit.verticalScrollBar().setValue(
            self._edit.verticalScrollBar().maximum()
        )
