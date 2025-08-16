from textual import events
from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from rovr.utils import config


class DeleteFiles(ModalScreen):
    """Screen with a dialog to confirm whether to delete files."""

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label(self.message, id="question")
            yield Button("\\[D]elete", variant="error", id="delete")
            if config["settings"]["use_recycle_bin"]:
                yield Button("\\[T]rash", variant="warning", id="trash")
                with Container():
                    yield Button("\\[C]ancel", variant="primary", id="cancel")
            else:
                yield Button("\\[C]ancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss(event.button.id)

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        match event.key.lower():
            case "d":
                event.stop()
                self.dismiss("delete")
            case "c" | "escape":
                event.stop()
                self.dismiss("cancel")
            case "t" if config["settings"]["use_recycle_bin"]:
                event.stop()
                self.dismiss("trash")
            case "tab":
                event.stop()
                self.focus_next()
            case "shift+tab":
                event.stop()
                self.focus_previous()
            case "enter":
                event.stop()
                self.query_one(f"#{self.focused.id}").action_press()
