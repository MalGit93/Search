"""Module entrypoint for `python -m garage_news`."""

from .cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
