from textual import work, on
from textual.app import App, ComposeResult
from textual.containers import (
    HorizontalGroup,
    HorizontalScroll,
    Vertical,
    VerticalGroup,
)
from textual.widgets import (
    OptionList,
    #    TabbedContent,
    TextArea,
    #    Switch,
    #    Label,
    Button,
    #    Static,
    Header,
    Footer,
    Input,
)
from textual.validation import Function
from os import getcwd, path, chdir
from maps import ICONS
from lzstring import LZString
from WidgetsCore import PathAutoCompleteInput, FileList, update_file_list
import state

log = state.log
lzstring = LZString()

state.load_config()

class Application(App):
    BINDINGS = [
        ("escape", "focus_file_list()", "Focus File List"),
        ("ctrl+enter", "submit()", "Submit"),
    ]
    CSS_PATH = "style.tcss"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_selected_option = None
        self.main_sort_by = "name"
        self.main_sort_order = "ascending"
        self.cwd = getcwd()

    def compose(self) -> ComposeResult:
        path_switcher = Input(
            id="path_switcher",
            validators=[Function(lambda x: path.exists(x), "Path does not exist")],
        )
        yield Header(name="tfe", show_clock=True, icon="📁")
        yield Vertical(
            HorizontalScroll(
                Button(
                    ICONS["general"]["up"],
                    classes="option",
                    id="sort_order",
                ),
                id="menu",
            ),
            VerticalGroup(
                HorizontalGroup(
                    Button(ICONS["general"]["left"], id="back"),
                    Button(ICONS["general"]["right"], id="forward"),
                    Button(ICONS["general"]["up"], id="up"),
                    Button(ICONS["general"]["refresh"], id="reload"),
                    path_switcher,
                ),
                # Container(
                PathAutoCompleteInput(
                    target=path_switcher,
                    path=getcwd().split(path.sep)[0],
                    folder_prefix=ICONS["folder"]["default"] + " ",
                    file_prefix=ICONS["file"]["default"] + " ",
                    id="path_autocomplete",
                ),
                # ),
                id="below_menu",
            ),
            HorizontalGroup(
                OptionList("hi", id="sidebar"),
                FileList(
                    id="file_list",
                    name="File List",
                    classes="file-list",
                    sort_by=self.main_sort_by,
                    sort_order=self.main_sort_order,
                ),
                TextArea(
                    'print("Welcome to tfe!")',
                    language="python",
                    show_line_numbers=True,
                    read_only=True,
                    id="text_preview",
                    soft_wrap=False,
                ),
                id="main",
            ),
            id="root",
        )
        yield Footer()

    def on_mount(self):
        self.query_one("#menu").border_title = "Options"
        self.query_one("#below_menu").border_title = "Directory Actions"
        self.query_one("#sidebar").border_title = "Sidebar"
        self.query_one("#file_list").border_title = "Files"
        self.query_one("#text_preview").border_title = "File Preview"
        self.theme = state.config["interface"]["theme"]["default"]

    @on(Button.Pressed, "#back")
    def go_back_in_history(self, event: Button.Pressed) -> None:
        """Go back in the session's history"""
        state.sessionHistoryIndex = state.sessionHistoryIndex - 1
        log(state.sessionHistoryIndex)
        chdir(state.sessionDirectories[state.sessionHistoryIndex]["path"])
        update_file_list(
            self,
            "#file_list",
            self.main_sort_by,
            self.main_sort_order,
            add_to_session=False,
        )

    @on(Button.Pressed, "#forward")
    def go_forward_in_history(self, event: Button.Pressed) -> None:
        """Go forward in the session's history"""
        state.sessionHistoryIndex = state.sessionHistoryIndex + 1
        log(state.sessionHistoryIndex)
        chdir(state.sessionDirectories[state.sessionHistoryIndex]["path"])
        update_file_list(
            self,
            "#file_list",
            self.main_sort_by,
            self.main_sort_order,
            add_to_session=False,
        )

    @on(Button.Pressed)
    @work
    async def button_log_i_guess(self, event: Button.Pressed) -> None:
        log(f"button {event.button.id}")

    @on(Button.Pressed, "#up")
    def go_up_path(self, event: Button.Pressed) -> None:
        """Go up the current location's directory"""
        log(f"up {state.sessionDirectories[state.sessionHistoryIndex]}")
        chdir(path.sep.join(getcwd().split(path.sep)[:-1]))
        update_file_list(self, "#file_list", self.main_sort_by, self.main_sort_order)

    @on(Input.Submitted, "#path_switcher")
    def switch_to_path(self, event: Input.Submitted) -> None:
        """Use a custom path entered as the current workind directory"""
        chdir(event.value)
        update_file_list(self, "#file_list", self.main_sort_by, self.main_sort_order)

    @on(Button.Pressed, "#reload")
    def reload_file_list(self, event: Button.Pressed) -> None:
        """Reload the file list"""
        update_file_list(
            self,
            "#file_list",
            self.main_sort_by,
            self.main_sort_order,
            add_to_session=False,
        )

    @work
    async def update_session_dicts(self, sessionDirs, sessionHisIndex):
        """Update the session directories and history index"""
        state.update_session_state(sessionDirs, sessionHisIndex)
    
    def action_focus_file_list(self):
        """Focus the file list. What more did you expect?"""
        self.query_one("#file_list").focus()

    async def action_submit(self):
        """Submit the current input. What more did you expect?"""
        await self.query_exactly_one("#path_switcher").action_submit()

Application(watch_css=True).run()
