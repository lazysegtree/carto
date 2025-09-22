from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalGroup, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from rovr.variables.constants import config

class Shortcuts(ModalScreen):
    def compose(self) -> ComposeResult:
        keybind_data = self.get_keybind_data()

        # Create separate options for keys and descriptions
        key_options = [Option(f" {keys} ") for keys, _ in keybind_data]
        description_options = [Option(f" {description} ") for _, description in keybind_data]

        with VerticalGroup(id="shortcuts_group"):
            with Horizontal():
                yield OptionList(*key_options, id="shortcuts_keys")
                yield OptionList(*description_options, id="shortcuts_descriptions")

    def on_mount(self) -> None:
        # Cache widget references for performance
        self.shortcuts_keys = self.query_one("#shortcuts_keys")
        self.shortcuts_descriptions = self.query_one("#shortcuts_descriptions")

        self.shortcuts_keys.border_title = "Keys"
        self.shortcuts_keys.can_focus = False

        self.shortcuts_descriptions.border_title = "Actions"
        self.shortcuts_descriptions.border_subtitle = "Press Esc or Q to close"
        self.shortcuts_descriptions.can_focus = True
        self.shortcuts_descriptions.focus()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Synchronize the keys list with the descriptions list."""
        if event.option_list.id == "shortcuts_descriptions":
            print(f"OptionHighlighted: desc={event.option_list.highlighted}, keys={self.shortcuts_keys.highlighted}")
            self.shortcuts_keys.highlighted = event.option_list.highlighted

    def on_mouse_scroll_down(self, event) -> None:
        """Handle mouse wheel scroll down - sync after scroll happens."""
        print(f"Mouse scroll down: {event}")
        print(f"Event attributes: {dir(event)}")
        self.call_after_refresh(self._sync_scroll_position)

    def on_mouse_scroll_up(self, event) -> None:
        """Handle mouse wheel scroll up - sync after scroll happens."""
        print(f"Mouse scroll up: {event}")
        self.call_after_refresh(self._sync_scroll_position)

    def _sync_scroll_position(self) -> None:
        """Sync scroll positions between lists after scroll event."""
        print(f"Syncing: desc_offset={self.shortcuts_descriptions.scroll_offset}, keys_offset={self.shortcuts_keys.scroll_offset}")
        self.shortcuts_keys.scroll_offset = self.shortcuts_descriptions.scroll_offset
    

    def on_option_list_option_selected(self, event) -> None:
        return
        """Synchronize selection between lists."""
        if event.option_list.id == "shortcuts_descriptions":
            self.shortcuts_keys.highlighted = event.option_list.highlighted
            self.shortcuts_keys.scroll_to(index=event.option_list.highlighted)

    def on_key(self, event: events.Key) -> None:
        """Handle key presses."""
        match event.key.lower():
            case "escape" | "q":
                event.stop()
                self.dismiss()

    def get_keybind_data(self) -> list[tuple[str, str]]:
        # Hardcoded descriptions based on BINDINGS from various files
        keybind_descriptions = {
            # Navigation - from core/file_list.py, core/pinned_sidebar.py
            "up": "Up",
            "down": "Down",
            "home": "First",
            "end": "Last",
            "page_up": "Page Up",
            "page_down": "Page Down",
            "up_tree": "Go up directory",
            "down_tree": "Enter/Select",
            "hist_previous": "History back",
            "hist_next": "History forward",

            # File operations - from core/preview_container.py
            "copy": "Copy",
            "cut": "Cut",
            "paste": "Paste",
            "delete": "Delete",
            "rename": "Rename",
            "new": "New",
            "zip": "Zip",
            "unzip": "Unzip",
            "copy_path": "Copy path",

            # Interface - app-level shortcuts
            "focus_file_list": "Focus file list",
            "focus_toggle_pinned_sidebar": "Focus sidebar",
            "focus_toggle_preview_sidebar": "Focus preview",
            "focus_toggle_path_switcher": "Focus path",
            "focus_search": "Search",
            "focus_toggle_processes": "Focus processes",
            "focus_toggle_clipboard": "Focus clipboard",
            "focus_toggle_metadata": "Focus metadata",
            "toggle_pinned_sidebar": "Toggle sidebar",
            "toggle_preview_sidebar": "Toggle preview",
            "toggle_footer": "Toggle footer",
            "toggle_pin": "Pin folder",
            "show_shortcuts": "Show shortcuts",

            # Selection - from core/preview_container.py
            "toggle_visual": "Visual mode",
            "toggle_all": "Select all",
            "select_up": "Select up",
            "select_down": "Select down",
            "select_page_up": "Select page up",
            "select_page_down": "Select page down",
            "select_home": "Select to top",
            "select_end": "Select to end",

            # Tabs - app-level shortcuts
            "tab_new": "New tab",
            "tab_close": "Close tab",
            "tab_next": "Next tab",
            "tab_previous": "Previous tab",

            # Preview - from core/preview_container.py
            "preview_scroll_left": "Scroll left",
            "preview_scroll_right": "Scroll right",
            "preview_select_left": "Select left",
            "preview_select_right": "Select right",
        }

        # Generate keybind data programmatically
        keybind_data = []
        for action, keys in config["keybinds"].items():
            if action in keybind_descriptions:
                formatted_keys = ", ".join(f"<{key}>" for key in keys)
                description = keybind_descriptions[action]
                keybind_data.append((formatted_keys, description))

        return keybind_data