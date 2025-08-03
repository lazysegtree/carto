from os import getcwd, makedirs, path
from shutil import move

from textual import work
from textual.content import Content
from textual.widgets import Button

from .ScreensCore import DeleteFiles, ModalInput, YesOrNo
from .utils import config, decompress, get_icon, normalise


class SortOrderButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            get_icon("general", "up")[0],
            classes="option",
            id="sort_order",
            *args,
            **kwargs,
        )

    #  actions soon :tm:

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Lists are in ascending order"


class CopyButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            get_icon("general", "copy")[0], classes="option", id="copy", *args, **kwargs
        )

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Copy selected files"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Copy selected files to the clipboard"""
        selected_files = await self.app.query_one("#file_list").get_selected_objects()
        if selected_files:
            await self.app.query_one("#clipboard").copy_to_clipboard(selected_files)
        else:
            self.app.notify("No files selected to copy.")


class CutButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            get_icon("general", "cut")[0], classes="option", id="cut", *args, **kwargs
        )

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Cut selected files"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Cut selected files to the clipboard"""
        selected_files = await self.app.query_one("#file_list").get_selected_objects()
        if selected_files:
            await self.app.query_one("#clipboard").cut_to_clipboard(selected_files)
        else:
            self.app.notify("No files selected to cut.")


class PasteButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            get_icon("general", "paste")[0],
            classes="option",
            id="paste",
            *args,
            **kwargs,
        )

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Paste files from clipboard"

    async def on_button_pressed(self, event: Button.Pressed):
        """Paste files from clipboard"""
        selected_items = self.app.query_one(
            "Clipboard"
        ).selected  # dont include highlighted
        if selected_items:
            # decompress items
            selected_items = [decompress(item) for item in selected_items]
            # split into two items, those ending with `-cut` and those ending with `-copy`
            to_copy, to_cut = (
                [item[:-5] for item in selected_items if item.endswith("-copy")],
                [item[:-4] for item in selected_items if item.endswith("-cut")],
            )

            async def callback(response: str) -> None:
                """Callback to paste files after confirmation"""
                if response:
                    self.app.query_one("ProcessContainer").paste_items(to_copy, to_cut)
                else:
                    self.app.notify(
                        "Paste operation cancelled", title="Paste Files", timeout=3
                    )

            self.app.push_screen(
                YesOrNo(
                    message="Are you sure you want to "
                    + (
                        f"copy {len(to_copy)} item{'s' if len(to_copy) != 1 else ''}{' and ' if len(to_cut) != 0 else ''}"
                        if len(to_copy) > 0
                        else ""
                    )
                    + (
                        f"cut {len(to_cut)} item{'s' if len(to_cut) != 1 else ''}"
                        if len(to_cut) > 0
                        else ""
                    )
                    + "?"
                ),
                callback=callback,
            )


class NewItemButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            get_icon("general", "new")[0], classes="option", id="new", *args, **kwargs
        )

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Create a new file or directory"

    @work
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        response: str = await self.app.push_screen(
            ModalInput(
                border_title="Create New Item",
                border_subtitle="End with a slash (/) to create a directory",
            ),
            wait_for_dismiss=True,
        )
        if response == "":
            return
        location = normalise(path.join(getcwd(), response)) + (
            "/" if response.endswith("/") or response.endswith("\\") else ""
        )
        if path.exists(location):
            self.app.notify(message=f"Location '{response}' already exists.")
        elif location.endswith("/"):
            # recursive directory creation
            try:
                makedirs(location)
            except Exception as e:
                self.app.notify(
                    message=Content(f"Error creating directory '{response}': {e}"),
                    severity="error",
                )
        elif len(location.split("/")) > 1:
            # recursive directory until file creation
            location_parts = location.split("/")
            dir_path = "/".join(location_parts[:-1])
            try:
                makedirs(dir_path)
                with open(location, "w") as f:
                    f.write("")  # Create an empty file
            except FileExistsError:
                with open(location, "w") as f:
                    f.write("")
            except Exception as e:
                self.app.notify(
                    message=Content(f"Error creating file '{location}': {e}"),
                    severity="error",
                )
        else:
            # normal file creation I hope
            try:
                with open(location, "w") as f:
                    f.write("")  # Create an empty file
            except Exception as e:
                self.app.notify(
                    message=Content(f"Error creating file '{location}': {e}"),
                    severity="error",
                )
        self.app.query_one("#refresh").action_press()
        self.app.query_one("#file_list").focus()


class RenameItemButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            get_icon("general", "rename")[0],
            classes="option",
            id="rename",
            *args,
            **kwargs,
        )

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Rename selected files"

    @work
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        selected_files = await self.app.query_one("#file_list").get_selected_objects()
        if selected_files is None or len(selected_files) != 1:
            self.app.notify(
                "Please select exactly one file to rename.",
                title="Rename File",
                severity="warning",
            )
        else:
            selected_file = selected_files[0]
            type_of_file = "Folder" if path.isdir(selected_file) else "File"
            response: str = await self.app.push_screen(
                ModalInput(
                    border_title=f"Rename {type_of_file}",
                    border_subtitle=f"Current name: {path.basename(selected_file)}",
                    initial_value=path.basename(selected_file),
                ),
                wait_for_dismiss=True,
            )
            old_name = normalise(path.realpath(path.join(getcwd(), selected_file)))
            new_name = normalise(path.realpath(path.join(getcwd(), response)))
            if not path.exists(old_name):
                self.app.notify(message=f"'{selected_file}' no longer exists.")
                return
            if path.exists(new_name):
                self.app.notify(message=f"'{response}' already exists.")
                return
            try:
                move(old_name, new_name)
            except Exception as e:
                self.app.notify(
                    message=Content(
                        f"Error renaming '{selected_file}' to '{response}': {e}"
                    )
                )
        self.app.query_one("#refresh").action_press()
        self.app.query_one("#file_list").focus()


class DeleteButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            get_icon("general", "delete")[0],
            classes="option",
            id="delete",
            *args,
            **kwargs,
        )

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Delete selected files"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Delete selected files or directories"""
        file_list = self.app.query_one("#file_list")
        selected_files = await file_list.get_selected_objects()
        if selected_files:

            async def callback(response: str) -> None:
                """Callback to remove files after confirmation"""
                if response == "delete":
                    self.app.query_one("ProcessContainer").delete_files(
                        selected_files, compressed=False, ignore_trash=True
                    )
                elif response == "trash":
                    self.app.query_one("ProcessContainer").delete_files(
                        selected_files,
                        compressed=False,
                        ignore_trash=False,
                    )
                else:
                    self.app.notify(
                        "File deletion cancelled.", title="Delete Files", timeout=3
                    )

            self.app.push_screen(
                DeleteFiles(
                    message=f"Are you sure you want to delete {len(selected_files)} file{'s' if len(selected_files) != 1 else ''}?",
                ),
                callback=callback,
            )
        else:
            self.app.notify(
                "No files selected to delete.",
                title="Delete Files",
                severity="warning",
            )
