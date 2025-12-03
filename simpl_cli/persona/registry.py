#!/usr/bin/env python3

from typing import Dict, Type
from .base import BasePersona
from .general_chat import GeneralChatPersona
from .help_assistent import HelpAssistentPersona
from .web_search import WebSearchPersona


PERSONA_CLASSES: Dict[str, Type[BasePersona]] = {
    "general_chat": GeneralChatPersona,
    "search_service": WebSearchPersona,
    "help_assistent": HelpAssistentPersona,
}


def create_persona(name: str, ai_manager) -> BasePersona:
    persona_cls = PERSONA_CLASSES.get(name, GeneralChatPersona)
    return persona_cls(ai_manager)
