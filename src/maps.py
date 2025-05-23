ICONS = {
    "general": {
        "new": "\uf415",
        "open": "\uf47c",
        "save": "\uf0c7",
        "search": "\uf002",
        "refresh": "\uf021",
        "settings": "\uf013",
        "close": "\uf00d",
        "up": "\uf062",
        "down": "\uf063",
        "left": "\uf060",
        "right": "\uf061",
        "home": "\uf015",
        "check": "\uf00c",
    },
    "folder": {
        "default": "\uf07b",
        "open": "\uf07c",
        "empty": "\uf115",
        "documents": "\uf02d",
        "downloads": "\uf019",
        "music": "\uf001",
        "pictures": "\uf03e",
        "videos": "\uf03d",
        "git": "\ue5fb",
        "github": "\uf09b",
        "hidden": "\uf7c9",
        "node_modules": "\ue5fa",
    },
    "file": {
        "default": "\uf15b",
        "text": "\uf15c",
        "image": "\uf1c5",
        "audio": "\uf1c7",
        "video": "\uf1c8",
        "pdf": "\uf1c1",
        "archive": "\uf1c6",
        "python": "\ue73c",
        "javascript": "\ue781",
        "html": "\uf13b",
        "haskell": "\ue777",
        "json": "\ue60b",
        "markdown": "\ue73e",
        "go": "\uf7b7",
        "rust": "\ue7a8",
        "c": "\uf0c3",
        "cs": "\ue648",
        "cpp": "\uf0e3",
        "css": "\ue749",
        "yaml": "\ue8eb",
        "yml": "\ue6a8",
        "toml": "\ue6b2",
        "swift": "\ue755",
        "java": "\ue738",
        "typescript": "\ue8ca",
        "kotlin": "\ue81b",
        "vue": "\ue6a0",
        "php": "\ue73d",
        "executable": "\uf085",
        "config": "\uf085",
        "binary": "\uf471",
        "lock": "\uea75",
        "git": "\uf1d3",
        "diff": "\uf4d2",
        "cert": "\ueb11",
        "package": "\uf487",
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


def get_icon_for_file(location: str) -> str:
    """Get the icon for a file based on its name or extension.

    Args:
        location (str): The name or path of the file.

    Returns:
        str: The icon for the file.
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


def get_icon_for_folder(location: str) -> str:
    """Get the icon for a folder based on its name.

    Args:
        location (str): The name or path of the folder.

    Returns:
        str: The icon for the folder.
    """
    folder_name = location.lower()
    # Check for special folder types
    if folder_name in FOLDER_MAP:
        return ICONS["folder"][FOLDER_MAP[folder_name]]
    else:
        return ICONS["folder"]["default"]
