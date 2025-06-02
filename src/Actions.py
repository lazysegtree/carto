from os import path, remove, makedirs, getcwd
import shutil
import state
from textual.app import App
from textual.content import Content
from send2trash import send2trash

state.load_config()


async def remove_files(
    appInstance: App,
    files: list[str],
    compressed: bool = True,
    ignore_trash: bool = False,
) -> None:
    """Remove files from the filesystem.

    Args:
        appInstance (App): The application instance.
        files (list[str]): List of file paths to remove.
        compressed (bool): Whether the file paths are compressed. Defaults to True.
        ignore_trash (bool): If True, files will be permanently deleted instead of sent to the recycle bin. Defaults to False.
    """
    for file in files:
        if compressed:
            file = state.decompress(file)
        file = path.realpath(file)
        try:
            if path.exists(file):
                if state.config["filelist"]["use_recycle_bin"] and not ignore_trash:
                    try:
                        send2trash(file)
                    except Exception as e:
                        appInstance.notify(
                            message=Content(f"Error sending {file} to trash: {e}"),
                            severity="error",
                        )
                else:
                    shutil.rmtree(file) if path.isdir(file) else remove(file)
        except Exception as e:
            appInstance.notify(
                message=Content(f"Error removing file {file}: {e}"), severity="error"
            )
    appInstance.query_one("#reload").action_press()
    appInstance.query_one("#file_list").focus()


async def create_new_item(appInstance: App, location: str):
    location = location.strip().replace("\\", "/")
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
        # normal file creation i hope
        try:
            with open(location, "w") as f:
                f.write("")  # Create an empty file
        except Exception as e:
            appInstance.notify(
                message=Content(f"Error creating file '{location}': {e}"),
                severity="error",
            )
    appInstance.query_one("#reload").action_press()
    appInstance.query_one("#file_list").focus()


async def rename_object(appInstance: App, old_name: str, new_name: str):
    """Rename a file or directory.

    Args:
        appInstance (App): The application instance.
        old_name (str): The current name of the file or directory.
        new_name (str): The new name for the file or directory.
    """
    old_name = path.realpath(path.join(getcwd(), old_name.strip().replace("\\", "/")))
    new_name = path.realpath(path.join(getcwd(), new_name.strip().replace("\\", "/")))

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

    appInstance.query_one("#reload").action_press()
    appInstance.query_one("#file_list").focus()
