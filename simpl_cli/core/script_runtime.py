#!/usr/bin/env python3

import code
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Optional

from ..ui.theme import PanelTheme


class ScriptRuntime:
    """Lightweight Python interpreter with persistent session state."""

    def __init__(self, console) -> None:
        self.console = console
        self._locals: dict[str, object] = {}
        self._interpreter = code.InteractiveConsole(locals=self._locals)
        self._active = False
        self._awaiting_more = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def awaiting_more_input(self) -> bool:
        return self._awaiting_more

    def activate(self) -> None:
        if not self._active:
            self._active = True
            self._awaiting_more = False
            self.console.print(
                PanelTheme.build(
                    "Script mode enabled. Type Python code or 'py exit' to leave.",
                    title="Script",
                    style="info",
                    fit=True,
                )
            )

    def deactivate(self, announce: bool = True) -> None:
        if self._active:
            self._active = False
            self._awaiting_more = False
            self._interpreter.resetbuffer()
            if announce:
                self.console.print(
                    PanelTheme.build(
                        "Script mode disabled.",
                        title="Script",
                        style="info",
                        fit=True,
                    )
                )

    def reset(self) -> None:
        self._locals.clear()
        self._interpreter = code.InteractiveConsole(locals=self._locals)
        self._awaiting_more = False
        self.console.print(
            PanelTheme.build(
                "Script state cleared.",
                title="Script",
                style="warning",
                fit=True,
            )
        )

    def run_inline(self, source: str) -> None:
        previously_active = self._active
        if not previously_active:
            self._active = True
        try:
            more = self._push(source)
            if more:
                self.console.print(
                    PanelTheme.build(
                        "Incomplete Python statement. Enter script mode with 'py' for multi-line blocks.",
                        title="Script",
                        style="warning",
                        fit=True,
                    )
                )
                self._awaiting_more = False
        finally:
            if not previously_active:
                self._active = False

    def run_line(self, source: str) -> None:
        if not self._active:
            self.activate()
        self._push(source)

    def _push(self, source: str) -> bool:
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                needs_more = self._interpreter.push(source)
        except SystemExit:
            self.console.print(
                PanelTheme.build(
                    "SystemExit ignored inside script mode.",
                    title="Script",
                    style="warning",
                    fit=True,
                )
            )
            needs_more = False
        finally:
            stdout_value = stdout_capture.getvalue()
            stderr_value = stderr_capture.getvalue()

            if stdout_value:
                self.console.print(stdout_value, end="")
            if stderr_value:
                self.console.print(stderr_value, end="")

        self._awaiting_more = needs_more
        if needs_more:
            self.console.print(
                PanelTheme.build(
                    "...",
                    title="Script (continue input)",
                    style="info",
                    fit=True,
                )
            )
        return needs_more
