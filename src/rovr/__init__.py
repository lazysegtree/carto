try:
    from .app import Application

    def main() -> None:
        Application(watch_css=True).run()

except KeyboardInterrupt:
    pass
