from textual.widgets import Button

from rovr.functions.icons import get_icon
from rovr.variables.constants import config


class PathCopyButton(Button):
    ALLOW_MAXIMIZE = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            get_icon("general", "link")[0],
            classes="option",
            id="copy_path",
            *args,
            **kwargs,
        )

    def on_mount(self) -> None:
        if config["interface"]["tooltips"]:
            self.tooltip = "Copy path of item to the clipboard"

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Copy selected files to the clipboard"""
        if self.disabled:
            return
        selected_files = await self.app.query_one("#file_list").get_selected_objects()
        if len(selected_files) == 1:
            self.app.copy_to_clipboard(selected_files[0])
            self.notify("Copied!", title="Copy Path", severity="information")
        elif len(selected_files) > 1:
            self.notify(
                "Exactly one must be selected.",
                title="Copy Path",
                severity="information",
            )
        else:
            self.notify(
                "No items were selected.", title="Copy Path", severity="information"
            )
