#!/usr/bin/env python3

import json
from typing import Generator, List

import requests

from ...config import Config
from .base import ChatProvider


class FireworksProvider(ChatProvider):
    name = "fireworks"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = Config.API_BASE_URL

    def _build_payload(self, messages: List[dict], stream: bool) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        payload.update(Config.AI_CONFIG)
        return payload

    def stream(self, messages: List[dict]) -> Generator[str, None, None]:
        payload = self._build_payload(messages, stream=True)
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        response = requests.post(
            self.endpoint,
            headers=headers,
            data=json.dumps(payload),
            stream=True,
            timeout=Config.API_TIMEOUT,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode("utf-8")
            if not line_str.startswith("data: "):
                continue

            json_str = line_str[6:]
            if json_str.strip() == "[DONE]":
                break

            try:
                chunk_data = json.loads(json_str)
            except json.JSONDecodeError:
                continue

            choices = chunk_data.get("choices") or []
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            content = delta.get("content")
            if content:
                yield content

    def complete(self, messages: List[dict], max_tokens: int = 1024) -> str:
        payload = self._build_payload(messages, stream=False)
        payload["max_tokens"] = max_tokens

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        response = requests.post(
            Config.API_BASE_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=Config.API_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""

        return choices[0].get("message", {}).get("content", "")
