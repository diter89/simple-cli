#!/usr/bin/env python3
from datetime import datetime
from typing import Callable, Iterable, Optional
import os
import select
import subprocess
import sys

try:  
    import termios 
    import tty  
except ImportError:  
    termios = None  
    tty = None  

import signal

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from .theme import PanelTheme
from ..config import Config


class LiveMarkdownStreamRenderer:
    def __init__(self, console: Console, max_visible_lines: int = 10) -> None:
        self.console = console
        self.max_visible_lines = max_visible_lines
        self.rolling_buffer: list[str] = []
        self.full_content: str = ""
        self.current_line: str = ""
        self.word_count = 0

    def reset(self) -> None:
        self.rolling_buffer = []
        self.full_content = ""
        self.current_line = ""
        self.word_count = 0

    def add_chunk(self, chunk: str) -> None:
        self.full_content += chunk
        self.current_line += chunk

        self.word_count = len(self.full_content.split())

        if "\n" in self.current_line:
            lines = self.current_line.split("\n")
            for completed_line in lines[:-1]:
                self.rolling_buffer.append(completed_line)
            self.current_line = lines[-1]

        if len(self.rolling_buffer) > self.max_visible_lines:
            self.rolling_buffer = self.rolling_buffer[-self.max_visible_lines :]

    def get_streaming_content(self):
        display_lines = self.rolling_buffer.copy()
        if self.current_line:
            display_lines.append(self.current_line + "▊")

        buffer_content = "\n".join(display_lines[-self.max_visible_lines :])

        if not buffer_content.strip():
            buffer_content = " Connecting to AI...▊"

        try:
            return Markdown(buffer_content)
        except Exception:  
            return Text(buffer_content, overflow="fold")

    def get_final_content(self):
        try:
            return Markdown(self.full_content)
        except Exception: 
            return Text(self.full_content, overflow="fold")

    def get_word_count(self) -> int:
        return self.word_count


class StreamingContentRenderer:

    def __init__(self) -> None:
        self.content = ""

    def update(self, new_content: str) -> None:
        self.content = new_content

    def __rich__(self):
        if not self.content:
            return Text(" Waiting for response...")

        if "```" in self.content:
            try:
                return Markdown(self.content)
            except Exception:  
                return Text(self.content)
        if any(
            indicator in self.content
            for indicator in ["def ", "import ", "class ", "function", "```"]
        ):
            try:
                return Markdown(self.content)
            except Exception:  
                return Text(self.content)
        return Text(self.content, overflow="fold")


class ShellLiveStreamRenderer:

    def __init__(self, max_visible_lines: int = 15) -> None:
        self.max_visible_lines = max_visible_lines
        self.lines: list[str] = []
        self.current_line: str = ""
        self.full_content: str = ""

    def reset(self) -> None:
        self.lines = []
        self.current_line = ""
        self.full_content = ""

    def add_chunk(self, chunk: str) -> None:
        if not chunk:
            return

        normalized = chunk.replace("\r\n", "\n").replace("\r", "\n")
        self.full_content += normalized

        composed = self.current_line + normalized
        parts = composed.split("\n")
        self.lines.extend(parts[:-1])
        self.current_line = parts[-1]

        if len(self.lines) > self.max_visible_lines:
            self.lines = self.lines[-self.max_visible_lines :]

    def get_renderable(self) -> Text:
        display_lines = self.lines[-self.max_visible_lines :].copy()
        if self.current_line:
            display_lines.append(self.current_line)

        if not display_lines:
            return Text(" Waiting for output...", overflow="fold")

        return Text("\n".join(display_lines), overflow="fold")

    def get_full_output(self) -> str:
        return self.full_content


class StreamingUIManager:

    def __init__(self, console: Console) -> None:
        self.console = console
        self.markdown_renderer = LiveMarkdownStreamRenderer(console)
        self.cancelled_stream_state: Optional[dict] = None
        self.shell_renderer = ShellLiveStreamRenderer()

    def stream_ai_response_with_live_markdown(
        self,
        api_call_func,
        *args,
        final_title: str = "󰟍 AI Assistant - Complete",
        finalizer: Optional[Callable[[object, str], "Panel"]] = None,
        **kwargs,
    ):

        self.markdown_renderer.reset()

        with Live(console=self.console, refresh_per_second=12) as live:
            try:
                live.update(
                    PanelTheme.build(
                        Align.center("󰣸  Establishing connection to AI service..."),
                        title="󰟍 AI Assistant",
                        style="info",
                        padding=(1, 2),
                        fit=True,
                    )
                )

                for chunk in api_call_func(*args, **kwargs):
                    self.markdown_renderer.add_chunk(chunk)

                    streaming_content = self.markdown_renderer.get_streaming_content()
                    live.update(
                        PanelTheme.build(
                            streaming_content,
                            title="󰟍 AI Assistant Response",
                            style="info",
                            padding=(0, 1),
                            fit=True,
                        )
                    )

                final_content = self.markdown_renderer.get_final_content()
                final_panel = (
                    finalizer(final_content, self.markdown_renderer.full_content)
                    if finalizer
                    else PanelTheme.build(
                        final_content,
                        title=final_title,
                        style="success",
                        padding=(0, 1),
                        fit=True,
                    )
                )
                live.update(final_panel)
                return self.markdown_renderer.full_content

            except KeyboardInterrupt:
                partial_content = (
                    self.markdown_renderer.get_final_content()
                    if self.markdown_renderer.full_content
                    else Align.center(" Response cancelled by user")
                )

                live.update(
                    PanelTheme.build(
                        partial_content,
                        title="󰟍 AI Assistant - Cancelled",
                        style="warning",
                        padding=(1, 2),
                        fit=True,
                    )
                )

                return " Response cancelled"

            except Exception as error:  
                live.update(
                    PanelTheme.build(
                        f" Error: {str(error)}",
                        title="󰟍 AI Assistant - Error",
                        style="error",
                        padding=(1, 2),
                        fit=True,
                    )
                )
                return f" Error: {str(error)}"

    def save_cancelled_state(self, user_message: str, partial_content: str, messages: list):
        self.cancelled_stream_state = {
            "user_message": user_message,
            "partial_content": partial_content,
            "messages": messages,
            "timestamp": datetime.now().isoformat(),
            "word_count": self.markdown_renderer.get_word_count(),
        }

    def has_cancelled_stream(self) -> bool:
        return self.cancelled_stream_state is not None

    def clear_cancelled_state(self) -> None:
        self.cancelled_stream_state = None

    def get_cancelled_state_info(self) -> Optional[dict]:
        if not self.has_cancelled_stream():
            return None

        return {
            "user_message": self.cancelled_stream_state["user_message"],
            "partial_word_count": self.cancelled_stream_state["word_count"],
            "timestamp": self.cancelled_stream_state["timestamp"],
        }

    def stream_ai_response_with_resume(
        self,
        api_call_func,
        *args,
        finalizer: Optional[Callable[[object, str], "Panel"]] = None,
        **kwargs,
    ):
        if self.has_cancelled_stream():
            return self._resume_cancelled_stream(
                api_call_func, *args, finalizer=finalizer, **kwargs
            )
        return self.stream_ai_response_with_live_markdown(
            api_call_func, *args, finalizer=finalizer, **kwargs
        )

    def _resume_cancelled_stream(
        self,
        api_call_func,
        *args,
        finalizer: Optional[Callable[[object, str], "Panel"]] = None,
        **kwargs,
    ):
        if not self.has_cancelled_stream():
            return " No cancelled stream to resume"

        saved_state = self.cancelled_stream_state
        user_message = saved_state["user_message"]
        partial_content = saved_state["partial_content"]
        original_messages = saved_state["messages"]

        self.markdown_renderer.reset()
        self.markdown_renderer.full_content = partial_content
        self.markdown_renderer.current_line = ""
        self.markdown_renderer.word_count = len(partial_content.split())

        with Live(console=self.console, refresh_per_second=12) as live:
            try:
                live.update(
                    PanelTheme.build(
                        Align.center(
                            f"󰐎 Resuming response to: '{user_message[:50]}{'...' if len(user_message) > 50 else ''}'"
                        ),
                        title="󰟍 AI Assistant - Resume",
                        style="warning",
                        padding=(1, 2),
                        fit=True,
                    )
                )

                for chunk in api_call_func(*args, **kwargs):
                    self.markdown_renderer.add_chunk(chunk)

                    streaming_content = self.markdown_renderer.get_streaming_content()
                    live.update(
                        PanelTheme.build(
                            streaming_content,
                            title="󰟍 AI Assistant - Resuming",
                            style="warning",
                            padding=(0, 1),
                            fit=True,
                        )
                    )

                final_content = self.markdown_renderer.get_final_content()
                final_panel = (
                    finalizer(final_content, self.markdown_renderer.full_content)
                    if finalizer
                    else PanelTheme.build(
                        final_content,
                        title="󰟍 AI Assistant - Resume Complete",
                        style="success",
                        padding=(0, 1),
                        fit=True,
                    )
                )
                live.update(final_panel)

                self.clear_cancelled_state()

                return self.markdown_renderer.full_content

            except KeyboardInterrupt:
                self.save_cancelled_state(
                    user_message, self.markdown_renderer.full_content, original_messages
                )

                partial_content = (
                    self.markdown_renderer.get_final_content()
                    if self.markdown_renderer.full_content
                    else Align.center(" Resume cancelled by user")
                )

                live.update(
                    PanelTheme.build(
                        partial_content,
                        title="󰟍 AI Assistant - Resume Cancelled",
                        style="warning",
                        padding=(1, 2),
                        fit=True,
                    )
                )
                return " Resume cancelled"

            except Exception as error: 
                live.update(
                    PanelTheme.build(
                        f" Resume Error: {str(error)}",
                        title="󰟍 AI Assistant - Resume Error",
                        style="error",
                        padding=(1, 2),
                        fit=True,
                    )
                )
                return f" Resume Error: {str(error)}"

    def stream_content(self, iterable: Iterable[str]):
        for chunk in iterable:
            self.markdown_renderer.add_chunk(chunk)
            yield self.markdown_renderer.get_streaming_content()

    def stream_shell_command(self, command: str, process: subprocess.Popen):
        if process.stdout is None:
            exit_code = process.wait()
            return "", exit_code, False

        renderer = self.shell_renderer
        renderer.reset()

        cancelled = False
        exit_code = None
        title_command = command if len(command) <= 60 else f"{command[:57]}..."

        stdout_fd = process.stdout.fileno()
        stdin_fd = sys.stdin.fileno() if sys.stdin.isatty() else None
        input_enabled = stdin_fd is not None and process.stdin is not None and termios and tty

        old_term_settings = None
        if input_enabled:
            old_term_settings = termios.tcgetattr(stdin_fd)  
            tty.setcbreak(stdin_fd) 

        final_output = ""

        final_output = ""
        final_title = " Shell Command - Complete"
        final_style = "success"

        try:
            with Live(console=self.console, refresh_per_second=12) as live:
                live.update(
                    PanelTheme.build(
                        Align.center(f"󰣸  Executing: '{title_command}'"),
                        title=" Shell Command",
                        style="info",
                        padding=(1, 2),
                        fit=True,
                        highlight=True,
                    )
                )

                while True:
                    watch_fds = [stdout_fd]
                    if input_enabled:
                        watch_fds.append(stdin_fd)  

                    ready, _, _ = select.select(watch_fds, [], [], 0.1)

                    if stdout_fd in ready:
                        try:
                            chunk = os.read(stdout_fd, 4096)
                        except OSError:
                            chunk = b""

                        if not chunk:
                            if process.poll() is not None:
                                break
                        else:
                            text_chunk = chunk.decode("utf-8", errors="replace")
                            renderer.add_chunk(text_chunk)
                            live.update(
                                PanelTheme.build(
                                    renderer.get_renderable(),
                                    title=f" {title_command}",
                                    style="info",
                                    padding=(0, 1),
                                    fit=True,
                                    highlight=True,
                                )
                            )

                    if input_enabled and stdin_fd in ready and process.stdin:
                        try:
                            user_input = os.read(stdin_fd, 4096)
                        except OSError:
                            user_input = b""

                        if user_input:
                            if b"\x03" in user_input:  # Ctrl+C
                                cancelled = True
                                try:
                                    process.send_signal(signal.SIGINT)
                                except Exception:
                                    process.terminate()
                                break
                            try:
                                process.stdin.write(user_input)
                                process.stdin.flush()
                            except Exception: 
                                pass

                    if process.poll() is not None and not select.select([stdout_fd], [], [], 0)[0]:
                        break

                try:
                    exit_code = process.wait(timeout=0.1)
                except Exception:  
                    exit_code = process.poll()

                final_style = "success"
                if cancelled:
                    final_style = "warning"
                elif exit_code not in (0, None):
                    final_style = "error"

                final_title = " Shell Command - Complete"
                if cancelled:
                    final_title = " Shell Command - Cancelled"
                elif exit_code not in (0, None):
                    final_title = f" Shell Command - Exit {exit_code}"

                final_output = renderer.get_full_output()

                if Config.is_shell_stream_summary_enabled():
                    summary_lines = []
                    if cancelled:
                        summary_lines.append(" Command cancelled. Partial output shown below.")
                    else:
                        summary_lines.append(
                            f" Exit code: {exit_code if exit_code is not None else 'unknown'}"
                        )
                        if final_output:
                            summary_lines.append("Output printed below.")
                        else:
                            summary_lines.append("No output produced.")

                    summary_text = Align.left("\n".join(summary_lines))

                    live.update(
                        PanelTheme.build(
                            summary_text,
                            title=final_title,
                            style=final_style,
                            padding=(0, 1),
                            fit=True,
                            highlight=True,
                        )
                    )
                else:
                    live.update(
                        Align.left(
                            f"Command finished with exit code {exit_code if exit_code is not None else 'unknown'}"
                        )
                    )

        except KeyboardInterrupt:
            cancelled = True
            try:
                process.send_signal(signal.SIGINT)
            except Exception:  
                try:
                    process.terminate()
                except Exception:  
                    pass

        finally:
            if input_enabled and old_term_settings is not None:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_term_settings) 

        if exit_code is None:
            try:
                exit_code = process.wait(timeout=1)
            except Exception: 
                exit_code = process.poll()

        display_text: Text | None = None
        if final_output:
            display_text = Text(final_output, overflow="fold")
        elif not cancelled:
            display_text = Text("(no output)", style="dim")

        if display_text is not None:
            if Config.is_shell_stream_output_panel_enabled():
                self.console.print(
                    PanelTheme.build(
                        display_text,
                        title=final_title,
                        style=final_style,
                        padding=(0, 1),
                        fit=True,
                        highlight=True,
                    )
                )

            else:
                self.console.print(display_text)

        return renderer.get_full_output(), exit_code, cancelled
