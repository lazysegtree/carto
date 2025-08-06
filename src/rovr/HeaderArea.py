from os import chdir, getcwd, path

from textual import events, on, work
from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.containers import HorizontalGroup
from textual.css.query import NoMatches
from textual.widgets import Button, Static, Tabs
from textual.widgets._header import HeaderClock
from textual.widgets._tabs import Tab

from .utils import SessionManager, config, normalise


class TablineTab(Tab):
    def __init__(self, directory: str = "", label: str = "", *args, **kwargs):
        """Initialise a Tab.

        Args:
            directory (str): The directory to set the tab as.
            label (ContentText): The label to use in the tab.
            id (str | None): Optional ID for the widget.
            classes (str | None): Space separated list of class names.
            disabled (bool): Whether the tab is disabled or not.
        """
        if directory == "":
            directory = getcwd()
        directory = normalise(directory)
        if label == "":
            label = path.basename(directory)
        super().__init__(label=label, *args, **kwargs)
        self.directory = directory
        self.session = SessionManager()


class Tabline(Tabs):
    async def add_tab(
        self, directory: str = "", label: str = "", *args, **kwargs
    ) -> AwaitComplete:
        """Add a new tab to the end of the tab list.

        Args:
            directory (str): The directory to set the tab as.
            label (ContentText): The label to use in the tab.
            before (Tab | str | None): Optional tab or tab ID to add the tab before.
            after (Tab | str | None): Optional tab or tab ID to add the tab after.

        Returns:
            An optionally awaitable object that waits for the tab to be mounted and
                internal state to be fully updated to reflect the new tab.

        Raises:
            Tabs.TabError: If there is a problem with the addition request.

        Note:
            Only one of `before` or `after` can be provided. If both are
            provided a `Tabs.TabError` will be raised.
        """
        tab = TablineTab(directory=directory, label=label)
        super().add_tab(tab, *args, **kwargs)
        self._activate_tab(tab)
        # redo max-width
        self.parent.on_resize()

    @on(Tab.Clicked)
    @on(Tabs.TabActivated)
    async def check_tab_click(self, event: TablineTab.Clicked | Tab.Clicked):
        if normalise(getcwd()) == event.tab.directory:
            return
        chdir(event.tab.directory)
        self.app.query_one("FileList").update_file_list(add_to_session=False)


class NewTabButton(Button):
    def __init__(self, *args, **kwargs):
        super().__init__(label="+", variant="primary", compact=True, *args, **kwargs)

    async def on_button_pressed(self, event: Button.Pressed):
        await self.parent.parent.query_one(Tabline).add_tab(getcwd())


class HeaderArea(HorizontalGroup):
    def compose(self) -> ComposeResult:
        if (
            config["interface"]["clock"]["enabled"]
            and config["interface"]["clock"]["align"] == "left"
        ):
            yield HeaderClock()
        yield Tabline(
            TablineTab(directory=getcwd()),
        )
        with HorizontalGroup(id="newTabRight"):
            yield NewTabButton()
            yield Static()
        if (
            config["interface"]["clock"]["enabled"]
            and config["interface"]["clock"]["align"] == "right"
        ):
            yield HeaderClock()

    @work(thread=True)
    def on_resize(self, event: events.Resize | None = None):
        try:
            tab_line = self.query_exactly_one(Tabline)
        except NoMatches:
            return  # havent mounted yet
        # this might be a bit concerning, so im gonna explain it a bit.
        # max width serves to ensure the tab container doesnt get too long
        # and push header clock to the right.
        # width serves to ensure the new tab button follows the tabline's
        # width, so that it always stays at the right
        tab_line.styles.max_width = (
            self.app.size.width
            - (10 if config["interface"]["clock"]["enabled"] else 0)
            - 5
        )
        tab_line_width = 0
        for tab in tab_line.query(TablineTab):
            tab_line_width += len(tab.label.__str__()) + 2
        tab_line.styles.width = tab_line_width
