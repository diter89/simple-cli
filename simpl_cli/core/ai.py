#!/usr/bin/env python3
import json
import os
import subprocess
from typing import Dict, Generator, Iterable, List, Optional, Tuple

from ..config import Config
from ..context import ChromaMemoryStore
from ..persona import PersonaSearchService, create_persona
from .providers import ChatProvider, create_provider
from .router import AdvancedRouter, RouterDecision, create_router


class AIChatManager:
    def __init__(self, api_key: str, context_manager) -> None:
        self.api_key = api_key
        self.context_manager = context_manager
        self.memory_store: Optional[ChromaMemoryStore] = None
        self.memory_enabled = Config.MEMORY_ENABLED
        self.memory_top_k = Config.MEMORY_TOP_K
        self.memory_error: Optional[str] = None
        self.router_enabled = Config.is_router_enabled()
        self.router: Optional[AdvancedRouter] = None
        self.router_error: Optional[str] = None
        self.router_provider_name: Optional[str] = None
        self.search_service = PersonaSearchService()
        self.persona_memory: Dict[str, Dict] = {}
        self.command_executor = None
        self.provider: Optional[ChatProvider] = None
        self.provider_name = Config.get_ai_provider()
        self.provider_error: Optional[str] = None

        if self.memory_enabled:
            try:
                self.memory_store = ChromaMemoryStore(
                    embedding_dimension=Config.MEMORY_EMBEDDING_DIM,
                    persist_directory=str(Config.MEMORY_PATH),
                    max_items=Config.MEMORY_MAX_ITEMS,
                )
            except Exception as error: 
                self.memory_store = None
                self.memory_enabled = False
                self.memory_error = str(error)

        self._init_provider(self.provider_name)
        self._init_router()

    def set_command_executor(self, executor) -> None:
        self.command_executor = executor

    def prepare_interaction(self, user_message: str) -> Dict:
        diagnostics: List[str] = []

        decision = self._route(user_message, diagnostics)
        persona_name = decision.persona if decision else "general_chat"
        persona_context = self._build_persona_context(user_message, decision)

        persona = create_persona(persona_name, self)
        result = persona.process(user_message, persona_context)

        self.persona_memory[persona_name] = result.metadata

        return {
            "type": "persona",
            "messages": result.messages,
            "decision": decision,
            "diagnostics": diagnostics,
            "renderable": result.renderable,
            "metadata": result.metadata,
            "persona": persona_name,
        }

    def _route(self, user_message: str, diagnostics: List[str]) -> Optional[RouterDecision]:
        if not self.router_enabled:
            diagnostics.append("[yellow]Router disabled via configuration; defaulting to general_chat.[/yellow]")
            return None

        if not self.router:
            diagnostics.append("[yellow]Router unavailable, defaulting to general_chat.[/yellow]")
            if self.router_error:
                diagnostics.append(f"[red]Router error:[/red] {self.router_error}")
            return None

        diagnostics.append("[cyan]Advanced Router analyzing intent (LLM-based)...[/cyan]")
        try:
            decision = self.router.route(user_message, self.context_manager.conversation_history)
        except Exception as error: 
            diagnostics.append(f"[red]Router error:[/red] {error}")
            return None

        if decision:
            diagnostics.append(
                f"[green]LLM Decision:[/green] {decision.persona} (confidence: {decision.confidence:.2f})"
            )
            if decision.reasoning:
                diagnostics.append(f"[dim]   Reasoning: {decision.reasoning}[/dim]")

        self._append_router_debug_info(diagnostics, decision)

        if decision and decision.confidence < 0.5:
            diagnostics.append("[yellow]Confidence low, fallback ke general_chat.[/yellow]")
            return None

        return decision

    def _build_persona_context(self, user_message: str, decision: Optional[RouterDecision]) -> Dict:
        shell_context = self.context_manager.build_context_for_ai()
        memory_snippets = self._retrieve_memory_snippets(user_message)

        metadata_bundle = {
            "decision": decision,
            "query": decision.query if decision else None,
            "shell_context": shell_context,
            "memory_snippets": memory_snippets,
            "supplemental_text": self._collect_persona_metadata_text(),
            "metadata": self.persona_memory.copy(),
        }
        return metadata_bundle

    def _collect_persona_metadata_text(self) -> str:
        supplemental = []
        for meta in self.persona_memory.values():
            if meta.get("results"):
                supplemental.append(meta["results"])

        return "\n\n".join(supplemental)

    def complete(self, messages: List[dict], max_tokens: int = 1024) -> str:
        provider = self._require_provider()
        return provider.complete(messages, max_tokens=max_tokens)

    def run_shell_command(self, command: str) -> Dict[str, str | int]:
        shell_env = os.environ.copy()
        shell_kwargs = {}
        if os.name != "nt":
            shell_kwargs["executable"] = Config.get_shell()

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                env=shell_env,
                **shell_kwargs,
            )
        except Exception as error:  
            output = f"Command error: {error}"
            self.context_manager.add_shell_context(command, output)
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": output,
            }

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = (stdout + stderr).strip() or f"Exit code {result.returncode}"
        self.context_manager.add_shell_context(command, combined)

        if self.command_executor:
            try:
                self.command_executor._update_completion_if_needed(command)  
            except Exception:
                pass

        if self.memory_enabled and self.memory_store:
            try:
                self.memory_store.add_interaction(
                    content=f"Command: {command}\nOutput: {combined[:2000]}",
                    metadata={
                        "type": "shell_persona",
                        "cwd": os.getcwd(),
                    },
                )
            except Exception:
                pass

        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    def create_stream(self, messages: List[dict]) -> Generator[str, None, None]:
        provider = self._require_provider()
        yield from provider.stream(messages)

    def store_conversation(self, user_message: str, ai_response: str) -> None:
        self.context_manager.add_conversation(user_message, ai_response)
        if self.memory_enabled and self.memory_store:
            try:
                self.memory_store.add_interaction(
                    content=f"User: {user_message}\nAssistant: {ai_response}",
                    metadata={
                        "type": "conversation",
                        "cwd": self.context_manager.current_directory,
                    },
                )
            except Exception:
                pass

    def add_shell_memory(self, command: str, output: str, cwd: str) -> None:
        if not self.memory_enabled or not self.memory_store:
            return

        try:
            content = f"Command: {command}\nOutput: {output.strip()[:2000]}"
            self.memory_store.add_interaction(
                content=content,
                metadata={
                    "type": "shell",
                    "cwd": cwd,
                },
            )
        except Exception:
            pass

    def _retrieve_memory_snippets(self, user_message: str) -> List:
        if not self.memory_enabled or not self.memory_store:
            return []

        try:
            return self.memory_store.similarity_search(
                query=user_message,
                top_k=self.memory_top_k,
            )
        except Exception:
            return []

    def _init_provider(self, preferred: Optional[str] = None) -> None:
        target = preferred or Config.get_ai_provider()
        try:
            self.provider = create_provider(target, fireworks_api_key=self.api_key)
            self.provider_name = self.provider.name
            self.provider_error = None
        except Exception as error:  
            self.provider = None
            self.provider_name = target
            self.provider_error = str(error)

    def _init_router(self, preferred_provider: Optional[str] = None) -> None:
        if not self.router_enabled:
            self.router = None
            self.router_error = None
            self.router_provider_name = None
            return

        target_provider = self._resolve_router_provider(
            preferred_provider or self.provider_name
        )
        self.router_provider_name = target_provider

        try:
            self.router = create_router(
                self.api_key,
                preferred_provider=target_provider,
            )
            self.router_error = None
        except Exception as error:  
            self.router = None
            self.router_error = str(error)

    def _resolve_router_provider(self, preferred: Optional[str]) -> Optional[str]:
        env_value = os.getenv("HYBRIDSHELL_ROUTER_PROVIDER")
        if env_value is not None:
            normalized = env_value.strip().lower()
            if normalized not in {"", "auto", "same"}:
                return normalized
            return preferred

        configured = (getattr(Config, "ROUTER_AI_PROVIDER", "") or "").strip().lower()
        if not configured or configured in {"auto", "same"}:
            return preferred

        if (
            configured == Config.DEFAULT_AI_PROVIDER
            and preferred
            and preferred != Config.DEFAULT_AI_PROVIDER
        ):
            return preferred

        return configured

    def _append_router_debug_info(
        self,
        diagnostics: List[str],
        decision: Optional[RouterDecision],
    ) -> None:
        if not Config.is_router_debug_enabled():
            return

        raw_payload: Optional[str] = None
        if decision and decision.raw_response:
            raw_payload = decision.raw_response
        elif self.router and getattr(self.router, "last_raw_response", None):
            raw_payload = self.router.last_raw_response

        provider_label = (
            self.router_provider_name
            or getattr(getattr(self.router, "provider", None), "name", None)
            or "unknown"
        )

        if not raw_payload:
            diagnostics.append(
                f"[dim]Router debug ({provider_label}): (no raw response captured)[/dim]"
            )
            return

        diagnostics.append(
            f"[dim]Router raw response ({provider_label}): {self._format_router_debug(raw_payload)}[/dim]"
        )

    def _format_router_debug(self, raw_text: str, limit: int = 1200) -> str:
        if not raw_text:
            return "<empty>"

        text = raw_text.strip()
        if not text:
            return "<empty>"

        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, ensure_ascii=False)
        except Exception:
            pass

        if len(text) > limit:
            return text[: limit - 3] + "..."
        return text

    def _require_provider(self) -> ChatProvider:
        if not self.provider:
            message = self.provider_error or "AI provider unavailable."
            raise RuntimeError(message)
        return self.provider

    def set_provider(self, provider_name: str) -> Tuple[bool, str]:
        self._init_provider(provider_name)
        if self.provider:
            self._init_router(self.provider.name)
            return True, self.provider.name
        return False, self.provider_error or "Unknown provider error"

    def get_provider_status(self) -> Dict[str, Optional[str]]:
        return {
            "provider": self.provider_name,
            "error": self.provider_error,
        }

    def set_memory_enabled(self, enabled: bool) -> bool:
        self.memory_error = None

        if enabled:
            if not self.memory_store:
                try:
                    self.memory_store = ChromaMemoryStore(
                        embedding_dimension=Config.MEMORY_EMBEDDING_DIM,
                        persist_directory=str(Config.MEMORY_PATH),
                        max_items=Config.MEMORY_MAX_ITEMS,
                    )
                except Exception as error: 
                    self.memory_store = None
                    self.memory_error = str(error)
            self.memory_enabled = self.memory_store is not None
        else:
            self.memory_enabled = False
        return self.memory_enabled

    def set_memory_top_k(self, value: int) -> int:
        value = max(1, min(50, value))
        self.memory_top_k = value
        return self.memory_top_k

    def reload_configuration(self) -> None:
        self.api_key = Config.get_api_key() or self.api_key
        self.provider_name = Config.get_ai_provider()
        self.memory_top_k = Config.MEMORY_TOP_K
        desired_memory_enabled = Config.MEMORY_ENABLED
        self.memory_error = None

        if desired_memory_enabled:
            need_new_store = self.memory_store is None
            current_path = getattr(self.memory_store, "storage_path", None) if self.memory_store else None
            if current_path and str(current_path) != str(Config.MEMORY_PATH):
                need_new_store = True

            if need_new_store:
                try:
                    self.memory_store = ChromaMemoryStore(
                        embedding_dimension=Config.MEMORY_EMBEDDING_DIM,
                        persist_directory=str(Config.MEMORY_PATH),
                        max_items=Config.MEMORY_MAX_ITEMS,
                    )
                except Exception as error:  
                    self.memory_store = None
                    self.memory_enabled = False
                    self.memory_error = str(error)
            self.memory_enabled = self.memory_store is not None
        else:
            self.memory_enabled = False
            self.memory_store = None

        self.router_enabled = Config.is_router_enabled()
        self._init_provider(Config.get_ai_provider())
        self._init_router()

    def get_memory_stats(self) -> dict:
        stats = {
            "configured": Config.MEMORY_ENABLED,
            "enabled": self.memory_enabled,
            "available": self.memory_store is not None,
            "top_k": self.memory_top_k,
            "max_items": Config.MEMORY_MAX_ITEMS,
            "path": str(Config.MEMORY_PATH),
            "count": 0,
            "error": self.memory_error,
        }

        if self.memory_store:
            try:
                stats["count"] = self.memory_store.count()
                stats["path"] = self.memory_store.storage_path
            except Exception:
                stats["count"] = -1

        return stats

    def clear_memory(self) -> bool:
        if not self.memory_store:
            return False

        try:
            self.memory_store.clear()
            return True
        except Exception:
            return False

    def _format_search_results(self, payload: Dict) -> str:
        results = payload.get("organic_results", [])[:8]
        if not results:
            return "(no results)"

        lines: List[str] = []
        for item in results:
            title = item.get("title", "Untitled")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            domain = item.get("domain", "")
            date = item.get("date")
            bullet = f"- Title: {title}\n  Domain: {domain}"
            if date:
                bullet += f" | Date: {date}"
            bullet += f"\n  Summary: {snippet}\n  Link: {link}"
            lines.append(bullet)

        return "\n\n".join(lines)

    def record_interaction(self, user_message: str, ai_response: str, interaction: Dict) -> None:
        if not ai_response:
            return

        self.store_conversation(user_message, ai_response)

        if (
            interaction.get("persona") == "search_service"
            and self.memory_enabled
            and self.memory_store
            and interaction.get("metadata")
        ):
            formatted = interaction["metadata"].get("results") or ""
            try:
                self.memory_store.add_interaction(
                    content=(
                        f"Search query: {user_message}\n"
                        f"Results:\n{formatted}\n\nSummary:\n{ai_response}"
                    ),
                    metadata={
                        "type": "search",
                        "cwd": self.context_manager.current_directory,
                    },
                )
            except Exception:
                pass
