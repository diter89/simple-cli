#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Generator, Iterable, List


class ChatProvider(ABC):
    name: str

    @abstractmethod
    def stream(self, messages: List[dict]) -> Generator[str, None, None]:
        """Yield response chunks for the provided conversation messages."""

    @abstractmethod
    def complete(self, messages: List[dict], max_tokens: int = 1024) -> str:
        """Return a non-streaming completion for the given conversation messages."""


def iter_text_chunks(chunks: Iterable[str]):
    for chunk in chunks:
        if chunk:
            yield chunk
