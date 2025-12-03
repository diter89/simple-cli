#!/usr/bin/env python3

from typing import Dict 
from .base import BasePersona, PersonaResult


class GeneralChatPersona(BasePersona):
    name = "general_chat"

    def process(self, user_message: str, context: Dict) -> PersonaResult:
        supplemental = context.get("supplemental_text", "")
        shell_context = context.get("shell_context")
        memory_snippets = context.get("memory_snippets") or []

        system_message = (
            "You are a helpful AI assistant integrated with the shell. "
            "Answer concisely and mirror the user's language."
        )

        if shell_context:
            system_message += (
                "\n\nLatest shell context:"
                f"\n{shell_context}"
            )

        if supplemental:
            system_message += (
                "\n\nUse the following supplemental information when relevant:"
                f"\n---\n{supplemental}\n---"
            )

        messages = [{"role": "system", "content": system_message}]

        if memory_snippets:
            joined_snippets = "\n".join(
                [f"- {snippet.metadata.get('type','unknown')}: {snippet.content}" for snippet in memory_snippets]
            )
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Relevant memory for context-aware answer:\n"
                        f"{joined_snippets}"
                    ),
                }
            )

        messages.extend(self.ai_manager.context_manager.conversation_history)
        messages.append({"role": "user", "content": user_message})

        return PersonaResult(messages=messages, metadata={})
