from textual import work, on, events
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
    CSS_PATH = "style.tcss"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_selected_option = None
        self.main_sort_by = state.config["filelist"]["sort_by"]
        self.main_sort_order = state.config["filelist"]["sort_order"]

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

    def action_focus(self, widget_selector: str) -> None:
        """Focus a widget by its ID"""
        self.query_one(widget_selector).focus()

    async def on_key(self, event: events.Key) -> None:
        if self.focused.id == "path_switcher" and event.key in ["enter", "escape"]:
            self.query_one("#file_list").focus()
            await self.query_one("#path_switcher").action_submit()
        elif self.focused.id == "path_switcher" and event.key == "backspace":
            return
        if event.key == state.config["keybinds"]["focus"]["pinned_sidebar"]:
            self.query_one("#sidebar").focus()
        elif event.key == state.config["keybinds"]["focus"]["file_list"]:
            self.query_one("#file_list").focus()
        elif event.key == state.config["keybinds"]["focus"]["path_switcher"]:
            self.query_one("#path_switcher").focus()
        elif event.key == state.config["keybinds"]["navigation"]["previous"]:
            self.query_one("#back").focus()
        elif event.key == state.config["keybinds"]["navigation"]["next"]:
            self.query_one("#forward").focus()
        elif event.key == state.config["keybinds"]["navigation"]["up"]:
            self.query_one("#up").focus()
        elif event.key == state.config["keybinds"]["navigation"]["reload"]:
            self.query_one("#reload").focus()


Application(watch_css=True).run()
