#!/usr/bin/env python3

import json
import os
from datetime import datetime
from typing import List, Optional

from ..config import Config
from ..environment import get_all_env_info


class ContextManager:
    def __init__(self) -> None:
        self.shell_context: List[dict] = []
        self.conversation_history: List[dict] = []

    def add_shell_context(self, command: str, output: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        context_entry = {
            "timestamp": timestamp,
            "command": command,
            "output": output,
            "cwd": os.getcwd(),
            "epoch_time": datetime.now().timestamp(),
        }
        self.shell_context.append(context_entry)

        if len(self.shell_context) > Config.MAX_SHELL_CONTEXT:
            self.shell_context.pop(0)

    def build_context_for_ai(self) -> str:
        if not self.shell_context:
            return ""

        recent_contexts = sorted(
            self.shell_context, key=lambda x: x.get("epoch_time", 0), reverse=True
        )

        context_parts = ["Recent shell activity (prioritized by recency):"]

        priority_contexts = recent_contexts[:3]
        if priority_contexts:
            context_parts.append("\n MOST RECENT COMMANDS:")
            for i, entry in enumerate(priority_contexts):
                priority_marker = ">>> LATEST:" if i == 0 else f">>> #{i + 1}:"
                context_parts.append(
                    f"\n{priority_marker} [{entry['timestamp']}] In: {entry['cwd']}"
                )
                context_parts.append(f"Command: {entry['command']}")

                if entry["output"]:
                    output = entry["output"]
                    max_length = 800 if i == 0 else 400
                    command_parts = entry["command"].strip().split()
                    base_command = command_parts[0] if command_parts else ""
                    if base_command in {"cat", "bat", "batcat", "type"}:
                        max_length = 4000 if i == 0 else 1500
                    if len(output) > max_length:
                        output = output[:max_length] + "... (truncated)"
                    context_parts.append(f"Output: {output}")
                context_parts.append("-" * 50)

        older_contexts = recent_contexts[3 : Config.CONTEXT_FOR_AI]
        if older_contexts:
            context_parts.append("\n ADDITIONAL CONTEXT (older commands):")
            for entry in older_contexts:
                context_parts.append(
                    f"[{entry['timestamp']}] {entry['command']} -> {entry['output'][:100]}..."
                )

        context_parts.append(
            "\n NOTE: When user asks about errors or issues, prioritize the LATEST/MOST RECENT commands above."
        )

        return "\n".join(context_parts)

    def get_latest_command_context(self) -> Optional[dict]:
        if not self.shell_context:
            return None

        recent_contexts = sorted(
            self.shell_context, key=lambda x: x.get("epoch_time", 0), reverse=True
        )
        return recent_contexts[0]

    def add_conversation(self, user_message: str, ai_response: str) -> None:
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": ai_response})

        if len(self.conversation_history) > Config.MAX_CONVERSATION_HISTORY:
            self.conversation_history = self.conversation_history[
                -Config.MAX_CONVERSATION_HISTORY :
            ]

    def clear_context(self) -> None:
        self.shell_context = []

    def clear_conversation(self) -> None:
        self.conversation_history = []

    def clear_all(self) -> None:
        self.clear_context()
        self.clear_conversation()

    def save_history(self, filepath: str | None = None) -> None:
        if filepath is None:
            filepath = Config.HISTORY_FILE

        try:
            Config.ensure_directories()
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(self.conversation_history, file, indent=2)
        except Exception as error:
            print(f"Failed to save history: {error}")

    def load_history(self, filepath: str | None = None) -> None:
        if filepath is None:
            filepath = Config.HISTORY_FILE

        try:
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as file:
                    self.conversation_history = json.load(file)
        except Exception as error:
            print(f"Failed to load history: {error}")
            self.conversation_history = []


class EnhancedContextManager(ContextManager):
    def build_context_for_ai(self) -> str:
        context_parts: List[str] = []

        env_info = get_all_env_info()
        if any(env_info.values()):
            context_parts.append(" CURRENT ENVIRONMENT:")

            if env_info.get("python"):
                py_env = env_info["python"]
                context_parts.append(
                    f"Python: {py_env['display']} (v{py_env['python_version']}) - {py_env['type']}"
                )

            if env_info.get("git"):
                git_info = env_info["git"]
                status = "clean" if not git_info.get("has_changes") else "modified"
                ahead_behind = ""
                if git_info.get("ahead", 0) > 0:
                    ahead_behind += f" ↑{git_info['ahead']}"
                if git_info.get("behind", 0) > 0:
                    ahead_behind += f" ↓{git_info['behind']}"
                context_parts.append(
                    f"Git: branch '{git_info['branch']}' ({status}){ahead_behind}"
                )

            if env_info.get("node"):
                node_info = env_info["node"]
                context_parts.append(
                    f"Node.js: {node_info['name']} v{node_info['version']}"
                )

            if env_info.get("docker"):
                docker_info = env_info["docker"]
                context_parts.append(f"Docker: {docker_info['display']}")

            context_parts.append("-" * 60)

        shell_context = super().build_context_for_ai()
        if shell_context:
            context_parts.append(shell_context)

        return "\n".join(context_parts)
