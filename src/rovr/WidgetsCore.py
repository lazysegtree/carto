import asyncio
from os import DirEntry, chdir, getcwd, path
from os import system as cmd
from typing import ClassVar

import textual_image.widget as timg
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container
from textual.content import Content
from textual.strip import Strip
from textual.widgets import Button, OptionList, SelectionList, Static, TextArea
from textual.widgets.option_list import Option, OptionDoesNotExist
from textual.widgets.selection_list import Selection
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import utils
from .maps import EXT_TO_LANG_MAP, PIL_EXTENSIONS
from .utils import config


class PreviewContainer(Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_task = None
        self._current_content = None
        self._current_file_path = None
        self._is_image = False
        self._initial_height = self.size.height

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

    @work(exclusive=True)
    async def show_preview(self, file_path: str) -> None:
        """
        Debounce requests, then show preview
        Args:
            file_path(str): The file path
        """
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
        """
        Load the file preview
        Args:
            file_path(str): The file path
        """
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
                self._current_content = config["interface"]["preview_binary"]
            except (FileNotFoundError, PermissionError, OSError):
                self._current_content = config["interface"]["preview_error"]

        await self._render_preview()

    async def _render_preview(self) -> None:
        """Render function"""
        if self._current_file_path is None:
            return

        await self.remove_children()
        self.remove_class("bat", "full")

        if self._is_image:
            try:
                if config["settings"]["image_protocol"] in [
                    "Auto",
                    "TGP",
                    "Sixel",
                    "Halfcell",
                    "Unicode",
                ]:
                    await self.mount(
                        timg.__dict__[f"{config['settings']['image_protocol']}Image"](
                            self._current_file_path,
                            id="image_preview",
                            classes="inner_preview",
                        )
                    )
                else:
                    raise utils.ConfigError(
                        f"settings.image_protocol needs to be either `Auto`, `TGP`, `Sixel`, `Halfcell` or `Unicode`, but `{config['settings']['image_protocol']}` was received"
                    )
            # at times, when travelling too fast, this can happen
            except FileNotFoundError:
                await self.mount(
                    TextArea(
                        id="text_preview",
                        show_line_numbers=True,
                        soft_wrap=False,
                        read_only=True,
                        text=config["interface"]["preview_error"],
                        language="markdown",
                        compact=True,
                    )
                )
            self.border_title = "Image Preview"
            self.query_one("#image_preview").can_focus = True
            return

        if self._current_content is None:
            return

        is_special_content = self._current_content in (
            config["interface"]["preview_binary"],
            config["interface"]["preview_error"],
        )

        bat_output = None
        bat_failed = False
        error_message = ""

        preview_full = config["settings"]["preview_full"]
        if config["plugins"]["bat"]["enabled"] and not is_special_content:
            bat_executable = config["plugins"]["bat"]["executable"]

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

            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    bat_output = stdout.decode("utf-8", errors="ignore")
                else:
                    bat_failed = True
                    error_message = stderr.decode("utf-8", errors="ignore")
            except (FileNotFoundError, Exception) as e:
                bat_failed = True
                error_message = str(e)

        if bat_output is not None:
            scrollable_container = Static(
                Text.from_ansi(bat_output),
                id="text_preview",
                classes="inner_preview" + (" clip" if not preview_full else ""),
            )
            await self.mount(scrollable_container)
            scrollable_container.can_focus = True
            self.border_title = "File Preview (bat)"
            self.add_class("bar")
            if preview_full:
                self.add_class("full")
            return

        # Fallback! This guy doesn't have bat
        if bat_failed:
            self.app.notify(
                f"bat preview failed: {error_message}",
                severity="warning",
                timeout=5,
            )

        text_to_display = self._current_content

        if not preview_full:
            lines = text_to_display.splitlines()

            max_lines = self.size.height
            if max_lines > 0:
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
            else:
                lines = []

            # No clue why it's 5 though
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
        if not is_special_content:
            language = EXT_TO_LANG_MAP.get(
                path.splitext(self._current_file_path)[1], "markdown"
            )

        try:
            await self.mount(
                TextArea(
                    id="text_preview",
                    show_line_numbers=True,
                    soft_wrap=False,
                    read_only=True,
                    text=text_to_display,
                    language=language,
                    classes="inner_preview",
                )
            )
        # travelling fast also causes this
        except KeyError:
            await self.mount(
                TextArea(
                    id="text_preview",
                    show_line_numbers=True,
                    soft_wrap=False,
                    read_only=True,
                    text=config["interface"]["preview_error"],
                    language="markdown",
                    compact=True,
                )
            )
        self.border_title = "File Preview"

    async def show_folder(self, folder_path: str) -> None:
        """
        Show the folder in the preview container.
        Args:
            folder_path(str): The folder path
        """
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
                enter_into=utils.normalise(path.relpath(getcwd(), folder_path)),
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
        """Re-render the preview on resize if it's was rendered by batcat and height changed"""
        if (
            self._current_content is not None
            and "clip" in self.classes
            and event.size.height != self._initial_height
        ):
            await self._render_preview()

    @on(events.Key)
    async def on_key(self, event: events.Key) -> None:
        """Check for vim keybinds"""
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


class FolderNotFileError(Exception):
    """Raised when a folder is expected but a file is provided instead."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Static()

    @work(exclusive=True)
    async def reload_pins(self) -> None:
        """Reload pins shown"""
        # be extra sure
        available_pins = utils.load_pins()
        pins = available_pins["pins"]
        default = available_pins["default"]
        print(f"Reloading pins: {available_pins}")
        await self.remove_children()
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
                Option(
                    Content.from_markup(
                        f" [{icon[1]}]{icon[0]}[/{icon[1]}] $name",
                        name=default_folder["name"],
                    ),
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
                Option(
                    Content.from_markup(
                        f" [{icon[1]}]{icon[0]}[/{icon[1]}] $name",
                        name=pin["name"],
                    ),
                    id=f"{utils.compress(pin['path'])}-pinned",
                )
            )
        self.add_option(Option(" Drives", id="drives-header"))
        drives = utils.get_mounted_drives()
        for drive in drives:
            self.add_option(
                Option(
                    f" {utils.get_icon('folder', ':/drive:')[0]} {drive}",
                    id=f"{utils.compress(drive)}-drives",
                )
            )
        self.disable_option("pinned-header")
        self.disable_option("drives-header")

    async def on_mount(self) -> None:
        """Reload the pinned files from the config."""
        self.reload_pins()

    async def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle the selection of an option in the pinned sidebar."""
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


class FileListSelectionWidget(Selection):
    def __init__(self, dir_entry: DirEntry, *args, **kwargs):
        """
        Initialise the selection.

        Args:
            dir_entry (DirEntry): The nt.DirEntry class
            prompt (ContentText): The prompt for the selection.
            value (SelectionType): The value for the selection.
            initial_state (bool) = False: The initial selected state of the selection.
            id (str or None) = None: The optional ID for the selection.
            disabled (bool) = False: The initial enabled/disabled state. Enabled by default.
        """
        super().__init__(*args, **kwargs)
        self.dir_entry = dir_entry


class FileListEventHandler(FileSystemEventHandler):
    """Handles file system events and notifies the FileList widget."""

    def __init__(self, file_list_widget: "FileList"):
        super().__init__()
        self.file_list_widget = file_list_widget

    def on_any_event(self, event: FileSystemEvent) -> None:
        """
        Called when any event is detected.

        Args:
            event: The event object.
        """
        self.file_list_widget.app.call_from_thread(self.file_list_widget.queue_refresh)


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
        self.observer = None
        self._refresh_task = None

    def on_unmount(self) -> None:
        """Stop the directory watcher when the widget is unmounted."""
        self.stop_watching()

    def start_watching(self, path: str) -> None:
        """
        Start watching a directory for changes.

        Args:
            path (str): The path to the directory to watch.
        """
        self.stop_watching()
        self.observer = Observer()
        event_handler = FileListEventHandler(self)
        self.observer.schedule(event_handler, path, recursive=False)
        self.observer.start()

    def stop_watching(self) -> None:
        """Stop watching the current directory."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    @work(exclusive=True)
    async def queue_refresh(self) -> None:
        """Queue a refresh of the file list."""
        if self._refresh_task:
            self._refresh_task.stop()
        self._refresh_task = self.set_timer(0.1, self.update_file_list)

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
            if self.highlighted == clicked_option:
                self.action_select()
            else:
                self.highlighted = clicked_option

    @work(exclusive=True)
    async def update_file_list(
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
        cwd = utils.normalise(getcwd())
        self.clear_options()
        # get sessionstate
        try:
            session = self.app.tabWidget.active_tab.session
        except AttributeError:  # before mounting
            return
        print(self.app.tabWidget.active_tab)
        # Separate folders and files
        folders, files = utils.get_cwd_object(cwd, sort_order, sort_by)
        if folders == [PermissionError] or files == [PermissionError]:
            self.add_option(
                Selection(
                    Content("  Permission Error: Unable to access this directory."),
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
                    FileListSelectionWidget(
                        prompt=Content.from_markup(
                            f" [{item['icon'][1]}]{item['icon'][0]}[/{item['icon'][1]}] $name",
                            name=item["name"],
                        ),
                        value=utils.compress(item["name"]),
                        id=utils.compress(item["name"]),
                        dir_entry=item["dir_entry"],
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
        self.start_watching(cwd)
        self.app.query_one("Button#back").disabled = session.sessionHistoryIndex == 0
        print("sessionHistoryIndex", session.sessionHistoryIndex)
        print("sessionDirectories", session.sessionDirectories)
        self.app.query_one("Button#forward").disabled = (
            session.sessionHistoryIndex == len(session.sessionDirectories) - 1
        )
        try:
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
        self.app.tabWidget.active_tab.label = path.basename(cwd)
        self.app.tabWidget.active_tab.directory = cwd
        self.app.tabWidget.parent.on_resize()

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
            cwd = utils.normalise(getcwd())
        self.clear_options()
        # Separate folders and files
        folders, files = utils.get_cwd_object(cwd, sort_order, sort_by)
        if folders == [PermissionError] or files == [PermissionError]:
            self.add_option(
                Selection(
                    Content("  Permission Error: Unable to access this directory."),
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
                FileListSelectionWidget(
                    prompt=Content.from_markup(
                        f" [{item['icon'][1]}]{item['icon'][0]}[/{item['icon'][1]}] $name",
                        name=item["name"],
                    ),
                    value=utils.compress(item["name"]),
                    dir_entry=item["dir_entry"],
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
            cwd = utils.normalise(getcwd())
            # Get the selected option
            selected_option = self.get_option_at_index(
                self.highlighted
            )  # ? Trust me bro
            # Get the filename from the option id
            file_name = utils.decompress(selected_option.value)
            # Check if it's a folder or a file
            if path.isdir(path.join(cwd, file_name)):
                # If it's a folder, navigate into it
                try:
                    chdir(path.join(cwd, file_name))
                except PermissionError:
                    # Cannot access, so don't change anything I guess
                    return
                self.app.query_one("#file_list").update_file_list(
                    self.sort_by, self.sort_order
                )
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
        global utils
        if self.dummy:
            return
        elif event.option.value == "HTI":
            self.app.query_one(PreviewContainer).remove_children()
            return  # ignore folders that go to prev dir
        if self.select_mode_enabled:
            utils.set_scuffed_subtitle(
                self.parent,
                "SELECT",
                f"{len(self.selected)}/{len(self.options)}",
                True,
            )
        else:
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
        await self.on_mount(add_to_history=False)
        self.highlighted = highlighted

    async def get_selected_objects(self) -> list[str] | None:
        """Get the selected objects in the file list."""
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
            if event.key in config["keybinds"]["toggle_all"]:
                if not self.select_mode_enabled:
                    await self.toggle_mode()
                if len(self.selected) == len(self.options):
                    self.deselect_all()
                else:
                    self.select_all()
            elif (
                self.select_mode_enabled
                and event.key in config["keybinds"]["select_up"]
            ):
                """Select the current and previous file."""
                if self.highlighted == 0:
                    self.select(self.get_option_at_index(0))
                else:
                    self.select(self.get_option_at_index(self.highlighted))
                    self.action_cursor_up()
                    self.select(self.get_option_at_index(self.highlighted))
                return
            elif (
                self.select_mode_enabled
                and event.key in config["keybinds"]["select_down"]
            ):
                """Select the current and next file."""
                if self.highlighted == len(self.options) - 1:
                    self.select(self.get_option_at_index(self.option_count - 1))
                else:
                    self.select(self.get_option_at_index(self.highlighted))
                    self.action_cursor_down()
                    self.select(self.get_option_at_index(self.highlighted))
                return
            elif (
                self.select_mode_enabled
                and event.key in config["keybinds"]["select_page_up"]
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
            elif (
                self.select_mode_enabled
                and event.key in config["keybinds"]["select_page_down"]
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
            elif (
                self.select_mode_enabled
                and event.key in config["keybinds"]["select_home"]
            ):
                old = self.highlighted
                self.action_first()
                new = self.highlighted
                if old is None:
                    old = 0
                for index in range(new, old + 1):
                    self.select(self.get_option_at_index(index))
                return
            elif (
                self.select_mode_enabled
                and event.key in config["keybinds"]["select_end"]
            ):
                old = self.highlighted
                self.action_last()
                new = self.highlighted
                if old is None:
                    old = 0
                for index in range(old, new + 1):
                    self.select(self.get_option_at_index(index))
                return
            elif (
                config["plugins"]["editor"]["enabled"]
                and event.key in config["plugins"]["editor"]["keybinds"]
            ):
                print(
                    path.isdir(
                        path.join(
                            getcwd(),
                            utils.decompress(
                                self.get_option_at_index(self.highlighted).id
                            ),
                        )
                    )
                )
                if path.isdir(
                    path.join(
                        getcwd(),
                        utils.decompress(self.get_option_at_index(self.highlighted).id),
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
            elif (
                event.key in config["keybinds"]["hist_previous"]
                and not self.select_mode_enabled
            ):
                if self.app.query_one("#back").disabled:
                    self.app.query_one("UpButton").on_button_pressed(Button.Pressed)
                else:
                    self.app.query_one("BackButton").on_button_pressed(Button.Pressed)
            elif (
                event.key in config["keybinds"]["hist_next"]
                and not self.select_mode_enabled
                and not self.app.query_one("#forward").disabled
            ):
                self.app.query_one("ForwardButton").on_button_pressed(Button.Pressed)
            elif (
                event.key in config["keybinds"]["up_tree"]
                and not self.select_mode_enabled
            ):
                self.app.query_one("UpButton").on_button_pressed(Button.Pressed)
            elif event.key in config["keybinds"]["refresh"]:
                self.app.query_one("RefreshButton").on_button_pressed(Button.Pressed)
            # Toggle pin on current directory
            elif event.key in config["keybinds"]["toggle_pin"]:
                utils.toggle_pin(path.basename(getcwd()), getcwd())
                self.app.query_one(PinnedSidebar).reload_pins()
