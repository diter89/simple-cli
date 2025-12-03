#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PersonaResult:
    messages: List[dict]
    metadata: Dict
    renderable: Optional[object] = None

class BasePersona:
    name: str = "base"

    def __init__(self, ai_manager) -> None:
        self.ai_manager = ai_manager

    def process(self, user_message: str, context: Dict) -> PersonaResult: 
        raise NotImplementedError
