#!/usr/bin/env python3
from __future__ import annotations
from rich.console import Console
from .context import ContextManager, EnhancedContextManager
from .ui import (
    LiveMarkdownStreamRenderer,
    StreamingContentRenderer,
    StreamingUIManager,
    UIManager,
)

__all__ = [
    "UIManager",
    "LiveMarkdownStreamRenderer",
    "StreamingContentRenderer",
    "StreamingUIManager",
    "ContextManager",
    "EnhancedContextManager",
    "create_streaming_api_generator",
    "create_enhanced_ui_manager",
    "create_enhanced_context_manager",
]


def create_streaming_api_generator(api_response_iterator):

    for chunk in api_response_iterator:
        if chunk:
            yield chunk


def create_enhanced_ui_manager(console: Console, use_environment_context: bool = True) -> UIManager:  

    return UIManager(console)


def create_enhanced_context_manager() -> EnhancedContextManager:

    return EnhancedContextManager()
