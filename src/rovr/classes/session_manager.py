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
        sessionSelectMode (bool): whether select mode is enabled for that directory.
        sessionSelectedItems (list[str]): A dictionary mapping directory paths to the list of
            selected items in that directory.
    """

    def __init__(self) -> None:
        self.sessionDirectories: list[dict] = []
        self.sessionHistoryIndex: int = 0
        self.sessionLastHighlighted: dict[str, int] = {}
        self.sessionSelectMode: bool = False
        self.sessionSelectedItems: list[str] = []
