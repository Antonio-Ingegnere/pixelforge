from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._edit = QPlainTextEdit()
        self._edit.setReadOnly(True)
        self._edit.setMaximumBlockCount(2000)
        self._edit.setPlaceholderText("— ready —")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
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
        fmt.setForeground(QColor("#e05555"))
        cursor.insertText(f"ERROR: {text}\n", fmt)
        self._edit.setTextCursor(cursor)
        self._edit.verticalScrollBar().setValue(
            self._edit.verticalScrollBar().maximum()
        )

    def append_ok(self, text: str):
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#5dbb8e"))
        cursor.insertText(f"{text}\n", fmt)
        self._edit.setTextCursor(cursor)
        self._edit.verticalScrollBar().setValue(
            self._edit.verticalScrollBar().maximum()
        )
