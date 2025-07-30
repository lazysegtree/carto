"""Plans to move the functions here out, because this file is too small to be worth a seperate file"""

import shutil
from os import getcwd, makedirs, path

from textual.app import App
from textual.content import Content

from . import utils

utils.load_config()


async def create_new_item(appInstance: App, location: str) -> None:
    """
    Create a new item
    Args:
        appInstance(App): The current app class
        location(str): The path that you want to create a new item at
    """
    location = utils.normalise(location.strip())
    if location == "":
        return
    elif path.exists(location):
        appInstance.notify(
            message=f"Location '{location}' already exists.", severity="error"
        )
    elif location.endswith("/"):
        # recursive directory creation
        try:
            makedirs(location)
        except Exception as e:
            appInstance.notify(
                message=Content(f"Error creating directory '{location}': {e}"),
                severity="error",
            )
    elif len(location.split("/")) > 1:
        # recursive directory until file creation
        location_parts = location.split("/")
        dir_path = "/".join(location_parts[:-1])
        try:
            makedirs(dir_path)
            with open(location, "w") as f:
                f.write("")  # Create an empty file
        except FileExistsError:
            with open(location, "w") as f:
                f.write("")
        except Exception as e:
            appInstance.notify(
                message=Content(f"Error creating file '{location}': {e}"),
                severity="error",
            )
    else:
        # normal file creation I hope
        try:
            with open(location, "w") as f:
                f.write("")  # Create an empty file
        except Exception as e:
            appInstance.notify(
                message=Content(f"Error creating file '{location}': {e}"),
                severity="error",
            )
    appInstance.query_one("#refresh").action_press()
    appInstance.query_one("#file_list").focus()


async def rename_object(appInstance: App, old_name: str, new_name: str):
    """Rename a file or directory.

    Args:
        appInstance (App): The application instance.
        old_name (str): The current name of the file or directory.
        new_name (str): The new name for the file or directory.
    """
    old_name = utils.normalise(path.realpath(path.join(getcwd(), old_name.strip())))
    new_name = utils.normalise(path.realpath(path.join(getcwd(), new_name.strip())))

    if not path.exists(old_name):
        appInstance.notify(message=f"'{old_name}' does not exist.", severity="error")
        return

    if path.exists(new_name):
        appInstance.notify(message=f"'{new_name}' already exists.", severity="error")
        return

    try:
        shutil.move(old_name, new_name)
    except Exception as e:
        appInstance.notify(
            message=Content(f"Error renaming '{old_name}' to '{new_name}': {e}"),
            severity="error",
        )

    appInstance.query_one("#refresh").action_press()
    appInstance.query_one("#file_list").focus()
