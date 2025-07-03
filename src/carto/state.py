"""Module that holds variable states + other functions"""

import platform
from os import path
from threading import Thread
from time import sleep

import psutil
import toml
import ujson
from lzstring import LZString
from textual.widget import Widget
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .maps import BORDER_BOTTOM, VAR_TO_DIR

lzstring = LZString()


# what is textual reactive?
sessionDirectories = []
sessionHistoryIndex = 0
sessionLastHighlighted = {}
config = {}
pins = {}


def compress(text: str) -> str:
    return lzstring.compressToEncodedURIComponent(text)


def decompress(text: str) -> str:
    return lzstring.decompressFromEncodedURIComponent(text)


def get_nested_value(dictionary, keys_list):
    """
    Get a value from a nested dictionary using a list of keys.

    Args:
        dictionary (dict): The dictionary to traverse
        keys_list (list): List of keys to navigate the dictionary
        default: Value to return if the path doesn't exist (default: None)

    Returns:
        The value at the specified path or default if not found
    """
    current = dictionary

    try:
        for key in keys_list:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return None


def update_session_state(directories, index, lastHighlighted={}) -> None:
    """
    Update the session state with the given directories and index.

    Args:
        directories (list): List of directories in the session.
        index (int): Current index in the session history.
        lastHighlighted (str): The last highlighted file or directory.
    """
    global sessionDirectories
    global sessionHistoryIndex
    global sessionLastHighlighted
    sessionDirectories = directories
    sessionHistoryIndex = index
    sessionLastHighlighted = lastHighlighted


def load_config() -> None:
    """
    Load the configuration from a TOML file.

    Args:
        config_path (str): Path to the configuration file.
    """

    global config
    with open(path.join(path.dirname(__file__), "config/config.toml"), "r") as f:
        config = toml.loads(f.read())
    # update styles
    # get vars to replace


def load_pins() -> None:
    """
    Load the pinned files from a JSON file.
    """
    global pins
    pins_file_path = path.join(path.dirname(__file__), "config/pins.json")

    if not path.exists(pins_file_path):
        pins = {"default": [], "pins": []}
        try:
            with open(pins_file_path, "w") as f:
                ujson.dump(pins, f, escape_forward_slashes=False, indent=2)
        except IOError:
            pass
        return

    try:
        with open(pins_file_path, "r") as f:
            loaded_data = ujson.load(f)
    except (IOError, ValueError):
        pins = {"default": [], "pins": []}
        return

    for section_key in ["default", "pins"]:
        if section_key in loaded_data:
            for item in loaded_data[section_key]:
                if (
                    isinstance(item, dict)
                    and "path" in item
                    and isinstance(item["path"], str)
                ):
                    # Expand variables
                    for var, dir_path_val in VAR_TO_DIR.items():
                        item["path"] = item["path"].replace(f"${var}", dir_path_val)
                    # Normalize to forward slashes
                    item["path"] = item["path"].replace("\\", "/")
    pins = loaded_data


def add_pin(pin_name: str, pin_path: str) -> None:
    """
    Add a pin to the pins file.

    Args:
        pin_name (str): Name of the pin.
        pin_path (str): Path of the pin.
    """
    global pins

    pins_to_write = ujson.loads(ujson.dumps(pins))

    pin_path_normalized = pin_path.replace("\\", "/")
    pins_to_write.setdefault("pins", []).append(
        {
            "name": pin_name,
            "path": pin_path_normalized,
        }
    )

    sorted_vars = sorted(VAR_TO_DIR.items(), key=lambda x: len(x[1]), reverse=True)
    for section_key in ["default", "pins"]:
        if section_key in pins_to_write:
            for item in pins_to_write[section_key]:
                if (
                    isinstance(item, dict)
                    and "path" in item
                    and isinstance(item["path"], str)
                ):
                    for var, dir_path_val in sorted_vars:
                        item["path"] = item["path"].replace(dir_path_val, f"${var}")

    try:
        with open(path.join(path.dirname(__file__), "config/pins.json"), "w") as f:
            ujson.dump(pins_to_write, f, escape_forward_slashes=False, indent=2)
    except IOError:
        pass

    load_pins()


def remove_pin(pin_path: str) -> None:
    """
    Remove a pin from the pins file.

    Args:
        pin_path (str): Path of the pin to remove.
    """
    global pins

    pins_to_write = ujson.loads(ujson.dumps(pins))

    pin_path_normalized = pin_path.replace("\\", "/")
    if "pins" in pins_to_write:
        pins_to_write["pins"] = [
            pin
            for pin in pins_to_write["pins"]
            if not (isinstance(pin, dict) and pin.get("path") == pin_path_normalized)
        ]

    sorted_vars = sorted(VAR_TO_DIR.items(), key=lambda x: len(x[1]), reverse=True)
    for section_key in ["default", "pins"]:
        if section_key in pins_to_write:
            for item in pins_to_write[section_key]:
                if (
                    isinstance(item, dict)
                    and "path" in item
                    and isinstance(item["path"], str)
                ):
                    for var, dir_path_val in sorted_vars:
                        item["path"] = item["path"].replace(dir_path_val, f"${var}")

    try:
        with open(path.join(path.dirname(__file__), "config/pins.json"), "w") as f:
            ujson.dump(pins_to_write, f, escape_forward_slashes=False, indent=2)
    except IOError:
        pass

    load_pins()  # Reload


def toggle_pin(pin_name: str, pin_path: str) -> None:
    """
    Toggle a pin in the pins file. If it exists, remove it; if not, add it.

    Args:
        pin_name (str): Name of the pin.
        pin_path (str): Path of the pin.
    """
    pin_path_normalized = pin_path.replace("\\", "/")

    pin_exists = False
    if "pins" in pins:
        for pin_item in pins["pins"]:
            if (
                isinstance(pin_item, dict)
                and pin_item.get("path") == pin_path_normalized
            ):
                pin_exists = True
                break

    if pin_exists:
        remove_pin(pin_path_normalized)
    else:
        add_pin(pin_name, pin_path_normalized)


def get_mounted_drives() -> list:
    """
    Get a list of mounted drives on the system.

    Returns:
        list: List of mounted drives.
    """
    drives = []
    try:
        # get all partitions
        partitions = psutil.disk_partitions(all=False)

        if platform.system() == "Windows":
            # For Windows, return the drive letters
            drives = [
                p.mountpoint.replace("\\", "/")
                for p in partitions
                if p.device and ":" in p.device
            ]
        else:
            # For Unix-like systems, return the mount points
            drives = [
                p.mountpoint
                for p in partitions
                if p.fstype not in ("autofs", "devfs", "devtmpfs", "tmpfs")
            ]
    except Exception as e:
        print(f"Error getting mounted drives: {e}")
        print("Using fallback method")
        drives = [path.expanduser("~")]
    return drives


def set_scuffed_subtitle(element: Widget, mode: str, frac: str, hover: bool) -> None:
    """The most scuffed way to display a custom subtitle

    Args:
        element (Widget): The element containing style information.
        mode (str): The mode of the subtitle.
        frac (str): The fraction to display.
        hover (bool): Whether the widget is in hover state.
    """
    border_bottom = BORDER_BOTTOM.get(
        element.styles.border_bottom[0], BORDER_BOTTOM["blank"]
    )
    border_color = element.styles.border.bottom[1].hex
    element.border_subtitle = (
        f"{mode} [{border_color} on $background]{border_bottom}[/] {frac}"
    )


class FileEventHandler(FileSystemEventHandler):
    @staticmethod
    def on_modified(event):
        if event.is_directory:
            return
        src_path_basename = path.basename(event.src_path)
        if src_path_basename in ["config.toml", "template_style.tcss"]:
            load_config()
        elif src_path_basename == "pins.json":
            pass


def watch_config_file() -> None:
    event_handler = FileEventHandler()
    observer = Observer()
    observer.schedule(
        event_handler, path=path.join(path.dirname(__file__), "config"), recursive=False
    )
    observer.start()
    try:
        while True:
            sleep(1)
    except Exception:
        observer.stop()
    observer.join()


def start_watcher():
    Thread(
        target=watch_config_file,
        daemon=True,
    ).start()


if __name__ == "__main__":
    start_watcher()
