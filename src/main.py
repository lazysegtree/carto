from Actions import create_new_item, remove_files, rename_object
from maps import ICONS
from types import SimpleNamespace as Namespace
from os import getcwd, path, chdir
from ScreensCore import ZToDirectory, ModalInput, DeleteFiles
import shutil
import state
from textual import work, on, events
from textual.app import App, ComposeResult
from textual.containers import (
    HorizontalGroup,
    HorizontalScroll,
    Vertical,
    VerticalGroup,
)
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
)
from themes import get_custom_themes
from WidgetsCore import (
    PathAutoCompleteInput,
    update_file_list,
    PreviewContainer,
    PinnedSidebar,
    FileList,
    Clipboard,
    dummy_update_file_list,
)


state.load_config()
state.load_pins()


class Application(App):
    CSS_PATH = "style.tcss"

    HORIZONTAL_BREAKPOINTS = [(0, "-filelistonly"), (60, "-nopreview"), (90, "-all")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_selected_option = None
        self.main_sort_by = state.config["settings"]["filelist_sort_by"]
        self.main_sort_order = state.config["settings"]["filelist_sort_order"]

    def compose(self) -> ComposeResult:
        print("Starting Carto...")
        path_switcher = Input(
            id="path_switcher",
            validators=[Function(lambda x: path.exists(x), "Path does not exist")],
        )
        yield Header(name="carto", show_clock=True, icon="📁")
        with Vertical(id="root"):
            with HorizontalScroll(id="menu"):
                yield Button(
                    ICONS["general"]["up"][0],
                    classes="option",
                    id="sort_order",
                )
                yield Button(ICONS["general"]["copy"][0], classes="option", id="copy")
                yield Button(
                    ICONS["general"]["cut"][0],
                    classes="option",
                    id="cut",
                )
                yield Button(
                    ICONS["general"]["paste"][0],
                    classes="option",
                    id="paste",
                    disabled=True,
                )
                yield Button(
                    ICONS["general"]["new"][0],
                    classes="option",
                    id="new",
                )
                yield Button(
                    ICONS["general"]["rename"][0],
                    classes="option",
                    id="rename",
                )
                yield Button(
                    ICONS["general"]["delete"][0],
                    classes="option",
                    id="delete",
                )
            with VerticalGroup(id="below_menu"):
                with HorizontalGroup():
                    yield Button(ICONS["general"]["left"][0], id="back")
                    yield Button(ICONS["general"]["right"][0], id="forward")
                    yield Button(ICONS["general"]["up"][0], id="up")
                    yield Button(ICONS["general"]["refresh"][0], id="reload")
                    yield path_switcher
                yield PathAutoCompleteInput(
                    target=path_switcher,
                    path=getcwd().split(path.sep)[0],
                    folder_prefix=ICONS["folder"]["default"][0] + " ",
                    file_prefix=ICONS["file"]["default"][0] + " ",
                    id="path_autocomplete",
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
                yield RichLog(id="processes", highlight=True, markup=True, wrap=True)
                yield VerticalGroup(id="metadata")
                yield Clipboard(id="clipboard")

    def on_mount(self):
        # border titles
        self.query_one("#menu").border_title = "Options"
        self.query_one("#below_menu").border_title = "Directory Actions"
        self.query_one("#pinned_sidebar_container").border_title = "Sidebar"
        self.query_one("#file_list_container").border_title = "Files"
        self.query_one("#processes").border_title = "Processes"
        self.query_one("#metadata").border_title = "Metadata"
        self.query_one("#clipboard").border_title = "Clipboard"
        self.title = "Carto - " + getcwd().replace(path.sep, "/")
        # themes
        for theme in get_custom_themes():
            self.register_theme(theme)
        self.theme = state.config["theme"]["default"]
        # tooltips
        if state.config["interface"]["tooltips"]:
            self.query_one("#sort_order").tooltip = "Lists are in ascending order"
            self.query_one("#copy").tooltip = "Copy selected files"
            self.query_one("#cut").tooltip = "Cut selected files"
            self.query_one("#paste").tooltip = "Paste files from clipboard"
            self.query_one("#delete").tooltip = "Delete selected files"
            self.query_one("#rename").tooltip = "Rename selected file"
            self.query_one("#new").tooltip = "Create a new file or directory"
            self.query_one("#back").tooltip = "Go back in history"
            self.query_one("#forward").tooltip = "Go forward in history"
            self.query_one("#up").tooltip = "Go up the directory tree"
            self.query_one("#reload").tooltip = "Reload the file list"

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
    async def reload_file_list(self, event: Button.Pressed) -> None:
        """Reload the file list"""
        update_file_list(
            self,
            "#file_list",
            self.main_sort_by,
            self.main_sort_order,
            add_to_session=False,
        )
        file_list = self.query_one("#file_list")
        cd_into = file_list.get_option_at_index(file_list.highlighted).value
        self.query_one("#preview_sidebar").show_preview(cd_into)

    @on(Button.Pressed, "#copy")
    async def copy_files(self, event: Button.Pressed) -> None:
        """Copy selected files to the clipboard"""
        file_list = self.query_one("#file_list")
        selected_files = await file_list.get_selected_objects()
        if selected_files:
            await self.query_one("#clipboard").add_to_clipboard(selected_files)
        else:
            self.app.notify(
                "No files selected to copy.", title="Clipboard", severity="warning"
            )

    @on(Button.Pressed, "#cut")
    async def cut_files(self, event: Button.Pressed) -> None:
        """Cut selected files to the clipboard"""
        file_list = self.query_one("#file_list")
        selected_files = await file_list.get_selected_objects()
        if selected_files:
            await self.query_one("#clipboard").cut_to_clipboard(selected_files)
        else:
            self.app.notify(
                "No files selected to cut.", title="Clipboard", severity="warning"
            )

    @on(Button.Pressed, "#new")
    async def create_new_object(self, event: Button.Pressed) -> None:
        self.push_screen(
            ModalInput(
                border_title="Create New Item",
                border_subtitle="End with a slash (/) to create a directory",
            ),
            callback=lambda response: create_new_item(self, response),
        )

    @on(Button.Pressed, "#delete")
    async def delete_files(self, event: Button.Pressed) -> None:
        """Delete selected files or directories"""
        file_list = self.query_one("#file_list")
        selected_files = await file_list.get_selected_objects()
        if selected_files:

            async def callback(response: str) -> None:
                """Callback to remove files after confirmation"""
                if response == "delete":
                    await remove_files(
                        self, selected_files, ignore_trash=True, compressed=False
                    )
                elif response == "trash":
                    await remove_files(
                        self, selected_files, ignore_trash=False, compressed=False
                    )
                else:
                    self.notify("File deletion cancelled.", title="Delete Files")

            self.push_screen(
                DeleteFiles(
                    message=f"Are you sure you want to delete {len(selected_files)} files?",
                ),
                callback=callback,
            )
        else:
            self.notify(
                "No files selected to delete.", title="Delete Files", severity="warning"
            )

    @on(Button.Pressed, "#rename")
    async def rename_file(self, event: Button.Pressed) -> None:
        """Rename the selected file or directory"""
        file_list = self.query_one("#file_list")
        selected_files = await file_list.get_selected_objects()
        if selected_files is None or len(selected_files) != 1:
            self.notify(
                "Please select exactly one file to rename.",
                title="Rename File",
                severity="warning",
            )
        else:
            selected_file = selected_files[0]
            type_of_file = "Folder" if path.isdir(selected_file) else "File"
            self.push_screen(
                ModalInput(
                    border_title=f"Rename {type_of_file}",
                    border_subtitle=f"Current name: {path.basename(selected_file)}",
                    initial_value=path.basename(selected_file),
                ),
                callback=lambda response: rename_object(self, selected_file, response),
            )

    @work
    async def update_session_dicts(
        self, sessionDirs, sessionHisIndex, sessionLastHighlight
    ) -> None:
        """Update the session directories and history index"""
        state.update_session_state(sessionDirs, sessionHisIndex, sessionLastHighlight)

    @work
    async def on_key(self, event: events.Key) -> None:
        if self.focused is None or not self.focused.id:
            return
        # make sure that keybinds dont break
        if self.focused.id == "path_switcher" and event.key in ["enter", "escape"]:
            self.query_one("#file_list").focus()
            await self.query_one("#path_switcher").action_submit()
            return
        elif "search" in self.focused.id and event.key == "escape":
            if self.focused.id == "search_file_list":
                self.query_one("#file_list").focus()
            elif self.focused.id == "search_pinned_sidebar":
                self.query_one("#pinned_sidebar").focus()
                return
        elif (
            type(self.focused) is Input or "search" in self.focused.id
        ) and event.key == "backspace":
            return
        # focus toggle pinned sidebar
        event.prevent_default()
        if event.key in state.config["keybinds"]["focus_toggle_pinned_sidebar"]:
            if (
                self.focused.id == "pinned_sidebar"
                or "hide" in self.query_one("#pinned_sidebar_container").classes
            ):
                self.query_one("#file_list").focus()
            else:
                self.query_one("#pinned_sidebar").focus()
        # focus file list from anywhere except input
        elif event.key in state.config["keybinds"]["focus_file_list"]:
            self.query_one("#file_list").focus()
        # focus toggle preview sidebar
        elif event.key in state.config["keybinds"]["focus_toggle_preview_sidebar"]:
            if (
                self.focused.id == "preview_sidebar"
                or self.focused.parent.id == "preview_sidebar"
                or "hide" in self.query_one("#preview_sidebar").classes
            ):
                self.query_one("#file_list").focus()
            else:
                self.query_one("#preview_sidebar *").focus()
        # focus path switcher
        elif event.key in state.config["keybinds"]["focus_toggle_path_switcher"]:
            self.query_one("#path_switcher").focus()
        # focus processes
        elif event.key in state.config["keybinds"]["focus_toggle_processes"]:
            if (
                self.focused.id == "processes"
                or "hide" in self.query_one("#processes").classes
            ):
                self.query_one("#file_list").focus()
            else:
                self.query_one("#processes").focus()
        # focus metadata
        elif event.key in state.config["keybinds"]["focus_toggle_metadata"]:
            if self.focused.id == "metadata":
                self.query_one("#file_list").focus()
            else:
                self.query_one("#metadata").focus()
        # focus clipboard
        elif event.key in state.config["keybinds"]["focus_toggle_clipboard"]:
            if self.focused.id == "clipboard":
                self.query_one("#file_list").focus()
            else:
                self.query_one("#clipboard").focus()
        # navi buttons but keybind
        elif event.key in state.config["keybinds"]["hist_previous"]:
            if self.query_one("#back").disabled:
                self.go_up_path(Button.Pressed(self.query_one("#up")))
            else:
                self.go_back_in_history(Button.Pressed(self.query_one("#back")))
        elif event.key in state.config["keybinds"]["hist_next"]:
            if not self.query_one("#forward").disabled:
                self.go_forward_in_history(
                    Button.Pressed(
                        self.query_one("#forward"),
                    )
                )
        elif event.key in state.config["keybinds"]["up_tree"]:
            self.go_up_path(Button.Pressed(self.query_one("#up")))
        elif event.key in state.config["keybinds"]["reload"]:
            self.reload_file_list(Button.Pressed(self.query_one("#reload")))
        # toggle pin on current directory
        elif event.key in state.config["keybinds"]["toggle_pin"]:
            state.toggle_pin(path.basename(getcwd()), getcwd())
            await self.query_one("#pinned_sidebar").reload_pins()
        # toggle hiding panels
        elif event.key in state.config["keybinds"]["toggle_pinned_sidebar"]:
            self.query_one("#file_list").focus()
            if self.query_one("#pinned_sidebar_container").display:
                self.query_one("#pinned_sidebar_container").add_class("hide")
            else:
                self.query_one("#pinned_sidebar_container").remove_class("hide")
        elif event.key in state.config["keybinds"]["toggle_preview_sidebar"]:
            self.query_one("#file_list").focus()
            if self.query_one("#preview_sidebar").display:
                self.query_one("#preview_sidebar").add_class("hide")
            else:
                self.query_one("#preview_sidebar").remove_class("hide")
        elif event.key in state.config["keybinds"]["toggle_footer"]:
            self.query_one("#file_list").focus()
            if self.query_one("#footer").display:
                self.query_one("#footer").add_class("hide")
            else:
                self.query_one("#footer").remove_class("hide")
        elif event.key in state.config["keybinds"]["toggle_visual"]:
            await self.query_one("#file_list").toggle_mode()
        elif (
            event.key in state.config["plugins"]["zoxide"]["keybinds"]
            and state.config["plugins"]["zoxide"]["enabled"]
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
                    self.switch_to_path(Namespace(value=state.decompress(response)))

            self.push_screen(ZToDirectory(), on_response)


state.start_watcher()
app = Application(watch_css=True)
app.run()
