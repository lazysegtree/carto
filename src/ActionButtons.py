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
        self.tooltip = "Lists are in ascending order"
