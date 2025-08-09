import shutil
from contextlib import suppress
from os import path
from types import SimpleNamespace

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    HorizontalGroup,
    HorizontalScroll,
    Vertical,
    VerticalGroup,
)
from textual.css.query import NoMatches
from textual.widgets import Input

from . import utils
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
from .HeaderArea import HeaderArea
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
from .utils import config
from .WidgetsCore import (
    FileList,
    PinnedSidebar,
    PreviewContainer,
)


class Application(App, inherit_bindings=False):
    # dont need ctrl+c
    BINDINGS = [
        Binding(
            "ctrl+q",
            "quit",
            "Quit",
            tooltip="Quit the app and return to the command prompt.",
            show=False,
            priority=True,
        )
    ]
    # higher index = higher priority
    CSS_PATH = ["style.tcss", path.join(VAR_TO_DIR["CONFIG"], "style.tcss")]
    # reactivity
    HORIZONTAL_BREAKPOINTS = [(0, "-filelistonly"), (60, "-nopreview"), (90, "-all")]
    # VERTICAL_BREAKPOINTS = [(0, "-footerless"), ()]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.prev_selected_option = None
        # TODO: need to actually do this.
        self.main_sort_by = config["settings"]["filelist_sort_by"]
        self.main_sort_order = config["settings"]["filelist_sort_order"]

    def compose(self) -> ComposeResult:
        print("Starting Rovr...")
        with Vertical(id="root"):
            yield HeaderArea(id="headerArea")
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
        # this will stay until a beta release.
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
        self.tabWidget = self.query_one("Tabline")
        # make the file list
        self.query_one("#file_list").update_file_list()
        self.query_one("#file_list").focus()

    def action_focus_next(self) -> None:
        if config["settings"]["allow_tab_nav"]:
            super().action_focus_next()
        else:
            return

    def action_focus_previous(self) -> None:
        if config["settings"]["allow_tab_nav"]:
            super().action_focus_previous()
        else:
            return

    async def on_key(self, event: events.Key) -> None:
        # Not really sure why this can happen, but I will still handle this
        if self.focused is None or not self.focused.id:
            return
        # Make sure that key binds don't break
        match event.key:
            # after input
            case key if (
                key in ["enter", "escape"] and self.focused.id == "path_switcher"
            ):
                await self.query_one(PathInput).action_submit()
                self.query_one("#file_list").focus()
                return
            # placeholder, not yet existing
            case "escape" if "search" in self.focused.id:
                match self.focused.id:
                    case "search_file_list":
                        self.query_one("#file_list").focus()
                    case "search_pinned_sidebar":
                        self.query_one("#pinned_sidebar").focus()
                return
            # backspace is used by default bindings to head up in history
            # so just avoid it
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
                elif self.query_one("#pinned_sidebar_container").display:
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
                elif self.query_one(PreviewContainer).display:
                    with suppress(NoMatches):
                        self.query_one("PreviewContainer > *").focus()
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
                elif self.query_one("#footer").display:
                    self.query_one("#processes").focus()
            # Focus metadata
            case key if key in config["keybinds"]["focus_toggle_metadata"]:
                if self.focused.id == "metadata":
                    self.query_one("#file_list").focus()
                elif self.query_one("#footer").display:
                    self.query_one("#metadata").focus()
            # Focus clipboard
            case key if key in config["keybinds"]["focus_toggle_clipboard"]:
                if self.focused.id == "clipboard":
                    self.query_one("#file_list").focus()
                elif self.query_one("#footer").display:
                    self.query_one("#clipboard").focus()
            # file list keybind stuff
            case key if (
                key in config["keybinds"]["copy"]
                and self.query_one("#file_list").has_focus
            ):
                await self.query_one(CopyButton).on_button_pressed(CopyButton.Pressed)
            case key if (
                key in config["keybinds"]["cut"]
                and self.query_one("#file_list").has_focus
            ):
                await self.query_one(CutButton).on_button_pressed(CutButton.Pressed)
            case key if (
                key in config["keybinds"]["paste"]
                and self.query_one("#file_list").has_focus
            ):
                await self.query_one(PasteButton).on_button_pressed(PasteButton.Pressed)
            case key if (
                key in config["keybinds"]["new"]
                and self.query_one("#file_list").has_focus
            ):
                self.query_one(NewItemButton).on_button_pressed(NewItemButton.Pressed)
            case key if (
                key in config["keybinds"]["rename"]
                and self.query_one("#file_list").has_focus
            ):
                self.query_one(RenameItemButton).on_button_pressed(
                    RenameItemButton.Pressed
                )
            case key if (
                key in config["keybinds"]["delete"]
                and self.query_one("#file_list").has_focus
            ):
                await self.query_one(DeleteButton).on_button_pressed(
                    DeleteButton.Pressed
                )
            # toggle select mode
            case key if (
                key in config["keybinds"]["toggle_visual"]
                and self.query_one("#file_list").has_focus
            ):
                await self.query_one("#file_list", FileList).toggle_mode()
            # Toggle hiding panels
            case key if key in config["keybinds"]["toggle_pinned_sidebar"]:
                self.query_one("#file_list").focus()
                if self.query_one("#pinned_sidebar_container").display:
                    self.query_one("#pinned_sidebar_container").add_class("hide")
                else:
                    self.query_one("#pinned_sidebar_container").remove_class("hide")
            case key if key in config["keybinds"]["toggle_preview_sidebar"]:
                self.query_one("#file_list").focus()
                if self.query_one(PreviewContainer).display:
                    self.query_one(PreviewContainer).add_class("hide")
                else:
                    self.query_one(PreviewContainer).remove_class("hide")
            case key if key in config["keybinds"]["toggle_footer"]:
                self.query_one("#file_list").focus()
                if self.query_one("#footer").display:
                    self.query_one("#footer").add_class("hide")
                else:
                    self.query_one("#footer").remove_class("hide")
            case key if (
                key in config["keybinds"]["tab_next"]
                and self.tabWidget.active_tab is not None
            ):
                self.tabWidget.action_next_tab()
            case key if (
                key in config["keybinds"]["tab_previous"]
                and self.tabWidget.active_tab is not None
            ):
                self.tabWidget.action_previous_tab()
            case key if key in config["keybinds"]["tab_new"]:
                await self.tabWidget.add_tab(after=self.tabWidget.active_tab)
            case key if (
                key in config["keybinds"]["tab_close"] and self.tabWidget.tab_count > 1
            ):
                await self.tabWidget.remove_tab(self.tabWidget.active_tab)
            # zoxide
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
                        pathinput.value = utils.decompress(response).replace(
                            path.sep, "/"
                        )
                        pathinput.on_input_submitted(
                            SimpleNamespace(value=pathinput.value)
                        )

                self.push_screen(ZToDirectory(), on_response)
            # zen mode
            case key if key in config["plugins"]["zen_mode"]["keybinds"]:
                if "zen" in self.classes:
                    self.remove_class("zen")
                else:
                    self.add_class("zen")


app = Application(watch_css=True)
