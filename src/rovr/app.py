import shutil
from os import getcwd, path
from types import SimpleNamespace as Namespace

from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import (
    HorizontalGroup,
    HorizontalScroll,
    Vertical,
    VerticalGroup,
)
from textual.css.query import NoMatches
from textual.widgets import Header, Input

from .ActionButtons import (
    CopyButton,
    CutButton,
    DeleteButton,
    NewItemButton,
    PasteButton,
    RenameItemButton,
    SortOrderButton,
)
from .FooterWidgets import (
    Clipboard,
    MetadataContainer,
    ProcessContainer,
)
from .maps import VAR_TO_DIR
from .NavigationWidgets import (
    BackButton,
    ForwardButton,
    PathAutoCompleteInput,
    PathInput,
    RefreshButton,
    UpButton,
)
from .ScreensCore import YesOrNo, ZToDirectory
from .themes import get_custom_themes
from .utils import (
    config,
    decompress,
    load_config,
    start_watcher,
    toggle_pin,
)
from .WidgetsCore import (
    FileList,
    PinnedSidebar,
    PreviewContainer,
)

load_config()


class Application(App):
    CSS_PATH = ["style.tcss", path.join(VAR_TO_DIR["CONFIG"], "style.tcss")]

    HORIZONTAL_BREAKPOINTS = [(0, "-filelistonly"), (60, "-nopreview"), (90, "-all")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_selected_option = None
        self.main_sort_by = config["settings"]["filelist_sort_by"]
        self.main_sort_order = config["settings"]["filelist_sort_order"]

    def compose(self) -> ComposeResult:
        print("Starting Rovr...")
        yield Header(
            name="rovr",
            show_clock=True,
            icon="📁" if config["interface"]["nerd_font"] else "fs",
        )
        with Vertical(id="root"):
            with HorizontalScroll(id="menu"):
                yield SortOrderButton()
                yield CopyButton()
                yield CutButton()
                yield PasteButton()
                yield NewItemButton()
                yield RenameItemButton()
                yield DeleteButton()
            with VerticalGroup(id="below_menu"):
                with HorizontalGroup():
                    yield BackButton()
                    yield ForwardButton()
                    yield UpButton()
                    yield RefreshButton()
                    path_switcher = PathInput()
                    yield path_switcher
                yield PathAutoCompleteInput(
                    target=path_switcher,
                )
            with HorizontalGroup(id="main"):
                with VerticalGroup(id="pinned_sidebar_container"):
                    yield PinnedSidebar(id="pinned_sidebar")
                with VerticalGroup(id="file_list_container"):
                    yield FileList(
                        id="file_list",
                        name="File List",
                        classes="file-list",
                        sort_by=self.main_sort_by,
                        sort_order=self.main_sort_order,
                    )
                yield PreviewContainer(
                    id="preview_sidebar",
                )
            with HorizontalGroup(id="footer"):
                # ? should we switch to a vertical scroll for richlog?
                yield ProcessContainer()
                yield MetadataContainer(id="metadata")
                yield Clipboard(id="clipboard")

    def on_mount(self) -> None:
        def warning(response: bool) -> None:
            match response:
                case True:
                    pass
                case False:
                    self.app.exit(message="Bye! Hope to see you soon!")

        self.push_screen(
            YesOrNo(
                "This is a pre-alpha application.\nUse at your own risk.\nContinue?",
                reverse_color=True,
            ),
            warning,
        )
        # border titles
        self.query_one("#menu").border_title = "Options"
        self.query_one("#below_menu").border_title = "Directory Actions"
        self.query_one("#pinned_sidebar_container").border_title = "Sidebar"
        self.query_one("#file_list_container").border_title = "Files"
        self.query_one("#processes").border_title = "Processes"
        self.query_one("#metadata").border_title = "Metadata"
        self.query_one("#clipboard").border_title = "Clipboard"
        self.title = "Rovr - " + getcwd().replace(path.sep, "/")
        # themes
        for theme in get_custom_themes():
            self.register_theme(theme)
        self.theme = config["theme"]["default"]
        # tooltips
        if config["interface"]["tooltips"]:
            self.query_one("#back").tooltip = "Go back in history"
            self.query_one("#forward").tooltip = "Go forward in history"
            self.query_one("#up").tooltip = "Go up the directory tree"
            self.query_one("#refresh").tooltip = "Refresh the file list"

    @work
    async def on_key(self, event: events.Key) -> None:
        if self.focused is None or not self.focused.id:
            return
        # Make sure that key binds don't break
        match event.key:
            case key if (
                key in ["enter", "escape"] and self.focused.id == "path_switcher"
            ):
                self.query_one("#file_list").focus()
                await self.query_one("#path_switcher").action_submit()
                return
            case "escape" if "search" in self.focused.id:
                match self.focused.id:
                    case "search_file_list":
                        self.query_one("#file_list").focus()
                    case "search_pinned_sidebar":
                        self.query_one("#pinned_sidebar").focus()
                return
            case "backspace" if (
                type(self.focused) is Input or "search" in self.focused.id
            ):
                return
            # focus toggle pinned sidebar
            case key if key in config["keybinds"]["focus_toggle_pinned_sidebar"]:
                if (
                    self.focused.id == "pinned_sidebar"
                    or "hide" in self.query_one("#pinned_sidebar_container").classes
                ):
                    self.query_one("#file_list").focus()
                else:
                    self.query_one("#pinned_sidebar").focus()
            # Focus file list from anywhere except input
            case key if key in config["keybinds"]["focus_file_list"]:
                self.query_one("#file_list").focus()
            # Focus toggle preview sidebar
            case key if key in config["keybinds"]["focus_toggle_preview_sidebar"]:
                if (
                    self.focused.id == "preview_sidebar"
                    or self.focused.parent.id == "preview_sidebar"
                    or "hide" in self.query_one("#preview_sidebar").classes
                ):
                    self.query_one("#file_list").focus()
                else:
                    try:
                        self.query_one("#preview_sidebar > *").focus()
                    except NoMatches:
                        pass
            # Focus path switcher
            case key if key in config["keybinds"]["focus_toggle_path_switcher"]:
                self.query_one("#path_switcher").focus()
            # Focus processes
            case key if key in config["keybinds"]["focus_toggle_processes"]:
                if (
                    self.focused.id == "processes"
                    or "hide" in self.query_one("#processes").classes
                ):
                    self.query_one("#file_list").focus()
                else:
                    self.query_one("#processes").focus()
            # Focus metadata
            case key if key in config["keybinds"]["focus_toggle_metadata"]:
                if self.focused.id == "metadata":
                    self.query_one("#file_list").focus()
                else:
                    self.query_one("#metadata").focus()
            # Focus clipboard
            case key if key in config["keybinds"]["focus_toggle_clipboard"]:
                if self.focused.id == "clipboard":
                    self.query_one("#file_list").focus()
                else:
                    self.query_one("#clipboard").focus()
            # Navigation buttons but with key binds
            case key if key in config["keybinds"]["hist_previous"]:
                if self.query_one("#back").disabled:
                    self.query_one("#up").action_press()
                else:
                    self.query_one("#back").action_press()
            case key if key in config["keybinds"]["hist_next"]:
                if not self.query_one("#forward").disabled:
                    self.query_one("#forward").action_press()
            case key if key in config["keybinds"]["up_tree"]:
                self.query_one("#up").action_press()
            case key if key in config["keybinds"]["refresh"]:
                self.query_one("#refresh").action_press()
            # Toggle pin on current directory
            case key if key in config["keybinds"]["toggle_pin"]:
                toggle_pin(path.basename(getcwd()), getcwd())
                self.query_one("#pinned_sidebar").reload_pins()
            # Toggle hiding panels
            case key if key in config["keybinds"]["toggle_pinned_sidebar"]:
                self.query_one("#file_list").focus()
                if self.query_one("#pinned_sidebar_container").display:
                    self.query_one("#pinned_sidebar_container").add_class("hide")
                else:
                    self.query_one("#pinned_sidebar_container").remove_class("hide")
            case key if key in config["keybinds"]["toggle_preview_sidebar"]:
                self.query_one("#file_list").focus()
                if self.query_one("#preview_sidebar").display:
                    self.query_one("#preview_sidebar").add_class("hide")
                else:
                    self.query_one("#preview_sidebar").remove_class("hide")
            case key if key in config["keybinds"]["toggle_footer"]:
                self.query_one("#file_list").focus()
                if self.query_one("#footer").display:
                    self.query_one("#footer").add_class("hide")
                else:
                    self.query_one("#footer").remove_class("hide")
            case key if (
                event.key in config["plugins"]["zoxide"]["keybinds"]
                and config["plugins"]["zoxide"]["enabled"]
            ):
                if shutil.which("zoxide") is None:
                    self.notify(
                        "Zoxide is not installed or not in PATH.",
                        title="Zoxide",
                        severity="error",
                    )

                def on_response(response: str) -> None:
                    """Handle the response from the ZToDirectory dialog."""
                    if response:
                        pathinput = self.query_one(PathInput)
                        pathinput.value = decompress(response).replace(path.sep, "/")
                        pathinput.on_input_submitted(Namespace(value=pathinput.value))
                self.push_screen(ZToDirectory(), on_response)
            case _:
                if self.query_one("#file_list").has_focus:
                    match event.key:
                        case key if key in config["keybinds"]["copy"]:
                            self.query_one("#copy").action_press()
                        case key if key in config["keybinds"]["cut"]:
                            self.query_one("#cut").action_press()
                        case key if key in config["keybinds"]["new"]:
                            self.query_one("#new").action_press()
                        case key if key in config["keybinds"]["rename"]:
                            self.query_one("#rename").action_press()
                        case key if key in config["keybinds"]["delete"]:
                            self.query_one("#delete").action_press()
                        case key if key in config["keybinds"]["toggle_visual"]:
                            await self.query_one("#file_list").toggle_mode()


start_watcher()
app = Application(watch_css=True)
