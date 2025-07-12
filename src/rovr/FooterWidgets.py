import asyncio
import platform
import stat
from datetime import datetime
from os import lstat, path, walk
from typing import ClassVar

from humanize import naturalsize
from rich.segment import Segment
from rich.style import Style
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import HorizontalGroup, VerticalGroup, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.strip import Strip
from textual.types import UnusedParameter
from textual.widgets import Label, ProgressBar, SelectionList, Static
from textual.widgets._progress_bar import Bar, ETAStatus, PercentageStatus
from textual.widgets.option_list import OptionDoesNotExist
from textual.widgets.selection_list import Selection

from .utils import compress, config, get_icon, get_toggle_button_icon


class Clipboard(SelectionList, inherit_bindings=False):
    """A selection list that displays the clipboard contents."""

    BINDINGS: ClassVar[list[BindingType]] = (
        [
            Binding(bind, "cursor_down", "Down", show=False)
            for bind in config["keybinds"]["down"]
        ]
        + [
            Binding(bind, "last", "Last", show=False)
            for bind in config["keybinds"]["end"]
        ]
        + [
            Binding(bind, "select", "Select", show=False)
            for bind in config["keybinds"]["down_tree"]
        ]
        + [
            Binding(bind, "first", "First", show=False)
            for bind in config["keybinds"]["home"]
        ]
        + [
            Binding(bind, "page_down", "Page Down", show=False)
            for bind in config["keybinds"]["page_down"]
        ]
        + [
            Binding(bind, "page_up", "Page Up", show=False)
            for bind in config["keybinds"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_up", "Up", show=False)
            for bind in config["keybinds"]["up"]
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
            self.add_option(Selection(Content(item), value=compress(item)))

    async def copy_to_clipboard(self, items: list[str]) -> None:
        """Copy the selected files to the clipboard"""
        for item in items[::-1]:
            self.insert_selection_at_beginning(
                Selection(
                    Content(f"{get_icon('general', 'copy')[0]} {item}"),
                    value=compress(f"{item}-copy"),
                    id=compress(item),
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
                        Content(f"{get_icon('general', 'cut')[0]} {item}"),
                        value=compress(f"{item}-cut"),
                        id=compress(item),
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
            get_toggle_button_icon("left")
            + get_toggle_button_icon("inner")
            + get_toggle_button_icon("right")
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
                Segment(get_toggle_button_icon("left"), style=side_style),
                Segment(
                    get_toggle_button_icon("inner_filled")
                    if selection.value in self._selected
                    else get_toggle_button_icon("inner"),
                    style=button_style,
                ),
                Segment(get_toggle_button_icon("right"), style=side_style),
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
            if event.key in config["keybinds"]["delete"]:
                """Delete the selected files from the clipboard."""
                if not self.selected:
                    self.app.notify(
                        "No files selected to delete from the clipboard.",
                        title="Clipboard",
                        severity="warning",
                    )
                    return
                self.remove_option_at_index(self.highlighted)
            elif event.key in config["keybinds"]["toggle_all"]:
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
        self._update_task = None

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
        """Debounce the update, because some people can be speed typers"""
        if self._update_task:
            self._update_task.stop()
        self._update_task = self.set_timer(
            0.25, lambda: self._perform_update(location_of_item)
        )

    async def _perform_update(self, location_of_item: str) -> None:
        """After debouncing"""
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
        for field in config["metadata"]["fields"]:
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
                                config["metadata"]["datetime_format"]
                            )
                        )
                    )
                case "accessed":
                    values_list.append(
                        Static(
                            datetime.fromtimestamp(file_stat.st_atime).strftime(
                                config["metadata"]["datetime_format"]
                            )
                        )
                    )
                case "created":
                    values_list.append(
                        Static(
                            datetime.fromtimestamp(file_stat.st_ctime).strftime(
                                config["metadata"]["datetime_format"]
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
            for field in config["metadata"]["fields"]:
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


class BetterProgressBar(ProgressBar):
    def __init__(self, total: int | None = None, *args, **kwargs):
        super().__init__(
            total=total, show_percentage=True, show_eta=True, *args, **kwargs
        )
        self.label = Label()

    def compose(self) -> ComposeResult:
        with VerticalGroup():
            with HorizontalGroup():
                yield self.label
                if config["interface"]["show_progress_percentage"]:
                    yield PercentageStatus(id="percentage").data_bind(
                        BetterProgressBar.percentage
                    )
                if config["interface"]["show_progress_eta"]:
                    yield ETAStatus(id="eta").data_bind(
                        eta=BetterProgressBar._display_eta
                    )
            yield (
                Bar(id="bar", clock=self._clock)
                .data_bind(BetterProgressBar.percentage)
                .data_bind(BetterProgressBar.gradient)
            )

    def update_label(self, label: str, step: bool = True) -> None:
        self.label.update(label)
        if step:
            self.advance(1)

    def update_progress(
        self,
        total: None | float | UnusedParameter = UnusedParameter,
        progress: float | UnusedParameter = UnusedParameter,
        advance: float | UnusedParameter = UnusedParameter,
    ):
        self.update(total=total, progress=progress, advance=advance)


class ProcessContainer(VerticalScroll):
    def __init__(self, *args, **kwargs):
        super().__init__(id="processes", *args, **kwargs)

    async def new_process_bar(
        self, max: int | None = None, id: str | None = None, classes: str | None = None
    ):
        new_bar = BetterProgressBar(total=max, id=id, classes=classes)
        await self.mount(new_bar)
        return new_bar
