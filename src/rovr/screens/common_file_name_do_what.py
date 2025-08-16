from textual import events
from textual.app import ComposeResult
from textual.containers import Grid, HorizontalGroup
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Switch


class CommonFileNameDoWhat(ModalScreen):
    """Screen with a dialog to confirm whether to overwrite, rename, skip or cancel."""

    def __init__(self, message: str, border_title: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.message = message
        self.border_title = border_title

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label(self.message, id="question")
            yield Button("\\[O]verwrite", variant="error", id="overwrite")
            yield Button("\\[R]ename", variant="warning", id="rename")
            yield Button("\\[S]kip", variant="default", id="skip")
            yield Button("\\[C]ancel", variant="primary", id="cancel")
            with HorizontalGroup(id="dontAskAgain"):
                yield Switch()
                yield Label("Don't \\[a]sk again")

    def on_mount(self) -> None:
        self.query_one("#dialog").border_title = self.border_title

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss({
            "value": event.button.id,
            "same_for_next": self.query_one(Switch).value,
        })

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        match event.key.lower():
            case "o":
                event.stop()
                self.dismiss({
                    "value": "overwrite",
                    "same_for_next": self.query_one(Switch).value,
                })
            case "r":
                event.stop()
                self.dismiss({
                    "value": "rename",
                    "same_for_next": self.query_one(Switch).value,
                })
            case "s":
                event.stop()
                self.dismiss({
                    "value": "skip",
                    "same_for_next": self.query_one(Switch).value,
                })
            case "c" | "escape":
                event.stop()
                self.dismiss({
                    "value": "cancel",
                    "same_for_next": self.query_one(Switch).value,
                })
            case "a":
                event.stop()
                self.query_one(Switch).action_toggle_switch()
