import asyncio
import platform
import stat
import subprocess
from datetime import datetime
from os import chdir, getcwd, listdir, lstat, path, scandir
from os import system as cmd
from os import walk
from pathlib import Path
from typing import ClassVar

from humanize import naturalsize
from rich.segment import Segment
from rich.style import Style
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, VerticalGroup, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.strip import Strip
from textual.widgets import OptionList, SelectionList, Static, TextArea
from textual.widgets.option_list import Option, OptionDoesNotExist
from textual.widgets.selection_list import Selection
from textual_autocomplete import DropdownItem, PathAutoComplete, TargetState
from textual_image.widget import AutoImage

from . import state
from .maps import (
    EXT_TO_LANG_MAP,
    ICONS,
    PIL_EXTENSIONS,
    TOGGLE_BUTTON_ICONS,
    get_icon_for_file,
    get_icon_for_folder,
)

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
    # Sort folders and files properly
    folders.sort(key=lambda x: x["name"].lower(), reverse=(sort_order == "descending"))
    files.sort(key=lambda x: x["name"].lower(), reverse=(sort_order == "descending"))
    print(f"Found {len(folders)} folders and {len(files)} files in {cwd}")
    return folders, files


class PreviewContainer(Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_task = None
        self._current_content = None
        self._current_file_path = None
        self._is_image = False

    def compose(self) -> ComposeResult:
        yield TextArea(
            id="text_preview",
            show_line_numbers=True,
            soft_wrap=False,
            read_only=True,
            text=state.config["interface"]["preview_start"],
            language="markdown",
            compact=True,
        )

    @work(exclusive=True)
    async def show_preview(self, file_path: str) -> None:
        """Debounce super fast requests, then show preview"""
        if self._update_task:
            self._update_task.stop()

        if path.isdir(file_path):
            self._current_content = None
            self._current_file_path = None
            self._is_image = False
            self._update_task = self.set_timer(
                0.25, lambda: self.show_folder(file_path)
            )
        else:
            self._update_task = self.set_timer(0.25, lambda: self.show_file(file_path))

    async def show_file(self, file_path: str) -> None:
        """Load the file preview"""
        self._current_file_path = file_path
        if any(file_path.endswith(ext) for ext in PIL_EXTENSIONS):
            self._is_image = True
            self._current_content = None
        else:
            self._is_image = False
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self._current_content = f.read()
            except UnicodeDecodeError:
                self._current_content = state.config["interface"]["preview_binary"]
            except (FileNotFoundError, PermissionError, OSError):
                self._current_content = state.config["interface"]["preview_error"]

        await self._render_preview()

    async def _render_preview(self) -> None:
        """Render function"""
        if self._current_file_path is None:
            return

        await self.remove_children()

        if self._is_image:
            await self.mount(
                AutoImage(
                    self._current_file_path, id="image_preview", classes="inner_preview"
                )
            )
            self.border_title = "Image Preview"
            self.query_one("#image_preview").can_focus = True
            return

        if self._current_content is None:
            return

        preview_full = state.config["settings"]["preview_full"]
        text_to_display = self._current_content

        if not preview_full:
            lines = text_to_display.splitlines()

            max_lines = self.size.height
            if max_lines > 0:
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
            else:
                lines = []

            # no clue why its 5 lmao
            max_width = self.size.width - 5
            if max_width > 0:
                processed_lines = []
                for line in lines:
                    if len(line) > max_width:
                        processed_lines.append(line[:max_width])
                    else:
                        processed_lines.append(line)
                lines = processed_lines

            text_to_display = "\n".join(lines)

        language = "markdown"
        if self._current_content not in (
            state.config["interface"]["preview_binary"],
            state.config["interface"]["preview_error"],
        ):
            language = EXT_TO_LANG_MAP.get(
                path.splitext(self._current_file_path)[1], "markdown"
            )

        await self.mount(
            TextArea(
                id="text_preview",
                show_line_numbers=True,
                soft_wrap=False,  # Per user feedback, disable word wrap
                read_only=True,
                text=text_to_display,
                language=language,
                compact=preview_full,
                classes="inner_preview",
            )
        )
        self.border_title = "File Preview"

    async def show_folder(self, folder_path: str) -> None:
        """Show the folder in the preview container."""
        if len(self.children) != 0:
            await self.remove_children()
        await self.mount(
            FileList(
                id="folder_preview",
                name=folder_path,
                classes="file-list inner_preview",
                sort_by="name",
                sort_order="ascending",
                dummy=True,
                enter_into=path.relpath(getcwd().replace(path.sep, "/"), folder_path),
            )
        )
        self.app.query_one("#folder_preview").dummy_update_file_list(
            sort_by="name",
            sort_order="ascending",
            cwd=folder_path,
        )
        self.border_title = "Folder Preview"

    @on(events.Resize)
    async def on_resize(self, event: events.Resize) -> None:
        """Re-render the preview on resize if it's a text file."""
        if self._current_content is not None:
            await self._render_preview()


class FolderNotFileError(Exception):
    """Raised when a folder is expected but a file is provided instead."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PinnedSidebar(OptionList, inherit_bindings=False):
    BINDINGS: ClassVar[list[BindingType]] = (
        [
            Binding(bind, "cursor_down", "Down", show=False)
            for bind in state.config["keybinds"]["down"]
        ]
        + [
            Binding(bind, "last", "Last", show=False)
            for bind in state.config["keybinds"]["end"]
        ]
        + [
            Binding(bind, "select", "Select", show=False)
            for bind in state.config["keybinds"]["down_tree"]
        ]
        + [
            Binding(bind, "first", "First", show=False)
            for bind in state.config["keybinds"]["home"]
        ]
        + [
            Binding(bind, "page_down", "Page Down", show=False)
            for bind in state.config["keybinds"]["page_down"]
        ]
        + [
            Binding(bind, "page_up", "Page Up", show=False)
            for bind in state.config["keybinds"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_up", "Up", show=False)
            for bind in state.config["keybinds"]["up"]
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

    @work(exclusive=True)
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
        self.reload_pins()

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
        self.app.query_one("#file_list").update_file_list("name", "ascending")
        self.app.query_one("#file_list").focus()


class FileList(SelectionList, inherit_bindings=False):
    """
    OptionList but can multi-select files and folders.
    """

    BINDINGS: ClassVar[list[BindingType]] = (
        [
            Binding(bind, "cursor_down", "Down", show=False)
            for bind in state.config["keybinds"]["down"]
        ]
        + [
            Binding(bind, "last", "Last", show=False)
            for bind in state.config["keybinds"]["end"]
        ]
        + [
            Binding(bind, "select", "Select", show=False)
            for bind in state.config["keybinds"]["down_tree"]
        ]
        + [
            Binding(bind, "first", "First", show=False)
            for bind in state.config["keybinds"]["home"]
        ]
        + [
            Binding(bind, "page_down", "Page Down", show=False)
            for bind in state.config["keybinds"]["page_down"]
        ]
        + [
            Binding(bind, "page_up", "Page Up", show=False)
            for bind in state.config["keybinds"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_up", "Up", show=False)
            for bind in state.config["keybinds"]["up"]
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
            self.update_file_list(
                sort_by=self.sort_by,
                sort_order=self.sort_order,
                add_to_session=add_to_history,
            )
            self.focus()

    def update_file_list(
        self,
        sort_by: str = "name",
        sort_order: str = "ascending",
        add_to_session: bool = True,
    ) -> None:
        """Update the file list with the current directory contents.

        Args:
            sort_by (str): The attribute to sort by ("name" or "size").
            sort_order (str): The order to sort by ("ascending" or "descending").
            add_to_session (bool): Whether to add the current directory to the session history.
        """
        cwd = getcwd().replace(path.sep, "/").replace(path.sep, "/")
        self.clear_options()
        # seperate folders and files
        folders, files = get_cwd_object(cwd, sort_order, sort_by)
        if folders == [PermissionError] or files == [PermissionError]:
            self.add_option(
                Selection(
                    Content("Permission Error: Unable to access this directory."),
                    value="",
                    id="",
                    disabled=True,
                ),
            )
            file_list_options = [".."]
        elif folders == [] and files == []:
            self.add_option(Selection("  --no-files--", value="", id="", disabled=True))
            self.app.query_one(PreviewContainer).remove_children()
            # nothing inside
        else:
            file_list_options = (
                files + folders if sort_order == "descending" else folders + files
            )
            for item in file_list_options:
                self.add_option(
                    Selection(
                        Content.from_markup(
                            f" [{item['icon'][1]}]{item['icon'][0]}[/{item['icon'][1]}] $name",
                            name=item["name"],
                        ),
                        value=state.compress(item["name"]),
                        id=state.compress(item["name"]),
                    )
                )
        # session handler
        self.app.query_one("#path_switcher").value = cwd + "/"
        if add_to_session:
            if state.sessionHistoryIndex != len(state.sessionDirectories) - 1:
                state.sessionDirectories = state.sessionDirectories[
                    : state.sessionHistoryIndex + 1
                ]
            state.sessionDirectories.append(
                {
                    "path": cwd,
                }
            )
            if state.sessionLastHighlighted.get(cwd) is None:
                # hard coding is my passion (referring to the id)
                state.sessionLastHighlighted[cwd] = (
                    self.app.query_one("#file_list").options[0].value
                )
            state.sessionHistoryIndex = len(state.sessionDirectories) - 1
            self.app.update_session_dicts(
                state.sessionDirectories,
                state.sessionHistoryIndex,
                state.sessionLastHighlighted,
            )
        self.app.query_one("Button#back").disabled = (
            True if state.sessionHistoryIndex == 0 else False
        )
        self.app.query_one("Button#forward").disabled = (
            True
            if state.sessionHistoryIndex == len(state.sessionDirectories) - 1
            else False
        )
        try:
            self.highlighted = self.get_option_index(state.sessionLastHighlighted[cwd])
        except OptionDoesNotExist:
            self.highlighted = 0
            state.sessionLastHighlighted[cwd] = (
                self.app.query_one("#file_list").options[0].value
            )
        self.app.title = f"carto - {cwd.replace(path.sep, '/')}"

    def dummy_update_file_list(
        self,
        sort_by: str = "name",
        sort_order: str = "ascending",
        cwd: str = "",
    ) -> None:
        """Update the file list with the current directory contents.

        Args:
            sort_by (str): The attribute to sort by ("name" or "size").
            sort_order (str): The order to sort by ("ascending" or "descending").
            cwd (str): The current working directory.
        """
        if cwd == "":
            cwd = getcwd().replace(path.sep, "/")
        self.clear_options()
        # seperate folders and files
        folders, files = get_cwd_object(cwd, sort_order, sort_by)
        if folders == [PermissionError] or files == [PermissionError]:
            self.add_option(
                Selection(
                    Content("Permission Error: Unable to access this directory."),
                    id="",
                    value="",
                    disabled=True,
                )
            )
            return
        elif folders == [] and files == []:
            self.add_option(Selection("  --no-files--", value="", id="", disabled=True))
            return
        file_list_options = (
            files + folders if sort_order == "descending" else folders + files
        )
        for item in file_list_options:
            self.add_option(
                Selection(
                    Content.from_markup(
                        f" [{item['icon'][1]}]{item['icon'][0]}[/{item['icon'][1]}] $name",
                        name=item["name"],
                    ),
                    value=state.compress(item["name"]),
                )
            )
        # somehow prevents more debouncing, ill take it
        self.refresh(repaint=True, layout=True)

    async def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        if self.dummy:
            return
        if not self.select_mode_enabled:
            event.prevent_default()
            cwd = getcwd().replace(path.sep, "/")
            # Get the selected option
            selected_option = self.get_option_at_index(
                self.highlighted
            )  # ? trust me bro
            # Get the file name from the option id
            file_name = state.decompress(selected_option.value)
            # Check if it's a folder or a file
            if path.isdir(path.join(cwd, file_name)):
                # If it's a folder, navigate into it
                try:
                    chdir(path.join(cwd, file_name))
                except PermissionError:
                    # cannot access, so dont change anything ig
                    return
                self.app.query_one("#file_list").update_file_list(
                    self.sort_by, self.sort_order
                )
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
        global state
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
        else:
            state.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                True,
            )
        # Get the highlighted option
        highlighted_option = event.option
        state.sessionLastHighlighted[getcwd().replace(path.sep, "/")] = (
            highlighted_option.value
        )
        self.app.update_session_dicts(
            state.sessionDirectories,
            state.sessionHistoryIndex,
            state.sessionLastHighlighted,
        )
        # Get the file name from the option id
        file_name = state.decompress(highlighted_option.value)
        # total files as footer
        if self.highlighted is None:
            self.highlighted = 0
        # preview
        self.app.query_one("#preview_sidebar").show_preview(
            path.join(getcwd(), file_name).replace(path.sep, "/")
        )
        self.app.query_one(MetadataContainer).update_metadata(
            path.join(getcwd(), file_name).replace(path.sep, "/")
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
        if self.dummy:
            return
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

    async def get_selected_objects(self) -> list[str] | None:
        """Get the selected objects in the file list."""
        cwd = getcwd().replace(path.sep, "/")
        if self.get_option_at_index(self.highlighted).value == "HTI":
            return None
        if not self.select_mode_enabled:
            return [
                path.join(
                    cwd,
                    state.decompress(self.get_option_at_index(self.highlighted).value),
                ).replace(path.sep, "/")
            ]
        else:
            return [
                path.join(cwd, state.decompress(option)).replace(path.sep, "/")
                for option in self.selected
            ]

    async def on_key(self, event: events.Key) -> None:
        """Handle key events for the file list."""
        if not self.dummy:
            if event.key in state.config["keybinds"]["toggle_all"]:
                if not self.select_mode_enabled:
                    await self.toggle_mode()
                if len(self.selected) == len(self.options):
                    self.deselect_all()
                else:
                    self.select_all()
            elif self.select_mode_enabled:
                if event.key in state.config["keybinds"]["select_up"]:
                    """Select the current and previous file."""
                    if self.highlighted == 0:
                        self.select(self.get_option_at_index(0))
                    else:
                        self.select(self.get_option_at_index(self.highlighted))
                        self.action_cursor_up()
                        self.select(self.get_option_at_index(self.highlighted))
                    return
                elif event.key in state.config["keybinds"]["select_down"]:
                    """Select the current and next file."""
                    if self.highlighted == len(self.options) - 1:
                        self.select(self.get_option_at_index(self.option_count - 1))
                    else:
                        self.select(self.get_option_at_index(self.highlighted))
                        self.action_cursor_down()
                        self.select(self.get_option_at_index(self.highlighted))
                    return
                elif event.key in state.config["keybinds"]["select_page_up"]:
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
                elif event.key in state.config["keybinds"]["select_page_down"]:
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
                elif event.key in state.config["keybinds"]["select_home"]:
                    old = self.highlighted
                    self.action_first()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    for index in range(new, old + 1):
                        self.select(self.get_option_at_index(index))
                    return
                elif event.key in state.config["keybinds"]["select_end"]:
                    old = self.highlighted
                    self.action_last()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    for index in range(old, new + 1):
                        self.select(self.get_option_at_index(index))
                    return
            elif event.key in state.config["plugins"]["editor"]["keybinds"]:
                with self.app.suspend():
                    cmd(
                        f'{state.config["plugins"]["editor"]["executable"]} "{path.join(getcwd(), state.decompress(self.get_option_at_index(self.highlighted).id))}"'
                    )


class Clipboard(SelectionList, inherit_bindings=False):
    """A selection list that displays the clipboard contents."""

    BINDINGS: ClassVar[list[BindingType]] = (
        [
            Binding(bind, "cursor_down", "Down", show=False)
            for bind in state.config["keybinds"]["down"]
        ]
        + [
            Binding(bind, "last", "Last", show=False)
            for bind in state.config["keybinds"]["end"]
        ]
        + [
            Binding(bind, "select", "Select", show=False)
            for bind in state.config["keybinds"]["down_tree"]
        ]
        + [
            Binding(bind, "first", "First", show=False)
            for bind in state.config["keybinds"]["home"]
        ]
        + [
            Binding(bind, "page_down", "Page Down", show=False)
            for bind in state.config["keybinds"]["page_down"]
        ]
        + [
            Binding(bind, "page_up", "Page Up", show=False)
            for bind in state.config["keybinds"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_up", "Up", show=False)
            for bind in state.config["keybinds"]["up"]
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

    async def copy_to_clipboard(self, items: list[str]) -> None:
        """Copy the selected files to the clipboard"""
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
        if self.has_focus:
            if event.key in state.config["keybinds"]["delete"]:
                """Delete the selected files from the clipboard."""
                if not self.selected:
                    self.app.notify(
                        "No files selected to delete from the clipboard.",
                        title="Clipboard",
                        severity="warning",
                    )
                    return
                self.remove_option_at_index(self.highlighted)
            elif event.key in state.config["keybinds"]["toggle_all"]:
                """Select all items in the clipboard."""
                if len(self.selected) == len(self.options):
                    self.deselect_all()
                else:
                    self.select_all()


class MetadataContainer(VerticalScroll):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_path: str | None = None
        self._size_worker = None

    def info_of_file_path(self, file_path: str) -> str:
        try:
            file_stat = lstat(file_path)
        except (OSError, FileNotFoundError):
            return "?????????"
        mode = file_stat.st_mode

        permission_string = ""

        if stat.S_ISLNK(mode):
            permission_string = "l"
        elif platform.system() == "Windows":
            if (
                hasattr(file_stat, "st_file_attributes")
                and file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                permission_string = "j"
            elif stat.S_ISDIR(mode):
                permission_string = "d"
            else:
                permission_string = "-"
        elif stat.S_ISDIR(mode):
            permission_string = "d"
        else:
            permission_string = "-"

        permission_string += "r" if mode & stat.S_IRUSR else "-"
        permission_string += "w" if mode & stat.S_IWUSR else "-"
        permission_string += "x" if mode & stat.S_IXUSR else "-"

        permission_string += "r" if mode & stat.S_IRGRP else "-"
        permission_string += "w" if mode & stat.S_IWGRP else "-"
        permission_string += "x" if mode & stat.S_IXGRP else "-"

        permission_string += "r" if mode & stat.S_IROTH else "-"
        permission_string += "w" if mode & stat.S_IWOTH else "-"
        permission_string += "x" if mode & stat.S_IXOTH else "-"
        return permission_string

    @work(exclusive=True)
    async def update_metadata(self, location_of_item: str) -> None:
        if self._size_worker:
            self._size_worker.cancel()
            self._size_worker = None
        self.current_path = location_of_item
        try:
            file_stat = lstat(location_of_item)
            file_info = self.info_of_file_path(location_of_item)
        except (OSError, FileNotFoundError):
            await self.remove_children()
            await self.mount(Static("Item not found or inaccessible."))
            return

        type_str = "Unknown"
        if file_info.startswith("j"):
            type_str = "Junction"
        elif file_info.startswith("l"):
            type_str = "Symlink"
        elif file_info.startswith("d"):
            type_str = "Directory"
        elif file_info.startswith("-"):
            type_str = "File"
        # got the type, now we follow
        file_stat = lstat(path.realpath(location_of_item))
        values_list = []
        for field in state.config["metadata"]["fields"]:
            match field:
                case "type":
                    values_list.append(Static(type_str))
                case "permissions":
                    values_list.append(Static(file_info))
                case "size":
                    values_list.append(
                        Static(
                            naturalsize(file_stat.st_size)
                            if type_str == "File"
                            else "--",
                            id="metadata-size",
                        )
                    )
                case "modified":
                    values_list.append(
                        Static(
                            datetime.fromtimestamp(file_stat.st_mtime).strftime(
                                state.config["metadata"]["datetime_format"]
                            )
                        )
                    )
                case "accessed":
                    values_list.append(
                        Static(
                            datetime.fromtimestamp(file_stat.st_atime).strftime(
                                state.config["metadata"]["datetime_format"]
                            )
                        )
                    )
                case "created":
                    values_list.append(
                        Static(
                            datetime.fromtimestamp(file_stat.st_ctime).strftime(
                                state.config["metadata"]["datetime_format"]
                            )
                        )
                    )

        values = VerticalGroup(*values_list, id="metadata-values")

        try:
            await self.query_one("#metadata-values").remove()
            await self.mount(values)
        except NoMatches:
            await self.remove_children()
            keys_list = []
            for field in state.config["metadata"]["fields"]:
                if field == "type":
                    keys_list.append(Static("Type"))
                elif field == "permissions":
                    keys_list.append(Static("Permissions"))
                elif field == "size":
                    keys_list.append(Static("Size"))
                elif field == "modified":
                    keys_list.append(Static("Modified"))
                elif field == "accessed":
                    keys_list.append(Static("Accessed"))
                elif field == "created":
                    keys_list.append(Static("Created"))
            keys = VerticalGroup(*keys_list, id="metadata-keys")
            await self.mount(keys, values)

        if type_str == "Directory" and self.has_focus:
            self._size_worker = self.calculate_folder_size(location_of_item)

    @work
    async def calculate_folder_size(self, folder_path: str) -> None:
        """Calculate the size of a folder and update the metadata."""
        size_widget = self.query_one("#metadata-size", Static)
        self.call_later(size_widget.update, "Calculating...")

        total_size = 0
        try:
            for dirpath, _, filenames in walk(folder_path):
                if self._size_worker.is_cancelled:
                    self.call_later(size_widget.update, "--")
                    return
                for f in filenames:
                    fp = path.join(dirpath, f)
                    if not path.islink(fp):
                        try:
                            total_size += lstat(fp).st_size
                        except (OSError, FileNotFoundError):
                            pass  # File might have been removed
                await asyncio.sleep(0)  # Yield to the event loop
        except (OSError, FileNotFoundError):
            self.call_later(size_widget.update, "Error")
            return

        if not self._size_worker.is_cancelled:
            self.call_later(size_widget.update, naturalsize(total_size))

    @on(events.Focus)
    def on_focus(self) -> None:
        if self.current_path and path.isdir(self.current_path):
            if self._size_worker:
                self._size_worker.cancel()
            self._size_worker = self.calculate_folder_size(self.current_path)

    @on(events.Blur)
    def on_blur(self) -> None:
        if self._size_worker:
            self._size_worker.cancel()
            self._size_worker = None
            try:
                size_widget = self.query_one("#metadata-size", Static)
                size_widget.update("--")
            except NoMatches:
                pass
