from textual import events
from textual.widgets import Input, OptionList


def query_fuzzy(searchfor: str, findin: str) -> bool:
    searchfor, findin = searchfor.lower(), findin.lower()
    for char in searchfor:
        try:
            findin.split(char)[1]
            findin = char.join(findin.split(char)[1:])
        except IndexError:
            return False
    return True


class SearchInput(Input):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            *args, password=False, compact=True, select_on_focus=False, **kwargs
        )

    def on_mount(self) -> None:
        self.items_list: OptionList = self.parent.query_one(OptionList)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.value == "":
            for option in self.items_list.options:
                if not option.id.endswith("header"):
                    option.disabled = False
        for option in self.items_list.options:
            if option.id.endswith("header"):
                option.disabled = True
                continue
            try:
                option.disabled = not query_fuzzy(event.value, option.label)
            except IndexError:
                # Special section dividers, like Pinned Sidebar's dividers
                option.disabled = True
        self.items_list.refresh()
        if (
            self.items_list.highlighted is None
            or self.items_list.get_option_at_index(self.items_list.highlighted).disabled
        ):
            self.items_list.action_cursor_down()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.items_list.focus()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.items_list.focus()
            event.stop()
