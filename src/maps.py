from os import path

from platformdirs import PlatformDirs

dirs = PlatformDirs("NSPC911", "carto")

VAR_TO_DIR = {
    "DOCUMENTS": dirs.user_documents_dir.replace("\\", "/"),
    "DOWNLOADS": dirs.user_downloads_dir.replace("\\", "/"),
    "MUSIC": dirs.user_music_dir.replace("\\", "/"),
    "PICTURES": dirs.user_pictures_dir.replace("\\", "/"),
    "DESKTOP": dirs.user_desktop_dir.replace("\\", "/"),
    "HOME": path.expanduser("~").replace("\\", "/"),
    "VIDEOS": dirs.user_videos_dir.replace("\\", "/"),
}

ICONS = {
    "general": {
        "new": ["\uea7f", "green"],
        "open": ["\uf07c", "blue"],
        "save": ["\uf0c7", "cyan"],
        "search": ["\uf002", "orange"],
        "refresh": ["\uf021", "teal"],
        "settings": ["\uf013", "gray"],
        "close": ["\uf00d", "red"],
        "up": ["\uf062", "white"],
        "down": ["\uf063", "white"],
        "left": ["\uf060", "white"],
        "right": ["\uf061", "white"],
        "home": ["\uf015", "indigo"],
        "check": ["\uf00c", "green"],
        "copy": ["\uebcc", "white"],
        "paste": ["\uf429", "white"],
        "cut": ["\uf0c4", "white"],
        "rename": ["\uf246", "white"],
        "delete": ["\uf48e", "red"],
    },
    "folder": {
        "default": ["\uf07b", "gold"],
        "open": ["\uf07c", "orange"],
        "empty": ["\uf115", "yellow"],
        "documents": ["\uf02d", "coral"],
        "downloads": ["\uf019", "lime"],
        "music": ["\uf001", "magenta"],
        "pictures": ["\uf03e", "purple"],
        "videos": ["\uf03d", "violet"],
        "git": ["\ue5fb", "red"],
        "github": ["\uf09b", "black"],
        "hidden": ["\uf7c9", "gray"],
        "node_modules": ["\ue5fa", "green"],
        "carto": ["\uf14e", "teal"],
    },
    "file": {
        "default": ["\uf4a5", "white"],
        "text": ["\uf15c", "white"],
        "image": ["\uf1c5", "purple"],
        "audio": ["\uf1c7", "pink"],
        "video": ["\uf1c8", "violet"],
        "pdf": ["\uf1c1", "red"],
        "archive": ["\uf1c6", "brown"],
        "python": ["\ue73c", "#3776AB"],
        "javascript": ["\ue781", "#F7DF1E"],
        "html": ["\uf13b", "#E34F26"],
        "haskell": ["\ue777", "#5D4F85"],
        "json": ["\ue60b", "gold"],
        "markdown": ["\ue73e", "white"],
        "go": ["\uf7b7", "#00ADD8"],
        "rust": ["\ue7a8", "#DEA584"],
        "c": ["\uf0c3", "#A8B9CC"],
        "cs": ["\ue648", "#239120"],
        "cpp": ["\uf0e3", "#F34B7D"],
        "css": ["\ue749", "#1572B6"],
        "yaml": ["\ue8eb", "teal"],
        "yml": ["\ue6a8", "teal"],
        "toml": ["\ue6b2", "red"],
        "swift": ["\ue755", "#F05138"],
        "java": ["\ue738", "#ED8B00"],
        "typescript": ["\ue8ca", "#3178C6"],
        "kotlin": ["\ue81b", "#7F52FF"],
        "vue": ["\ue6a0", "#4FC08D"],
        "php": ["\ue73d", "#777BB4"],
        "tcss": ["\uf37f", "light_blue"],
        "executable": ["\uf085", "gray"],
        "config": ["\uf085", "slate"],
        "binary": ["\uf471", "dark_gray"],
        "lock": ["\uea75", "red"],
        "git": ["\uf1d3", "#F05032"],
        "diff": ["\uf4d2", "green"],
        "cert": ["\ueb11", "maroon"],
        "package": ["\uf487", "tan"],
    },
}

FOLDER_MAP = {
    # documents
    "documents": "documents",
    "docs": "documents",
    # downloads
    "downloads": "downloads",
    "download": "downloads",
    # music
    "music": "music",
    "audio": "music",
    "songs": "music",
    "sounds": "music",
    # pictures
    "pictures": "pictures",
    "photos": "pictures",
    "images": "pictures",
    "assets": "pictures",
    "textures": "pictures",
    # videos
    "videos": "videos",
    "movies": "videos",
    # git
    ".git": "git",
    ".github": "github",
    # other stuff
    "node_modules": "node_modules",
    "carto": "carto",
}

FILES_MAP = {
    # Text files
    ".txt": "text",
    ".log": "text",
    # Image files
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".bmp": "image",
    ".svg": "image",
    ".webp": "image",
    # Audio files
    ".mp3": "audio",
    ".wav": "audio",
    ".flac": "audio",
    ".ogg": "audio",
    # Video files
    ".mp4": "video",
    ".avi": "video",
    ".mkv": "video",
    ".mov": "video",
    # Document files
    ".pdf": "pdf",
    ".md": "markdown",
    ".markdown": "markdown",
    # Archive files
    ".zip": "archive",
    ".rar": "archive",
    ".tar": "archive",
    ".gz": "archive",
    ".7z": "archive",
    # Programming languages
    ".py": "python",
    ".pyc": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".json": "json",
    ".go": "go",
    ".rs": "rust",
    ".rlib": "rust",
    ".c": "c",
    ".cs": "cs",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".hs": "haskell",
    ".lhs": "haskell",
    ".swift": "swift",
    ".vue": "vue",
    ".php": "php",
    ".tcss": "tcss",
    # Config files
    ".ini": "config",
    ".conf": "config",
    ".yaml": "yaml",
    ".yml": "yml",
    ".toml": "toml",
    ".lock": "lock",
    # Binary files
    ".bin": "binary",
    ".exe": "executable",
    # Certificates
    ".crt": "cert",
    ".pem": "cert",
    ".cer": "cert",
    # Other specific files
    ".diff": "diff",
    ".patch": "diff",
    # Specific files
    "cargo.lock": "package",
    "package.json": "package",
    "package-lock.json": "package",
}

EXT_TO_LANG_MAP = {
    ".py": "python",
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".css": "css",
    ".js": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".sql": "sql",
    ".java": "java",
    ".sh": "bash",
    ".xml": "xml",
}

PIL_EXTENSIONS = [
    ".avif",
    ".bmp",
    ".dds",
    ".eps",
    ".ps",
    ".gif",
    ".icns",
    ".ico",
    ".im",
    ".jpg",
    ".jpeg",
    ".jpe",
    ".msp",
    ".pcx",
    ".png",
    ".pbm",
    ".pgm",
    ".ppm",
    ".pnm",
    ".sgi",
    ".rgb",
    ".rgba",
    ".bw",
    ".spi",
    ".tga",
    ".tif",
    ".tiff",
    ".webp",
    ".xbm",
    ".j2k",
    ".jp2",
    ".jpx",
    ".j2c",
    ".jxr",
    ".wdp",
    ".apng",
    ".fit",
    ".fits",
    ".flif",
    ".ftex",
    ".heic",
    ".heif",
    ".mim",
    ".mpo",
    ".psd",
    ".svg",
    ".palm",
    ".pxr",
    ".qoi",
    ".tim",
]


def get_icon_for_file(location: str) -> list:
    """Get the icon and color for a file based on its name or extension.

    Args:
        location (str): The name or path of the file.

    Returns:
        list: The icon and color for the file.
    """
    file_name = location.lower()
    # Map extensions to icons
    if file_name.startswith(".git"):
        return ICONS["file"]["git"]
    elif file_name in FILES_MAP:
        return ICONS["file"][FILES_MAP[file_name]]
    elif "." in file_name:
        extension = f".{file_name.split('.')[-1]}"
        if extension in FILES_MAP:
            return ICONS["file"][FILES_MAP[extension]]
    if file_name.startswith(".git"):
        return ICONS["file"]["git"]
    else:
        # Default file icon
        return ICONS["file"]["default"]


def get_icon_for_folder(location: str) -> list:
    """Get the icon and color for a folder based on its name.

    Args:
        location (str): The name or path of the folder.

    Returns:
        list: The icon and color for the folder.
    """
    folder_name = location.lower()
    # Check for special folder types
    if folder_name in FOLDER_MAP:
        return ICONS["folder"][FOLDER_MAP[folder_name]]
    else:
        return ICONS["folder"]["default"]


TOGGLE_BUTTON_ICONS = {
    "left": " ",
    "right": "",
    "inner": "\ue640",
    "inner_filled": "\uf4a7",
}

BORDER_BOTTOM = {
    "ascii": "-",
    "blank": " ",
    "dashed": "╍",
    "double": "═",
    "heavy": "━",
    "hidden": " ",
    "none": " ",
    "hkey": "▁",
    "inner": "▀",
    "outer": "▄",
    "panel": "▁",
    "round": "─",
    "solid": "─",
    "tall": "▁",
    "thick": "▄",
    "vkey": "▔",
    "wide": "▔",
}
