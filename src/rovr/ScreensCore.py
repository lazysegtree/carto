from subprocess import run

from textual import events, on, work
from textual.app import ComposeResult
from textual.containers import Container, Grid, HorizontalGroup, VerticalGroup
from textual.content import Content
from textual.screen import ModalScreen
from textual.types import DuplicateID
from textual.widgets import Button, Input, Label, OptionList, Switch
from textual.widgets.option_list import Option

from . import utils


class Dismissable(ModalScreen):
    """Super simple screen that can be dismissed."""

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label(self.message, id="message")
            with Container():
                yield Button("Ok", variant="primary", id="ok")

    def on_mount(self) -> None:
        self.query_one("#ok").focus()

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        if event.key in ["escape", "enter"]:
            event.stop()
            self.dismiss()
        elif event.key == "tab":
            event.stop()
            self.focus_next()
        elif event.key == "shift+tab":
            event.stop()
            self.focus_previous()

    @on(Button.Pressed, "#ok")
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss()


class YesOrNo(ModalScreen):
    """Screen with a dialog that asks whether you accept or deny"""

    def __init__(self, message: str, reverse_color: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.reverse_color = reverse_color

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            with VerticalGroup(id="question_container"):
                for message in self.message.splitlines():
                    yield Label(message, classes="question")
            yield Button(
                "\\[Y]es",
                variant="error" if self.reverse_color else "primary",
                id="yes",
            )
            yield Button(
                "\\[N]o", variant="primary" if self.reverse_color else "error", id="no"
            )

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        if event.key.lower() == "y":
            event.stop()
            self.dismiss(True)
        elif event.key.lower() in ["n", "escape"]:
            event.stop()
            self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class CopyOverwrite(ModalScreen):
    """Screen with a dialog to confirm whether to overwrite, rename, skip or cancel."""

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label(self.message, id="question")
            yield Button("\\[O]verwrite", variant="error", id="overwrite")
            yield Button("\\[R]ename", variant="warning", id="rename")
            yield Button("\\[S]kip", variant="default", id="skip")
            yield Button("\\[C]ancel", variant="primary", id="cancel")
            with HorizontalGroup(id="dontAskAgain"):
                yield Switch()
                yield Label("Don't ask again")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss({
            "value": event.button.id,
            "same_for_next": self.query_one(Switch).value,
        })

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key.lower() == "o":
            event.stop()
            self.dismiss({
                "value": "overwrite",
                "same_for_next": self.query_one(Switch).value,
            })
        elif event.key.lower() == "r":
            event.stop()
            self.dismiss({
                "value": "rename",
                "same_for_next": self.query_one(Switch).value,
            })
        elif event.key.lower() == "s":
            event.stop()
            self.dismiss({
                "value": "skip",
                "same_for_next": self.query_one(Switch).value,
            })
        elif event.key.lower() in ["c", "escape"]:
            event.stop()
            self.dismiss({
                "value": "cancel",
                "same_for_next": self.query_one(Switch).value,
            })


class DeleteFiles(ModalScreen):
    """Screen with a dialog to confirm whether to delete files."""

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label(self.message, id="question")
            yield Button("\\[D]elete", variant="error", id="delete")
            yield Button("\\[T]rash", variant="warning", id="trash")
            with Container():
                yield Button("\\[C]ancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss(event.button.id)

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key.lower() == "d":
            event.stop()
            self.dismiss("delete")
        elif event.key.lower() in ["c", "escape"]:
            event.stop()
            self.dismiss("cancel")
        elif event.key.lower() == "t":
            event.stop()
            self.dismiss("trash")
        elif event.key == "tab":
            event.stop()
            self.focus_next()
        elif event.key == "shift+tab":
            event.stop()
            self.focus_previous()
        elif event.key == "enter":
            event.stop()
            self.query_one(f"#{self.focused.id}").action_press()


class ZToDirectory(ModalScreen):
    """Screen with a dialog to z to a directory, using zoxide"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._search_task = None  # To hold the current search task

    def compose(self) -> ComposeResult:
        with VerticalGroup(id="zoxide_group", classes="zoxide_group"):
            yield Input(
                id="zoxide_input",
                placeholder="Enter directory name or pattern",
            )
            yield OptionList(
                Option("  No input provided", disabled=True),
                id="zoxide_options",
                classes="empty",
            )

    def on_mount(self) -> None:
        zoxide_input = self.query_one("#zoxide_input")
        zoxide_input.border_title = "zoxide"
        zoxide_input.focus()
        zoxide_options = self.query_one("#zoxide_options")
        zoxide_options.border_title = "Folders"
        zoxide_options.can_focus = False
        self.on_input_changed(Input.Changed(zoxide_input, value=""))

    @work(thread=True, exclusive=True)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Update the list"""
        search_term = self.query_one("#zoxide_input").value.strip()
        zoxide_output = run(
            ["zoxide", "query", "--list"] + search_term.split(),
            capture_output=True,
            text=True,
        )
        zoxide_options = self.query_one("#zoxide_options")
        zoxide_options.add_class("empty")
        options = []
        try:
            if zoxide_output.stdout:
                # unline normally, im using an add_option**s** function
                # using it without has a likelyhood of DuplicateID being
                # raised, or just nothing showing up. By having the clear
                # options and add options functions nearby, it hopefully
                # reduces the likelihood of an empty option list
                for line in zoxide_output.stdout.splitlines():
                    options.append(Option(Content(f" {line}"), id=utils.compress(line)))
                self.app.call_from_thread(zoxide_options.clear_options)
                self.app.call_from_thread(zoxide_options.add_options, options)
                zoxide_options.remove_class("empty")
                zoxide_options.highlighted = 0
            else:
                self.app.call_from_thread(zoxide_options.clear_options)
                self.app.call_from_thread(
                    zoxide_options.add_option,
                    Option("  --No matches found--", disabled=True),
                )
        except DuplicateID:
            # if this function runs again somehow, this helps solve it partially
            # testing it here, before I can see what I can do in other places
            if self._search_task:
                self._search_task.cancel()
            self._search_task = self.set_timer(
                0.25, self.query_one(Input).action_submit
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        zoxide_options = self.query_one("#zoxide_options")
        if zoxide_options.highlighted is None:
            zoxide_options.highlighted = 0
        zoxide_options.action_select()

    # You cant manually tab into the option list, but you can click, so I guess
    @work(exclusive=True)
    async def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle option selection."""
        selected_value = event.option.id
        run(
            ["zoxide", "add", utils.decompress(selected_value)],
            capture_output=True,
            text=True,
        )
        if selected_value:
            self.dismiss(selected_value)
        else:
            self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        if event.key in ["escape"]:
            event.stop()
            self.dismiss(None)
        elif event.key == "down":
            event.stop()
            zoxide_options = self.query_one("#zoxide_options")
            if zoxide_options.options:
                zoxide_options.action_cursor_down()
        elif event.key == "up":
            event.stop()
            zoxide_options = self.query_one("#zoxide_options")
            if zoxide_options.options:
                zoxide_options.action_cursor_up()
        elif event.key == "tab":
            event.stop()
            self.focus_next()
        elif event.key == "shift+tab":
            event.stop()
            self.focus_previous()


class ModalInput(ModalScreen):
    def __init__(
        self,
        border_title: str,
        border_subtitle: str = "",
        initial_value: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.border_title = border_title
        self.border_subtitle = border_subtitle
        self.initial_value = initial_value

    def compose(self) -> ComposeResult:
        with Container():
            yield Input(
                id="input",
                compact=True,
                value=self.initial_value,
            )

    def on_mount(self) -> None:
        self.query_one(Container).border_title = self.border_title
        if self.border_subtitle != "":
            self.query_one(Container).border_subtitle = self.border_subtitle
        self.query_one("#input").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        self.dismiss(event.input.value)

    def on_key(self, event: events.Key) -> None:
        """Handle escape key to dismiss the dialog."""
        if event.key == "escape":
            event.stop()
            self.dismiss("")
