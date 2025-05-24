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
    for key in state.config["interface"]["theme"].keys():
        if type(state.config["interface"]["theme"][key]) is dict:
            custom_themes.append(
                Theme(
                    name=state.config["interface"]["theme"][key]["name"],
                    primary=state.config["interface"]["theme"][key]["primary"],
                    secondary=state.config["interface"]["theme"][key]["secondary"],
                    accent=state.config["interface"]["theme"][key]["accent"],
                    foreground=state.config["interface"]["theme"][key]["foreground"],
                    background=state.config["interface"]["theme"][key]["background"],
                    success=state.config["interface"]["theme"][key]["success"],
                    warning=state.config["interface"]["theme"][key]["warning"],
                    error=state.config["interface"]["theme"][key]["error"],
                    surface=state.config["interface"]["theme"][key]["surface"],
                    panel=state.config["interface"]["theme"][key]["panel"],
                    dark=state.config["interface"]["theme"][key]["is_dark"],
                )
            )
    return custom_themes