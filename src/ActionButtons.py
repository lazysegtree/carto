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
            await self.app.query_one("#clipboard").add_to_clipboard(selected_files)
        else:
            self.app.notify("No files selected to copy.")

    async def on_key(self, event: events.Key) -> None:
        if (
            self.app.highlighted.id == "file_list"
            and event.key in state.config["keybinds"]["copy"]
        ):
            self.action_press()
