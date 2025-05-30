from humanize import naturalsize
from maps import (
    get_icon_for_file,
    get_icon_for_folder,
    EXT_TO_LANG_MAP,
    PIL_EXTENSIONS,
    TOGGLE_BUTTON_ICONS,
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
from textual.containers import Container
from textual.content import Content
from textual.css.query import NoMatches
from textual.strip import Strip
from textual.widgets import OptionList, Static, TextArea, SelectionList
from textual.widgets.option_list import Option, OptionDoesNotExist
from textual.widgets.selection_list import Selection
from textual_autocomplete import PathAutoComplete, TargetState, DropdownItem


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

    async def show_file(self, file_path: str) -> None:
        """Show the file in the preview container."""
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


class PinnedSidebar(OptionList):
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
        file_path = state.decompress(selected_option.value.split("-")[0])
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


class FileList(SelectionList):
    """
    OptionList but can multi-select files and folders.
    """

    def __init__(
        self,
        sort_by: str,
        sort_order: str,
        dummy: bool = False,
        enter_into: str = "",
        visual: bool = False,
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
            visual (bool): Whether the selection is visual or normal.
        """
        super().__init__(*args, **kwargs)
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.dummy = dummy
        self.enter_into = enter_into
        self.visual = visual

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

    async def on_mount(self) -> None:
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
            )
            self.focus()

    async def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        if self.dummy:
            return
        if not self.visual:
            event.prevent_default()
            cwd = getcwd()
            # Get the selected option
            selected_option = self.highlighted  # ? trust me bro
            # Get the file name from the option id
            file_name = state.decompress(selected_option)
            # Check if it's a folder or a file
            if path.isdir(path.join(cwd, file_name)):
                # If it's a folder, navigate into it
                chdir(path.join(cwd, file_name))
                update_file_list(self.app, "#file_list", self.sort_by, self.sort_order)
            else:
                open_file(path.join(cwd, file_name))
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

    async def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if self.dummy:
            return
        elif event.option.value == "HTI" or self.visual:
            self.app.query_one("#preview_sidebar").remove_children()
            if self.visual:
                state.set_scuffed_subtitle(
                    self.parent,
                    "SELECT",
                    f"{len(self.selected)}/{len(self.options)}",
                    True,
                )
            return  # ignore folders that go to prev dir
        # Get the highlighted option
        highlighted_option = event.option
        state.sessionDirectories[state.sessionHistoryIndex]["highlighted"] = (
            event.option.value
        )
        # Get the file name from the option id
        file_name = state.decompress(highlighted_option.value)
        # total files as footer
        state.set_scuffed_subtitle(
            self.parent, "NORMAL", f"{self.highlighted + 1}/{self.option_count}", True
        )
        # Check if it's a folder or a file
        file_path = path.join(getcwd(), file_name)
        if path.isdir(file_path):
            await self.app.query_one("#preview_sidebar").show_folder(file_path)
        else:
            await self.app.query_one("#preview_sidebar").show_file(file_path)

    def _get_left_gutter_width(
        self,
    ) -> (
        int
    ):  # to be fair, we couldve just left it alone because monospace, but screw that
        """Returns the size of any left gutter that should be taken into account.

        Returns:
            The width of the left gutter.
        """
        if self.dummy or not self.visual:
            return 0
        else:
            return len(
                TOGGLE_BUTTON_ICONS["left"]
                + TOGGLE_BUTTON_ICONS["inner"]
                + TOGGLE_BUTTON_ICONS["right"]
                + " "
            )

    def render_line(
        self, y: int
    ) -> Strip:  # reminder that this is taken from textual's repository and modified
        """Render a line in the display.

        Args:
            y: The line to render.

        Returns:
            A [`Strip`][textual.strip.Strip] that is the line to render.
        """
        # TODO: This is rather crufty and hard to fathom. Candidate for a rewrite.

        # First off, get the underlying prompt from OptionList.
        # lysm claude
        line = super(SelectionList, self).render_line(y)

        # ignore if not visual or is dummy
        if self.dummy or not self.visual:
            return Strip([*line])

        # We know the prompt we're going to display, what we're going to do
        # is place a CheckBox-a-like button next to it. So to start with
        # let's pull out the actual Selection we're looking at right now.
        _, scroll_y = self.scroll_offset
        selection_index = scroll_y + y
        try:
            selection = self.get_option_at_index(selection_index)
        except OptionDoesNotExist:
            return line

        # Figure out which component style is relevant for a checkbox on
        # this particular line.
        component_style = "selection-list--button"
        if selection.value in self._selected:
            component_style += "-selected"
        if self.highlighted == selection_index:
            component_style += "-highlighted"

        # # # Get the underlying style used for the prompt.
        # TODO: This is not a reliable way of getting the base style
        underlying_style = next(iter(line)).style or self.rich_style
        assert underlying_style is not None

        # Get the style for the button.
        button_style = self.get_component_rich_style(component_style)

        # Build the style for the side characters. Note that this is
        # sensitive to the type of character used, so pay attention to
        # BUTTON_LEFT and BUTTON_RIGHT.
        side_style = Style.from_color(button_style.bgcolor, underlying_style.bgcolor)

        # Add the option index to the style. This is used to determine which
        # option to select when the button is clicked or hovered.
        side_style += Style(meta={"option": selection_index})
        button_style += Style(meta={"option": selection_index})

        # At this point we should have everything we need to place a
        # "button" before the option.
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

    @work
    async def toggle_mode(self) -> None:
        """Toggle the selection mode between visual and normal."""
        self.visual = not self.visual
        highlighted = self.highlighted
        await self.on_mount()
        self.highlighted = highlighted

    @on(events.Focus)
    @work
    async def event_on_focus(self, event: events.Focus) -> None:
        """Handle the focus event to update the border style."""
        if self.visual:
            state.set_scuffed_subtitle(
                self.parent, "SELECT", f"{len(self.selected)}/{len(self.options)}", True
            )
        else:
            state.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                True,
            )

    @on(events.Leave)
    @work
    async def event_on_leave(self, event: events.Leave) -> None:
        """Handle the leave event to update the border style"""
        if self.visual:
            state.set_scuffed_subtitle(
                self.parent,
                "SELECT",
                f"{len(self.selected)}/{len(self.options)}",
                False,
            )
        else:
            state.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                False,
            )
