"""A formatted, word-wrapped view for the agent's prose response.

Streams plain text live for progress, then renders the final answer as
Markdown (headings, bold, lists, code) so a long response reads like a
document instead of an overflowing monospace dump.
"""

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextBrowser, QWidget


class ResponseView(QTextBrowser):
    """Rich, wrapped rendering of the assistant response."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "response")
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)
        # Word-wrap to the widget width (QTextBrowser default), never a
        # horizontal scrollbar.
        self.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self._buffer = ""

    def clear_response(self) -> None:
        self._buffer = ""
        self.clear()

    def append_stream(self, text: str) -> None:
        """Append a streamed chunk as plain text (live progress)."""
        self._buffer += text
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.insertPlainText(text if text.endswith("\n") else text + "\n")
        self.moveCursor(QTextCursor.MoveOperation.End)

    def render_markdown(self, text: str) -> None:
        """Replace the content with the final answer rendered as Markdown."""
        self._buffer = text
        self.setMarkdown(text)
        self.moveCursor(QTextCursor.MoveOperation.Start)

    def markdown(self) -> str:
        """The current response text (markdown source)."""
        return self._buffer
