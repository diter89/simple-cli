#!/usr/bin/env python3

import json
from typing import Generator, List

import requests

from ...config import Config
from .base import ChatProvider


class GeminiProvider(ChatProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = Config.GEMINI_API_BASE_URL.rstrip("/")

    def _build_contents(self, messages: List[dict]) -> List[dict]:
        contents: List[dict] = []
        for message in messages:
            role = message.get("role", "user")
            text = message.get("content", "")
            if not text:
                continue

            if role == "assistant":
                gemini_role = "model"
            else:
                gemini_role = "user"
                if role == "system":
                    text = f"System: {text}"

            contents.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": text}],
                }
            )
        return contents

    def _extract_text(self, payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        collected = []
        for part in parts:
            part_text = part.get("text")
            if part_text:
                collected.append(part_text)
        return "".join(collected)

    def stream(self, messages: List[dict]) -> Generator[str, None, None]:
        contents = self._build_contents(messages)
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"contents": contents},
            stream=True,
            timeout=Config.API_TIMEOUT,
        )
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data: "):
                continue

            data_str = line[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue

            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            text = self._extract_text(payload)
            if text:
                yield text

    def complete(self, messages: List[dict], max_tokens: int = 1024) -> str:
        contents = self._build_contents(messages)
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"contents": contents},
            timeout=Config.API_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        return self._extract_text(payload)
