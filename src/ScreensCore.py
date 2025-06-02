from subprocess import run
from textual import on, events, work
from textual.app import ComposeResult, App
from textual.containers import Grid, Container, VerticalGroup
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Input, OptionList, Static
from textual.widgets.option_list import Option
from textual.binding import Binding
import state


class Dismissable(ModalScreen):
    """Super simple screen that can be dismissed."""

    DEFAULT_CSS = """
    Dismissable {
        align: center middle;
    }
    #dialog {
        grid-size: 1;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 1 3;
        width: 50vw;
        max-height: 13;
        border: round $primary-lighten-3;
        column-span: 3;
    }
    #message {
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    Container {
        align: center middle;
    }
    Button {
        width: 50%;
    }
    """

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
        event.stop()
        """Handle key presses."""
        if event.key in "escape":
            self.dismiss()
        elif event.key == "tab":
            self.focus_next()
        elif event.key == "shift+tab":
            self.focus_previous()

    @on(Button.Pressed, "#ok")
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        self.dismiss()


class YesOrNo(ModalScreen):
    """Screen with a dialog to quit."""

    DEFAULT_CSS = """
    YesOrNo {
        align: center middle;
    }
    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 1 3;
        width: 50vw;
        max-height: 13;
        border: round $primary-lighten-3;
    }
    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    Button {
        width: 100%;
    }
    """

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        with Grid(id="dialog"):
            yield Label(self.message, id="question")
            yield Button("\\[Y]es", variant="error", id="yes")
            yield Button("\\[N]o", variant="primary", id="no")

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "y":
            self.dismiss(True)
        elif event.key in ["n", "escape"]:
            self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class CopyOverwrite(ModalScreen):
    """Screen with a dialog to confirm whether to overwrite, rename, skip or cancel."""

    DEFAULT_CSS = """
    CopyOverwrite {
        align: center middle;
    }
    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3 3;
        padding: 1 3;
        max-width: 50vw;
        max-height: 15;
        border: round $primary-lighten-3;
    }
    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    Button {
        width: 100%;
    }
    """

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

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "o":
            self.dismiss("overwrite")
        elif event.key == "r":
            self.dismiss("rename")
        elif event.key == "s":
            self.dismiss("skip")
        elif event.key in ["c", "escape"]:
            self.dismiss("cancel")


class DeleteFiles(ModalScreen):
    """Screen with a dialog to confirm whether to delete files."""

    DEFAULT_CSS = """
    DeleteFiles {
        align: center middle;
    }
    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 1 3;
        max-width: 50vw;
        max-height: 15;
        border: round $primary-lighten-3;
    }
    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    Button {
        width: 100%;
    }
    Container {
        column-span: 2;
        align: center middle;
    }
    Button#cancel {
        width: 50%;
    }
    """

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
        if event.button.id == "delete":
            self.dismiss("delete")
        elif event.button.id == "trash":
            self.dismiss("trash")
        elif event.button.id == "cancel":
            self.dismiss("cancel")

    def on_key(self, event) -> None:
        event.stop()
        """Handle key presses."""
        if event.key == "d":
            self.dismiss("delete")
        elif event.key in ["c", "escape"]:
            self.dismiss("cancel")
        elif event.key == "t":
            self.dismiss("trash")
        elif event.key == "tab":
            self.focus_next()
        elif event.key == "shift+tab":
            self.focus_previous()


class ZToDirectory(ModalScreen):
    """Screen with a dialog to z to a directory, using zoxide, or other directory management tools."""

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
                Option(" No input provided", disabled=True),
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

    @work(exclusive=True)
    async def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes to update the option list."""
        # Cancel any previous pending search
        if self._search_task and self._search_task._active:
            self._search_task.stop()
        # Schedule a new search after delay
        self._search_task = self.set_timer(0.125, self._perform_search)

    async def _perform_search(self) -> None:
        """Perform the actual search after debounce delay."""
        search_term = self.query_one("#zoxide_input").value.strip()
        zoxide_output = run(
            ["zoxide", "query", "--list"] + search_term.split(),
            capture_output=True,
            text=True,
        )
        zoxide_options = self.query_one("#zoxide_options")
        zoxide_options.clear_options()
        zoxide_options.add_class("empty")
        if zoxide_output.stdout:
            for line in zoxide_output.stdout.splitlines():
                zoxide_options.add_option(
                    Option(Content(" " + line), id=state.compress(line))
                )
            zoxide_options.remove_class("empty")
            zoxide_options.highlighted = 0
        else:
            zoxide_options.add_option(Option(" No matches found", disabled=True))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.value.strip() == "" or "empty" in event.input.classes:
            pass
        else:
            zoxide_options = self.query_one("#zoxide_options")
            if zoxide_options.highlighted is None:
                zoxide_options.highlighted = 0
            zoxide_options.action_select()

    # you cant manually tab into the option list, but you can click, so i guess
    @work(exclusive=True)
    async def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle option selection."""
        selected_value = event.option.id
        run(
            ["zoxide", "add", state.decompress(selected_value)],
            capture_output=True,
            text=True,
        )
        if selected_value:
            self.dismiss(selected_value)
        else:
            self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        event.stop()
        if event.key in ["escape"]:
            self.dismiss(None)
        elif event.key == "down":
            zoxide_options = self.query_one("#zoxide_options")
            if zoxide_options.options:
                zoxide_options.action_cursor_down()
        elif event.key == "up":
            zoxide_options = self.query_one("#zoxide_options")
            if zoxide_options.options:
                zoxide_options.action_cursor_up()
        elif event.key == "tab":
            self.focus_next()
        elif event.key == "shift+tab":
            self.focus_previous()


class ModalInput(ModalScreen):
    DEFAULT_CSS = """
    ModalInput {
        align: center middle;
    }
    Container {
        border: round $primary-lighten-3;
        width: 50vw;
        max-width: 50vw;
        max-height: 3;
        padding: 0 1;
        background: transparent !important;
    }
    Input {
        background: transparent !important
    }
    """

    def __init__(self, border_title: str, border_subtitle: str = "", **kwargs):
        super().__init__(**kwargs)
        self.border_title = border_title
        self.border_subtitle = border_subtitle

    def compose(self) -> ComposeResult:
        with Container():
            yield Input(
                id="input",
                compact=True,
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
        if event.key == "escape":
            """Handle escape key to dismiss the dialog."""
            self.dismiss("")


if __name__ == "__main__":
    state.load_config()

    class TestApp(App):
        CSS_PATH = "style.tcss"

        def compose(self) -> ComposeResult:
            with VerticalGroup():
                yield Button("Open Dismissable Dialog", id="open_dismissable")
                yield Button("Open Yes/No Dialog", id="open_dialog")
                yield Button("Open Delete Files Dialog", id="open_delete_files")
                yield Button("Open Input Dialog", id="open_input_dialog")
                yield (
                    Button(
                        "Open Copy/Overwrite Dialog", id="open_copy_overwrite_dialog"
                    ),
                )
                yield Button(
                    "Open ZToDirectory Dialog", id="open_zoxide_to_directory_dialog"
                )

        @on(Button.Pressed, "#open_dismissable")
        def open_dismissable(self, event: Button.Pressed) -> None:
            """Open the Dismissable dialog."""

            def on_receive_response(response) -> None:
                self.mount(Label("Dismissable dialog closed."))

            self.push_screen(
                Dismissable("This is a dismissable dialog."), on_receive_response
            )

        @on(Button.Pressed, "#open_dialog")
        def open_dialog(self, event: Button.Pressed) -> None:
            """Open the Yes/No dialog."""

            def on_receive_response(response: bool) -> None:
                if response:
                    self.mount(Label("User chose to proceed."))
                else:
                    self.mount(Label("User chose not to proceed."))

            self.push_screen(YesOrNo("Do you want to proceed?"), on_receive_response)

        @on(Button.Pressed, "#open_input_dialog")
        def open_input_dialog(self, event: Button.Pressed) -> None:
            """Open the Input dialog."""

            def on_input_received(input_value: str) -> None:
                self.mount(Label(f"User input: {input_value}"))

            self.push_screen(
                ModalInput("Test the modal input", border_subtitle="subtitle"),
                on_input_received,
            )

        @on(Button.Pressed, "#open_delete_files")
        def open_delete_files(self, event: Button.Pressed) -> None:
            """Open the DeleteFiles dialog."""

            def on_response(response: str) -> None:
                if response == "delete":
                    self.mount(Label("User chose to delete files."))
                elif response == "trash":
                    self.mount(Label("User chose to move files to trash."))
                else:
                    self.mount(Label("User cancelled the operation."))

            self.push_screen(
                DeleteFiles("How do you want to delete the files?"), on_response
            )

        @on(Button.Pressed, "#open_copy_overwrite_dialog")
        def open_copy_overwrite_dialog(self, event: Button.Pressed) -> None:
            """Open the Copy/Overwrite dialog."""

            def on_response(response: str) -> None:
                self.mount(Label(f"User chose: {response}"))

            self.push_screen(
                CopyOverwrite("File already exists. What do you want to do?"),
                on_response,
            )

        @on(Button.Pressed, "#open_zoxide_to_directory_dialog")
        def open_zoxide_to_directory_dialog(self, event: Button.Pressed) -> None:
            """Open the ZToDirectory dialog."""

            def on_response(response: str) -> None:
                if response:
                    self.mount(Label(f"User selected: {state.decompress(response)}"))
                else:
                    self.mount(Label("No directory selected."))

            self.push_screen(ZToDirectory(), on_response)

    state.start_watcher()
    TestApp().run()
