from os import chdir, getcwd, path

from textual.widgets import Button

from rovr.utils import get_icon


class BackButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(get_icon("general", "left")[0], id="back", *args, **kwargs)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Go back in the sesison's history"""
        state = self.app.tabWidget.active_tab.session
        state.sessionHistoryIndex -= 1
        # ! reminder to add a check for path!
        chdir(state.sessionDirectories[state.sessionHistoryIndex]["path"])
        self.app.query_one("#file_list").update_file_list(add_to_session=False)


class ForwardButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(get_icon("general", "right")[0], id="forward", *args, **kwargs)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Go forward in the session's history"""
        state = self.app.tabWidget.active_tab.session
        state.sessionHistoryIndex += 1
        # ! reminder to add a check for path!
        chdir(state.sessionDirectories[state.sessionHistoryIndex]["path"])
        self.app.query_one("#file_list").update_file_list(add_to_session=False)


class UpButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(get_icon("general", "up")[0], id="up", *args, **kwargs)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Go up the current location's directory"""
        parent = getcwd().split(path.sep)[-1]
        chdir(path.sep.join(getcwd().split(path.sep)[:-1]) + path.sep)
        self.app.query_one("#file_list").update_file_list(focus_on=parent)


class RefreshButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            get_icon("general", "refresh")[0], id="refresh", *args, **kwargs
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reload the file list"""
        self.app.query_one("#file_list").update_file_list(add_to_session=False)
