#!/usr/bin/env python3
from typing import Optional

from ...config import Config
from .base import ChatProvider
from .fireworks import FireworksProvider
from .gemini import GeminiProvider


def create_provider(
    preferred: Optional[str] = None,
    fireworks_api_key: Optional[str] = None,
    fireworks_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
) -> ChatProvider:
    provider_name = (preferred or Config.get_ai_provider()).lower()

    if provider_name == "gemini":
        api_key = Config.get_gemini_api_key()
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please export the environment variable before selecting the Gemini provider."
            )
        model = gemini_model or Config.get_gemini_model()
        return GeminiProvider(api_key=api_key, model=model)

    api_key = fireworks_api_key or Config.get_api_key()
    if not api_key:
        raise ValueError(
            "FIREWORKS_API_KEY is not set. Please export the environment variable or switch providers."
        )
    model = fireworks_model or Config.get_model_name()
    return FireworksProvider(api_key=api_key, model=model)


__all__ = [
    "ChatProvider",
    "create_provider",
]
