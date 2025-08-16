from os import getcwd, path

from pathvalidate import sanitize_filepath
from textual.validation import ValidationResult, Validator

from rovr.utils import normalise


class IsValidFilePath(Validator):
    def __init__(self, strict: bool = False) -> None:
        super().__init__(failure_description="Path contains illegal characers.")
        self.strict = strict

    def validate(self, value: str) -> ValidationResult:
        value = normalise(getcwd() + "/" + value)
        if value == normalise(sanitize_filepath(value)):
            return self.success()
        else:
            return self.failure()


class PathDoesntExist(Validator):
    def __init__(self, strict: bool = True) -> None:
        super().__init__(failure_description="Path already exists.")
        self.strict = strict

    def validate(self, value: str) -> ValidationResult:
        value = normalise(getcwd() + "/" + value)
        if path.exists(value):
            return self.failure()
        else:
            return self.success()


class EndsWithWord(Validator):
    def __init__(self, ends_with: str | tuple, strict: bool = True) -> None:
        super().__init__(failure_description="Path does not end with .zip")
        self.ends_with = ends_with
        self.strict = strict

    def validate(self, value: str) -> ValidationResult:
        if value.endswith(self.ends_with):
            return self.success()
        else:
            return self.failure()
