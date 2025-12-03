# Simple-cli

**Simple-cli** is a shell wrapper that combines a traditional shell with AI.

Experimental / Toy Project | **License:** MIT (use/modify freely, no restrictions)  
**As-is:** No warranty, no support

## Installation

```bash
pip install .
```

## Configuration

To enable AI features, you need to set the appropriate API key as an environment variable.

```bash
export FIREWORKS_API_KEY="your_api_key" (optional)
export GEMINI_API_KEY="your_api_key" (optional)
```

## Binary

```bash
# Download from releases

```

## Key Bindings

| Key | Action |
|-----|--------|
| `Ctrl+A` | AI mode |
| `Ctrl+S` | Shell mode |
| `Alt+H` | Help |
| `Alt+C` | Clear |
| `Ctrl+C` | Exit |

## Structure

```
.
├── __init__.py
├── app.py              # Main application setup and initialization
├── cli.py              # Entry point for the command-line interface (CLI)
├── commands
│   ├── __init__.py
│   └── executor.py     # Handles execution of shell commands (ls, cd, etc.)
├── completion.py       # Manages command and path auto-completion
├── config.py           # Central configuration for the entire application
├── context
│   ├── __init__.py
│   ├── manager.py      # Manages shell context and conversation history
│   └── memory.py       # Provides long-term, searchable memory via ChromaDB
├── core
│   ├── __init__.py
│   ├── ai.py           # Core AI logic; manages providers, router, and personas
│   ├── hybrid_shell.py # The main orchestrator; combines shell and AI modes
│   ├── providers
│   │   ├── __init__.py
│   │   ├── base.py     # Defines the interface for all AI providers
│   │   ├── fireworks.py# Implements connection to the Fireworks AI API
│   │   └── gemini.py   # Implements connection to the Google Gemini API
│   └── router.py       # Decides which AI persona should handle a user's request
├── customization.py    # Simple API for customizing the shell's components
├── environment.py      # Detects the user's environment (Git, Python, etc.)
├── persona
│   ├── __init__.py
│   ├── base.py         # Defines the interface for all AI personas
│   ├── general_chat.py # Persona for simple Q&A conversations
│   ├── help_assistent.py # Advanced AI agent that can plan and execute commands
│   ├── registry.py     # Manages the available personas
│   ├── search_service.py # Persona for performing web searches
│   └── web_search.py   # Handles the web search execution logic
└── ui
    ├── __init__.py
    ├── highlighter.py  # Provides custom syntax highlighting
    ├── manager.py      # Manages static UI elements (prompts, panels, tables)
    ├── streaming.py    # Manages live, streaming display of AI and shell output
    └── theme.py        # Defines the visual theme (colors, styles) for UI panels
```

## Screenshots
