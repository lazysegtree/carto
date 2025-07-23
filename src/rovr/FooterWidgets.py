import platform
import stat
from datetime import datetime
from os import lstat, path, remove, walk
from shutil import rmtree
from typing import ClassVar

from humanize import naturalsize
from rich.segment import Segment
from rich.style import Style
from send2trash import send2trash
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.color import Gradient
from textual.containers import VerticalGroup, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.strip import Strip
from textual.types import UnusedParameter
from textual.widgets import Label, ProgressBar, SelectionList, Static
from textual.widgets.option_list import OptionDoesNotExist
from textual.widgets.selection_list import Selection

from .ScreensCore import Dismissable, YesOrNo
from .utils import (
    compress,
    config,
    decompress,
    file_is_type,
    get_icon,
    get_recursive_files,
    get_toggle_button_icon,
)


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
        file_type = file_is_type(file_path)
        match file_type:
            case "symlink":
                permission_string = "l"
            case "directory":
                permission_string = "d"
            case "junction":
                permission_string = "j"
            case "file":
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


class ProgressBarContainer(VerticalGroup):
    def __init__(
        self,
        total: int | None = None,
        label: str = "",
        gradient: Gradient | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.progress_bar = ProgressBar(
            total=total, show_percentage=False, show_eta=True, gradient=gradient
        )
        self.label = Label(label)

    async def on_mount(self) -> None:
        await self.mount_all([self.label, self.progress_bar])

    def update_label(self, label: str, step: bool = True) -> None:
        """
        Updates the label, and optionally steps it
        Args:
            label(str): The new label
            step(bool): Whether or not to increase the progress by 1
        """
        self.label.update(label)
        if step:
            self.progress_bar.advance(1)

    def update_progress(
        self,
        total: None | float | UnusedParameter = UnusedParameter(),
        progress: float | UnusedParameter = UnusedParameter(),
        advance: float | UnusedParameter = UnusedParameter(),
    ):
        self.progress_bar.update(total=total, progress=progress, advance=advance)


class ProcessContainer(VerticalScroll):
    def __init__(self, *args, **kwargs):
        super().__init__(id="processes", *args, **kwargs)

    async def new_process_bar(
        self, max: int | None = None, id: str | None = None, classes: str | None = None
    ):
        new_bar = ProgressBarContainer(total=max, id=id, classes=classes)
        await self.mount(new_bar)
        return new_bar

    @work(thread=True)
    def delete_files(
        self, files: list[str], compressed: bool = True, ignore_trash: bool = False
    ) -> None:
        """
        Remove files from the filesystem.

        Args:
            files (list[str]): List of file paths to remove.
            compressed (bool): Whether the file paths are compressed. Defaults to True.
            ignore_trash (bool): If True, files will be permanently deleted instead of sent to the recycle bin. Defaults to False.
        """
        # Create progress/process bar (why have I set names as such...)
        bar = self.app.call_from_thread(self.new_process_bar, classes="active")
        self.app.call_from_thread(
            bar.update_label,
            f"{get_icon('general', 'delete')[0]} Getting files to delete...",
            step=False,
        )
        # get files to delete
        files_to_delete = []
        folders_to_delete = []
        for file in files:
            if compressed:
                file = decompress(file)
            if path.isdir(file):
                folders_to_delete.append(file)
            files_to_delete.extend(get_recursive_files(file))
        self.app.call_from_thread(bar.update_progress, total=len(files_to_delete))
        for file_dict in files_to_delete:
            self.app.call_from_thread(
                bar.update_label,
                f"{get_icon('general', 'delete')[0]} {file_dict['relative_loc']}",
            )
            if path.exists(file):
                # I know that it `path.exists` prevents issues, but on the
                # off chance that anything happens, this should help
                try:
                    print(file_dict["path"])
                    if config["settings"]["use_recycle_bin"] and not ignore_trash:
                        try:
                            path_to_trash = file_dict["path"]
                            self.app.notify(
                                f"Windows: {platform.system() == 'Windows'}\nhas nonsense: {path_to_trash.startswith('\\\\\\\\?\\\\')}\ncheck start: {path_to_trash.split('?')[0]}"
                            )
                            if (
                                platform.system() == "Windows"
                                and path_to_trash.startswith("\\\\\\\\?\\\\")
                            ):
                                # An inherent issue with long paths on windows
                                path_to_trash = path_to_trash[6:]
                            send2trash(path_to_trash)
                        except FileNotFoundError:
                            pass
                        except Exception as e:
                            perma_delete = self.app.call_from_thread(
                                self.app.push_screen_wait,
                                YesOrNo(
                                    f"Trashing failed due to\n{e}\nDo Permenant Deletion?"
                                ),
                            )
                            if perma_delete:
                                ignore_trash = True
                            else:
                                self.app.call_from_thread(
                                    bar.update_label,
                                    f"{get_icon('general', 'close')[0]} Process Interrupted",
                                )
                                return
                    else:
                        remove(file_dict["path"])
                except FileNotFoundError:
                    pass
                except PermissionError:
                    do_continue = self.app.call_from_thread(
                        self.app.push_screen_wait,
                        YesOrNo(
                            f"{file_dict['path']} could not be deleted due to PermissionError.\nContinue?"
                        ),
                    )
                    if not do_continue:
                        return
                except Exception as e:
                    self.app.call_from_thread(
                        bar.update_label,
                        f"{get_icon('general', 'close')[0]} Unhandled Error.",
                    )
                    self.app.call_from_thread(
                        self.app.push_screen_wait,
                        Dismissable(f"Deleting failed due to\n{e}\nProcess Aborted."),
                    )
                    return
        for folder in folders_to_delete:
            try:
                rmtree(folder)
            except PermissionError:
                self.app.notify(
                    f"Certain files in {folder} could not be deleted.", severity="error"
                )
        self.app.call_from_thread(
            bar.update_label,
            f"{get_icon('general', 'close')[0]} {path.basename(files[-1])}",
        )

    async def on_key(self, event: events.Key):
        if event.key in config["keybinds"]["delete"]:
            await self.remove_children(".done")
            await self.remove_children(".error")
