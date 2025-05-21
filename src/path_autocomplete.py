from textual_autocomplete import PathAutoComplete


class PathAutoCompleteInput(PathAutoComplete):
    def post_completion(self) -> None:
        """Called after a completion is selected."""
        super().post_completion()
        self._target.action_submit()

    def _align_to_target(self) -> None:
        """Empty function that was supposed to align the completion box to the cursor."""
        pass

    def _on_show(self, event):
        super()._on_show(event)
        self._target.add_class("hide_border_bottom", update=True)

    def _on_hide(self, event):
        super()._on_hide(event)
        self._target.remove_class("hide_border_bottom", update=True)
