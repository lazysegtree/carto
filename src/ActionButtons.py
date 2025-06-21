from textual import events
from textual.widgets import Button

import state
from maps import ICONS
from Actions import create_new_item
from ScreensCore import ModalInput


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
        self.push_screen(
            ModalInput(
                border_title="Create New Item",
                border_subtitle="End with a slash (/) to create a directory",
            ),
            callback=lambda response: create_new_item(self, response),
        )

    async def on_key(self, event: events.Key) -> None:
        if (
            self.app.query_one("#file_list").has_focus
            and event.key in state.config["keybinds"]["new"]
        ):
            self.action_press()
