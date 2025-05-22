from textual_autocomplete import PathAutoComplete, TargetState, DropdownItem
from os import scandir
from state import log
from pathlib import Path

class PathDropdownItem(DropdownItem):
    def __init__(self, completion: str, path: Path) -> None:
        super().__init__(completion)
        self.path = path

class PathAutoCompleteInput(PathAutoComplete):
    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """Get the candidates for the current path segment, folders only."""
        current_input = target_state.text[: target_state.cursor_position]

        if "/" in current_input:
            last_slash_index = current_input.rindex("/")
            path_segment = current_input[:last_slash_index] or "/"
            directory = self.path / path_segment if path_segment != "/" else self.path
        else:
            directory = self.path

        # Use the directory path as the cache key
        cache_key = str(directory)
        cached_entries = self._directory_cache.get(cache_key)

        if cached_entries is not None:
            entries = cached_entries
        else:
            try:
                entries = list(scandir(directory))
                self._directory_cache[cache_key] = entries
            except OSError:
                return []

        results: list[PathDropdownItem] = []
        has_directories = False
        
        for entry in entries:
            if entry.is_dir():
                has_directories = True
                completion = entry.name
                if not self.show_dotfiles and completion.startswith("."):
                    continue
                completion += "/"
                results.append(PathDropdownItem(completion, path=Path(entry.path)))
        
        if not has_directories:
            self._empty_directory = True
            return [DropdownItem("", prefix="No folders found")]
        else:
            self._empty_directory = False

        results.sort(key=self.sort_key)
        folder_prefix = self.folder_prefix
        return [
            DropdownItem(
                item.main,
                prefix=folder_prefix,
            )
            for item in results
        ]

    async def post_completion(self) -> None:
        """Called after a completion is selected."""
        super().post_completion()
        log(self._target.id)
        await self.app.query_one(f"#{self._target.id}").action_submit()

    def _align_to_target(self) -> None:
        """Empty function that was supposed to align the completion box to the cursor."""
        pass

    def _on_show(self, event):
        super()._on_show(event)
        self._target.add_class("hide_border_bottom", update=True)

    async def _on_hide(self, event):
        """Handle hide events for the autocomplete."""
        super()._on_hide(event)
        self._target.remove_class("hide_border_bottom", update=True)
        
        # Only submit if we didn't just hide an empty directory dropdown
        if not getattr(self, '_empty_directory', False):
            log("submitting", self._target.id)
            await self.app.query_one(f"#{self._target.id}").action_submit()