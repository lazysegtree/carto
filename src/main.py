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
from textual.widgets.selection_list import Selection
from textual.validation import Function
from textual.widgets import (
    # OptionList,
    # TabbedContent,
    # Switch,
    # Label,
    Button,
    # Static,
    Header,
    Input,
    RichLog,
    SelectionList,
)
from themes import get_custom_themes
from WidgetsCore import (
    PathAutoCompleteInput,
    update_file_list,
    PreviewContainer,
    PinnedSidebar,
    FileList,
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
                    ICONS["general"]["up"][0],
                    classes="option",
                    id="sort_order",
                ),
                id="menu",
            ),
            VerticalGroup(
                HorizontalGroup(
                    Button(ICONS["general"]["left"][0], id="back"),
                    Button(ICONS["general"]["right"][0], id="forward"),
                    Button(ICONS["general"]["up"][0], id="up"),
                    Button(ICONS["general"]["refresh"][0], id="reload"),
                    path_switcher,
                ),
                # Container(
                PathAutoCompleteInput(
                    target=path_switcher,
                    path=getcwd().split(path.sep)[0],
                    folder_prefix=ICONS["folder"]["default"][0] + " ",
                    file_prefix=ICONS["file"]["default"][0] + " ",
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
                # ? should we switch to a vertical scroll?
                RichLog(id="processes", highlight=True, markup=True, wrap=True),
                VerticalGroup(id="metadata"),
                SelectionList[str](
                    Selection(
                        path.join(path.dirname(__file__), "log.txt"),
                        path.join(path.dirname(__file__), "log.txt"),
                    ),
                    Selection(
                        path.join(path.dirname(__file__), "error.txt"),
                        path.join(path.dirname(__file__), "error.txt"),
                    ),
                    id="clipboard",
                ),
                id="footer",
            ),
            id="root",
        )

    def on_mount(self):
        self.query_one("#menu").border_title = "Options"
        self.query_one("#below_menu").border_title = "Directory Actions"
        self.query_one("#pinned_sidebar_container").border_title = "Sidebar"
        self.query_one("#file_list_container").border_title = "Files"
        self.query_one("#processes").border_title = "Processes"
        self.query_one("#metadata").border_title = "Metadata"
        self.query_one("#clipboard").border_title = "Clipboard"
        for theme in get_custom_themes():
            self.register_theme(theme)
        self.theme = state.config["interface"]["theme"]["default"]
        self.title = "Carto - " + getcwd().replace(path.sep, "/")

    @on(Button.Pressed, "#back")
    def go_back_in_history(self, event: Button.Pressed) -> None:
        """Go back in the session's history or go up the directory tree"""
        state.sessionHistoryIndex = state.sessionHistoryIndex - 1
        #! reminder to add a check for path
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
        #! reminder to add a check for path
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
        #! on the off chance that parent's parent got nuked, might need to check if the parent exists
        chdir(path.sep.join(getcwd().split(path.sep)[:-1]))
        update_file_list(self, "#file_list", self.main_sort_by, self.main_sort_order)

    @on(Input.Submitted, "#path_switcher")
    def switch_to_path(self, event: Input.Submitted) -> None:
        """Use a custom path entered as the current workind directory"""
        if path.exists(event.value):
            chdir(event.value)
        #! at least try to alert user
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

    @work
    async def on_key(self, event: events.Key) -> None:
        if not self.focused.id:
            return
        # make sure that keybinds dont break
        if self.focused.id == "path_switcher" and event.key in ["enter", "escape"]:
            if "visual" in self.query_one("#file_list_container").classes:
                self.query_one("#file_list_visual").focus()
            else:
                self.query_one("#file_list").focus()
            await self.query_one("#path_switcher").action_submit()
        elif "search" in self.focused.id and event.key == "escape":
            if self.focused.id == "search_file_list":
                if "visual" in self.query_one("#file_list_container").classes:
                    self.query_one("#file_list_visual").focus()
                else:
                    self.query_one("#file_list").focus()
            elif self.focused.id == "search_pinned_sidebar":
                self.query_one("#pinned_sidebar").focus()
        elif (
            self.focused.id == "path_switcher" or "search" in self.focused.id
        ) and event.key == "backspace":
            return
        # focus toggle pinned sidebar
        elif event.key in state.config["keybinds"]["focus"]["pinned_sidebar"]:
            if (
                self.focused.id == "pinned_sidebar"
                or "hide" in self.query_one("#pinned_sidebar_container").classes
            ):
                if "visual" in self.query_one("#file_list_container").classes:
                    self.query_one("#file_list_visual").focus()
                else:
                    self.query_one("#file_list").focus()
            else:
                self.query_one("#pinned_sidebar").focus()
        # focus file list from anywhere except input
        elif event.key in state.config["keybinds"]["focus"]["file_list"]:
            if "visual" in self.query_one("#file_list_container").classes:
                self.query_one("#file_list_visual").focus()
            else:
                self.query_one("#file_list").focus()
        # focus toggle preview sidebar
        elif event.key in state.config["keybinds"]["focus"]["preview_sidebar"]:
            if (
                self.focused.id == "preview_sidebar"
                or self.focused.parent.id == "preview_sidebar"
                or "hide" in self.query_one("#preview_sidebar").classes
            ):
                if "visual" in self.query_one("#file_list_container").classes:
                    self.query_one("#file_list_visual").focus()
                else:
                    self.query_one("#file_list").focus()
            else:
                self.query_one("#preview_sidebar *").focus()
        # focus path switcher
        elif event.key in state.config["keybinds"]["focus"]["path_switcher"]:
            self.query_one("#path_switcher").focus()
        # focus processes
        elif event.key in state.config["keybinds"]["focus"]["processes"]:
            if (
                self.focused.id == "processes"
                or "hide" in self.query_one("#processes").classes
            ):
                if "visual" in self.query_one("#file_list_container").classes:
                    self.query_one("#file_list_visual").focus()
                else:
                    self.query_one("#file_list").focus()
            else:
                self.query_one("#processes").focus()
        # focus metadata
        elif event.key in state.config["keybinds"]["focus"]["metadata"]:
            if self.focused.id == "metadata":
                if "visual" in self.query_one("#file_list_container").classes:
                    self.query_one("#file_list_visual").focus()
                else:
                    self.query_one("#file_list").focus()
            else:
                self.query_one("#metadata").focus()
        # focus clipboard
        elif event.key in state.config["keybinds"]["focus"]["clipboard"]:
            if self.focused.id == "clipboard":
                if "visual" in self.query_one("#file_list_container").classes:
                    self.query_one("#file_list_visual").focus()
                else:
                    self.query_one("#file_list").focus()
            else:
                self.query_one("#clipboard").focus()
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
            self.reload_file_list(Button.Pressed(self.query_one("#reload")))
        # toggle pin on current directory
        elif event.key in state.config["keybinds"]["toggle_pin"]:
            state.toggle_pin(path.basename(getcwd()), getcwd())
            await self.query_one("#pinned_sidebar").reload_pins()
        # toggle hiding panels
        elif event.key in state.config["keybinds"]["hide"]["pinned_sidebar"]:
            if "visual" in self.query_one("#file_list_container").classes:
                self.query_one("#file_list_visual").focus()
            else:
                self.query_one("#file_list").focus()
            if self.query_one("#pinned_sidebar_container").display:
                self.query_one("#pinned_sidebar_container").add_class("hide")
            else:
                self.query_one("#pinned_sidebar_container").remove_class("hide")
        elif event.key in state.config["keybinds"]["hide"]["preview_sidebar"]:
            if "visual" in self.query_one("#file_list_container").classes:
                self.query_one("#file_list_visual").focus()
            else:
                self.query_one("#file_list").focus()
            if self.query_one("#preview_sidebar").display:
                self.query_one("#preview_sidebar").add_class("hide")
            else:
                self.query_one("#preview_sidebar").remove_class("hide")
        elif event.key in state.config["keybinds"]["hide"]["footer"]:
            if "visual" in self.query_one("#file_list_container").classes:
                self.query_one("#file_list_visual").focus()
            else:
                self.query_one("#file_list").focus()
            if self.query_one("#footer").display:
                self.query_one("#footer").add_class("hide")
            else:
                self.query_one("#footer").remove_class("hide")
        elif event.key in state.config["keybinds"]["mode"]["visual"]:
            self.query_one("#file_list").toggle_mode()


state.start_watcher()
app = Application(watch_css=True)
app.run()
