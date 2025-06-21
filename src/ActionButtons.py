from textual import events, on, work
from textual.widgets import Button

import state
from maps import ICONS


class SortOrderButton(Button):
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
        self.app.notify(str(self.app.query_one("#file_list").has_focus))
        if (
            self.app.query_one("#file_list").has_focus
            and event.key in state.config["keybinds"]["cut"]
        ):
            self.action_press()


class PasteButton(Button):
    def __init__(self, *args, **kwargs):
        super().__init__(
            ICONS["general"]["paste"][0], classes="option", id="paste", *args, **kwargs
        )

    def on_mount(self):
        if state.config["interface"]["tooltips"]:
            self.tooltip = "Paste files from clipboard"
