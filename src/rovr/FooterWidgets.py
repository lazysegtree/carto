import platform
import shutil
import stat
import time
from contextlib import suppress
from datetime import datetime
from os import DirEntry, getcwd, listdir, lstat, makedirs, path, remove, walk
from typing import ClassVar
from zipfile import ZIP_DEFLATED, ZipFile

from rich.segment import Segment
from rich.style import Style
from send2trash import send2trash
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.color import Gradient
from textual.containers import VerticalGroup, VerticalScroll
from textual.content import Content, ContentText
from textual.css.query import NoMatches
from textual.strip import Strip
from textual.types import UnusedParameter
from textual.widgets import Label, ProgressBar, SelectionList, Static
from textual.widgets.option_list import OptionDoesNotExist
from textual.widgets.selection_list import Selection
from textual.worker import WorkerState

from . import utils
from .maps import SPINNER
from .ScreensCore import CommonFileNameDoWhat, Dismissable, YesOrNo
from .utils import config


class ClipboardSelection(Selection):
    def __init__(self, prompt: ContentText, *args, **kwargs) -> None:
        """
        Initialise the selection.

        Args:
            prompt: The prompt for the selection.
            value: The value for the selection.
            initial_state: The initial selected state of the selection.
            id: The optional ID for the selection.
            disabled: The initial enabled/disabled state. Enabled by default.
        """
        super().__init__(prompt, *args, **kwargs)
        self.initial_prompt = prompt


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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.clipboard_contents = []

    def compose(self) -> ComposeResult:
        yield Static()

    async def on_mount(self) -> None:
        """Initialize the clipboard contents."""
        await self.remove_children()

    async def copy_to_clipboard(self, items: list[str]) -> None:
        """Copy the selected files to the clipboard"""
        for item in items[::-1]:
            self.insert_selection_at_beginning(
                ClipboardSelection(
                    prompt=Content(f"{utils.get_icon('general', 'copy')[0]} {item}"),
                    value=utils.compress(f"{item}-copy"),
                    id=utils.compress(item),
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
                    ClipboardSelection(
                        prompt=Content(f"{utils.get_icon('general', 'cut')[0]} {item}"),
                        value=utils.compress(f"{item}-cut"),
                        id=utils.compress(item),
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
            utils.get_toggle_button_icon("left")
            + utils.get_toggle_button_icon("inner")
            + utils.get_toggle_button_icon("right")
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

        return Strip([
            Segment(utils.get_toggle_button_icon("left"), style=side_style),
            Segment(
                utils.get_toggle_button_icon("inner_filled")
                if selection.value in self._selected
                else utils.get_toggle_button_icon("inner"),
                style=button_style,
            ),
            Segment(utils.get_toggle_button_icon("right"), style=side_style),
            Segment(" ", style=underlying_style),
            *line,
        ])

    # Why isnt this already a thing
    def insert_selection_at_beginning(self, content: ClipboardSelection) -> None:
        """Insert a new selection at the beginning of the clipboard list.

        Args:
            content (ClipboardSelection): A pre-created Selection object to insert.
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
        self._option_to_index[content] = 0

        # update id mapping
        if content.id is not None:
            self._id_to_option[content.id] = content

        # force redraw
        self._clear_caches()

        # since you insert at beginning, highlighted should go down
        if self.highlighted is not None:
            self.highlighted += 1

        # redraw
        self.refresh(layout=True)

    @work
    async def on_key(self, event: events.Key) -> None:
        if self.has_focus:
            if event.key in config["keybinds"]["delete"]:
                """Delete the selected files from the clipboard."""
                if self.highlighted is None:
                    self.notify(
                        "No files selected to delete from the clipboard.",
                        title="Clipboard",
                        severity="warning",
                    )
                    return
                self.remove_option_at_index(self.highlighted)
                event.stop()
            elif event.key in config["keybinds"]["toggle_all"]:
                """Select all items in the clipboard."""
                if len(self.selected) == len(self.options):
                    self.deselect_all()
                else:
                    self.select_all()
                event.stop()


class MetadataContainer(VerticalScroll):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.current_path: str | None = None
        self._size_worker = None
        self._update_task = None
        self._queued_task = None
        self._queued_task_args: None | DirEntry = None

    def info_of_dir_entry(self, dir_entry: DirEntry, type_string: str) -> str:
        """Get the permission line from a given DirEntry object
        Args:
            dir_entry (DirEntry): The nt.DirEntry class
            type_string (str): The type of file. It should already be handled.
        Returns:
            str: A permission string.
        """
        try:
            file_stat = lstat(dir_entry.path)
        except (OSError, FileNotFoundError):
            return "?????????"
        mode = file_stat.st_mode

        permission_string = ""
        match type_string:
            case "Symlink":
                permission_string = "l"
            case "Directory":
                permission_string = "d"
            case "Junction":
                permission_string = "j"
            case "File":
                permission_string = "-"
            case "Unknown":
                return "???????"

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

    def any_in_queue(self) -> bool:
        if self._queued_task is not None:
            self._queued_task(self._queued_task_args)
            self._queued_task, self._queued_task_args = None, None
            return True
        return False

    def update_metadata(self, dir_entry: DirEntry) -> None:
        """
        Debounce the update, because some people can be speed travellers
        Args:
            dir_entry (DirEntry): The nt.DirEntry object
        """
        if any(
            worker.is_running
            and worker.node is self
            and worker.name == "_perform_update"
            for worker in self.app.workers
        ):
            self._queued_task = self._perform_update
            self._queued_task_args = dir_entry
        else:
            self._perform_update(dir_entry)

    @work(thread=True)
    def _perform_update(self, dir_entry: DirEntry) -> None:
        """
        After debouncing the update
        Args:
            dir_entry (DirEntry): The nt.DirEntry object
        """
        if self.any_in_queue():
            return
        if not path.exists(dir_entry.path):
            self.app.call_from_thread(self.remove_children)
            self.app.call_from_thread(
                self.mount, Static("Item not found or inaccessible.")
            )
            return

        type_str = "Unknown"
        if dir_entry.is_junction():
            type_str = "Junction"
        elif dir_entry.is_symlink():
            type_str = "Symlink"
        elif dir_entry.is_dir():
            type_str = "Directory"
        elif dir_entry.is_file():
            type_str = "File"
        file_info = self.info_of_dir_entry(dir_entry, type_str)
        # got the type, now we follow
        file_stat = dir_entry.stat()
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
                            utils.natural_size(file_stat.st_size)
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
        if self.any_in_queue():
            return
        values = VerticalGroup(*values_list, id="metadata-values")

        try:
            for index, child_widget in enumerate(
                self.query_one("#metadata-values").children
            ):
                self.app.call_from_thread(
                    child_widget.update, values_list[index]._content
                )
        except NoMatches:
            self.app.call_from_thread(self.remove_children)
            keys_list = []
            for field in config["metadata"]["fields"]:
                match field:
                    case "type":
                        keys_list.append(Static("Type"))
                    case "permissions":
                        keys_list.append(Static("Permissions"))
                    case "size":
                        keys_list.append(Static("Size"))
                    case "modified":
                        keys_list.append(Static("Modified"))
                    case "accessed":
                        keys_list.append(Static("Accessed"))
                    case "created":
                        keys_list.append(Static("Created"))
            keys = VerticalGroup(*keys_list, id="metadata-keys")
            self.app.call_from_thread(self.mount, keys, values)
        finally:
            if self.any_in_queue():
                return
        self.current_path = dir_entry.path
        if type_str == "Directory" and self.has_focus:
            self._size_worker = self.calculate_folder_size(dir_entry.path)
        if self.any_in_queue():
            return
        else:
            self._queued_task = None

    @work(thread=True)
    async def calculate_folder_size(self, folder_path: str) -> None:
        """Calculate the size of a folder and update the metadata."""
        size_widget = self.query_one("#metadata-size", Static)
        self.app.call_from_thread(size_widget.update, "Calculating...")

        total_size = 0
        spinner_index = -1
        last_update_time = time.monotonic()
        try:
            for dirpath, _, filenames in walk(folder_path):
                for f in filenames:
                    if self._size_worker is None or self._size_worker.is_cancelled:
                        return
                    fp = path.join(dirpath, f)
                    if not path.islink(fp):
                        with suppress(OSError, FileNotFoundError):
                            total_size += lstat(fp).st_size
                if time.monotonic() - last_update_time > 0.25:
                    spinner_index = spinner_index + 1 if spinner_index // 3 == 0 else 0
                    self.app.call_from_thread(
                        size_widget.update,
                        f"{utils.natural_size(total_size)} {SPINNER[spinner_index]}",
                    )
                    last_update_time = time.monotonic()
        except (OSError, FileNotFoundError):
            self.app.call_from_thread(size_widget.update, "Error")
            return

        if not self._size_worker.is_cancelled:
            self.app.call_from_thread(
                size_widget.update, utils.natural_size(total_size)
            )

    @on(events.Focus)
    def on_focus(self) -> None:
        if self.current_path and path.isdir(self.current_path):
            if self._size_worker:
                return
            self._size_worker = self.calculate_folder_size(self.current_path)

    @on(events.Blur)
    def on_blur(self) -> None:
        if self._size_worker is None or self.app.app_blurred:
            return
        elif self._size_worker.state == WorkerState.SUCCESS:
            self._size_worker = None
        else:
            self._size_worker.cancel()
            self._size_worker = None
            self.set_timer(
                0.1, lambda: self.query_one("#metadata-size", Static).update("--")
            )


class ProgressBarContainer(VerticalGroup):
    def __init__(
        self,
        total: int | None = None,
        label: str = "",
        gradient: Gradient | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.progress_bar = ProgressBar(
            total=total,
            show_percentage=config["interface"]["show_progress_percentage"],
            show_eta=config["interface"]["show_progress_eta"],
            gradient=gradient,
        )
        self.label = Label(label)

    async def on_mount(self) -> None:
        await self.mount_all([self.label, self.progress_bar])

    def update_label(self, label: str, step: bool = False) -> None:
        """
        Updates the label, and optionally steps it
        Args:
            label (str): The new label
            step (bool) = False: Whether or not to increase the progress by 1
        """
        self.label.update(label)
        if step:
            self.progress_bar.advance(1)

    def update_progress(
        self,
        total: None | float | UnusedParameter = UnusedParameter(),
        progress: float | UnusedParameter = UnusedParameter(),
        advance: float | UnusedParameter = UnusedParameter(),
    ) -> None:
        self.progress_bar.update(total=total, progress=progress, advance=advance)


class ProcessContainer(VerticalScroll):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(id="processes", *args, **kwargs)

    async def new_process_bar(
        self, max: int | None = None, id: str | None = None, classes: str | None = None
    ) -> ProgressBarContainer:
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
            f"{utils.get_icon('general', 'delete')[0]} Getting files to delete...",
        )
        # get files to delete
        files_to_delete = []
        folders_to_delete = []
        for file in files:
            if compressed:
                file = utils.decompress(file)
            if path.isdir(file):
                folders_to_delete.append(file)
            files_to_delete.extend(utils.get_recursive_files(file))
        self.app.call_from_thread(bar.update_progress, total=len(files_to_delete) + 1)
        for item_dict in files_to_delete:
            self.app.call_from_thread(
                bar.update_label,
                f"{utils.get_icon('general', 'delete')[0]} {item_dict['relative_loc']}",
                step=True,
            )
            if path.exists(item_dict["path"]):
                # I know that it `path.exists` prevents issues, but on the
                # off chance that anything happens, this should help
                try:
                    if config["settings"]["use_recycle_bin"] and not ignore_trash:
                        try:
                            path_to_trash = item_dict["path"]
                            if (
                                platform.system() == "Windows"
                                and path_to_trash.startswith("\\\\\\\\?\\\\")
                            ):
                                # An inherent issue with long paths on windows
                                path_to_trash = path_to_trash[6:]
                            send2trash(path_to_trash)
                        except FileNotFoundError:
                            if path.exists(path_to_trash):
                                # edge case: have no write access
                                msg = (
                                    "Trashing failed due to no write access.\nContinue?"
                                )
                            else:
                                # really isn't found
                                msg = f"{path_to_trash} could not be found.\nContinue?"
                            do_continue = self.app.call_from_thread(
                                self.app.push_screen_wait, YesOrNo(msg)
                            )
                            if do_continue:
                                continue
                            else:
                                self.app.call_from_thread(
                                    bar.update_label,
                                    f"{utils.get_icon('general', 'delete')[0]} {utils.get_icon('general', 'close')[0]} Process Cancelled",
                                )
                                self.app.call_from_thread(bar.add_class, "error")
                                return
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
                                    f"{utils.get_icon('general', 'delete')[0]} {utils.get_icon('general', 'close')[0]} Process Interrupted",
                                )
                                self.app.call_from_thread(bar.add_class, "error")
                                return
                    else:
                        remove(item_dict["path"])
                except FileNotFoundError:
                    pass
                except PermissionError:
                    do_continue = self.app.call_from_thread(
                        self.app.push_screen_wait,
                        YesOrNo(
                            f"{item_dict['path']} could not be deleted due to PermissionError.\nContinue?"
                        ),
                    )
                    if not do_continue:
                        self.app.call_from_thread(bar.add_class, "error")
                        return
                except Exception as e:
                    # TODO: should probably let it continue, then have a summary
                    self.app.call_from_thread(
                        bar.update_label,
                        f"{utils.get_icon('general', 'delete')[0]} {utils.get_icon('general', 'close')[0]} Unhandled Error.",
                    )
                    self.app.call_from_thread(bar.add_class, "error")
                    self.app.call_from_thread(
                        self.app.push_screen_wait,
                        Dismissable(f"Deleting failed due to\n{e}\nProcess Aborted."),
                    )
                    return
        # The reason for an extra +1 in the total is for this
        # handling folders
        for folder in folders_to_delete:
            try:
                shutil.rmtree(folder)
            except PermissionError:
                # TODO: allow continuation and not return on error
                self.notify(
                    f"Certain files in {folder} could not be deleted.", severity="error"
                )
                self.app.call_from_thread(
                    bar.update_label,
                    f"{utils.get_icon('general', 'delete')[0]} {utils.get_icon('general', 'close')[0]} {bar.label._content[2:]}",
                )
                self.app.call_from_thread(bar.add_class, "error")
                return
        # if there werent any files, show something useful
        # aside from 'Getting files to delete...'
        if files_to_delete == []:
            self.app.call_from_thread(
                bar.update_label,
                f"{utils.get_icon('general', 'delete')[0]} {folders_to_delete[-1]}",
            )
        # finished successfully
        self.app.call_from_thread(
            bar.update_label,
            f"{utils.get_icon('general', 'delete')[0]} {utils.get_icon('general', 'check')[0]} {bar.label._content[2:]}",
            step=True,
        )
        self.app.call_from_thread(bar.progress_bar.advance)
        self.app.call_from_thread(bar.add_class, "done")

    @work(thread=True)
    def zip_files(self, files: list[str], archive_name: str) -> None:
        """
        Compress files into a zip archive.

        Args:
            files (list[str]): List of file paths to compress.
            archive_name (str): Path for the output zip archive.
        """
        bar = self.app.call_from_thread(self.new_process_bar, classes="active")
        self.app.call_from_thread(
            bar.update_label,
            f"{utils.get_icon('general', 'zip')[0]} Getting files to zip...",
        )

        files_to_zip = []
        for p in files:
            if path.isdir(p):
                if not listdir(p):  # empty dir
                    files_to_zip.append(p)
                else:
                    for dirpath, _, filenames in walk(p):
                        for f in filenames:
                            files_to_zip.append(path.join(dirpath, f))
            else:
                files_to_zip.append(p)

        files_to_zip = sorted(list(set(files_to_zip)))

        self.app.call_from_thread(bar.update_progress, total=len(files_to_zip) + 1)

        if len(files) == 1:
            base_path = path.dirname(files[0])
        else:
            base_path = path.commonpath(files)

        try:
            with ZipFile(archive_name, "w", ZIP_DEFLATED) as zipf:
                for file_path in files_to_zip:
                    arcname = path.relpath(file_path, base_path)
                    self.app.call_from_thread(
                        bar.update_label,
                        f"{utils.get_icon('general', 'zip')[0]} {arcname}",
                        step=True,
                    )
                    zipf.write(file_path, arcname)
                for p in files:
                    if path.isdir(p) and not listdir(p):
                        arcname = path.relpath(p, base_path)
                        zipf.write(p, arcname)

        except Exception as e:
            self.app.call_from_thread(
                bar.update_label,
                f"{utils.get_icon('general', 'zip')[0]} {utils.get_icon('general', 'close')[0]} Error creating zip file.",
            )
            self.app.call_from_thread(bar.add_class, "error")
            self.app.call_from_thread(
                self.app.push_screen_wait,
                Dismissable(f"Zipping failed due to\n{e}\nProcess Aborted."),
            )
            return

        self.app.call_from_thread(
            bar.update_label,
            f"{utils.get_icon('general', 'zip')[0]} {utils.get_icon('general', 'check')[0]} {bar.label._content[2:]}",
            step=True,
        )
        self.app.call_from_thread(bar.add_class, "done")
        self.app.call_from_thread(self.app.query_one("#refresh").action_press)

    @work(thread=True)
    def unzip_file(self, archive_path: str, destination_path: str) -> None:
        """
        Extracts a zip archive to a destination.

        Args:
            archive_path (str): Path to the zip archive.
            destination_path (str): Path to the destination folder.
        """
        bar = self.app.call_from_thread(self.new_process_bar, classes="active")
        self.app.call_from_thread(
            bar.update_label,
            f"{utils.get_icon('general', 'open')[0]} Preparing to extract...",
        )

        do_what_on_existance = "ask"
        ignore_permission_error = False
        try:
            if not path.exists(destination_path):
                makedirs(destination_path)

            with ZipFile(archive_path, "r") as zip_ref:
                file_list = zip_ref.infolist()
                self.app.call_from_thread(bar.update_progress, total=len(file_list) + 1)

                for file in file_list:
                    self.app.call_from_thread(
                        bar.update_label,
                        f"{utils.get_icon('general', 'open')[0]} {file.filename}",
                        step=True,
                    )
                    if path.exists(destination_path):
                        if do_what_on_existance == "ask":
                            response = self.app.call_from_thread(
                                self.app.push_screen_wait,
                                CommonFileNameDoWhat(
                                    f"{file.filename} already exists in destination",
                                    border_title=f"Extracting to {destination_path}",
                                ),
                            )
                            if response["same_for_next"]:
                                do_what_on_existance = response["value"]
                            val = response["value"]
                        else:
                            val = do_what_on_existance
                        match val:
                            case "overwrite":
                                pass
                            case "skip":
                                continue
                            case "rename":
                                exists = True
                                base = ".".join(destination_path.split(".")[:-1])
                                extension = destination_path.split(".")[-1]
                                tested_number = 1
                                while exists:
                                    # similar to how explorer does it
                                    if path.exists(
                                        path.join(
                                            destination_path,
                                            ".".join([
                                                base + f" ({tested_number})",
                                                extension,
                                            ]),
                                        )
                                    ):
                                        tested_number += 1
                                new_path = utils.normalise(
                                    path.join(
                                        destination_path,
                                        ".".join([
                                            base + f" ({tested_number})",
                                            extension,
                                        ]),
                                    )
                                )
                                with (
                                    zip_ref.open(file) as source,
                                    open(new_path, "wb") as target,
                                ):
                                    target.write(source.read())
                                continue
                            case "cancel":
                                self.app.call_from_thread(
                                    bar.update_label,
                                    f"{utils.get_icon('general', 'copy')[0]}",
                                )
                                self.app.call_from_thread(bar.add_class, "error")
                                return
                    try:
                        zip_ref.extract(file.filename, path=destination_path)
                    except PermissionError:
                        if not ignore_permission_error:
                            result = self.app.call_from_thread(
                                self.app.push_screen_wait,
                                YesOrNo(
                                    f"{file.filename} could not be overwritten due to a PermissionError.\nContinue?",
                                    with_toggle=True,
                                ),
                            )
                            ignore_permission_error = result["toggle"]
                            if not result["value"]:
                                bar.add_class("error")
                                return
        except Exception as e:
            self.app.call_from_thread(
                bar.update_label,
                f"{utils.get_icon('general', 'open')[0]} {utils.get_icon('general', 'close')[0]} Error extracting archive.",
            )
            self.app.call_from_thread(bar.add_class, "error")
            self.app.call_from_thread(
                self.app.push_screen_wait,
                Dismissable(f"Unzipping failed due to\n{e}\nProcess Aborted."),
            )
            return

        self.app.call_from_thread(
            bar.update_label,
            f"{utils.get_icon('general', 'open')[0]} {utils.get_icon('general', 'check')[0]} {bar.label._content[2:]}",
            step=True,
        )
        self.app.call_from_thread(bar.add_class, "done")
        self.app.call_from_thread(self.app.query_one("#refresh").action_press)

    @work(thread=True)
    def paste_items(self, copied: list[str], cutted: list[str], dest: str = "") -> None:
        """
        Paste copied or cut files to the current directory
        Args:
            copied (list[str]): A list of items to be copied to the location
            cutted (list[str]): A list of items to be cut to the location
            dest (str) = getcwd(): The directory to copy to.
        """
        # so overall before its done, I need copied to copy over, and
        # cutted, to move have copy go first, then cut over items, then
        # remove cut items from clipboard. to remove, you add `-cut` to
        # the end, then compress, then get option by id, remove item
        if dest == "":
            dest = getcwd()
        bar: ProgressBarContainer = self.app.call_from_thread(
            self.new_process_bar, classes="active"
        )
        self.app.call_from_thread(
            bar.update_label,
            f"{utils.get_icon('general', 'paste')[0]} Getting items to paste...",
        )
        files_to_copy = []
        files_to_cut = []
        cut_files__folders = []
        for file in copied:
            files_to_copy.extend(utils.get_recursive_files(file))
        for file in cutted:
            if path.isdir(file):
                cut_files__folders.append(utils.normalise(file))
            files_to_cut.extend(utils.get_recursive_files(file))
        self.app.call_from_thread(
            bar.update_progress, total=int(len(files_to_copy) + len(files_to_cut)) + 1
        )
        # can be either 'ask', 'skip' or 'overwrite'
        action_on_existance = "ask"
        for item_dict in files_to_copy:
            self.app.call_from_thread(
                bar.update_label,
                f"{utils.get_icon('general', 'copy')[0]} {item_dict['relative_loc']}",
                step=True,
            )
            if path.exists(item_dict["path"]):
                # again checks just in case something goes wrong
                try:
                    makedirs(
                        utils.normalise(
                            path.join(dest, item_dict["relative_loc"], "..")
                        ),
                        exist_ok=True,
                    )
                    if path.exists(path.join(dest, item_dict["relative_loc"])):
                        # check if overwrite
                        match action_on_existance:
                            case "overwrite":
                                pass
                            case "skip":
                                continue
                            case "rename":
                                exists = True
                                base = ".".join(
                                    item_dict["relative_loc"].split(".")[:-1]
                                )
                                extension = item_dict["relative_loc"].split(".")[-1]
                                tested_number = 1
                                while exists:
                                    # similar to how explorer does it
                                    if path.exists(
                                        path.join(
                                            dest,
                                            ".".join([
                                                base + f" ({tested_number})",
                                                extension,
                                            ]),
                                        )
                                    ):
                                        tested_number += 1
                                    else:
                                        exists = False
                                item_dict["relative_loc"] = utils.normalise(
                                    path.join(
                                        dest,
                                        ".".join([
                                            base + f" ({tested_number})",
                                            extension,
                                        ]),
                                    )
                                )
                            case _:
                                # check if they are the same
                                if utils.normalise(
                                    dest + "/" + item_dict["relative_loc"]
                                ) == utils.normalise(item_dict["path"]):
                                    # why would you ever want to ask
                                    continue
                                response = self.app.call_from_thread(
                                    self.app.push_screen_wait,
                                    CommonFileNameDoWhat(
                                        f"The destination already has a file named {item_dict['relative_loc']}.",
                                        f"Copying to {dest}",
                                    ),
                                )
                                if response["same_for_next"]:
                                    action_on_existance = response["value"]
                                match response["value"]:
                                    case "overwrite":
                                        pass
                                    case "skip":
                                        continue
                                    case "rename":
                                        exists = True
                                        base = ".".join(
                                            item_dict["relative_loc"].split(".")[:-1]
                                        )
                                        extension = item_dict["relative_loc"].split(
                                            "."
                                        )[-1]
                                        tested_number = 1
                                        while exists:
                                            # similar to how explorer does it
                                            if path.exists(
                                                path.join(
                                                    dest,
                                                    ".".join([
                                                        base + f" ({tested_number})",
                                                        extension,
                                                    ]),
                                                )
                                            ):
                                                tested_number += 1
                                            else:
                                                exists = False
                                        item_dict["relative_loc"] = utils.normalise(
                                            path.join(
                                                dest,
                                                ".".join([
                                                    base + f" ({tested_number})",
                                                    extension,
                                                ]),
                                            )
                                        )
                                    case "cancel":
                                        self.app.call_from_thread(
                                            bar.update_label,
                                            f"{utils.get_icon('general', 'copy')[0]} {utils.get_icon('general', 'close')[0]} Process cancelled",
                                        )
                                        self.app.call_from_thread(
                                            bar.add_class, "error"
                                        )
                                        return
                    if config["settings"]["copy_includes_metadata"]:
                        shutil.copy2(
                            item_dict["path"],
                            path.join(dest, item_dict["relative_loc"]),
                        )
                    else:
                        shutil.copy(
                            item_dict["path"],
                            path.join(dest, item_dict["relative_loc"]),
                        )
                except (OSError, PermissionError) as e:
                    # OSError from shutil: The destination location must be writable; otherwise, an OSError exception will be raised
                    # Permission Error just in case
                    do_continue = self.app.call_from_thread(
                        self.app.push_screen_wait,
                        YesOrNo(
                            f"{item_dict['path']} could not be copied due to {e}.\nContinue?"
                        ),
                    )
                    if not do_continue:
                        self.app.call_from_thread(bar.add_class, "error")
                        return
                    pass
                except FileNotFoundError:
                    # by chance if somehow this is raised, still catch it
                    pass
                except Exception as e:
                    # TODO: should probably let it continue, then have a summary
                    self.app.call_from_thread(
                        bar.update_label,
                        f"{utils.get_icon('general', 'copy')[0]} {utils.get_icon('general', 'close')[0]} Unhandled Error.",
                    )
                    self.app.call_from_thread(bar.add_class, "error")
                    self.app.call_from_thread(
                        self.app.push_screen_wait,
                        Dismissable(f"Deleting failed due to\n{e}\nProcess Aborted."),
                    )
                    return

        cut_ignore = []
        for item_dict in files_to_cut:
            self.app.call_from_thread(
                bar.update_label,
                f"{utils.get_icon('general', 'cut')[0]} {item_dict['relative_loc']}",
                step=True,
            )
            if path.exists(item_dict["path"]):
                # again checks just in case something goes wrong
                try:
                    makedirs(
                        utils.normalise(
                            path.join(dest, item_dict["relative_loc"], "..")
                        ),
                        exist_ok=True,
                    )
                    if path.exists(path.join(dest, item_dict["relative_loc"])):
                        match action_on_existance:
                            case "overwrite":
                                pass
                            case "skip":
                                cut_ignore.append(item_dict["path"])
                                continue
                            case "rename":
                                exists = True
                                base = ".".join(
                                    item_dict["relative_loc"].split(".")[:-1]
                                )
                                extension = item_dict["relative_loc"].split(".")[-1]
                                tested_number = 1
                                while exists:
                                    # similar to how explorer does it
                                    if path.exists(
                                        path.join(
                                            dest,
                                            ".".join([
                                                base + f" ({tested_number})",
                                                extension,
                                            ]),
                                        )
                                    ):
                                        tested_number += 1
                                    else:
                                        exists = False
                                item_dict["relative_loc"] = utils.normalise(
                                    path.join(
                                        dest,
                                        ".".join([
                                            base + f" ({tested_number})",
                                            extension,
                                        ]),
                                    )
                                )
                            case _:
                                # check if they are the same
                                if utils.normalise(
                                    dest + "/" + item_dict["relative_loc"]
                                ) == utils.normalise(item_dict["path"]):
                                    # why would you ever want to ask
                                    cut_ignore.append(item_dict["path"])
                                    continue
                                response = self.app.call_from_thread(
                                    self.app.push_screen_wait,
                                    CommonFileNameDoWhat(
                                        f"The destination already has a file named {item_dict['relative_loc']}.",
                                        f"Moving to {dest}",
                                    ),
                                )
                                if response["same_for_next"]:
                                    action_on_existance = response["value"]
                                match response["value"]:
                                    case "overwrite":
                                        pass
                                    case "skip":
                                        cut_ignore.append(item_dict["path"])
                                        continue
                                    case "rename":
                                        exists = True
                                        base = ".".join(
                                            item_dict["relative_loc"].split(".")[:-1]
                                        )
                                        extension = item_dict["relative_loc"].split(
                                            "."
                                        )[-1]
                                        tested_number = 1
                                        while exists:
                                            # similar to how explorer does it
                                            if path.exists(
                                                path.join(
                                                    dest,
                                                    ".".join([
                                                        base + f" ({tested_number})",
                                                        extension,
                                                    ]),
                                                )
                                            ):
                                                tested_number += 1
                                            else:
                                                exists = False
                                        item_dict["relative_loc"] = utils.normalise(
                                            path.join(
                                                dest,
                                                ".".join([
                                                    base + f" ({tested_number})",
                                                    extension,
                                                ]),
                                            )
                                        )
                                    case "cancel":
                                        self.app.call_from_thread(
                                            bar.update_label,
                                            f"{utils.get_icon('general', 'copy')[0]} {utils.get_icon('general', 'close')[0]} Process cancelled",
                                        )
                                        self.app.call_from_thread(
                                            bar.add_class, "error"
                                        )
                                        return
                    shutil.move(
                        item_dict["path"],
                        path.join(dest, item_dict["relative_loc"]),
                    )
                except (OSError, PermissionError):
                    # OSError from shutil: The destination location must be writable; otherwise, an OSError exception will be raised
                    # Permission Error just in case
                    do_continue = self.app.call_from_thread(
                        self.app.push_screen_wait,
                        YesOrNo(
                            f"{item_dict['path']} could not be copied due to Permission Errors.\nContinue?"
                        ),
                    )
                    if not do_continue:
                        self.app.call_from_thread(bar.add_class, "error")
                        return
                    pass
                except FileNotFoundError:
                    # by chance if somehow this is raised, still catch it
                    pass
                except Exception as e:
                    # utils.TODO: should probably let it continue, then have a summary
                    self.app.call_from_thread(
                        bar.update_label,
                        f"{utils.get_icon('general', 'copy')[0]} {utils.get_icon('general', 'close')} Unhandled Error.",
                    )
                    self.app.call_from_thread(bar.add_class, "error")
                    self.app.call_from_thread(
                        self.app.push_screen_wait,
                        Dismissable(f"Deleting failed due to \n{e}\nProcess Aborted."),
                    )
        # delete the folders
        for folder in cut_files__folders:
            try:
                skip = False
                for file in cut_ignore:
                    if folder in file:
                        skip = True
                        break
                if not skip:
                    shutil.rmtree(folder)
            except PermissionError:
                # TODO: allow continuation and not return on error
                self.notify(
                    f"Certain files in {folder} could not be moved.", severity="error"
                )
                self.app.call_from_thread(
                    bar.update_label,
                    f"{utils.get_icon('general', 'cut')[0]} {utils.get_icon('general', 'close')[0]} {path.basename(cutted[-1])}",
                )
                self.app.call_from_thread(bar.add_class, "error")
                return
        # remove from clipboard
        for item in cutted:
            # cant bother to figure out how this happens,
            # just catch it
            with suppress(OptionDoesNotExist):
                self.app.call_from_thread(
                    self.app.query_one(Clipboard).remove_option, utils.compress(item)
                )
        self.app.call_from_thread(
            bar.update_label,
            f"{utils.get_icon('general', 'cut' if len(cutted) else 'copy')[0]} {utils.get_icon('general', 'check')[0]} {bar.label._content[2:]}",
            step=True,
        )
        self.app.call_from_thread(bar.add_class, "done")

    async def on_key(self, event: events.Key) -> None:
        if event.key in config["keybinds"]["delete"]:
            event.stop()
            await self.remove_children(".done")
            await self.remove_children(".error")
