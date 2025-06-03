import state
from textual.theme import Theme

state.load_config()


def get_custom_themes():
    """
    Get the custom themes defined in the config file.

    Returns:
        dict: A dictionary of custom themes.
    """
    custom_themes = []
    for theme in state.config["custom_theme"]:
        custom_themes.append(
            Theme(
                name=theme["name"]
                .lower()
                .replace(" ", "-"),  # keep it similar to default textual behaviour
                primary=theme["primary"],
                secondary=theme["secondary"],
                accent=theme["accent"],
                foreground=theme["foreground"],
                background=theme["background"],
                success=theme["success"],
                warning=theme["warning"],
                error=theme["error"],
                surface=theme["surface"],
                panel=theme["panel"],
                dark=theme["is_dark"],
            )
        )
    return custom_themes
