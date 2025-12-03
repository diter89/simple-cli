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

## Binary Download (x86_64)

1. Download `simple-cli-x86_64.zip` from the release page: (https://github.com/diter89/simple-cli/releases/tag/x86_64).
2. Extract the archive:
   ```bash
   unzip simple-cli-x86_64.zip
   ```
3. Make sure the binary is executable (usually already is):
   ```bash
   chmod +x simple-cli-x86_64
   ```
4. Run HybridShell:
   ```bash
   sudo mandb
   ./simple-cli-x86_64
   ```

The first launch creates `~/.simple_cli/config.ini`; tweak that file to customize prompts, styles, and command behavior without rebuilding the binary.

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
<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-00-11" src="https://github.com/user-attachments/assets/bc424804-e17c-4fe6-965b-ea92a5095a83" />
<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-06-40" src="https://github.com/user-attachments/assets/b4c52698-5bc5-4838-8d4a-dc019836cf57" />
<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-19-32" src="https://github.com/user-attachments/assets/b97096cc-e8f0-4ff0-bfac-d84f61b08138" />
<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-23-55" src="https://github.com/user-attachments/assets/b3463f86-ad0c-4ab2-9662-f5816cdcac35" />



<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-00-52" src="https://github.com/user-attachments/assets/32e4facc-8c4c-4e06-854c-b76d80a35d1f" />

<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-03-01" src="https://github.com/user-attachments/assets/9e0b9b0f-ed53-41cf-b953-1e3060ffaba5" />

<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-15-25" src="https://github.com/user-attachments/assets/aeedab54-03aa-40c9-b9aa-26b533e01d98" />
<img width="1362" height="748" alt="Screenshot from 2025-12-03 12-18-01" src="https://github.com/user-attachments/assets/eb8d01bc-d8cd-4761-ab85-493626c0d860" />
