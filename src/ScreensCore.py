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
        yield Grid(
            Label(self.message, id="question"),
            Button("\\[Y]es", variant="error", id="yes"),
            Button("\\[N]o", variant="primary", id="no"),
            id="dialog",
        )

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
        yield Grid(
            Label(self.message, id="question"),
            Button("\\[O]verwrite", variant="error", id="overwrite"),
            Button("\\[R]ename", variant="warning", id="rename"),
            Button("\\[S]kip", variant="default", id="skip"),
            Button("\\[C]ancel", variant="primary", id="cancel"),
            id="dialog",
        )

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
                id="zoxide_options"
            )
    def on_mount(self) -> None:
        zoxide_input = self.query_one("#zoxide_input")
        zoxide_input.border_title = "zoxide"
        zoxide_input.focus()
        zoxide_options = self.query_one("#zoxide_options")
        zoxide_options.border_title = "Folders"
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
        if zoxide_output.stdout:
            for line in zoxide_output.stdout.splitlines():
                zoxide_options.add_option(Option(Content(" " + line), id=state.compress(line)))
        else:
            zoxide_options.add_option(Option(" No matches found", disabled=True))
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.value.strip() == "":
            pass
        else:
            zoxide_options = self.query_one("#zoxide_options")
            zoxide_options.focus()
            zoxide_options.action_first()
    
    @work(exclusive=True)
    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
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
        if event.key in ["escape"]:
            self.dismiss(None)


class ModalInput(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Dismiss Input", show=False)]
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

    def __init__(self, border_title: str, **kwargs):
        super().__init__(**kwargs)
        self.border_title = border_title

    def compose(self) -> ComposeResult:
        yield Container(
            Input(
                id="input",
                compact=True,
            )
        )

    def on_mount(self) -> None:
        self.query_one(Container).border_title = self.border_title
        self.query_one("#input").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        self.dismiss(event.input.value)


if __name__ == "__main__":
    state.load_config()
    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield VerticalGroup(
                Button("Open Yes/No Dialog", id="open_dialog"),
                Button("Open Input Dialog", id="open_input_dialog"),
                Button("Open Copy/Overwrite Dialog", id="open_copy_overwrite_dialog"),
                Button("Open ZToDirectory Dialog", id="open_zoxide_to_directory_dialog"),
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

            self.push_screen(ModalInput("Test the modal input"), on_input_received)

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

    TestApp().run()
