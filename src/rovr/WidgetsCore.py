import asyncio
from contextlib import suppress
from os import DirEntry, chdir, getcwd, path
from os import system as cmd
from typing import ClassVar

import textual_image.widget as timg
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.content import Content
from textual.geometry import Size
from textual.strip import Strip
from textual.widgets import Button, Input, OptionList, SelectionList, Static, TextArea
from textual.widgets.option_list import Option, OptionDoesNotExist
from textual.widgets.selection_list import Selection

from . import utils
from .maps import EXT_TO_LANG_MAP, PIL_EXTENSIONS
from .utils import config


class CustomTextArea(TextArea, inherit_bindings=False):
    BINDINGS: ClassVar[list[BindingType]] = (
        # Bindings from config
        [
            Binding(bind, "cursor_up", "Cursor up", show=False)
            for bind in config["keybinds"]["up"]
        ]
        + [
            Binding(bind, "cursor_down", "Cursor down", show=False)
            for bind in config["keybinds"]["down"]
        ]
        + [
            Binding(bind, "cursor_left", "Cursor left", show=False)
            for bind in config["keybinds"]["preview_scroll_left"]
        ]
        + [
            Binding(bind, "cursor_right", "Cursor right", show=False)
            for bind in config["keybinds"]["preview_scroll_right"]
        ]
        + [
            Binding(bind, "cursor_line_start", "Cursor line start", show=False)
            for bind in config["keybinds"]["home"]
        ]
        + [
            Binding(bind, "cursor_line_end", "Cursor line end", show=False)
            for bind in config["keybinds"]["end"]
        ]
        + [
            Binding(bind, "cursor_page_up", "Cursor page up", show=False)
            for bind in config["keybinds"]["page_up"]
        ]
        + [
            Binding(bind, "cursor_page_down", "Cursor page down", show=False)
            for bind in config["keybinds"]["page_down"]
        ]
        + [
            Binding(bind, "cursor_up(True)", "Cursor up select", show=False)
            for bind in config["keybinds"]["select_up"]
        ]
        + [
            Binding(bind, "cursor_down(True)", "Cursor down select", show=False)
            for bind in config["keybinds"]["select_down"]
        ]
        + [
            Binding(
                bind, "cursor_line_start(True)", "Cursor line start select", show=False
            )
            for bind in config["keybinds"]["select_home"]
        ]
        + [
            Binding(bind, "cursor_line_end(True)", "Cursor line end select", show=False)
            for bind in config["keybinds"]["select_end"]
        ]
        + [
            Binding(bind, "cursor_page_up(True)", "Cursor page up select", show=False)
            for bind in config["keybinds"]["select_page_up"]
        ]
        + [
            Binding(
                bind, "cursor_page_down(True)", "Cursor page down select", show=False
            )
            for bind in config["keybinds"]["select_page_down"]
        ]
        + [
            Binding(bind, "select_all", "Select all", show=False)
            for bind in config["keybinds"]["toggle_all"]
        ]
        + [
            Binding(bind, "delete_right", "Delete character right", show=False)
            for bind in config["keybinds"]["delete"]
        ]
        + [
            Binding(bind, "cut", "Cut", show=False)
            for bind in config["keybinds"]["cut"]
        ]
        + [
            Binding(bind, "copy", "Copy", show=False)
            for bind in config["keybinds"]["copy"]
        ]
        + [
            Binding(bind, "paste", "Paste", show=False)
            for bind in config["keybinds"]["paste"]
        ]
        + [
            Binding(bind, "cursor_right(True)", "Select right", show=False)
            for bind in config["keybinds"]["preview_select_right"]
        ]
        + [
            Binding(bind, "cursor_left(True)", "Select left", show=False)
            for bind in config["keybinds"]["preview_select_left"]
        ]
        # Hardcoded bindings
        + [
            Binding("ctrl+left", "cursor_word_left", "Cursor word left", show=False),
            Binding("ctrl+right", "cursor_word_right", "Cursor word right", show=False),
            Binding(
                "shift+left", "cursor_left(True)", "Cursor left select", show=False
            ),
            Binding(
                "shift+right", "cursor_right(True)", "Cursor right select", show=False
            ),
            Binding(
                "ctrl+shift+left",
                "cursor_word_left(True)",
                "Cursor left word select",
                show=False,
            ),
            Binding(
                "ctrl+shift+right",
                "cursor_word_right(True)",
                "Cursor right word select",
                show=False,
            ),
            Binding("f6", "select_line", "Select line", show=False),
        ]
    )


class PreviewContainer(Container):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queued_task = None
        self._queued_task_args: str | None = None
        self._current_content = None
        self._current_file_path = None
        self._is_image = False
        self._initial_height = self.size.height
        self._current_preview_type = "none"

    def compose(self) -> ComposeResult:
        # for some unknown reason, it started causing KeyErrors
        # and I just cannot catch the exception
        # yield TextArea(
        #     id="text_preview",
        #     show_line_numbers=True,
        #     soft_wrap=True,
        #     read_only=True,
        #     text=config["interface"]["preview_start"],
        #     language="markdown",
        #     compact=True
        # )
        yield Static(config["interface"]["preview_start"])

    async def _show_image_preview(self) -> None:
        """Ensure image preview widget exists and is updated."""
        if self.any_in_queue():
            return
        if self._current_preview_type != "image":
            self._current_preview_type = "none"
            await self.remove_children()
            self.remove_class("bat", "full", "clip")

            if self.any_in_queue():
                return
            try:
                await self.mount(
                    timg.__dict__[f"{config['settings']['image_protocol']}Image"](
                        self._current_file_path,
                        id="image_preview",
                        classes="inner_preview",
                    )
                )
                self.query_one("#image_preview").can_focus = True
            except FileNotFoundError:
                await self.mount(
                    CustomTextArea(
                        id="text_preview",
                        show_line_numbers=True,
                        soft_wrap=False,
                        read_only=True,
                        text=config["interface"]["preview_error"],
                        language="markdown",
                        compact=True,
                    )
                )
            self._current_preview_type = "image"
        else:
            try:
                self.query_one("#image_preview").image = self._current_file_path
            except Exception:
                self._current_preview_type = "none"
                # re-make the widget itself
                await self._show_image_preview()
        self.border_title = "Image Preview"

    async def _show_bat_file_preview(self) -> bool:
        """Render file preview using bat, updating in place if possible.
        Returns:
            bool: whether or not the action was successful"""
        bat_executable = config["plugins"]["bat"]["executable"]
        preview_full = config["settings"]["preview_full"]
        command = [
            bat_executable,
            "--force-colorization",
            "--paging=never",
            "--style=numbers"
            if config["plugins"]["bat"]["show_line_numbers"]
            else "--style=plain",
        ]
        if not preview_full:
            max_lines = self.size.height
            if max_lines > 0:
                command.append(f"--line-range=:{max_lines}")
        command.append(self._current_file_path)

        if self.any_in_queue():
            return

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if self.any_in_queue():
                return True

            if process.returncode == 0:
                bat_output = stdout.decode("utf-8", errors="ignore")
                new_content = Text.from_ansi(bat_output)

                if self._current_preview_type != "bat":
                    self._current_preview_type = "none"
                    await self.remove_children()
                    self.remove_class("full", "clip")

                    if self.any_in_queue():
                        return True

                    await self.mount(
                        Static(new_content, id="text_preview", classes="inner_preview")
                    )
                    self.query_one(Static).can_focus = True
                    self.add_class("bar")
                    self._current_preview_type = "bat"
                else:
                    self.query_one("#text_preview", Static).update(new_content)

                self.border_title = "File Preview (bat)"
                self.remove_class("full", "clip")
                if preview_full:
                    self.add_class("full")
                else:
                    self.add_class("clip")
                return True
            else:
                error_message = stderr.decode("utf-8", errors="ignore")
                self._current_preview_type = "none"
                await self.remove_children()
                self.notify(
                    f"bat preview failed: {error_message}",
                    severity="warning",
                    timeout=5,
                )
                return False
        except (FileNotFoundError, Exception) as e:
            self.notify(f"bat preview failed: {e}", severity="warning", timeout=5)
            return False

    async def _show_normal_file_preview(self) -> None:
        """Render file preview using TextArea, updating in place if possible."""
        text_to_display = self._current_content
        preview_full = config["settings"]["preview_full"]
        if not preview_full:
            lines = text_to_display.splitlines()
            max_lines = self.size.height
            if max_lines > 0:
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
            else:
                lines = []
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

        is_special_content = self._current_content in (
            config["interface"]["preview_binary"],
            config["interface"]["preview_error"],
        )
        language = (
            "markdown"
            if is_special_content
            else EXT_TO_LANG_MAP.get(
                path.splitext(self._current_file_path)[1], "markdown"
            )
        )

        if self.any_in_queue():
            return

        if self._current_preview_type != "normal_text":
            self._current_preview_type = "none"
            await self.remove_children()
            self.remove_class("bat", "full", "clip")

            if self.any_in_queue():
                return

            await self.mount(
                CustomTextArea(
                    id="text_preview",
                    show_line_numbers=True,
                    soft_wrap=False,
                    read_only=True,
                    text=text_to_display,
                    language=language,
                    classes="inner_preview",
                )
            )
            self._current_preview_type = "normal_text"
        else:
            text_area = self.query_one("#text_preview", CustomTextArea)
            text_area.text = text_to_display
            text_area.language = language

        self.border_title = "File Preview"

    async def _render_preview(self) -> None:
        """Render function dispatcher."""
        if self._current_file_path is None:
            return

        if self._is_image:
            await self._show_image_preview()
            return

        if self._current_content is None:
            return

        # you wouldnt want to re-render a failed thing, would you?
        is_special_content = self._current_content in (
            config["interface"]["preview_binary"],
            config["interface"]["preview_error"],
        )

        if (
            config["plugins"]["bat"]["enabled"]
            and not is_special_content
            and await self._show_bat_file_preview()
        ):
            self.log("bat success")
            return

        await self._show_normal_file_preview()

    async def _show_folder_preview(self, folder_path: str) -> None:
        """
        Show the folder in the preview container.
        Args:
            folder_path(str): The folder path
        """
        if self._current_preview_type != "folder":
            self._current_preview_type = "none"
            await self.remove_children()
            self.remove_class("bat", "full", "clip")

            if self.any_in_queue():
                return

            await self.mount(
                FileList(
                    id="folder_preview",
                    name=folder_path,
                    classes="file-list inner_preview",
                    dummy=True,
                    enter_into=folder_path,
                )
            )
            self._current_preview_type = "folder"

        if self.any_in_queue():
            return

        folder_preview = self.query_one("#folder_preview", FileList)
        folder_preview.dummy_update_file_list(
            cwd=folder_path,
        )
        self.border_title = "Folder Preview"

    def any_in_queue(self) -> bool:
        if self._queued_task is not None:
            self._queued_task(self._queued_task_args)
            self._queued_task, self._queued_task_args = None, None
            return True
        return False

    def show_preview(self, file_path: str) -> None:
        """
        Debounce requests, then show preview
        Args:
            file_path(str): The file path
        """
        if any(
            worker.is_running
            and worker.node is self
            and worker.name == "_perform_show_preview"
            for worker in self.app.workers
        ):
            self._queued_task = self._perform_show_preview
            self._queued_task_args = file_path
        else:
            self._perform_show_preview(file_path)

    @work(thread=True)
    def _perform_show_preview(self, file_path: str) -> None:
        """
        Load file content in a worker and then render the preview.
        Args:
            file_path(str): The file path
        """
        if self.any_in_queue():
            return

        if path.isdir(file_path):
            self.app.call_from_thread(self._update_ui, file_path, is_dir=True)
        else:
            is_image = any(file_path.endswith(ext) for ext in PIL_EXTENSIONS)
            content = None
            if not is_image:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    content = config["interface"]["preview_binary"]
                except (FileNotFoundError, PermissionError, OSError):
                    content = config["interface"]["preview_error"]

            if self.any_in_queue():
                return

            self.app.call_from_thread(
                self._update_ui,
                file_path,
                is_dir=False,
                is_image=is_image,
                content=content,
            )

        if self.any_in_queue():
            return
        else:
            self._queued_task = None

    async def _update_ui(
        self,
        file_path: str,
        is_dir: bool,
        is_image: bool = False,
        content: str | None = None,
    ) -> None:
        """
        Update the preview UI. This runs on the main thread.
        """
        self._current_file_path = file_path
        if is_dir:
            self._is_image = False
            self._current_content = None
            await self._show_folder_preview(file_path)
        else:
            self._is_image = is_image
            self._current_content = content
            await self._render_preview()

    async def on_resize(self, event: events.Resize) -> None:
        """Re-render the preview on resize if it's was rendered by batcat and height changed."""
        if (
            self._current_preview_type == "bat"
            and "clip" in self.classes
            and event.size.height != self._initial_height
        ):
            await self._render_preview()
            self._initial_height = event.size.height

    async def on_key(self, event: events.Key) -> None:
        """Check for vim keybinds."""
        if self.border_title == "File Preview (bat)":
            match event.key:
                case key if key in config["keybinds"]["up"]:
                    self.scroll_up(animate=False)
                case key if key in config["keybinds"]["down"]:
                    self.scroll_down(animate=False)
                case key if key in config["keybinds"]["page_up"]:
                    self.scroll_page_up(animate=False)
                case key if key in config["keybinds"]["page_down"]:
                    self.scroll_page_down(animate=False)
                case key if key in config["keybinds"]["home"]:
                    self.scroll_home(animate=False)
                case key if key in config["keybinds"]["end"]:
                    self.scroll_end(animate=False)
                case key if key in config["keybinds"]["preview_scroll_left"]:
                    self.scroll_left(animate=False)
                case key if key in config["keybinds"]["preview_scroll_right"]:
                    self.scroll_right(animate=False)


class FolderNotFileError(Exception):
    """Raised when a folder is expected but a file is provided instead."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PinnedSidebarOption(Option):
    def __init__(self, icon: list, label: str, *args, **kwargs) -> None:
        super().__init__(
            prompt=Content.from_markup(
                f" [{icon[1]}]{icon[0]}[/{icon[1]}] $name", name=label
            ),
            *args,
            **kwargs,
        )
        self.label = label


class PinnedSidebar(OptionList, inherit_bindings=False):
    # Just so that I can disable space
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

    def _update_lines(self) -> None:
        """Update internal structures when new lines are added."""
        if not self.scrollable_content_region:
            return

        line_cache = self._line_cache
        line_cache.clear()
        padding = self.get_component_styles("option-list--option").padding
        width = self.scrollable_content_region.width - self._get_left_gutter_width()
        for index, option in enumerate(self.options):
            # in future, if anything was changed, you just need to add the line below
            if not option.disabled or option.id.endswith("header"):
                line_cache.index_to_line[index] = len(line_cache.lines)
                line_count = (
                    self._get_visual(option).get_height(
                        self.styles, width - padding.width
                    )
                    + option._divider
                )
                line_cache.heights[index] = line_count
                line_cache.lines.extend([
                    (index, line_no) for line_no in range(0, line_count)
                ])

        last_divider = self.options and self.options[-1]._divider
        virtual_size = Size(
            self.scrollable_content_region.width,
            len(line_cache.lines) - (1 if last_divider else 0),
        )
        if virtual_size != self.virtual_size:
            self.virtual_size = virtual_size
            self._scroll_update(virtual_size)

    @work(exclusive=True)
    async def reload_pins(self) -> None:
        """Reload pins shown

        Raises:
            FolderNotFileError: If the pin location is a file, and not a folder.
        """
        # be extra sure
        available_pins = utils.load_pins()
        pins = available_pins["pins"]
        default = available_pins["default"]
        print(f"Reloading pins: {available_pins}")
        print(f"Reloading default folders: {default}")
        self.clear_options()
        for default_folder in default:
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
                icon = utils.get_icon_for_folder(default_folder["name"])
            else:
                icon = utils.get_icon_for_file(default_folder["name"])
            self.add_option(
                PinnedSidebarOption(
                    icon=icon,
                    label=default_folder["name"],
                    id=f"{utils.compress(default_folder['path'])}-default",
                )
            )
        self.add_option(Option(" Pinned", id="pinned-header"))
        for pin in pins:
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
                icon = utils.get_icon_for_folder(pin["name"])
            else:
                icon = utils.get_icon_for_file(pin["name"])
            self.add_option(
                PinnedSidebarOption(
                    icon=icon,
                    label=pin["name"],
                    id=f"{utils.compress(pin['path'])}-pinned",
                )
            )
        self.add_option(Option(" Drives", id="drives-header"))
        drives = utils.get_mounted_drives()
        for drive in drives:
            self.add_option(
                PinnedSidebarOption(
                    icon=utils.get_icon("folder", ":/drive:"),
                    label=drive,
                    id=f"{utils.compress(drive)}-drives",
                )
            )
        self.disable_option("pinned-header")
        self.disable_option("drives-header")

    async def on_mount(self) -> None:
        """Reload the pinned files from the config."""
        self.input = self.parent.query_one(Input)
        self.reload_pins()

    async def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle the selection of an option in the pinned sidebar.
        Args:
            event (OptionList.OptionSelected): The event

        Raises:
            FolderNotFileError: If the pin found is a file and not a folder.
        """
        selected_option = event.option
        # Get the file path from the option id
        file_path = utils.decompress(selected_option.id.split("-")[0])
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
        self.input.clear()

    def on_key(self, event: events.Key) -> None:
        if event.key in config["keybinds"]["focus_search"]:
            self.input.focus()


class FileListSelectionWidget(Selection):
    def __init__(
        self, icon: list, label: str, dir_entry: DirEntry, *args, **kwargs
    ) -> None:
        """
        Initialise the selection.

        Args:
            icon (list): The icon list from a utils function.
            label (str): The label for the option.
            dir_entry (DirEntry): The nt.DirEntry class
            value (SelectionType): The value for the selection.
            initial_state (bool) = False: The initial selected state of the selection.
            id (str or None) = None: The optional ID for the selection.
            disabled (bool) = False: The initial enabled/disabled state. Enabled by default.
        """
        super().__init__(
            prompt=Content.from_markup(
                f" [{icon[1]}]{icon[0]}[/{icon[1]}] $name", name=label
            ),
            *args,
            **kwargs,
        )
        self.dir_entry = dir_entry
        self.label = label


class FileList(SelectionList, inherit_bindings=False):
    """
    OptionList but can multi-select files and folders.
    """

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

    def __init__(
        self,
        dummy: bool = False,
        enter_into: str = "",
        select: bool = False,
        *args,
        **kwargs,
    ) -> None:
        """
        Initialize the FileList widget.
        Args:
            dummy (bool): Whether this is a dummy file list.
            enter_into (str): The path to enter into when a folder is selected.
            select (bool): Whether the selection is select or normal.
        """
        super().__init__(*args, **kwargs)
        self.dummy = dummy
        self.enter_into = enter_into
        self.select_mode_enabled = select

    def on_mount(self) -> None:
        if not self.dummy:
            self.input: Input = self.parent.query_one(Input)

    # ignore single clicks
    async def _on_click(self, event: events.Click) -> None:
        """
        React to the mouse being clicked on an item.

        Args:
            event: The click event.
        """
        event.prevent_default()
        clicked_option: int | None = event.style.meta.get("option")
        if clicked_option is not None and not self._options[clicked_option].disabled:
            # in future, if anything was changed, you just need to add the lines below
            if self.highlighted == clicked_option:
                self.action_select()
            else:
                self.highlighted = clicked_option

    def update_file_list(
        self,
        add_to_session: bool = True,
        focus_on: str | None = None,
    ) -> None:
        """Update the file list with the current directory contents.

        Args:
            add_to_session (bool): Whether to add the current directory to the session history.
            focus_on (str | None): A custom item to set the focus as.
        """
        cwd = utils.normalise(getcwd())
        self.clear_options()
        # get sessionstate
        with suppress(AttributeError):
            session = self.app.tabWidget.active_tab.session
        print(self.app.tabWidget.active_tab)
        # Separate folders and files
        folders, files = utils.get_cwd_object(cwd)
        if folders == [PermissionError] or files == [PermissionError]:
            self.add_option(
                Selection(
                    " Permission Error: Unable to access this directory.",
                    value="",
                    id="",
                    disabled=True,
                ),
            )
            file_list_options = [".."]
        elif folders == [] and files == []:
            self.add_option(Selection(" --no-files--", value="", id="", disabled=True))
            self.app.query_one(PreviewContainer).remove_children()
            # nothing inside
        else:
            file_list_options = folders + files
            for item in file_list_options:
                self.add_option(
                    FileListSelectionWidget(
                        icon=item["icon"],
                        label=item["name"],
                        dir_entry=item["dir_entry"],
                        value=utils.compress(item["name"]),
                        id=utils.compress(item["name"]),
                    )
                )
        # session handler
        self.app.query_one("#path_switcher").value = cwd + "/"
        # I question to myself why sessionDirectories isnt a list[str]
        # but is a list[dict], so I'm down to take some PRs, because
        # I have other things that are more important.
        # TODO: use list[str] instead of list[dict] for sessionDirectories
        if add_to_session:
            if session.sessionHistoryIndex != len(session.sessionDirectories) - 1:
                session.sessionDirectories = session.sessionDirectories[
                    : session.sessionHistoryIndex + 1
                ]
            session.sessionDirectories.append({
                "path": cwd,
            })
            if session.sessionLastHighlighted.get(cwd) is None:
                # Hard coding is my passion (referring to the id)
                session.sessionLastHighlighted[cwd] = (
                    self.app.query_one("#file_list").options[0].value
                )
            session.sessionHistoryIndex = len(session.sessionDirectories) - 1
        elif session.sessionDirectories == []:
            session.sessionDirectories = [{"path": utils.normalise(getcwd())}]
        self.app.query_one("Button#back").disabled = session.sessionHistoryIndex == 0
        print("sessionHistoryIndex", session.sessionHistoryIndex)
        print("sessionDirectories", session.sessionDirectories)
        self.app.query_one("Button#forward").disabled = (
            session.sessionHistoryIndex == len(session.sessionDirectories) - 1
        )
        try:
            if focus_on:
                self.highlighted = self.get_option_index(utils.compress(focus_on))
            else:
                self.highlighted = self.get_option_index(
                    session.sessionLastHighlighted[cwd]
                )
        except OptionDoesNotExist:
            self.highlighted = 0
            session.sessionLastHighlighted[cwd] = (
                self.app.query_one("#file_list").options[0].value
            )
        except KeyError:
            self.highlighted = 0
            session.sessionLastHighlighted[cwd] = (
                self.app.query_one("#file_list").options[0].value
            )
        self.app.tabWidget.active_tab.label = (
            path.basename(cwd) if path.basename(cwd) != "" else cwd.strip("/")
        )
        self.app.tabWidget.active_tab.directory = cwd
        self.app.tabWidget.parent.on_resize()
        self.input.clear()

    def dummy_update_file_list(
        self,
        cwd: str,
    ) -> None:
        """Update the file list with the current directory contents.

        Args:
            cwd (str): The current working directory.
        """
        self.enter_into = cwd
        self.clear_options()
        # Separate folders and files
        folders, files = utils.get_cwd_object(cwd)
        if folders == [PermissionError] or files == [PermissionError]:
            self.add_option(
                Selection(
                    " Permission Error: Unable to access this directory.",
                    id="",
                    value="",
                    disabled=True,
                )
            )
            return
        elif folders == [] and files == []:
            self.add_option(Selection(" --no-files--", value="", id="", disabled=True))
            return
        file_list_options = folders + files
        for item in file_list_options:
            self.add_option(
                FileListSelectionWidget(
                    icon=item["icon"],
                    label=item["name"],
                    dir_entry=item["dir_entry"],
                    value=utils.compress(item["name"]),
                    id=utils.compress(item["name"]),
                )
            )
        # somehow prevents more debouncing, ill take it
        self.refresh(repaint=True, layout=True)

    async def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        # Get the filename from the option id
        event.prevent_default()
        cwd = utils.normalise(getcwd())
        # Get the selected option
        selected_option = self.get_option_at_index(self.highlighted)
        file_name = utils.decompress(selected_option.value)
        if self.dummy:
            # kinda complicated
            if path.isdir(path.join(self.enter_into, file_name)):
                try:
                    chdir(path.join(self.enter_into, file_name))
                except PermissionError:
                    # cannot do anything about that
                    return
                self.app.query_one("#file_list").update_file_list()
                self.app.query_one("#file_list").focus()
        elif not self.select_mode_enabled:
            # Check if it's a folder or a file
            if path.isdir(path.join(cwd, file_name)):
                # If it's a folder, navigate into it
                try:
                    chdir(path.join(cwd, file_name))
                except PermissionError:
                    # Cannot access, so don't change anything I guess
                    return
                self.app.query_one("#file_list").update_file_list()
            else:
                utils.open_file(path.join(cwd, file_name))
            if self.highlighted is None:
                self.highlighted = 0
            utils.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                True,
            )
        else:
            utils.set_scuffed_subtitle(
                self.parent, "SELECT", f"{len(self.selected)}/{len(self.options)}", True
            )

    # No clue why I'm using an OptionList method for SelectionList
    async def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if self.dummy:
            return
        elif event.option.value == "HTI":
            self.app.query_one(PreviewContainer).remove_children()
            return  # ignore folders that go to prev dir
        if self.select_mode_enabled and self.selected is not None:
            utils.set_scuffed_subtitle(
                self.parent,
                "SELECT",
                f"{len(self.selected)}/{len(self.options)}",
                True,
            )
        elif self.selected is not None:
            utils.set_scuffed_subtitle(
                self.parent,
                "NORMAL",
                f"{self.highlighted + 1}/{self.option_count}",
                True,
            )
        # Get the highlighted option
        highlighted_option = event.option
        self.app.tabWidget.active_tab.session.sessionLastHighlighted[
            utils.normalise(getcwd())
        ] = highlighted_option.value
        # Get the filename from the option id
        file_name = utils.decompress(highlighted_option.value)
        # total files as footer
        if self.highlighted is None:
            self.highlighted = 0
        # preview
        self.app.query_one(PreviewContainer).show_preview(
            utils.normalise(path.join(getcwd(), file_name))
        )
        self.app.query_one("MetadataContainer").update_metadata(event.option.dir_entry)

    def _update_lines(self) -> None:
        """Update internal structures when new lines are added."""
        if not self.scrollable_content_region:
            return

        line_cache = self._line_cache
        line_cache.clear()
        padding = self.get_component_styles("option-list--option").padding
        width = self.scrollable_content_region.width - self._get_left_gutter_width()
        for index, option in enumerate(self.options):
            if not option.disabled or option.id.endswith("header"):
                line_cache.index_to_line[index] = len(line_cache.lines)
                line_count = (
                    self._get_visual(option).get_height(
                        self.styles, width - padding.width
                    )
                    + option._divider
                )
                line_cache.heights[index] = line_count
                line_cache.lines.extend([
                    (index, line_no) for line_no in range(0, line_count)
                ])

        last_divider = self.options and self.options[-1]._divider
        virtual_size = Size(
            self.scrollable_content_region.width,
            len(line_cache.lines) - (1 if last_divider else 0),
        )
        if virtual_size != self.virtual_size:
            self.virtual_size = virtual_size
            self._scroll_update(virtual_size)

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
            # in future, if anything was changed, you just need to add the line below
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

        # in future, if anything was changed, you just need to fix the segments below
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

    async def toggle_mode(self) -> None:
        """Toggle the selection mode between select and normal."""
        self.select_mode_enabled = not self.select_mode_enabled
        highlighted = self.highlighted
        self.update_file_list(add_to_session=False)
        self.highlighted = highlighted

    async def get_selected_objects(self) -> list[str] | None:
        """Get the selected objects in the file list.
        Returns:
            list[str]: If there are objects at that given location.
            None: If there are no objects at that given location.
        """
        cwd = utils.normalise(getcwd())
        if self.get_option_at_index(self.highlighted).value == "HTI":
            return None
        if not self.select_mode_enabled:
            return [
                utils.normalise(
                    path.join(
                        cwd,
                        utils.decompress(
                            self.get_option_at_index(self.highlighted).value
                        ),
                    )
                )
            ]
        else:
            return [
                utils.normalise(path.join(cwd, utils.decompress(option)))
                for option in self.selected
            ]

    async def on_key(self, event: events.Key) -> None:
        """Handle key events for the file list."""
        if not self.dummy:
            match event.key:
                # toggle select mode
                case key if key in config["keybinds"]["toggle_visual"]:
                    await self.query_one("#file_list", FileList).toggle_mode()
                case key if key in config["keybinds"]["toggle_all"]:
                    if not self.select_mode_enabled:
                        await self.toggle_mode()
                    if len(self.selected) == len(self.options):
                        self.deselect_all()
                    else:
                        self.select_all()
                case key if (
                    self.select_mode_enabled and key in config["keybinds"]["select_up"]
                ):
                    """Select the current and previous file."""
                    if self.highlighted == 0:
                        self.select(self.get_option_at_index(0))
                    else:
                        self.select(self.get_option_at_index(self.highlighted))
                        self.action_cursor_up()
                        self.select(self.get_option_at_index(self.highlighted))
                    return
                case key if (
                    self.select_mode_enabled
                    and key in config["keybinds"]["select_down"]
                ):
                    """Select the current and next file."""
                    if self.highlighted == len(self.options) - 1:
                        self.select(self.get_option_at_index(self.option_count - 1))
                    else:
                        self.select(self.get_option_at_index(self.highlighted))
                        self.action_cursor_down()
                        self.select(self.get_option_at_index(self.highlighted))
                    return
                case key if (
                    self.select_mode_enabled
                    and key in config["keybinds"]["select_page_up"]
                ):
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
                case key if (
                    self.select_mode_enabled
                    and key in config["keybinds"]["select_page_down"]
                ):
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
                case key if (
                    self.select_mode_enabled
                    and key in config["keybinds"]["select_home"]
                ):
                    old = self.highlighted
                    self.action_first()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    for index in range(new, old + 1):
                        self.select(self.get_option_at_index(index))
                    return
                case key if (
                    self.select_mode_enabled and key in config["keybinds"]["select_end"]
                ):
                    old = self.highlighted
                    self.action_last()
                    new = self.highlighted
                    if old is None:
                        old = 0
                    for index in range(old, new + 1):
                        self.select(self.get_option_at_index(index))
                    return
                case key if (
                    config["plugins"]["editor"]["enabled"]
                    and key in config["plugins"]["editor"]["keybinds"]
                ):
                    if path.isdir(
                        path.join(
                            getcwd(),
                            utils.decompress(
                                self.get_option_at_index(self.highlighted).id
                            ),
                        )
                    ):
                        with self.app.suspend():
                            cmd(
                                f'{config["plugins"]["editor"]["folder_executable"]} "{path.join(getcwd(), utils.decompress(self.get_option_at_index(self.highlighted).id))}"'
                            )
                    else:
                        with self.app.suspend():
                            cmd(
                                f'{config["plugins"]["editor"]["file_executable"]} "{path.join(getcwd(), utils.decompress(self.get_option_at_index(self.highlighted).id))}"'
                            )
                # hit buttons with keybinds
                case key if (
                    not self.select_mode_enabled
                    and key in config["keybinds"]["hist_previous"]
                ):
                    if self.app.query_one("#back").disabled:
                        self.app.query_one("UpButton").on_button_pressed(Button.Pressed)
                    else:
                        self.app.query_one("BackButton").on_button_pressed(
                            Button.Pressed
                        )
                case key if (
                    not self.select_mode_enabled
                    and event.key in config["keybinds"]["hist_next"]
                    and not self.app.query_one("#forward").disabled
                ):
                    self.app.query_one("ForwardButton").on_button_pressed(
                        Button.Pressed
                    )
                case key if (
                    not self.select_mode_enabled
                    and event.key in config["keybinds"]["up_tree"]
                ):
                    self.app.query_one("UpButton").on_button_pressed(Button.Pressed)
                case key if key in config["keybinds"]["refresh"]:
                    self.app.query_one("RefreshButton").on_button_pressed(
                        Button.Pressed
                    )
                # Toggle pin on current directory
                case key if key in config["keybinds"]["toggle_pin"]:
                    utils.toggle_pin(path.basename(getcwd()), getcwd())
                    self.app.query_one(PinnedSidebar).reload_pins()
                case key if key in config["keybinds"]["copy"]:
                    await self.app.query_one("#copy").on_button_pressed(Button.Pressed)
                case key if key in config["keybinds"]["cut"]:
                    await self.app.query_one("#cut").on_button_pressed(Button.Pressed)
                case key if key in config["keybinds"]["paste"]:
                    await self.app.query_one("#paste").on_button_pressed(Button.Pressed)
                case key if key in config["keybinds"]["new"]:
                    self.app.query_one("#new").on_button_pressed(Button.Pressed)
                case key if key in config["keybinds"]["rename"]:
                    self.app.query_one("#rename").on_button_pressed(Button.Pressed)
                case key if key in config["keybinds"]["delete"]:
                    await self.app.query_one("#delete").on_button_pressed(
                        Button.Pressed
                    )
                # search
                case key if key in config["keybinds"]["focus_search"]:
                    self.input.focus()
