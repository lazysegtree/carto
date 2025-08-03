import os
import platform
import stat
import subprocess
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
class SessionManager:
    """Manages session-related variables.

    Attributes:
        sessionDirectories (list[dict]): A list of dictionaries that contain a directory's name within.
            The closer it is to index 0, the older it is.
        sessionHistoryIndex (int): The index of the session in the sessionDirectories.
            This can be a number between 0 and the length of the list - 1, inclusive.
        sessionLastHighlighted (dict[str, int]): A dictionary mapping directory paths to the index of the
            last highlighted item. If a directory is not in the dictionary, the default is 0.
    """

    def __init__(self):
        self.sessionDirectories = []
        self.sessionHistoryIndex = 0
        self.sessionLastHighlighted = {}


class ConfigError(Exception):
    """Exception raised for config related errors.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


state = SessionManager()

config = {}
pins = {}


def normalise(location: str) -> str:
    """
    "Normalise" the path
    Args:
        location (str): The location to the item
    Returns:
        str: A normalised path
    """
    # path.normalise fixes the relative references
    # replace \\ with / on windows
    # by any chance if somehow a \\\\ was to enter, fix that
    return path.normpath(location).replace("\\", "/").replace("//", "/")


# Okay so the reason why I have wrapper functions is
# I was messing around with different LZString options
# and Encoded URI Component seems to best option. I've just
# left it here, in case we can switch to something like
# base 64 because Encoded URI Component can get quite long
# very fast, which isn't really the purpose of LZString
def compress(text: str) -> str:
    return lzstring.compressToEncodedURIComponent(text)


def decompress(text: str) -> str:
    return lzstring.decompressFromEncodedURIComponent(text)


def open_file(filepath: str) -> None:
    """Cross-platform function to open files with their default application.

    Args:
        filepath (str): Path to the file to open
    """
    system = platform.system().lower()

    try:
        match system:
            case "windows":
                os.startfile(filepath)
            case "darwin":  # macOS
                subprocess.run(["open", filepath], check=True)
            case _:  # Linux and other Unix-like
                subprocess.run(["xdg-open", filepath], check=True)
    except Exception as e:
        print(f"Error opening file: {e}")


def get_cwd_object(cwd: str, sort_order: str, sort_by: str) -> (list[dict], list[dict]):
    """
    Get the objects (files and folders) in a provided directory
    Args:
        cwd(str): The working directory to check
        sort_order(str): The sort order (ascending or descending)
        sort_by(str): How to sort it (currently unused)
    Returns:
        folders(list[dict]): A list of dictionaries, containing "name" as the item's name and "icon" as the respective icon
        files(list[dict]): A list of dictionaries, containing "name" as the item's name and "icon" as the respective icon
    """
    folders, files = [], []
    try:
        listed_dir = os.scandir(cwd)
    except (PermissionError, FileNotFoundError, OSError):
        print(f"PermissionError: Unable to access {cwd}")
        return [PermissionError], [PermissionError]
    for item in listed_dir:
        if item.is_dir():
            folders.append({
                "name": f"{item.name}",
                "icon": get_icon_for_folder(item.name),
                "dir_entry": item,
            })
        else:
            files.append({
                "name": item.name,
                "icon": get_icon_for_file(item.name),
                "dir_entry": item,
            })
    # Sort folders and files properly
    folders.sort(key=lambda x: x["name"].lower(), reverse=(sort_order == "descending"))
    files.sort(key=lambda x: x["name"].lower(), reverse=(sort_order == "descending"))
    print(f"Found {len(folders)} folders and {len(files)} files in {cwd}")
    return folders, files


def file_is_type(file_path: str) -> str:
    """
    Get a given path's type
    Args:
        file_path(str): The file path to check
    Returns:
        str: The string that says what type it is (unknown, symlink, directory, junction or file)
    """
    try:
        file_stat = os.lstat(file_path)
    except (OSError, FileNotFoundError):
        return "unknown"
    mode = file_stat.st_mode
    if stat.S_ISLNK(mode):
        return "symlink"
    elif stat.S_ISDIR(mode):
        return "directory"
    elif (
        platform.system() == "Windows"
        and hasattr(file_stat, "st_file_attributes")
        and file_stat.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        return "junction"
    else:
        return "file"


def get_recursive_files(object_path: str) -> list[str]:
    """
    Get the files available at a directory recursively, regardless of whether it is a directory or not
    Args:
        object_path (str): The object's path
    Returns:
        list: A list of dictionaries, with a "path" key and "relative_loc" key
    """
    if path.isfile(path.realpath(object_path)) or path.islink(
        path.realpath(object_path)
    ):
        return [
            {
                "path": normalise(object_path),
                "relative_loc": path.basename(object_path),
            }
        ]
    else:
        files = []
        for folder, _, files_in_folder in os.walk(object_path):
            for file in files_in_folder:
                full_path = normalise(path.join(folder, file))  # normalise the path
                if (
                    normalise(path.realpath(full_path)) != full_path
                ):  # ie we passed over a symlink
                    pass  # will hopefully be taken by shutil.rmtree
                else:
                    files.append({
                        "path": full_path,
                        "relative_loc": normalise(
                            path.relpath(full_path, object_path + "/..")
                        ),
                    })
        return files


def get_icon_for_file(location: str) -> list:
    """
    Get the icon and color for a file based on its name or extension.

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


def update_session_utils(directories, index, lastHighlighted={}) -> None:
    """
    Update the session utils with the given directories and index.

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
        dict: Merged dictionary
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
        with open(path.join(VAR_TO_DIR["CONFIG"], "config.toml"), "w") as file:
            file.write(
                "#:schema  https://raw.githubusercontent.com/NSPC911/rovr/refs/heads/master/src/rovr/config/schema.json"
            )

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
    # Don't really have to consider the else part, because it's created further down
    config = deep_merge(template_config, user_config)


load_config()


def load_pins() -> dict:
    """
    Load the pinned files from a JSON file in the user's config directory.
    Returns:
        dict: A dictionary with the default values, and the custom added pins.
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

    try:
        with open(user_pins_file_path, "r") as f:
            pins = ujson.load(f)
    except (IOError, ValueError):
        # Reset pins on corrupt or something else happened
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

    # If list died
    if "default" not in pins or not isinstance(pins["default"], list):
        pins["default"] = [
            {"name": "Home", "path": "$HOME"},
            {"name": "Downloads", "path": "$DOWNLOADS"},
            {"name": "Documents", "path": "$DOCUMENTS"},
            {"name": "Desktop", "path": "$DESKTOP"},
            {"name": "Pictures", "path": "$PICTURES"},
            {"name": "Videos", "path": "$VIDEOS"},
            {"name": "Music", "path": "$MUSIC"},
        ]
    if "pins" not in pins or not isinstance(pins["pins"], list):
        pins["pins"] = []

    for section_key in ["default", "pins"]:
        for item in pins[section_key]:
            if (
                isinstance(item, dict)
                and "path" in item
                and isinstance(item["path"], str)
            ):
                # Expand variables
                for var, dir_path_val in VAR_TO_DIR.items():
                    item["path"] = item["path"].replace(f"${var}", dir_path_val)
                # Normalize to forward slashes
                item["path"] = normalise(item["path"])
    return pins


def add_pin(pin_name: str, pin_path: str) -> None:
    """
    Add a pin to the pins file.

    Args:
        pin_name (str): Name of the pin.
        pin_path (str): Path of the pin.
    """
    global pins

    pins_to_write = ujson.loads(ujson.dumps(pins))

    pin_path_normalized = normalise(pin_path)
    pins_to_write.setdefault("pins", []).append({
        "name": pin_name,
        "path": pin_path_normalized,
    })

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

    pin_path_normalized = normalise(pin_path)
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
    pin_path_normalized = normalise(pin_path)

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
                normalise(p.mountpoint)
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
        hover (bool): Whether the widget is in hover utils.
    """
    border_bottom = BORDER_BOTTOM.get(
        element.styles.border_bottom[0], BORDER_BOTTOM["blank"]
    )
    element.border_subtitle = f"{mode} [r]{border_bottom}[/] {frac}"


# check config folder
if not path.exists(VAR_TO_DIR["CONFIG"]):
    os.makedirs(VAR_TO_DIR["CONFIG"])
# Textual doesn't seem to have a way to check whether the
# CSS file exists while it is in operation, but textual
# only craps itself when it can't find it as the app starts
# so no issues
if not path.exists(path.join(VAR_TO_DIR["CONFIG"], "style.tcss")):
    with open(path.join(VAR_TO_DIR["CONFIG"], "style.tcss"), "a") as _:
        pass


# watchers
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
