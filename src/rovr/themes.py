from dataclasses import dataclass, field

from textual.color import Color
from textual.theme import Theme

from .utils import config


@dataclass
class RovrThemeClass(Theme):
    name: str
    primary: str
    secondary: str | None = None
    warning: str | None = None
    error: str | None = None
    success: str | None = None
    accent: str | None = None
    foreground: str | None = None
    background: str | None = None
    surface: str | None = None
    panel: str | None = None
    boost: str | None = None
    dark: bool = True
    luminosity_spread: float = 0.15
    text_alpha: float = 0.95
    variables: dict[str, str] = field(default_factory=dict)
    bar_gradient: list[str] | None = None


def get_custom_themes() -> list:
    """
    Get the custom themes defined in the config file.

    Returns:
        list: A list of custom themes.
    """
    custom_themes = []
    for theme in config["custom_theme"]:
        if bar_gradient := theme.get("bar_gradient"):
            for color in bar_gradient:
                Color.parse(color)
        custom_themes.append(
            RovrThemeClass(
                bar_gradient=theme.get("bar_gradient", []),
                name=theme["name"]
                .lower()
                .replace(" ", "-"),  # Keep it similar to default textual behaviour
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
                variables=theme.get("variables", {}),
            )
        )
    return custom_themes
