from humanize import naturalsize
from lzstring import LZString
from maps import get_icon_for_file, get_icon_for_folder, EXT_TO_LANG_MAP
from os import listdir, path, walk, startfile, getcwd, chdir, scandir
from pathlib import Path
import state
from textual import events
from textual.app import ComposeResult, App
from textual.containers import Container
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option
from textual_autocomplete import PathAutoComplete, TargetState, DropdownItem

log = state.log
lzstring = LZString()


class PathDropdownItem(DropdownItem):
    def __init__(self, completion: str, path: Path) -> None:
        super().__init__(completion)
        self.path = path


class PathAutoCompleteInput(PathAutoComplete):
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


def get_folder_size(folder_path: str) -> int:
    """Get the size of a folder in bytes.

    Args:
        folder_path (str): The path to the folder.

    Returns:
        int: The size of the folder in bytes.
    """
    total_size = 0
    for dirpath, dirnames, filenames in walk(folder_path):
        for filename in filenames:
            file_path = path.join(dirpath, filename)
            if path.isfile(file_path) and not path.islink(file_path):
                try:
                    total_size += path.getsize(file_path)
                except (FileNotFoundError, PermissionError, OSError):
                    pass
    return total_size


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
    folders, files = [], []
    for item in listdir(getcwd()):
        if path.isdir(path.join(cwd, item)):
            folders.append(
                {
                    "name": item,
                    "icon": f" {get_icon_for_folder(item)}",
                }
            )
            if sort_by == "size":
                folders[-1]["size"] = get_folder_size(path.join(cwd, item))
                folders[-1]["better-size"] = naturalsize(folders[-1]["size"])
        else:
            files.append(
                {
                    "name": item,
                    "icon": f" {get_icon_for_file(item)}",
                }
            )
            if sort_by == "size":
                files[-1]["size"] = path.getsize(path.join(cwd, item))
                files[-1]["better-size"] = naturalsize(files[-1]["size"])
    # Sort folders and files properly
    if sort_by == "name":
        folders.sort(
            key=lambda x: x["name"].lower(), reverse=(sort_order == "descending")
        )
        files.sort(
            key=lambda x: x["name"].lower(), reverse=(sort_order == "descending")
        )
    elif sort_by == "size":
        folders.sort(
            key=lambda x: get_folder_size(path.join(cwd, x["name"])),
            reverse=(sort_order == "descending"),
        )
        files.sort(
            key=lambda x: path.getsize(path.join(cwd, x["name"])),
            reverse=(sort_order == "descending"),
        )
    file_list_options = (
        files + folders if sort_order == "descending" else folders + files
    )
    for item in file_list_options:
        file_list.add_option(
            Option(
                f"{item['icon']} {item['name']} {LZString.compressToEncodedURIComponent(item['name'])}",
                id=LZString.compressToEncodedURIComponent(item["name"]),
            )
        )
    appInstance.query_one("#path_switcher").value = cwd.replace(path.sep, "/") + "/"
    # session handler
    if add_to_session:
        if state.sessionHistoryIndex != len(state.sessionDirectories) - 1:
            state.sessionDirectories = state.sessionDirectories[
                : state.sessionHistoryIndex + 1
            ]
        state.sessionDirectories.append(
            {
                "path": cwd,
                "highlighted": appInstance.query_one("#file_list").options[0].id,
            }
        )
        state.sessionHistoryIndex = len(state.sessionDirectories) - 1
        log(state.sessionDirectories)
        log(state.sessionHistoryIndex)
    else:
        log(state.sessionDirectories[state.sessionHistoryIndex])
        log(state.sessionHistoryIndex)
    file_list.highlighted = file_list.get_option_index(
        state.sessionDirectories[state.sessionHistoryIndex]["highlighted"]
    )
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


class FileList(OptionList):
    CSS_PATH = "style.tcss"

    def __init__(self, sort_by, sort_order, **kwargs):
        super().__init__(**kwargs)
        self.sort_by = sort_by
        self.sort_order = sort_order

    def compose(self) -> ComposeResult:
        yield Static()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        cwd = getcwd()
        # Get the selected option
        selected_option = event.option
        log(f"selected {selected_option}")
        # Get the file name from the option id
        file_name = lzstring.decompressFromEncodedURIComponent(selected_option.id)
        # Check if it's a folder or a file
        if path.isdir(path.join(cwd, file_name)):
            # If it's a folder, navigate into it
            chdir(path.join(cwd, file_name))
            update_file_list(self.app, "#file_list", self.sort_by, self.sort_order)
        else:
            startfile(path.join(cwd, file_name))

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        # Get the highlighted option
        highlighted_option = event.option
        state.sessionDirectories[state.sessionHistoryIndex]["highlighted"] = (
            event.option.id
        )
        log(f"highlighted {highlighted_option}")
        # Get the file name from the option id
        file_name = lzstring.decompressFromEncodedURIComponent(highlighted_option.id)
        # Check if it's a folder or a file
        file_path = path.join(getcwd(), file_name)
        if not path.isdir(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.app.query_one("#text_preview").text = f.read()
                    file_lang = EXT_TO_LANG_MAP.get(
                        path.splitext(file_name)[1], "markdown"
                    )
                    self.app.query_one("#text_preview").language = file_lang
                    log(file_lang)
            except UnicodeDecodeError:
                self.app.query_one("#text_preview").text = state.config["sidebar"][
                    "text"
                ]["binary"]
            except (FileNotFoundError, PermissionError, OSError):
                self.app.query_one("#text_preview").text = state.config["sidebar"][
                    "text"
                ]["error"]
        else:
            self.app.query_one("#text_preview").text = state.config["sidebar"]["text"][
                "folder"
            ]

    def on_mount(self) -> None:
        update_file_list(
            self.app,
            "#file_list",
            sort_by=self.sort_by,
            sort_order=self.sort_order,
        )
        self.focus()
        self.query_one("Static").remove()
