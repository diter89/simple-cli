#!/usr/bin/env python3

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..config import Config
from .providers import ChatProvider, create_provider


ROUTER_INSTRUCTIONS = """
You are an expert router. Choose the best tool. Always return strict JSON with fields:
{"intent": "...", "confidence": 0.0, "reasoning": "...", "suggested_query": "..."}

VALID INTENTS:
- GENERAL_CHAT
- SEARCH_SERVICE
- HELP_ASSISTENT

NOTES:
- Use SEARCH_SERVICE ONLY when the user explicitly asks for web lookups, latest info, prices, news, or phrases like "find", "get me", "latest info", "price", "news".
- Use GENERAL_CHAT for explanations, code samples, theory, or questions solvable without fresh web data.
- Use HELP_ASSISTENT when the user requests navigating the local project, reading many files, running multiple shell commands in sequence, or needs structured code analysis (planner + execution).
- suggested_query for SEARCH_SERVICE must be a clean search string (no extra comments).
- Confidence range 0-1. No markdown, code fences, or extra keys.
"""


@dataclass
class RouterDecision:
    persona: str
    query: Optional[str]
    confidence: float
    reasoning: str
    use_context: bool = False
    previous_results: Optional[str] = None
    raw_response: Optional[str] = None


class AdvancedRouter:
    def __init__(self, provider: ChatProvider) -> None:
        self.provider = provider
        self.last_search_context: Optional[str] = None
        self.last_raw_response: Optional[str] = None

    def route(self, user_input: str, conversation_history: List[Dict]) -> RouterDecision:
        context_text, has_search_results = self._extract_context(conversation_history)
        decision = self._classify_intent(user_input, context_text, has_search_results)

        if decision and decision.confidence >= 0.6:
            return decision

        fallback_reason = "Fallback: router confidence too low"
        raw_payload = self.last_raw_response

        if decision:
            fallback_reason = decision.reasoning or fallback_reason
            raw_payload = decision.raw_response or raw_payload

        return RouterDecision(
            persona="general_chat",
            query=user_input,
            confidence=0.5,
            reasoning=fallback_reason,
            raw_response=raw_payload,
        )

    def _extract_context(self, messages: List[Dict]) -> Tuple[str, bool]:
        if not messages:
            return "", False

        relevant = [msg for msg in messages if msg.get("role") != "system"][-8:]
        parts: List[str] = []
        has_search_results = False

        for msg in relevant:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content") or ""

            if msg.get("role") == "assistant" and any(
                marker in content
                for marker in (
                    "Source:",
                    "Sumber:",
                    "# Key Points",
                    "Web Page Summary",
                    "Address Analysis",
                    "```",
                )
            ):
                has_search_results = True
                self.last_search_context = content

            snippet = content if len(content) <= 240 else f"{content[:240]}..."
            parts.append(f"{role}: {snippet}")

        return "\n".join(parts), has_search_results

    def _classify_intent(
        self,
        user_input: str,
        context: str,
        has_search_results: bool,
    ) -> Optional[RouterDecision]:
        prompt = self._build_prompt(user_input, context)
        response = self._call_router_model(prompt)
        self.last_raw_response = response

        if not response:
            return None

        try:
            payload = self._sanitize_router_response(response)
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None

        intent = data.get("intent", "GENERAL_CHAT")
        confidence = float(data.get("confidence", 0.5))
        reasoning = data.get("reasoning", "")
        suggested_query = data.get("suggested_query", user_input)

        tool_map = {
            "SEARCH_SERVICE": "search_service",
            "GENERAL_CHAT": "general_chat",
            "HELP_ASSISTENT": "help_assistent",
        }
        use_context = False
        previous_results = None
        query = suggested_query.strip() or user_input

        if intent == "GENERAL_CHAT":
            query = user_input
        elif intent == "SEARCH_SERVICE":
            query = suggested_query.strip() or user_input
        elif intent == "HELP_ASSISTENT":
            query = user_input

        return RouterDecision(
            persona=tool_map.get(intent, "general_chat"),
            query=query,
            confidence=confidence,
            reasoning=reasoning,
            use_context=use_context,
            previous_results=previous_results,
            raw_response=response,
        )

    def _sanitize_router_response(self, text: str) -> str:
        if not text:
            return ""

        cleaned = text.strip()
        if not cleaned:
            return ""

        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1 :]
            cleaned = cleaned.rstrip()
            if cleaned.endswith("```"):
                cleaned = cleaned[: -3]
        return cleaned.strip()

    def _build_prompt(self, user_input: str, context: str) -> str:
        context_block = context or "(empty)"
        return (
            f"{ROUTER_INSTRUCTIONS}\n\n"
            f"CONVERSATION CONTEXT:\n---\n{context_block}\n---\n\n"
            f'CURRENT USER INPUT:\n"{user_input}"'
        )

    def _call_router_model(self, prompt: str) -> Optional[str]:
        messages = [
            {
                "role": "system",
                "content": "You are a precise intent classifier. Always answer with JSON.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            return self.provider.complete(messages, max_tokens=512)
        except Exception:
            return None


def create_router(
    default_fireworks_api_key: Optional[str] = None,
    preferred_provider: Optional[str] = None,
) -> AdvancedRouter:
    provider = create_provider(
        preferred=preferred_provider or Config.get_router_provider(),
        fireworks_api_key=default_fireworks_api_key,
        fireworks_model=Config.get_router_model(),
        gemini_model=Config.get_gemini_router_model(),
    )
    return AdvancedRouter(provider)
