from asyncio import sleep
from subprocess import run

from pathvalidate import sanitize_filepath
from textual import events, on, work
from textual.app import ComposeResult
from textual.containers import Container, Grid, HorizontalGroup, VerticalGroup
from textual.content import Content
from textual.screen import ModalScreen
from textual.validation import Length
from textual.widgets import Button, Input, Label, OptionList, Switch
from textual.widgets.option_list import Option

from . import utils
from .utils import config


class Dismissable(ModalScreen):
    """Super simple screen that can be dismissed."""

    def __init__(self, message: str, **kwargs) -> None:
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
        match event.key:
            case "escape" | "enter":
                event.stop()
                self.dismiss()
            case "tab":
                event.stop()
                self.focus_next()
            case "shift+tab":
                event.stop()
                self.focus_previous()

    @on(Button.Pressed, "#ok")
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss()


class YesOrNo(ModalScreen):
    """Screen with a dialog that asks whether you accept or deny"""

    def __init__(
        self,
        message: str,
        reverse_color: bool = False,
        with_toggle: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.message = message
        self.reverse_color = reverse_color
        self.with_toggle = with_toggle

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
            if self.with_toggle:
                with HorizontalGroup(id="dontAskAgain"):
                    yield Switch()
                    yield Label("Don't \\[a]sk again")

    def on_mount(self) -> None:
        self.query_one("#dialog").classes = "with_toggle" if self.with_toggle else ""

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        match event.key.lower():
            case "y":
                event.stop()
                self.dismiss(
                    {"value": True, "toggle": self.query_one(Switch).value}
                    if self.with_toggle
                    else True
                )
            case "n" | "escape":
                event.stop()
                self.dismiss(
                    {"value": False, "toggle": self.query_one(Switch).value}
                    if self.with_toggle
                    else False
                )
            case "a":
                event.stop()
                self.query_one(Switch).action_toggle_switch()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(
            {"value": event.button.id == "yes", "toggle": self.query_one(Switch).value}
            if self.with_toggle
            else event.button.id == "yes"
        )


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


class ZToDirectory(ModalScreen):
    """Screen with a dialog to z to a directory, using zoxide"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._queued_task = None
        self._queued_task_args: str | None = None

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
        self.zoxide_updater(Input.Changed(zoxide_input, value=""))

    def on_input_changed(self, event: Input.Changed) -> None:
        if any(
            worker.is_running and worker.node is self for worker in self.app.workers
        ):
            self._queued_task = self.zoxide_updater
            self._queued_task_args = event
        else:
            self.zoxide_updater(event=event)

    def any_in_queue(self) -> bool:
        if self._queued_task is not None:
            self._queued_task(self._queued_task_args)
            self._queued_task, self._queued_task_args = None, None
            return True
        return False

    @work(thread=True)
    def zoxide_updater(self, event: Input.Changed) -> None:
        """Update the list"""
        search_term = self.query_one("#zoxide_input").value.strip()
        # check 1 for queue, to ignore subprocess as a whole
        if self.any_in_queue():
            return
        zoxide_output = run(
            ["zoxide", "query", "--list"] + search_term.split(),
            capture_output=True,
            text=True,
        )
        # check 2 for queue, to ignore mounting as a whole
        if self.any_in_queue():
            return
        zoxide_options = self.query_one("#zoxide_options", OptionList)
        zoxide_options.add_class("empty")
        options = []
        if zoxide_output.stdout:
            for line in zoxide_output.stdout.splitlines():
                options.append(Option(Content(f" {line}"), id=utils.compress(line)))
            if len(options) == len(zoxide_options.options) and all(
                options[i].id == zoxide_options.options[i].id
                for i in range(len(options))
            ):  # ie same~ish query, resulting in same result
                pass
            else:
                # unline normally, im using an add_option**s** function
                # using it without has a likelyhood of DuplicateID being
                # raised, or just nothing showing up. By having the clear
                # options and add options functions nearby, it hopefully
                # reduces the likelihood of an empty option list
                self.app.call_from_thread(zoxide_options.clear_options)
                self.app.call_from_thread(zoxide_options.add_options, options)
                zoxide_options.remove_class("empty")
                zoxide_options.highlighted = 0
        else:
            # No Matches to the query text
            self.app.call_from_thread(zoxide_options.clear_options)
            self.app.call_from_thread(
                zoxide_options.add_option,
                Option("  --No matches found--", disabled=True),
            )
        # check 3, if somehow theres a new request after the mount
        if self.any_in_queue():
            return  # nothing much to do now
        else:
            self._queued_task = None

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
        match event.key:
            case "escape":
                event.stop()
                self.dismiss(None)
            case "down":
                event.stop()
                zoxide_options = self.query_one("#zoxide_options")
                if zoxide_options.options:
                    zoxide_options.action_cursor_down()
            case "up":
                event.stop()
                zoxide_options = self.query_one("#zoxide_options")
                if zoxide_options.options:
                    zoxide_options.action_cursor_up()
            case "tab":
                event.stop()
                self.focus_next()
            case "shift+tab":
                event.stop()
                self.focus_previous()


class ModalInput(ModalScreen):
    def __init__(
        self,
        border_title: str,
        border_subtitle: str = "",
        initial_value: str = "",
        validators: list = [],
        is_path: bool = False,
        is_folder: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.border_title = border_title
        self.border_subtitle = border_subtitle
        self.initial_value = initial_value
        self.validators = [
            Length(minimum=1, failure_description="A value is required.")
        ] + validators
        self.is_path = is_path
        self.is_folder = is_folder
        if self.is_path:
            self.icon_widget = Label(
                f"> {utils.get_icon('file', 'default')[0]} ", id="icon", shrink=True
            )
        else:
            self.icon_widget = Label("> ", id="icon", shrink=True)

    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield self.icon_widget
            yield Input(
                id="input",
                compact=True,
                value=self.initial_value,
                valid_empty=False,
                validators=self.validators,
                validate_on=["changed", "submitted"],
            )

    @work(exclusive=True)
    async def on_input_changed(self, event: Input.Changed) -> None:
        if self.is_path:
            if (
                event.value == self.initial_value and event.value != ""
            ) or self.query_one(Input).is_valid:
                self.icon_widget.classes = "valid"
                self.horizontal_group.classes = "valid"
                self.horizontal_group.border_subtitle = self.border_subtitle
            else:
                self.icon_widget.classes = "invalid"
                self.horizontal_group.classes = "invalid"
                try:
                    self.horizontal_group.border_subtitle = str(
                        event.validation_result.failure_descriptions[0]
                    )
                except AttributeError:
                    self.horizontal_group.border_subtitle = self.border_subtitle
            if event.value.replace("\\", "/").endswith("/"):
                # dir
                icon = utils.get_icon_for_folder(event.value[:-1])
            elif self.is_folder:
                # dir
                icon = utils.get_icon_for_folder(event.value)
            else:
                # file
                icon = utils.get_icon_for_file(event.value)
            self.icon_widget.update(
                Content.from_markup(f"> [{icon[1]}]{icon[0]}[{icon[1]}] ")
            )

    def on_mount(self) -> None:
        self.horizontal_group: HorizontalGroup = self.query_one(HorizontalGroup)
        inp: Input = self.query_one(Input)
        self.horizontal_group.border_title = self.border_title
        if self.border_subtitle != "":
            self.horizontal_group.border_subtitle = self.border_subtitle
        inp.focus()
        inp.validate(inp.value)
        self.on_input_changed(inp.Changed(inp, inp.value))

    @work
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if not self.query_one(Input).is_valid and any(
            failure.validator.strict for failure in event.validation_result.failures
        ):
            # shake
            for i in range(2):
                self.horizontal_group.styles.offset = (1, 0)
                await sleep(0.1)
                self.horizontal_group.styles.offset = (0, 0)
                await sleep(0.1)
            return
        self.dismiss(
            sanitize_filepath(event.input.value) if self.is_path else event.input.value
        )

    def on_key(self, event: events.Key) -> None:
        """Handle escape key to dismiss the dialog."""
        if event.key == "escape":
            event.stop()
            self.dismiss("")
