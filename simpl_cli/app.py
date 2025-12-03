#!/usr/bin/env python3

import sys
from prompt_toolkit import prompt

from .config import Config
from .core import HybridShell
from .ui.highlighter import create_console


def check_dependencies() -> None:
    try:
        import rich
        import prompt_toolkit
        import requests
        import psutil
    except ImportError as error:
        print(f" Required dependency not found: {error}")
        print("Please install required packages:")
        print("pip install rich prompt-toolkit requests psutil")

        try:
            import tomli
        except ImportError:
            print("Optional: pip install tomli (for Poetry project detection)")

        sys.exit(1)


def get_api_key() -> str:
    api_key = Config.get_api_key()

    if not api_key:
        console = create_console()
        console.print(" [yellow]API Key not found in environment variables.[/yellow]")
        console.print(" [dim]If you don't have an API key, you can enter a random string (optional)[/dim]")
        api_key = prompt("Fireworks API Key: ", is_password=True).strip()

        if not api_key:
            console.print(" [red]API Key required to run the hybrid shell[/red]")
            sys.exit(1)

    return api_key


def main() -> None:
    check_dependencies()
    Config.ensure_directories()

    api_key = get_api_key()

    shell = HybridShell(api_key)
    shell.run()


if __name__ == "__main__":
    main()
