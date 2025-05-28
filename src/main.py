from maps import ICONS
from os import getcwd, path, chdir
import state
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
    #    Switch,
    Label,
    Button,
    #    Static,
    Header,
    Footer,
    Input,
    RichLog,
    RadioSet,
    RadioButton,
)
from textual.validation import Function
from themes import get_custom_themes
from WidgetsCore import (
    PathAutoCompleteInput,
    FileList,
    update_file_list,
    PreviewContainer,
    PinnedSidebar,
)


state.load_config()
state.load_pins()


class Application(App):
    CSS_PATH = "style.tcss"

    HORIZONTAL_BREAKPOINTS = [(0, "-filelistonly"), (60, "-nopreview"), (90, "-all")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_selected_option = None
        self.main_sort_by = state.config["filelist"]["sort_by"]
        self.main_sort_order = state.config["filelist"]["sort_order"]

    def compose(self) -> ComposeResult:
        print("Starting Carto...")
        path_switcher = Input(
            id="path_switcher",
            validators=[Function(lambda x: path.exists(x), "Path does not exist")],
        )
        yield Header(name="carto", show_clock=True, icon="📁")
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
                VerticalGroup(
                    PinnedSidebar(id="pinned_sidebar"),
                    id="pinned_sidebar_container",
                ),
                VerticalGroup(
                    FileList(
                        id="file_list",
                        name="File List",
                        classes="file-list",
                        sort_by=self.main_sort_by,
                        sort_order=self.main_sort_order,
                    ),
                    id="file_list_container",
                ),
                PreviewContainer(
                    id="preview_sidebar",
                ),
                id="main",
            ),
            HorizontalGroup(
                RichLog(id="processes", highlight=True, markup=True, wrap=True),
                VerticalGroup(id="metadata"),
                RadioSet(
                    RadioButton(
                        path.join(path.dirname(__file__), "log.txt"),
                        id=state.compress("log.txt"),
                        compact=True,
                    ),
                    RadioButton(
                        path.join(path.dirname(__file__), "error.txt"),
                        id=state.compress("error.txt"),
                        compact=True,
                    ),
                    id="clipboard",
                ),
                id="footer",
            ),
            id="root",
        )
        yield Footer()

    def on_mount(self):
        print("Mounting...")
        self.query_one("#menu").border_title = "Options"
        self.query_one("#below_menu").border_title = "Directory Actions"
        self.query_one("#pinned_sidebar_container").border_title = "Sidebar"
        self.query_one("#file_list_container").border_title = "Files"
        self.query_one("#processes").border_title = "Processes"
        self.query_one("#metadata").border_title = "Metadata"
        self.query_one("#clipboard").border_title = "Clipboard"
        self.query_one("#processes").write(
            "Welcome to [red]Carto[/red]!",
        )
        self.query_one("#processes").write(
            "This is a file manager application built with [green]Textual[/green].",
        )
        for theme in get_custom_themes():
            self.register_theme(theme)
        self.theme = state.config["interface"]["theme"]["default"]
        print("Done?")

    @on(Button.Pressed, "#back")
    def go_back_in_history(self, event: Button.Pressed) -> None:
        """Go back in the session's history or go up the directory tree"""
        state.sessionHistoryIndex = state.sessionHistoryIndex - 1
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
        chdir(state.sessionDirectories[state.sessionHistoryIndex]["path"])
        update_file_list(
            self,
            "#file_list",
            self.main_sort_by,
            self.main_sort_order,
            add_to_session=False,
        )

    @on(Button.Pressed, "#up")
    def go_up_path(self, event: Button.Pressed) -> None:
        """Go up the current location's directory"""
        chdir(path.sep.join(getcwd().split(path.sep)[:-1]))
        update_file_list(self, "#file_list", self.main_sort_by, self.main_sort_order)

    @on(Input.Submitted, "#path_switcher")
    def switch_to_path(self, event: Input.Submitted) -> None:
        """Use a custom path entered as the current workind directory"""
        if path.exists(event.value):
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

    async def on_key(self, event: events.Key) -> None:
        if not self.focused.id:
            return
        if self.focused.id == "path_switcher" and event.key in ["enter", "escape"]:
            self.query_one("#file_list").focus()
            await self.query_one("#path_switcher").action_submit()
        elif "search" in self.focused.id and event.key == "escape":
            if self.focused.id == "search_file_list":
                self.query_one("#file_list").focus()
            elif self.focused.id == "search_pinned_sidebar":
                self.query_one("#pinned_sidebar").focus()
        elif (
            self.focused.id == "path_switcher" or "search" in self.focused.id
        ) and event.key == "backspace":
            return
        elif event.key in state.config["keybinds"]["focus"]["pinned_sidebar"]:
            if self.focused.id == "pinned_sidebar":
                self.query_one("#file_list").focus()
            else:
                self.query_one("#pinned_sidebar").focus()
        elif event.key in state.config["keybinds"]["focus"]["file_list"]:
            self.query_one("#file_list").focus()
        elif event.key in state.config["keybinds"]["focus"]["preview_sidebar"]:
            if (
                self.focused.id == "preview_sidebar"
                or self.focused.parent.id == "preview_sidebar"
            ):
                self.query_one("#file_list").focus()
            else:
                self.query_one("#preview_sidebar *").focus()
        elif event.key in state.config["keybinds"]["focus"]["path_switcher"]:
            self.query_one("#path_switcher").focus()
        # this is so scuffed
        elif event.key in state.config["keybinds"]["navigation"]["previous"]:
            if self.query_one("#back").disabled:
                self.go_up_path(Button.Pressed(self.query_one("#up")))
            else:
                self.go_back_in_history(Button.Pressed(self.query_one("#back")))
        elif event.key in state.config["keybinds"]["navigation"]["next"]:
            if not self.query_one("#forward").disabled:
                self.go_forward_in_history(
                    Button.Pressed(
                        self.query_one("#forward"),
                    )
                )
        elif event.key in state.config["keybinds"]["navigation"]["up"]:
            self.go_up_path(Button.Pressed(self.query_one("#up")))
        elif event.key in state.config["keybinds"]["navigation"]["reload"]:
            self.go_back_in_history(Button.Pressed(self.query_one("#reload")))
        elif event.key in state.config["keybinds"]["toggle_pin"]:
            state.toggle_pin(path.basename(getcwd()), getcwd())
            await self.query_one("#pinned_sidebar").reload_pins()
        elif event.key in state.config["keybinds"]["hide"]["pinned_sidebar"]:
            if self.query_one("#pinned_sidebar_container").display:
                self.query_one("#pinned_sidebar_container").add_class("hide")
            else:
                self.query_one("#pinned_sidebar_container").remove_class("hide")
        elif event.key in state.config["keybinds"]["hide"]["preview_sidebar"]:
            if self.query_one("#preview_sidebar").display:
                self.query_one("#preview_sidebar").add_class("hide")
            else:
                self.query_one("#preview_sidebar").remove_class("hide")


state.start_watcher()
app = Application(watch_css=True)
app.run()
