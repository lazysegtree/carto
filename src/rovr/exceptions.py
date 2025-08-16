class FolderNotFileError(Exception):
    """Raised when a folder is expected but a file is provided instead."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
