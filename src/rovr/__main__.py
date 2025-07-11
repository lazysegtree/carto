from .app import Application


def main() -> None:
    Application(watch_css=True).run()
