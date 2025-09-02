from os import getcwd, path

from textual import on
from textual.widgets import Button, Tabs
from textual.widgets._tabs import Tab

from rovr.classes import SessionManager
from rovr.functions.path import normalise


class TablineTab(Tab):
    def __init__(
        self, directory: str | bytes = "", label: str = "", *args, **kwargs
    ) -> None:
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
            label = str(
                path.basename(directory)
                if path.basename(directory) != ""
                else directory.strip("/")
            )
        super().__init__(label=label, *args, **kwargs)
        self.directory = directory
        self.session = SessionManager()


class Tabline(Tabs):
    async def add_tab(
        self, directory: str = "", label: str = "", *args, **kwargs
    ) -> None:
        """Add a new tab to the end of the tab list.

        Args:
            directory (str): The directory to set the tab as.
            label (ContentText): The label to use in the tab.
            before (Tab | str | None): Optional tab or tab ID to add the tab before.
            after (Tab | str | None): Optional tab or tab ID to add the tab after.
        Note:
            Only one of `before` or `after` can be provided. If both are
            provided a `Tabs.TabError` will be raised.
        """
        """
        Returns:
            An optionally awaitable object that waits for the tab to be mounted and
                internal state to be fully updated to reflect the new tab.

        Raises:
            Tabs.TabError: If there is a problem with the addition request.
        """

        tab = TablineTab(directory=directory, label=label)
        super().add_tab(tab, *args, **kwargs)
        self._activate_tab(tab)
        # redo max-width
        self.parent.on_resize()

    async def remove_tab(self, tab_or_id: Tab | str | None) -> None:
        """Remove a tab.

        Args:
            tab_or_id: The Tab to remove or its id.
        """
        """
        Returns:
            An optionally awaitable object that waits for the tab to be mounted and
                internal state to be fully updated to reflect the new tab.

        Raises:
            Tabs.TabError: If there is a problem with the addition request.
        """
        super().remove_tab(tab_or_id=tab_or_id)
        self.parent.on_resize()

    @on(Tab.Clicked)
    @on(Tabs.TabActivated)
    async def check_tab_click(self, event: TablineTab.Clicked) -> None:
        assert isinstance(event.tab, TablineTab)
        self.app.cd(event.tab.directory, add_to_history=False)


class NewTabButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(label="+", variant="primary", compact=True, *args, **kwargs)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        await self.parent.parent.query_one(Tabline).add_tab(getcwd())
