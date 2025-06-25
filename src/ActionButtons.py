from os import path

from textual import events
from textual.widgets import Button

import state
from Actions import create_new_item, remove_files, rename_object
from maps import ICONS
from ScreensCore import DeleteFiles, ModalInput


class SortOrderButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["up"][0],
            classes="option",
            id="sort_order",
            *args,
            **kwargs,
        )

    #  actions soon :tm:

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Lists are in ascending order"


class CopyButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["copy"][0], classes="option", id="copy", *args, **kwargs
        )

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Copy selected files"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Copy selected files to the clipboard"""
        selected_files = await self.app.query_one("#file_list").get_selected_objects()
        if selected_files:
            await self.app.query_one("#clipboard").copy_to_clipboard(selected_files)
        else:
            self.app.notify("No files selected to copy.")

    async def on_key(self, event: events.Key) -> None:
        if (
            self.app.query_one("#file_list").has_focus
            and event.key in state.config["keybinds"]["copy"]
        ):
            self.action_press()


class CutButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["cut"][0], classes="option", id="cut", *args, **kwargs
        )

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Cut selected files"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Cut selected files to the clipboard"""
        selected_files = await self.app.query_one("#file_list").get_selected_objects()
        if selected_files:
            await self.app.query_one("#clipboard").cut_to_clipboard(selected_files)
        else:
            self.app.notify("No files selected to cut.")

    async def on_key(self, event: events.Key) -> None:
        if (
            self.app.query_one("#file_list").has_focus
            and event.key in state.config["keybinds"]["cut"]
        ):
            self.action_press()


class PasteButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["paste"][0], classes="option", id="paste", *args, **kwargs
        )

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Paste files from clipboard"


class NewItemButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["new"][0], classes="option", id="new", *args, **kwargs
        )

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Create a new file or directory"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.push_screen(
            ModalInput(
                border_title="Create New Item",
                border_subtitle="End with a slash (/) to create a directory",
            ),
            callback=lambda response: create_new_item(self.app, response),
        )

    async def on_key(self, event: events.Key) -> None:
        if (
            self.app.query_one("#file_list").has_focus
            and event.key in state.config["keybinds"]["new"]
        ):
            self.action_press()


class RenameItemButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["rename"][0],
            classes="option",
            id="rename",
            *args,
            **kwargs,
        )

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Rename selected files"

    async def on_button_pressed(self, event: Button.Pressed):
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
            self.app.push_screen(
                ModalInput(
                    border_title=f"Rename {type_of_file}",
                    border_subtitle=f"Current name: {path.basename(selected_file)}",
                    initial_value=path.basename(selected_file),
                ),
                callback=lambda response: rename_object(
                    self.app, selected_file, response
                ),
            )

    async def on_key(self, event: events.Key) -> None:
        if (
            self.app.query_one("#file_list").has_focus
            and event.key in state.config["keybinds"]["rename"]
        ):
            self.action_press()


class DeleteButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["delete"][0],
            classes="option",
            id="delete",
            *args,
            **kwargs,
        )

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Delete selected files"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Delete selected files or directories"""
        file_list = self.app.query_one("#file_list")
        selected_files = await file_list.get_selected_objects()
        if selected_files:

            async def callback(response: str) -> None:
                """Callback to remove files after confirmation"""
                if response == "delete":
                    await remove_files(
                        self.app, selected_files, ignore_trash=True, compressed=False
                    )
                elif response == "trash":
                    await remove_files(
                        self.app, selected_files, ignore_trash=False, compressed=False
                    )
                else:
                    self.app.notify("File deletion cancelled.", title="Delete Files")

            self.app.push_screen(
                DeleteFiles(
                    message=f"Are you sure you want to delete {len(selected_files)} files?",
                ),
                callback=callback,
            )
        else:
            self.app.notify(
                "No files selected to delete.", title="Delete Files", severity="warning"
            )

    async def on_key(self, event: events.Key):
        if (
            self.app.query_one("#file_list").has_focus
            and event.key in state.config["keybinds"]["delete"]
        ):
            self.action_press()
