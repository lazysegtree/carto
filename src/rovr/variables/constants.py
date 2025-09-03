from dataclasses import dataclass

from rovr.functions.config import config_setup, load_config

# Initialize the config once at import time
if "config" not in globals():
    global config
    config = load_config()
    config_setup()


@dataclass
class PreviewContainerTitles:
    image = "Image Preview"
    bat = "File Preview (bat)"
    file = "File Preview"
    folder = "Folder Preview"
    archive = "Archive Preview"


buttons_that_depend_on_path = [
    "#copy",
    "#cut",
    "#rename",
    "#delete",
    "#zip",
    "#copy_path",
]
