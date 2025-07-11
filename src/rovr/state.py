"""Module that holds variable states + other functions"""

import os
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

from .maps import (
    ASCII_ICONS,
    ASCII_TOGGLE_BUTTON_ICONS,
    BORDER_BOTTOM,
    FILE_MAP,
    FILES_MAP,
    FOLDER_MAP,
    ICONS,
    TOGGLE_BUTTON_ICONS,
    VAR_TO_DIR,
)

lzstring = LZString()


# What is textual reactive?
sessionDirectories = []
sessionHistoryIndex = 0
sessionLastHighlighted = {}
config = {}
pins = {}


# okay so the reason why I have wrapper functions is
# I was messing around with different lzstring options
# and encodeduricomponent seems to best option. ive just
# left it here, in case we can switch to something like
# base 64 because encodeduricomponent can get quite long
# very fast, which isnt really the purpose of lzstring
def compress(text: str) -> str:
    return lzstring.compressToEncodedURIComponent(text)


def decompress(text: str) -> str:
    return lzstring.decompressFromEncodedURIComponent(text)


def get_icon_for_file(location: str) -> list:
    """Get the icon and color for a file based on its name or extension.

    Args:
        location (str): The name or path of the file.

    Returns:
        list: The icon and color for the file.
    """
    if not config["interface"]["nerd_font"]:
        return ASCII_ICONS["file"]["default"]
    file_name = path.basename(location).lower()

    # 1. Check for full filename match
    if file_name in FILES_MAP:
        icon_key = FILES_MAP[file_name]
        return ICONS["file"].get(icon_key, ICONS["file"]["default"])

    # 2. Check for extension match
    if "." in file_name:
        # This is for hidden files like `.gitignore`
        extension = "." + file_name.split(".")[-1]
        if extension in FILE_MAP:
            icon_key = FILE_MAP[extension]
            return ICONS["file"].get(icon_key, ICONS["file"]["default"])

    # 3. Default icon
    return ICONS["file"]["default"]


def get_icon_for_folder(location: str) -> list:
    """Get the icon and color for a folder based on its name.

    Args:
        location (str): The name or path of the folder.

    Returns:
        list: The icon and color for the folder.
    """
    folder_name = path.basename(location).lower()
    if not config["interface"]["nerd_font"]:
        return ASCII_ICONS["folder"].get(folder_name, ASCII_ICONS["folder"]["default"])
    # Check for special folder types
    if folder_name in FOLDER_MAP:
        icon_key = FOLDER_MAP[folder_name]
        return ICONS["folder"].get(icon_key, ICONS["folder"]["default"])
    else:
        return ICONS["folder"]["default"]


def get_icon(outer_key: str, inner_key: str) -> list:
    """
    Get an icon from double keys.
    Args:
        outer_key (str): The category name (general/folder/file)
        inner_key (str): The icon's name
    Returns:
        list[str,str]: The icon and color for the icon
    """
    if not config["interface"]["nerd_font"]:
        return ASCII_ICONS.get(outer_key, {"empty": None}).get(inner_key, " ")
    else:
        return ICONS[outer_key][inner_key]


def get_toggle_button_icon(key: str) -> str:
    if not config["interface"]["nerd_font"]:
        return ASCII_TOGGLE_BUTTON_ICONS[key]
    else:
        return TOGGLE_BUTTON_ICONS[key]


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


def deep_merge(d, u) -> dict:
    """
    Mini lodash merge
    Args:
        d (dict): old dictionary
        u (dict): new dictionary, to merge on top of d
    Returns:
        dict
    """
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_merge(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def load_config() -> None:
    """
    Load both the template config and the user config
    """

    global config

    if not path.exists(VAR_TO_DIR["CONFIG"]):
        os.makedirs(VAR_TO_DIR["CONFIG"])
    if not path.exists(path.join(VAR_TO_DIR["CONFIG"], "config.toml")):
        with open(path.join(VAR_TO_DIR["CONFIG"], "config.toml"), "w") as _:
            pass

    with open(path.join(path.dirname(__file__), "config/config.toml"), "r") as f:
        template_config = toml.loads(f.read())

    user_config_path = path.join(VAR_TO_DIR["CONFIG"], "config.toml")
    user_config = {}
    if path.exists(user_config_path):
        try:
            with open(user_config_path, "r") as f:
                user_config_content = f.read()
                if user_config_content:
                    user_config = toml.loads(user_config_content)
        except (IOError, toml.TomlDecodeError):
            pass
    # dont really have to consider the else part, because it's created further down
    config = deep_merge(template_config, user_config)


def load_pins() -> None:
    """
    Load the pinned files from a JSON file in the user's config directory.
    """
    global pins
    user_pins_file_path = path.join(VAR_TO_DIR["CONFIG"], "pins.json")

    # Ensure the user's config directory exists
    if not path.exists(VAR_TO_DIR["CONFIG"]):
        os.makedirs(VAR_TO_DIR["CONFIG"])
    if not path.exists(user_pins_file_path):
        pins = {
            "default": [
                {"name": "Home", "path": "$HOME"},
                {"name": "Downloads", "path": "$DOWNLOADS"},
                {"name": "Documents", "path": "$DOCUMENTS"},
                {"name": "Desktop", "path": "$DESKTOP"},
                {"name": "Pictures", "path": "$PICTURES"},
                {"name": "Videos", "path": "$VIDEOS"},
                {"name": "Music", "path": "$MUSIC"},
            ],
            "pins": [],
        }
        try:
            with open(user_pins_file_path, "w") as f:
                ujson.dump(pins, f, escape_forward_slashes=False, indent=2)
        except IOError:
            pass
        return

    try:
        with open(user_pins_file_path, "r") as f:
            loaded_data = ujson.load(f)
    except (IOError, ValueError):
        # Reset pins on corrupt or smth idk
        pins = {
            "default": [
                {"name": "Home", "path": "$HOME"},
                {"name": "Downloads", "path": "$DOWNLOADS"},
                {"name": "Documents", "path": "$DOCUMENTS"},
                {"name": "Desktop", "path": "$DESKTOP"},
                {"name": "Pictures", "path": "$PICTURES"},
                {"name": "Videos", "path": "$VIDEOS"},
                {"name": "Music", "path": "$MUSIC"},
            ],
            "pins": [],
        }
        return

    # If list died
    if "default" not in loaded_data or not isinstance(loaded_data["default"], list):
        loaded_data["default"] = [
            {"name": "Home", "path": "$HOME"},
            {"name": "Downloads", "path": "$DOWNLOADS"},
            {"name": "Documents", "path": "$DOCUMENTS"},
            {"name": "Desktop", "path": "$DESKTOP"},
            {"name": "Pictures", "path": "$PICTURES"},
            {"name": "Videos", "path": "$VIDEOS"},
            {"name": "Music", "path": "$MUSIC"},
        ]
    if "pins" not in loaded_data or not isinstance(loaded_data["pins"], list):
        loaded_data["pins"] = []

    for section_key in ["default", "pins"]:
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
        user_pins_file_path = path.join(VAR_TO_DIR["CONFIG"], "pins.json")
        with open(user_pins_file_path, "w") as f:
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
        user_pins_file_path = path.join(VAR_TO_DIR["CONFIG"], "pins.json")
        with open(user_pins_file_path, "w") as f:
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


# check config folder
if not path.exists(VAR_TO_DIR["CONFIG"]):
    os.makedirs(VAR_TO_DIR["CONFIG"])
# Textual doesnt seem to have a way to check whether the
# css file exists while it is in operation, but textual
# only craps itself when it can't find it as the app starts
# so no issues
if not path.exists(path.join(VAR_TO_DIR["CONFIG"], "style.tcss")):
    with open(path.join(VAR_TO_DIR["CONFIG"], "style.tcss"), "a") as _:
        pass


class FileEventHandler(FileSystemEventHandler):
    @staticmethod
    def on_modified(event):
        if event.is_directory:
            return
        src_path_basename = path.basename(event.src_path)
        if src_path_basename == "config.toml":
            load_config()
        elif src_path_basename == "pins.json":
            load_pins()


def watch_config_file() -> None:
    event_handler = FileEventHandler()
    observer = Observer()
    observer.schedule(
        event_handler, path=path.join(path.dirname(__file__), "config"), recursive=False
    )
    user_config_dir = VAR_TO_DIR["CONFIG"]
    if path.exists(user_config_dir):
        observer.schedule(event_handler, path=user_config_dir, recursive=False)
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
