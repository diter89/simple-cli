#!/usr/bin/env python3
from typing import Optional
from time import perf_counter

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer

from ..commands import ShellCommandExecutor
from ..completion import create_completion_manager
from ..config import Config
from ..context import ContextManager
from ..ui import StreamingUIManager, UIManager
from ..ui.highlighter import create_console
from ..ui.theme import PanelTheme
from .ai import AIChatManager

try:  # Pygments is optional at runtime
    from pygments.lexers import find_lexer_class_by_name
except ImportError:  # pragma: no cover
    find_lexer_class_by_name = None


class HybridShell:

    def __init__(
        self,
        api_key: str,
        context_manager: Optional[ContextManager] = None,
    ) -> None:
        self.api_key = api_key
        self.mode = "shell"  

        self.session = PromptSession(history=FileHistory(str(Config.SHELL_HISTORY_FILE)))
        self.console = create_console()

        self.ui = UIManager(self.console)
        self.streaming_ui = StreamingUIManager(self.console)
        self.context_manager = context_manager or ContextManager()

        self.completion_manager = create_completion_manager()
        self.command_executor = ShellCommandExecutor(
            console=self.console,
            ui=self.ui,
            streaming_ui=self.streaming_ui,
            context_manager=self.context_manager,
            completion_manager=self.completion_manager,
        )
        self.ai_manager = AIChatManager(api_key, self.context_manager)
        self.command_executor.set_ai_manager(self.ai_manager)
        self.ai_manager.set_command_executor(self.command_executor)

        self._setup_keybindings()
        self.context_manager.load_history()

        self.prompt_lexer = self._create_prompt_lexer()

    def _setup_keybindings(self) -> None:
        self.bindings = KeyBindings()

        @self.bindings.add("c-a")
        def switch_to_ai(event):  
            self.mode = "ai"
            self.ui.show_mode_switch("AI Mode")

        @self.bindings.add("c-s")
        def switch_to_shell(event):  
            self.mode = "shell"
            self.ui.show_mode_switch("Shell Mode")

        @self.bindings.add("escape", "h")
        def show_help(event):  
            self.ui.show_help()

        @self.bindings.add("escape", "c")
        def clear_context(event):  
            self.context_manager.clear_all()
            self.ui.show_context_cleared()

        @self.bindings.add("escape", "r")
        def refresh_completion(event):  
            self.completion_manager.clear_cache()

        @self.bindings.add("escape", "z")
        def resume_cancelled_stream(event):  
            self.resume_cancelled_stream()

    def execute_shell_command(self, command: str) -> Optional[str]:
        return self.command_executor.execute(command)

    def stream_ai_response(self, user_message: str):
        overall_start = perf_counter()

        prep_start = perf_counter()
        interaction = self.ai_manager.prepare_interaction(user_message)
        prep_elapsed = perf_counter() - prep_start
        messages = interaction["messages"]

        diagnostics = list(interaction.get("diagnostics", []))
        diagnostics.append(f"[dim]AI prep: {self._format_duration(prep_elapsed)}[/dim]")
        self.ui.display_router_diagnostics(diagnostics)

        renderable = interaction.get("renderable")
        if renderable is not None:
            self.ui.display_persona_renderable(renderable)

        def api_streaming_func():
            return self.ai_manager.create_stream(messages)

        persona_name = interaction.get("persona", "general_chat")

        stream_start = perf_counter()

        def final_panel_builder(final_renderable, _full_text):
            total_elapsed = perf_counter() - overall_start
            stream_elapsed = perf_counter() - stream_start
            subtitle = f" {self._format_duration(total_elapsed)} | stream {self._format_duration(stream_elapsed)}"

            return PanelTheme.build(
                final_renderable,
                title=f"({persona_name}) ",
                style="success",
                fit=True,
                subtitle=subtitle,
                subtitle_align="right",
            )

        response = self.streaming_ui.stream_ai_response_with_live_markdown(
            api_streaming_func,
            finalizer=final_panel_builder,
        )

        if response == " Response cancelled":
            partial_content = self.streaming_ui.markdown_renderer.full_content
            self.streaming_ui.save_cancelled_state(user_message, partial_content, messages)
            self.ui.show_cancelled_stream_notification(user_message)
        elif response and not response.startswith("") and not response.startswith(""):
            self.ai_manager.record_interaction(user_message, response, interaction)

        return response

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0

        if seconds < 1:
            return f"{seconds * 1000:.0f}ms"

        total_seconds = int(seconds)
        minutes, secs = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")

        return " ".join(parts)

    def resume_cancelled_stream(self):
        if not self.streaming_ui.has_cancelled_stream():
            self.console.print(
                PanelTheme.build(
                    "[yellow]No cancelled stream to resume[/yellow]",
                    title="Resume Stream",
                    style="warning",
                )
            )
            return

        state_info = self.streaming_ui.get_cancelled_state_info()
        user_message = state_info["user_message"]  

        self.console.print()
        self.console.print(
            PanelTheme.build(
                f"[cyan]Resuming response to: '{user_message[:60]}{'...' if len(user_message) > 60 else ''}'[/cyan]",
                title=" Resume Stream",
                style="info",
            )
        )

        def api_streaming_func():
            original_messages = self.streaming_ui.cancelled_stream_state["messages"]
            return self.ai_manager.create_stream(original_messages)

        response = self.streaming_ui.stream_ai_response_with_resume(api_streaming_func)

        if response and not response.startswith("") and not response.startswith(""):
            self.ai_manager.store_conversation(user_message, response)

        return response

    def handle_ai_special_commands(self, user_input: str) -> bool:
        lowered = user_input.lower()
        if lowered in {"clear", "clear0"}:
            self.console.print(
                PanelTheme.build(
                    "[yellow]Perintah 'clear' kini digantikan oleh '[bold]memory clear[/bold]' di mode shell.[/yellow]",
                    title="Memory",
                    style="warning",
                )
            )
            return True
        if lowered == "context":
            self.ui.show_context_table(self.context_manager.shell_context)
            return True
        if lowered == "resume":
            self.resume_cancelled_stream()
            return True
        if lowered == "cancelstate":
            if self.streaming_ui.has_cancelled_stream():
                state_info = self.streaming_ui.get_cancelled_state_info()
                self.ui.show_cancelled_stream_info(state_info)
            else:
                self.console.print(
                    PanelTheme.build(
                        "[yellow]No cancelled stream available[/yellow]",
                        title="Cancel State",
                        style="warning",
                    )
                )
            return True
        return False

    def handle_shell_special_commands(self, user_input: str) -> bool: 
        normalized = user_input.strip()

        if normalized.startswith("memory"):
            return self._handle_memory_command(normalized)

        if normalized.startswith("/ai_provider"):
            provider_suffix = normalized[len("/ai_provider"):].strip(" _")
            command = "ai provider" if not provider_suffix else f"ai provider {provider_suffix}"
            return self._handle_ai_provider_command(command)

        if normalized in {"/config_reload", "config_reload"}:
            return self._handle_config_command("config reload")

        if normalized.startswith("config"):
            return self._handle_config_command(normalized)

        if normalized.startswith("ai "):
            return self._handle_ai_provider_command(normalized)

        return False

    def _handle_memory_command(self, command: str) -> bool:
        if not self.ai_manager:
            self.ui.display_memory_error("Memory subsystem unavailable")
            return True

        parts = command.split()
        action = parts[1] if len(parts) > 1 else "status"

        if action == "status":
            stats = self.ai_manager.get_memory_stats()
            self.ui.display_memory_status(stats)
            self.context_manager.add_shell_context(command, "Displayed memory status")
            return True

        if action == "clear":
            success = self.ai_manager.clear_memory()
            if success:
                self.context_manager.clear_all()
            self.ui.display_memory_cleared(success)
            status_msg = "Memory and context cleared" if success else "Memory clear failed"
            self.context_manager.add_shell_context(command, status_msg)
            return True

        if action == "enable":
            enabled = self.ai_manager.set_memory_enabled(True)
            self.ui.display_memory_toggle(enabled)
            status_msg = "Memory enabled" if enabled else "Failed to enable memory"
            self.context_manager.add_shell_context(command, status_msg)
            return True

        if action == "disable":
            self.ai_manager.set_memory_enabled(False)
            self.ui.display_memory_toggle(False)
            self.context_manager.add_shell_context(command, "Memory disabled")
            return True

        if action == "topk" and len(parts) >= 3:
            try:
                value = int(parts[2])
            except ValueError:
                self.ui.display_memory_error("Invalid top-k value")
                return True

            new_value = self.ai_manager.set_memory_top_k(value)
            self.ui.display_memory_topk(new_value)
            self.context_manager.add_shell_context(
                command, f"Memory top_k set to {new_value}"
            )
            return True

        self.ui.display_memory_error("Unknown memory command")
        return True

    def _handle_config_command(self, command: str) -> bool:
        parts = command.split()
        action = parts[1].lower() if len(parts) > 1 else ""

        if action == "reload":
            self._reload_configuration()
            return True

        usage = "config reload"
        self.console.print(
            PanelTheme.build(
                f"[yellow]Unknown config command.[/yellow]\nUsage: [cyan]{usage}[/cyan]",
                title="Config",
                style="warning",
            )
        )
        return True

    def _reload_configuration(self) -> None:
        with self.ui.create_status("Reloading configuration..."):
            success = Config.reload()

        if not success:
            self.console.print(
                PanelTheme.build(
                    "[red]Failed to reload configuration. Check config.ini for errors.[/red]",
                    title="Config",
                    style="error",
                    fit=True,
                )
            )
            return

        self.session = PromptSession(history=FileHistory(str(Config.SHELL_HISTORY_FILE)))
        self.completion_manager = create_completion_manager()
        self.command_executor.set_completion_manager(self.completion_manager)
        self.command_executor.refresh_configuration()
        if hasattr(self.ai_manager, "reload_configuration"):
            self.ai_manager.reload_configuration()
        self.prompt_lexer = self._create_prompt_lexer()

        self.console.print(
            PanelTheme.build(
                f"[green]Configuration reloaded from[/green] [cyan]{Config.CONFIG_FILE}[/cyan]",
                title="Config",
                style="success",
                fit=True,
            )
        )

    def _handle_ai_provider_command(self, command: str) -> bool:
        parts = command.split()
        if len(parts) == 2 and parts[1] == "provider":
            status = self.ai_manager.get_provider_status()
            error = status.get("error")
            message = f"Current provider: [cyan]{status.get('provider', 'unknown')}[/cyan]"
            if error:
                message += f"\n[red]Warning:[/red] {error}"
            self.console.print(
                PanelTheme.build(
                    message,
                    title="AI Provider",
                    style="info" if not error else "warning",
                    fit=True,
                )
            )
            return True

        if len(parts) >= 3 and parts[1] == "provider":
            target = parts[2].lower()
            success, info = self.ai_manager.set_provider(target)
            if success:
                self.console.print(
                    PanelTheme.build(
                        f"[green]AI provider switched to[/green] [cyan]{info}[/cyan]",
                        title="AI Provider",
                        style="success",
                        fit=True,
                    )
                )
            else:
                self.console.print(
                    PanelTheme.build(
                        f"[red]Failed to switch provider:[/red] {info}",
                        title="AI Provider",
                        style="error",
                        fit=True,
                    )
                )
            return True

        self.console.print(
            PanelTheme.build(
                "Usage: [cyan]ai provider <name>[/cyan]",
                title="AI Provider",
                style="warning",
                fit=True,
            )
        )
        return True

    def run(self) -> None:
        self.ui.show_welcome()

        session_history = AutoSuggestFromHistory()

        try:
            while True:
                try:
                    current_completer = None
                    if self.mode == "shell":
                        current_completer = self.completion_manager.get_completer()

                    user_input = self.session.prompt(
                        self.ui.get_prompt_text(self.mode),
                        key_bindings=self.bindings,
                        style=self.ui.get_style(),
                        auto_suggest=session_history,
                        clipboard=PyperclipClipboard(),
                        completer=current_completer,
                        lexer=self.prompt_lexer,
                        complete_while_typing=True,
                    ).strip()

                    if not user_input:
                        continue

                    if self.mode == "ai":
                        if self.handle_ai_special_commands(user_input):
                            continue

                        self.stream_ai_response(user_input)
                        self.console.print()

                    else:
                        if self.handle_shell_special_commands(user_input):
                            continue

                        result = self.execute_shell_command(user_input)
                        if result == "exit":
                            break

                except EOFError:
                    if self.command_executor.in_script_mode():
                        self.command_executor.exit_script_mode()
                        continue

                    self.ui.display_goodbye()
                    break

                except KeyboardInterrupt:
                    self.ui.display_goodbye()
                    break

        except KeyboardInterrupt:
            self.ui.display_goodbye()
        finally:
            self.context_manager.save_history()

    def _create_prompt_lexer(self):
        choice = Config.get_prompt_lexer_choice().strip()
        if not choice or choice.lower() == "auto":
            return None

        if not find_lexer_class_by_name:
            return None

        lexer_cls = find_lexer_class_by_name(choice)
        if lexer_cls is None:
            return None

        return PygmentsLexer(lexer_cls)
