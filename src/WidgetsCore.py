from humanize import naturalsize
from maps import (
    get_icon_for_file,
    get_icon_for_folder,
    EXT_TO_LANG_MAP,
    PIL_EXTENSIONS,
    TOGGLE_BUTTON_ICONS,
    ICONS,
)
from os import listdir, path, getcwd, chdir, scandir
from pathlib import Path
import platform
from rich.segment import Segment
from rich.style import Style
import state
import subprocess
from textual import events, work, on
from textual.app import ComposeResult, App
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.content import Content
from textual.css.query import NoMatches
from textual.strip import Strip
from textual.types import DuplicateID
from textual.widgets import OptionList, Static, TextArea, SelectionList
from textual.widgets.option_list import Option, OptionDoesNotExist
from textual.widgets.selection_list import Selection
from textual_autocomplete import PathAutoComplete, TargetState, DropdownItem
from typing import ClassVar

state.load_config()


def open_file(filepath: str) -> None:
    """Cross-platform function to open files with their default application.

    Args:
        filepath (str): Path to the file to open
    """
    system = platform.system().lower()

    try:
        if system == "windows":
            from os import startfile

            startfile(filepath)
        elif system == "darwin":  # macOS
            subprocess.run(["open", filepath], check=True)
        else:  # Linux and other Unix-like
            subprocess.run(["xdg-open", filepath], check=True)
    except Exception as e:
        print(f"Error opening file: {e}")


try:
    from textual_image.widget import AutoImage
except TimeoutError:
    pass


class PathDropdownItem(DropdownItem):
    def __init__(self, completion: str, path: Path) -> None:
        super().__init__(completion)
        self.path = path


class PathAutoCompleteInput(PathAutoComplete):
    def should_show_dropdown(self, search_string: str) -> bool:
        default_behavior = super().should_show_dropdown(search_string)
        return (
            default_behavior
            or (search_string == "" and self.target.value != "")
            and self.option_list.option_count > 0
        )

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """Get the candidates for the current path segment, folders only."""
        current_input = target_state.text[: target_state.cursor_position]

        if "/" in current_input:
            last_slash_index = current_input.rindex("/")
            path_segment = current_input[:last_slash_index] or "/"
            directory = self.path / path_segment if path_segment != "/" else self.path
        else:
            directory = self.path

        # Use the directory path as the cache key
        cache_key = str(directory)
        cached_entries = self._directory_cache.get(cache_key)

        if cached_entries is not None:
            entries = cached_entries
        else:
            try:
                entries = list(scandir(directory))
                self._directory_cache[cache_key] = entries
            except OSError:
                return []

        results: list[PathDropdownItem] = []
        has_directories = False

        for entry in entries:
            if entry.is_dir():
                has_directories = True
                completion = entry.name
                if not self.show_dotfiles and completion.startswith("."):
                    continue
                completion += "/"
                results.append(PathDropdownItem(completion, path=Path(entry.path)))

        if not has_directories:
            self._empty_directory = True
            return [DropdownItem("", prefix="No folders found")]
        else:
            self._empty_directory = False

        results.sort(key=self.sort_key)
        folder_prefix = self.folder_prefix
        return [
            DropdownItem(
                item.main,
                prefix=folder_prefix,
            )
            for item in results
        ]

    def _align_to_target(self) -> None:
        """Empty function that was supposed to align the completion box to the cursor."""
        pass

    def _on_show(self, event):
        super()._on_show(event)
        self._target.add_class("hide_border_bottom", update=True)

    async def _on_hide(self, event):
        super()._on_hide(event)
        self._target.remove_class("hide_border_bottom", update=True)
        await self._target.action_submit()
        self._target.focus()


def get_cwd_object(cwd: str, sort_order: str, sort_by: str) -> list[dict]:
    folders, files = [], []
    try:
        listed_dir = listdir(cwd)
    except (PermissionError, FileNotFoundError, OSError):
        print(f"PermissionError: Unable to access {cwd}")
        return [PermissionError], [PermissionError]
    for item in listed_dir:
        if path.isdir(path.join(cwd, item)):
            folders.append(
                {
                    "name": f"{item}",
                    "icon": get_icon_for_folder(item),
                }
            )
        else:
            files.append({"name": item, "icon": get_icon_for_file(item)})
    if files == [] and folders == []:
        print(f"No files or folders found in {cwd}")
        return [{"name": "..", "icon": ["", "red"]}], []
    # Sort folders and files properly
    folders.sort(key=lambda x: x["name"].lower(), reverse=(sort_order == "descending"))
    files.sort(key=lambda x: x["name"].lower(), reverse=(sort_order == "descending"))
    print(f"Found {len(folders)} folders and {len(files)} files in {cwd}")
    return folders, files


def update_file_list(
    appInstance: App,
    file_list_id: str,
    sort_by: str = "name",
    sort_order: str = "ascending",
    add_to_session: bool = True,
) -> None:
    """Update the file list with the current directory contents.

    Args:
        appInstance: The application instance.
        file_list_id (str): The ID of the file list widget.
        sort_by (str): The attribute to sort by ("name" or "size").
        sort_order (str): The order to sort by ("ascending" or "descending").
        add_to_session (bool): Whether to add the current directory to the session history.
    """
    cwd = getcwd()
    file_list = appInstance.query_one(f"{file_list_id}")
    file_list.clear_options()
    # seperate folders and files
    folders, files = get_cwd_object(cwd, sort_order, sort_by)
    if folders == [PermissionError] or files == [PermissionError]:
        file_list.add_option(
            Selection(
                Content("Permission Error: Unable to access this directory."),
                value="HTI",
            ),
        )
        file_list_options = [".."]
    else:
        file_list_options = (
            files + folders if sort_order == "descending" else folders + files
        )
        for item in file_list_options:
            file_list.add_option(
                Selection(
                    Content.from_markup(
                        f" [{item['icon'][1]}]{item['icon'][0]}[/{item['icon'][1]}] $name",
                        name=item["name"],
                    ),
                    value=state.compress(item["name"]),
                )
            )
    # session handler
    appInstance.query_one("#path_switcher").value = cwd.replace(path.sep, "/") + "/"
    if add_to_session:
        if state.sessionHistoryIndex != len(state.sessionDirectories) - 1:
            state.sessionDirectories = state.sessionDirectories[
                : state.sessionHistoryIndex + 1
            ]
        state.sessionDirectories.append(
            {
                "path": cwd,
                "highlighted": appInstance.query_one("#file_list").options[0].value,
            }
        )
        state.sessionHistoryIndex = len(state.sessionDirectories) - 1
        appInstance.update_session_dicts(
            state.sessionDirectories,
            state.sessionHistoryIndex,
        )
    appInstance.query_one("Button#back").disabled = (
        True if state.sessionHistoryIndex == 0 else False
    )
    appInstance.query_one("Button#forward").disabled = (
        True
        if state.sessionHistoryIndex == len(state.sessionDirectories) - 1
        else False
    )
    try:
        file_list.highlighted = file_list.get_option_index(
            state.sessionDirectories[state.sessionHistoryIndex]["highlighted"]
        )
    except OptionDoesNotExist:
        file_list.highlighted = 0
    appInstance.title = f"carto - {cwd.replace(path.sep, '/')}"


def dummy_update_file_list(
    appInstance: App,
    file_list_id: str,
    sort_by: str = "name",
    sort_order: str = "ascending",
    cwd: str = "",
) -> None:
    """Update the file list with the current directory contents.

    Args:
        appInstance: The application instance.
        file_list_id (str): The ID of the file list widget.
        sort_by (str): The attribute to sort by ("name" or "size").
        sort_order (str): The order to sort by ("ascending" or "descending").
        cwd (str): The current working directory.
    """
    if cwd == "":
        cwd = getcwd()
    file_list = appInstance.query_one(f"{file_list_id}")
    file_list.clear_options()
    # seperate folders and files
    folders, files = get_cwd_object(cwd, sort_order, sort_by)
    if folders == [PermissionError] or files == [PermissionError]:
        file_list.add_option(
            Selection(
                Content("Permission Error: Unable to access this directory."),
                id="HTI",
            )
        )
        return
    file_list_options = (
        files + folders if sort_order == "descending" else folders + files
    )
    for item in file_list_options:
        file_list.add_option(
            Selection(
                Content.from_markup(
                    f" [{item['icon'][1]}]{item['icon'][0]}[/{item['icon'][1]}] $name",
                    name=item["name"],
                ),
                value=state.compress(item["name"]),
            )
        )


class PreviewContainer(Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_task = False

    def compose(self) -> ComposeResult:
        yield TextArea(
            id="text_preview",
            show_line_numbers=True,
            soft_wrap=False,
            read_only=True,
            text=state.config["sidebar"]["text"]["start"],
            language="markdown",
            compact=True,
        )

    @work(exclusive=True)
    async def show_preview(self, file_path: str) -> None:
        """Show the preview of the file or folder in the preview container."""
        if self._update_task and self._update_task._active:
            self._update_task.stop()
        if path.isdir(file_path):
            self._update_task = self.set_timer(
                0.25, lambda: self.show_folder(file_path)
            )
        else:
            self._update_task = self.set_timer(0.25, lambda: self.show_file(file_path))

    async def show_file(self, file_path: str) -> None:
        """Show the file in the preview container."""
        if len(self.children) != 0:
            await self.remove_children()
        if any(file_path.endswith(ext) for ext in PIL_EXTENSIONS):
            await self.mount(AutoImage(file_path, id="image_preview"))
            self.border_title = "Image Preview"
            self.query_one("#image_preview").can_focus = True
        else:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    await self.mount(
                        TextArea(
                            id="text_preview",
                            show_line_numbers=True,
                            soft_wrap=False,
                            read_only=True,
                            text=f.read(),
                            language=EXT_TO_LANG_MAP.get(
                                path.splitext(file_path)[1], "markdown"
                            ),
                            compact=True,
                        )
                    )
            except UnicodeDecodeError:
                await self.mount(
                    TextArea(
                        id="text_preview",
                        show_line_numbers=True,
                        soft_wrap=False,
                        read_only=True,
                        text=state.config["sidebar"]["text"]["binary"],
                        language="markdown",
                        compact=True,
                    )
                )
            except (FileNotFoundError, PermissionError, OSError):
                await self.mount(
                    TextArea(
                        id="text_preview",
                        show_line_numbers=True,
                        soft_wrap=False,
                        read_only=True,
                        text=state.config["sidebar"]["text"]["error"],
                        language="markdown",
                        compact=True,
                    )
                )
            finally:
                self.border_title = "File Preview"

    async def show_folder(self, folder_path: str) -> None:
        """Show the folder in the preview container."""
        if len(self.children) != 0:
            await self.remove_children()
        await self.mount(
            FileList(
                id="folder_preview",
                name=folder_path,
                classes="file-list",
                sort_by="name",
                sort_order="ascending",
                dummy=True,
                enter_into=path.relpath(getcwd(), folder_path),
            )
        )
        dummy_update_file_list(
            self.app,
            "#folder_preview",
            sort_by="name",
            sort_order="ascending",
            cwd=folder_path,
        )
        self.border_title = "Folder Preview"


class FolderNotFileError(Exception):
    """Raised when a folder is expected but a file is provided instead."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PinnedSidebar(OptionList, inherit_bindings=False):
    BINDINGS: ClassVar[list[BindingType]] = (
        [
            Binding(bind, "cursor_down", "Down", show=False)
            for bind in state.config["keybinds"]["navigation"]["down"]
        ]
        + [
            Binding(bind, "last", "Last", show=False)
            for bind in state.config["keybinds"]["navigation"]["end"]
        ]
        + [
            Binding(bind, "select", "Select", show=False)
            for bind in state.config["keybinds"]["navigation"]["down_tree"]
        ]
        + [
            Binding(bind, "first", "First", show=False)
            for bind in state.config["keybinds"]["navigation"]["home"]
        ]
        + [
            Binding(bind, "page_down", "Page Down", show=False)
            for bind in state.config["keybinds"]["navigation"]["page_down"]
        ]
        + [
            Binding(bind, "page_up", "Page Up", show=False)
            for bind in state.config["keybinds"]["navigation"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_up", "Up", show=False)
            for bind in state.config["keybinds"]["navigation"]["up"]
        ]
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.default = state.pins["default"]
        print(self.default)
        self.pins = state.pins["pins"]
        print(self.pins)
        self.drives = state.get_mounted_drives()
        print(f"Detected drives: {self.drives}")

    def compose(self) -> ComposeResult:
        yield Static()

    async def reload_pins(self):
        # be extra sure
        state.load_pins()
        self.pins = state.pins["pins"]
        self.default = state.pins["default"]
        print(f"Reloading pins: {self.pins}")
        await self.remove_children()
        print(f"Reloading default folders: {self.default}")
        self.clear_options()
        for default_folder in self.default:
            if not path.isdir(default_folder["path"]):
                if path.exists(default_folder["path"]):
                    raise FolderNotFileError(
                        f"Expected a folder but got a file: {default_folder['path']}"
                    )
                else:
                    pass
            if "icon" in default_folder:
                icon = default_folder["icon"]
            elif path.isdir(default_folder["path"]):
                icon = get_icon_for_folder(default_folder["name"])
            else:
                icon = get_icon_for_file(default_folder["name"])
            self.add_option(
                Option(
                    Content.from_markup(
                        f" [{icon[1]}]{icon[0]}[/{icon[1]}] $name",
                        name=default_folder["name"],
                    ),
                    id=f"{state.compress(default_folder['path'])}-default",
                )
            )
        self.add_option(Option("Pinned", id="pinned-header"))
        for pin in self.pins:
            try:
                pin["path"]
            except KeyError:
                break
            if not path.isdir(pin["path"]):
                if path.exists(pin["path"]):
                    raise FolderNotFileError(
                        f"Expected a folder but got a file: {pin['path']}"
                    )
                else:
                    pass
            if "icon" in pin:
                icon = pin["icon"]
            elif path.isdir(pin["path"]):
                icon = get_icon_for_folder(pin["name"])
            else:
                icon = get_icon_for_file(pin["name"])
            self.add_option(
                Option(
                    Content.from_markup(
                        f" [{icon[1]}]{icon[0]}[/{icon[1]}] $name",
                        name=pin["name"],
                    ),
                    id=f"{state.compress(pin['path'])}-pinned",
                )
            )
        self.add_option(Option("Drives", id="drives-header"))
        self.drives = state.get_mounted_drives()
        for drive in self.drives:
            self.add_option(
                Option(
                    f" \uf0a0 {drive}",
                    id=f"{state.compress(drive)}-drives",
                )
            )
        self.disable_option("pinned-header")
        self.disable_option("drives-header")

    async def on_mount(self):
        """Reload the pinned files from the config."""
        state.load_pins()
        self.pins = state.pins["pins"]
        await self.reload_pins()

    async def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle the selection of an option in the pinned sidebar."""
        selected_option = event.option
        # Get the file path from the option id
        file_path = state.decompress(selected_option.id.split("-")[0])
        if not path.isdir(file_path):
            if path.exists(file_path):
                raise FolderNotFileError(
                    f"Expected a folder but got a file: {file_path}"
                )
            else:
                return
        chdir(file_path)
        update_file_list(self.app, "#file_list", "name", "ascending")
        self.app.query_one("#file_list").focus()


class FileList(SelectionList, inherit_bindings=False):
    """
    OptionList but can multi-select files and folders.
    """

    BINDINGS: ClassVar[list[BindingType]] = (
        [
            Binding(bind, "cursor_down", "Down", show=False)
            for bind in state.config["keybinds"]["navigation"]["down"]
        ]
        + [
            Binding(bind, "last", "Last", show=False)
            for bind in state.config["keybinds"]["navigation"]["end"]
        ]
        + [
            Binding(bind, "select", "Select", show=False)
            for bind in state.config["keybinds"]["navigation"]["down_tree"]
        ]
        + [
            Binding(bind, "first", "First", show=False)
            for bind in state.config["keybinds"]["navigation"]["home"]
        ]
        + [
            Binding(bind, "page_down", "Page Down", show=False)
            for bind in state.config["keybinds"]["navigation"]["page_down"]
        ]
        + [
            Binding(bind, "page_up", "Page Up", show=False)
            for bind in state.config["keybinds"]["navigation"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_up", "Up", show=False)
            for bind in state.config["keybinds"]["navigation"]["up"]
        ]
    )

    def __init__(
        self,
        sort_by: str,
        sort_order: str,
        dummy: bool = False,
        enter_into: str = "",
        select: bool = False,
        *args,
        **kwargs,
    ):
        """
        Initialize the FileList widget.
        Args:
            sort_by (str): The attribute to sort by ("name" or "size").
            sort_order (str): The order to sort by ("ascending" or "descending").
            dummy (bool): Whether this is a dummy file list.
            enter_into (str): The path to enter into when a folder is selected.
            select (bool): Whether the selection is select or normal.
        """
        super().__init__(*args, **kwargs)
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.dummy = dummy
        self.enter_into = enter_into
        self.select_mode_enabled = select

    # ignore single clicks
    async def _on_click(self, event: events.Click) -> None:
        """React to the mouse being clicked on an item.

        Args:
            event: The click event.
        """
        event.prevent_default()
        clicked_option: int | None = event.style.meta.get("option")
        if clicked_option is not None and not self._options[clicked_option].disabled:
            if self.highlighted == clicked_option:
                self.action_select()
            else:
                self.highlighted = clicked_option

    def compose(self) -> ComposeResult:
        yield Static()

    async def on_mount(self, add_to_history: bool = True) -> None:
        """Initialize the file list."""
        try:
            self.query_one("Static").remove()
        except NoMatches:
            pass
        if not self.dummy:
            update_file_list(
                self.app,
                "#file_list",
                sort_by=self.sort_by,
                sort_order=self.sort_order,
                add_to_session=add_to_history,
            )
            self.focus()

    async def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        if self.dummy:
            return
        if not self.select_mode_enabled:
            event.prevent_default()
            cwd = getcwd()
            # Get the selected option
            selected_option = self.get_option_at_index(
                self.highlighted
            )  # ? trust me bro
            # Get the file name from the option id
            file_name = state.decompress(selected_option.value)
            # Check if it's a folder or a file
            if path.isdir(path.join(cwd, file_name)):
                # If it's a folder, navigate into it
                chdir(path.join(cwd, file_name))
                update_file_list(self.app, "#file_list", self.sort_by, self.sort_order)
            else:
                open_file(path.join(cwd, file_name))
            if self.highlighted is None:
                self.highlighted = 0
            state.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                True,
            )
        else:
            state.set_scuffed_subtitle(
                self.parent, "SELECT", f"{len(self.selected)}/{len(self.options)}", True
            )

    # no clue why im using optionlist in a selectionlist, but it works
    async def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if self.dummy:
            return
        elif event.option.value == "HTI":
            self.app.query_one("#preview_sidebar").remove_children()
            return  # ignore folders that go to prev dir
        if self.select_mode_enabled:
            state.set_scuffed_subtitle(
                self.parent,
                "SELECT",
                f"{len(self.selected)}/{len(self.options)}",
                True,
            )
            return
        # Get the highlighted option
        highlighted_option = event.option
        state.sessionDirectories[state.sessionHistoryIndex]["highlighted"] = (
            event.option.value
        )
        # Get the file name from the option id
        file_name = state.decompress(highlighted_option.value)
        # total files as footer
        if self.highlighted is None:
            self.highlighted = 0
        state.set_scuffed_subtitle(
            self.parent, "NORMAL", f"{self.highlighted + 1}/{self.option_count}", True
        )
        # preview
        self.app.query_one("#preview_sidebar").show_preview(
            path.join(getcwd(), file_name)
        )

    # Use better versions of the checkbox icons

    def _get_left_gutter_width(
        self,
    ) -> int:
        """Returns the size of any left gutter that should be taken into account.

        Returns:
            The width of the left gutter.
        """
        if self.dummy or not self.select_mode_enabled:
            return 0
        else:
            return len(
                TOGGLE_BUTTON_ICONS["left"]
                + TOGGLE_BUTTON_ICONS["inner"]
                + TOGGLE_BUTTON_ICONS["right"]
                + " "
            )

    def render_line(self, y: int) -> Strip:
        """Render a line in the display.

        Args:
            y: The line to render.

        Returns:
            A [`Strip`][textual.strip.Strip] that is the line to render.
        """
        line = super(SelectionList, self).render_line(y)

        if self.dummy or not self.select_mode_enabled:
            return Strip([*line])

        _, scroll_y = self.scroll_offset
        selection_index = scroll_y + y
        try:
            selection = self.get_option_at_index(selection_index)
        except OptionDoesNotExist:
            return line

        component_style = "selection-list--button"
        if selection.value in self._selected:
            component_style += "-selected"
        if self.highlighted == selection_index:
            component_style += "-highlighted"

        underlying_style = next(iter(line)).style or self.rich_style
        assert underlying_style is not None

        button_style = self.get_component_rich_style(component_style)

        side_style = Style.from_color(button_style.bgcolor, underlying_style.bgcolor)

        side_style += Style(meta={"option": selection_index})
        button_style += Style(meta={"option": selection_index})

        return Strip(
            [
                Segment(TOGGLE_BUTTON_ICONS["left"], style=side_style),
                Segment(
                    TOGGLE_BUTTON_ICONS["inner_filled"]
                    if selection.value in self._selected
                    else TOGGLE_BUTTON_ICONS["inner"],
                    style=button_style,
                ),
                Segment(TOGGLE_BUTTON_ICONS["right"], style=side_style),
                Segment(" ", style=underlying_style),
                *line,
            ]
        )

    async def toggle_mode(self) -> None:
        """Toggle the selection mode between select and normal."""
        self.select_mode_enabled = not self.select_mode_enabled
        highlighted = self.highlighted
        await self.on_mount(add_to_history=False)
        self.highlighted = highlighted

    @on(events.Focus)
    @work
    async def event_on_focus(self, event: events.Focus) -> None:
        """Handle the focus event to update the border style."""
        if self.dummy:
            return
        elif self.select_mode_enabled:
            state.set_scuffed_subtitle(
                self.parent, "SELECT", f"{len(self.selected)}/{len(self.options)}", True
            )
        else:
            if self.highlighted is None:
                self.highlighted = 0
            state.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                True,
            )

    @on(events.Blur)
    @work
    async def event_on_blur(self, event: events.Blur) -> None:
        """Handle the leave event to update the border style"""
        if self.select_mode_enabled:
            state.set_scuffed_subtitle(
                self.parent,
                "SELECT",
                f"{len(self.selected)}/{len(self.options)}",
                False,
            )
        else:
            if self.highlighted is None:
                self.highlighted = 0
            state.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                False,
            )

    async def get_selected_objects(self) -> list[str]:
        """Get the selected objects in the file list."""
        cwd = getcwd()
        if not self.select_mode_enabled:
            return [
                path.join(
                    cwd,
                    state.decompress(self.get_option_at_index(self.highlighted).value),
                )
            ]
        else:
            return [
                path.join(cwd, state.decompress(option)) for option in self.selected
            ]

    async def on_key(self, event: events.Key) -> None:
        """Handle key events for the file list."""
        if not self.dummy:
            if self.select_mode_enabled:
                if event.key in state.config["mode"]["visual"]["select_up"]:
                    """Select the current and previous file."""
                    if self.highlighted == 0:
                        self.select(self.get_option_at_index(0))
                    else:
                        self.select(self.get_option_at_index(self.highlighted))
                        self.action_cursor_up()
                        self.select(self.get_option_at_index(self.highlighted))
                    return
                elif event.key in state.config["mode"]["visual"]["select_down"]:
                    """Select the current and next file."""
                    if self.highlighted == len(self.options) - 1:
                        self.select(self.get_option_at_index(self.option_count - 1))
                    else:
                        self.select(self.get_option_at_index(self.highlighted))
                        self.action_cursor_down()
                        self.select(self.get_option_at_index(self.highlighted))
                    return
                elif event.key in state.config["mode"]["visual"]["select_page_up"]:
                    """Select the options between the current and the previous 'page'."""
                    old = self.highlighted
                    self.action_page_up()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    if new is None:
                        new = 0
                    for index in range(new, old + 1):
                        self.select(self.get_option_at_index(index))
                    return
                elif event.key in state.config["mode"]["visual"]["select_page_down"]:
                    """Select the options between the current and the next 'page'."""
                    old = self.highlighted
                    self.action_page_down()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    if new is None:
                        new = 0
                    for index in range(old, new + 1):
                        self.select(self.get_option_at_index(index))
                    return
                elif event.key in state.config["mode"]["visual"]["select_home"]:
                    old = self.highlighted
                    self.action_first()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    for index in range(new, old + 1):
                        self.select(self.get_option_at_index(index))
                    return
                elif event.key in state.config["mode"]["visual"]["select_end"]:
                    old = self.highlighted
                    self.action_last()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    for index in range(old, new + 1):
                        self.select(self.get_option_at_index(index))
                    return
            if event.key in state.config["keybinds"]["manipulation"]["copy"]:
                """Copy the selected files to the clipboard."""
                selected_files = await self.get_selected_objects()
                if selected_files:
                    await self.app.query_one(Clipboard).add_to_clipboard(selected_files)
                else:
                    self.app.notify(
                        "No files selected to copy.",
                        title="Clipboard",
                        severity="warning",
                    )
            elif event.key in state.config["keybinds"]["manipulation"]["cut"]:
                """Cut the selected files to the clipboard."""
                selected_files = await self.get_selected_objects()
                if selected_files:
                    await self.app.query_one(Clipboard).cut_to_clipboard(selected_files)
                else:
                    self.app.notify(
                        "No files selected to cut.",
                        title="Clipboard",
                        severity="warning",
                    )
            elif event.key in state.config["keybinds"]["manipulation"]["toggle_all"]:
                if not self.select_mode_enabled:
                    await self.toggle_mode()
                if len(self.selected) == len(self.options):
                    self.deselect_all()
                else:
                    self.select_all()
            elif event.key in state.config["keybinds"]["manipulation"]["cut"]:
                """Cut the selected files to the clipboard."""


class Clipboard(SelectionList, inherit_bindings=False):
    """A selection list that displays the clipboard contents."""

    BINDINGS: ClassVar[list[BindingType]] = (
        [
            Binding(bind, "cursor_down", "Down", show=False)
            for bind in state.config["keybinds"]["navigation"]["down"]
        ]
        + [
            Binding(bind, "last", "Last", show=False)
            for bind in state.config["keybinds"]["navigation"]["end"]
        ]
        + [
            Binding(bind, "select", "Select", show=False)
            for bind in state.config["keybinds"]["navigation"]["down_tree"]
        ]
        + [
            Binding(bind, "first", "First", show=False)
            for bind in state.config["keybinds"]["navigation"]["home"]
        ]
        + [
            Binding(bind, "page_down", "Page Down", show=False)
            for bind in state.config["keybinds"]["navigation"]["page_down"]
        ]
        + [
            Binding(bind, "page_up", "Page Up", show=False)
            for bind in state.config["keybinds"]["navigation"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_up", "Up", show=False)
            for bind in state.config["keybinds"]["navigation"]["up"]
        ]
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.clipboard_contents = []

    def compose(self) -> ComposeResult:
        yield Static()

    async def on_mount(self) -> None:
        """Initialize the clipboard contents."""
        await self.remove_children()
        for item in self.clipboard_contents:
            self.add_option(Selection(Content(item), value=state.compress(item)))

    async def add_to_clipboard(self, items: list[str]) -> None:
        """Add items to the clipboard and update the selection list."""
        for item in items[::-1]:
            self.insert_selection_at_beginning(
                Selection(
                    Content(f"{ICONS['general']['copy'][0]} {item}"),
                    value=state.compress(f"{item}-copy"),
                    id=state.compress(item),
                )
            )
        self.deselect_all()
        for item_number in range(len(items)):
            self.select(self.get_option_at_index(item_number))

    async def cut_to_clipboard(self, items: list[str]) -> None:
        """Cut the selected files to the clipboard."""
        for item in items[::-1]:
            if isinstance(item, str):
                self.insert_selection_at_beginning(
                    Selection(
                        Content(f"{ICONS['general']['cut'][0]} {item}"),
                        value=state.compress(f"{item}-cut"),
                        id=state.compress(item),
                    )
                )
        self.deselect_all()
        for item_number in range(len(items)):
            self.select(self.get_option_at_index(item_number))

    # Use better versions of the checkbox icons

    def _get_left_gutter_width(
        self,
    ) -> int:
        """Returns the size of any left gutter that should be taken into account.

        Returns:
            The width of the left gutter.
        """
        return len(
            TOGGLE_BUTTON_ICONS["left"]
            + TOGGLE_BUTTON_ICONS["inner"]
            + TOGGLE_BUTTON_ICONS["right"]
            + " "
        )

    def render_line(self, y: int) -> Strip:
        """Render a line in the display.

        Args:
            y: The line to render.

        Returns:
            A [`Strip`][textual.strip.Strip] that is the line to render.
        """
        line = super(SelectionList, self).render_line(y)

        _, scroll_y = self.scroll_offset
        selection_index = scroll_y + y
        try:
            selection = self.get_option_at_index(selection_index)
        except OptionDoesNotExist:
            return line

        component_style = "selection-list--button"
        if selection.value in self._selected:
            component_style += "-selected"
        if self.highlighted == selection_index:
            component_style += "-highlighted"

        underlying_style = next(iter(line)).style or self.rich_style
        assert underlying_style is not None

        button_style = self.get_component_rich_style(component_style)

        side_style = Style.from_color(button_style.bgcolor, underlying_style.bgcolor)

        side_style += Style(meta={"option": selection_index})
        button_style += Style(meta={"option": selection_index})

        return Strip(
            [
                Segment(TOGGLE_BUTTON_ICONS["left"], style=side_style),
                Segment(
                    TOGGLE_BUTTON_ICONS["inner_filled"]
                    if selection.value in self._selected
                    else TOGGLE_BUTTON_ICONS["inner"],
                    style=button_style,
                ),
                Segment(TOGGLE_BUTTON_ICONS["right"], style=side_style),
                Segment(" ", style=underlying_style),
                *line,
            ]
        )

    # Why isnt this already a thing
    def insert_selection_at_beginning(self, content: Selection) -> None:
        """Insert a new selection at the beginning of the clipboard list.

        Args:
            content (Selection): A pre-created Selection object to insert.
        """
        # Check for duplicate ID
        if content.id is not None and content.id in self._id_to_option:
            self.remove_option(content.id)
            # raise DuplicateID(f"An option with ID {content.id} already exists.")

        # insert
        self._options.insert(0, content)

        # update self._values
        values = {content.value: 0}

        # update mapping
        for option, index in list(self._option_to_index.items()):
            self._option_to_index[option] = index + 1
        for key, value in self._values.items():
            values[key] = value + 1
        self._values = values
        print(self._values)
        self._option_to_index[content] = 0

        # update id mapping
        if content.id is not None:
            self._id_to_option[content.id] = content

        # force redraw
        self._clear_caches()

        # since you insert at beginning, highlighted should go down
        if self.highlighted is not None:
            self.highlighted += 1

        # // serve refreshments
        # redraw
        self.refresh(layout=True)

    @work
    async def on_key(self, event: events.Key):
        if event.key in state.config["keybinds"]["manipulation"]["delete"]:
            """Delete the selected files from the clipboard."""
            self.remove_option_at_index(self.highlighted)
        elif event.key in state.config["keybinds"]["manipulation"]["toggle_all"]:
            """Select all items in the clipboard."""
            if len(self.selected) == len(self.options):
                self.deselect_all()
            else:
                self.select_all()
