#!/usr/bin/env python3

from datetime import datetime
from typing import Dict
from rich.tree import Tree
from .base import BasePersona, PersonaResult


class WebSearchPersona(BasePersona):
    name = "search_service"

    def process(self, user_message: str, context: Dict) -> PersonaResult:
        query = context.get("query") or user_message
        search_payload = self.ai_manager.search_service.search(query)
        tree = self._build_tree(search_payload)

        current_time = datetime.now().strftime("%d %B %Y %H:%M %Z")
        results_text = self.ai_manager._format_search_results(search_payload)

        system_prompt = (
            "You are persona search_service. Summarize web search results concisely, "
            "respond in the user's language (default English), and close with a 'Sources' section."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Original request: {user_message}\n"
                    f"Search query: {query}\n"
                    f"Current time: {current_time}\n\n"
                    f"Search results:\n{results_text}\n\n"
                    "Provide bulleted highlights, key insights, and end with a sources list. "
                    "Use the helpful information above when relevant."
                ),
            },
        ]

        metadata = {"type": "search", "results": results_text}
        return PersonaResult(messages=messages, metadata=metadata, renderable=tree)

    def _build_tree(self, payload: Dict) -> Tree:
        tree = Tree("[bold blue]Search Results[/bold blue]")

        if payload.get("status") != "success":
            tree.add(f"[red]Search failed:[/red] {payload.get('message', 'Unknown error')}")
            return tree

        results = payload.get("organic_results", [])
        if not results:
            tree.add("No results")
            return tree

        for item in results[:8]:
            title = item.get("title", "Untitled")
            domain = item.get("domain", "")
            label = f"[bold]{title}[/bold]"
            if domain:
                label += f" [dim]({domain})[/dim]"

            node = tree.add(label)
            if item.get("date"):
                node.add(f"[green]Date:[/green] {item['date']}")
            if item.get("snippet"):
                node.add(item["snippet"])
            if item.get("link"):
                node.add(f"[cyan]{item['link']}[/cyan]")

        latency = payload.get("searchParameters", {}).get("latency_ms")
        if latency is not None:
            tree.add(f"[dim]Latency: {latency} ms[/dim]")

        return tree
