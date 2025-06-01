from os import path, remove, makedirs
import shutil
import state
from textual.app import App

try:
    import send2trash

    SEND2TRASH_AVAILABLE = True
except ImportError:
    SEND2TRASH_AVAILABLE = False

state.load_config()


async def remove_files(
    appInstance: App,
    files: list[str],
    compressed: bool = True,
    ignore_trash: bool = False,
) -> None:
    """Remove files from the filesystem.

    Args:
        files (list[str]): List of file paths to remove.
        compressed (bool): Whether the file paths are compressed. Defaults to True.
    """
    for file in files:
        if compressed:
            file = state.decompress(file)
        try:
            if path.exists(file):
                if (
                    state.config["filelist"]["use_recycle_bin"]
                    and SEND2TRASH_AVAILABLE
                    and not ignore_trash
                ):
                    try:
                        send2trash.send2trash(file)
                    except Exception as e:
                        appInstance.notify(f"Error sending {file} to trash: {e}")
                else:
                    shutil.rmtree(file) if path.isdir(file) else remove(file)
        except Exception as e:
            return f"Error removing file {file}: {e}"


async def create_new_item(appInstance: App, location: str):
    location = location.strip().replace("\\", "/")
    if location == "":
        return
    elif path.exists(location):
        appInstance.notify(f"Location '{location}' already exists.", severity="error")
    elif location.endswith("/"):
        # recursive directory creation
        try:
            makedirs(location)
        except Exception as e:
            appInstance.notify(
                f"Error creating directory '{location}': {e}", severity="error"
            )
    elif len(location.split("/")) > 1:
        # recursive directory until file creation
        location_parts = location.split("/")
        dir_path = "/".join(location_parts[:-1])
        try:
            makedirs(dir_path)
            with open(location, "w") as f:
                f.write("")  # Create an empty file
        except Exception as e:
            appInstance.notify(
                f"Error creating file '{location}': {e}", severity="error"
            )
    else:
        # normal file creation i hope
        try:
            with open(location, "w") as f:
                f.write("")  # Create an empty file
        except Exception as e:
            appInstance.notify(
                f"Error creating file '{location}': {e}", severity="error"
            )
    appInstance.query_one("#reload").action_press()
    appInstance.query_one("#file_list").focus()