#!/usr/bin/env python3
import configparser
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


class Config:
    # Default chat model used when FIREWORKS_MODEL is not provided.
    DEFAULT_API_MODEL = "accounts/fireworks/models/glm-4p6"
    # Fireworks inference endpoint and timeout shared by all personas.
    API_BASE_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
    API_TIMEOUT = 120
    DEFAULT_AI_PROVIDER = "fireworks"
    ROUTER_AI_PROVIDER = DEFAULT_AI_PROVIDER

    ROUTER_ENABLED = True
    ROUTER_DEBUG = False

    # Baseline sampling configuration sent with every completion request.
    AI_CONFIG = {
        "max_tokens": 7000,
        "top_p": 1,
        "top_k": 40,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "temperature": 0.6,
    }

    AI_PROVIDER = DEFAULT_AI_PROVIDER
    GEMINI_MODEL = "gemini-2.5-flash"
    GEMINI_ROUTER_MODEL = GEMINI_MODEL
    GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Vector-memory subsystem configuration for conversation recall.
    MEMORY_ENABLED = True
    MEMORY_TOP_K = 5
    MEMORY_EMBEDDING_DIM = 256
    MEMORY_MAX_ITEMS = 500
    MEMORY_PATH = Path.home() / ".cache" / "hybridshell" / "chroma"

    # Shell configuration
    MAX_SHELL_CONTEXT = 10
    MAX_CONVERSATION_HISTORY = 20
    CONTEXT_FOR_AI = 5

    # Interactive commands that take over the terminal
    INTERACTIVE_COMMANDS = {
        "nano",
        "vim",
        "vi",
        "emacs",
        "mc",
        "htop",
        "top",
        "fzf",
        "less",
        "more",
        "man",
        "tmux",
        "screen",
        "python3",
        "python",
        "node",
        "irb",
        "psql",
        "mysql",
        "nvim",
        "nu",
        "xonsh",
        "apt",
        "sudo",
        "sqlite3",
        "redis-cli",
        "mongo",
        "bash",
        "zsh",
        "fish",
        "jobs",
        "fg",
        "bg",
        "tree",
        "ping",
    }

    # Package manager commands that should stream
    STREAMING_COMMANDS = {
        "apt",
        "apt-get",
        "pip",
        "pip3",
        "npm",
        "pnpm",
        "yarn",
        "poetry",
        "composer",
        "cargo",
        "brew",
        "bundle",
        "go",
        "apk",
        "ping",
    }

    SHELL_STREAM_SUMMARY_PANEL = True
    SHELL_STREAM_OUTPUT_PANEL = True

    # Map file extensions to syntax lexers for Rich rendering.
    SYNTAX_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".fish": "fish",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".xml": "xml",
        ".md": "markdown",
        ".txt": "text",
    }

    SYNTAX_HIGHLIGHT_COMMANDS = ["cat", "head", "tail", "batcat", "bat"]

    LS_COMMANDS = ["ls", "la", "lsd", "ll"]

    FILE_ICONS = {
        "directory": "",
        "file": "",
        "executable": "",
        "symlink": "",
        "image": "",
        "video": "󰕧",
        "audio": "",
        "archive": "",
        "document": "󰷈",
        "code": " ",
    }

    FILE_COLORS = {
        "directory": "bold blue",
        "file": "white",
        "executable": "bold green",
        "symlink": "cyan",
        "image": "magenta",
        "video": "red",
        "audio": "yellow",
        "archive": "bold yellow",
        "document": "blue",
        "code": "green",
        "hidden": "dim white",
    }

    FILE_EXTENSIONS = {
        ".jpg": "image",
        ".jpeg": "image",
        ".png": "image",
        ".gif": "image",
        ".bmp": "image",
        ".svg": "image",
        ".webp": "image",
        ".ico": "image",
        ".mp4": "video",
        ".avi": "video",
        ".mkv": "video",
        ".mov": "video",
        ".wmv": "video",
        ".flv": "video",
        ".webm": "video",
        ".m4v": "video",
        ".mp3": "audio",
        ".wav": "audio",
        ".flac": "audio",
        ".aac": "audio",
        ".ogg": "audio",
        ".m4a": "audio",
        ".wma": "audio",
        ".zip": "archive",
        ".rar": "archive",
        ".7z": "archive",
        ".tar": "archive",
        ".gz": "archive",
        ".bz2": "archive",
        ".xz": "archive",
        ".deb": "archive",
        ".rpm": "archive",
        ".dmg": "archive",
        ".pdf": "document",
        ".doc": "document",
        ".docx": "document",
        ".xls": "document",
        ".xlsx": "document",
        ".ppt": "document",
        ".pptx": "document",
        ".txt": "document",
        ".rtf": "document",
        ".odt": "document",
        ".ods": "document",
        ".odp": "document",
        ".py": "code",
        ".js": "code",
        ".html": "code",
        ".css": "code",
        ".java": "code",
        ".cpp": "code",
        ".c": "code",
        ".h": "code",
        ".php": "code",
        ".rb": "code",
        ".go": "code",
        ".rs": "code",
        ".swift": "code",
        ".kt": "code",
        ".scala": "code",
        ".sh": "code",
        ".bash": "code",
        ".zsh": "code",
        ".fish": "code",
        ".json": "code",
        ".xml": "code",
        ".yaml": "code",
        ".yml": "code",
        ".toml": "code",
        ".ini": "code",
        ".cfg": "code",
        ".conf": "code",
        ".sql": "code",
        ".r": "code",
        ".m": "code",
    }

    REFRESH_RATE = 10

    # Controls whether shell selection is automatic or forced to a user choice.
    CHOICE_DEFAULT_SHELL = "auto"

    # Prompt lexer choice ("auto" disables highlighting, otherwise pygments lexer name).
    CHOICE_PROMPT_LEXER = "auto"

    CONFIG_DIR = Path.home() / ".simple_cli"
    CONFIG_FILE = CONFIG_DIR / "config.ini"
    LOG_FILE = CONFIG_DIR / "shell.log"
    HISTORY_FILE = CONFIG_DIR / "history.json"
    SHELL_HISTORY_FILE = CONFIG_DIR / "shell_history.txt"
    ALIAS_FILE = CONFIG_DIR / "aliases.json"
    COMMANDS_DESC_FILE = CONFIG_DIR / "commands_desc.json"

    WELCOME_MESSAGE = """[green bold]Simple-cli  [/green bold]
Alt+H: help • Ctrl+C: exit
Shell wrapper + AI & bash completion"""

    HELP_KEYBINDS = [
        ("Ctrl+A", "Switch to AI mode"),
        ("Ctrl+S", "Switch to Shell mode"),
        ("Alt+H", "Show this help"),
        ("Alt+C", "Clear context & conversation"),
        ("Ctrl+C", "Exit application"),
    ]

    HELP_SPECIAL_COMMANDS = [
        ("memory clear", "Shell", "Clear memory and reset conversation"),
        ("context", "AI", "Show current shell context"),
        ("exit", "Both", "Exit the shell"),
        ("ai provider <name>", "Shell", "Switch the active AI provider"),
    ]

    PROMPT_STYLES = {
        "left_part": "#c6d0f5",
        "right_part": "#c6d0f5",
        "prompt_padding": "#737994",
        "mode_ai": "#f4b8e4 bold",
        "mode_shell": "#8caaee bold",
        "separator": "#737994",
        "path": "#b5cef8 bold",
        "prompt_symbol": "#f2d5cf bold",
        "clock": "#c6d0f5 bold",
        "status": "#a6d189",
        "prompt_border": "#737994",
        "prompt_os": "#f2d5cf",
        "prompt_folder": "#8caaee bold",
    }

    COMPLETION_STYLES = {
        "completion.menu": "#0a0a0a",
        "scrollbar.background": "bg:#0a7e98 bold",
        "completion-menu.completion": "bg:#0a0a0a fg:#aaaaaa bold",
        "completion-menu.completion fuzzymatch.outside": "#aaaaaa underline",
        "completion-menu.completion fuzzymatch.inside": "fg:#9ece6a bold",
        "completion-menu.completion fuzzymatch.inside.character": "underline bold",
        "completion-menu.completion.current fuzzymatch.outside": "fg:#9ece6a underline",
        "completion-menu.completion.current fuzzymatch.inside": "fg:#f7768e bold",
        "completion-menu.meta.completion": "bg:#0a0a0a fg:#aaaaaa bold",
        "completion-menu.meta.completion.current": "bg:#888888",
    }

    BASH_COMPLETION_FILES = [
        "/usr/share/bash-completion/bash_completion",
        "/etc/bash_completion",
    ]

    BASH_COMPLETION_DIRS = [
        "/usr/share/bash-completion/completions",
        "/etc/bash_completion.d",
    ]

    PANEL_STYLES = {
        "default": {"border_style": "#888888", "padding": (0, 1)},
        "info": {"border_style": "#8caaee", "padding": (0, 1)},
        "success": {"border_style": "#a6d189", "padding": (0, 1)},
        "error": {"border_style": "#e78284", "padding": (0, 1)},
        "warning": {"border_style": "#e5c890", "padding": (0, 1)},
    }

    HIGHLIGHTER_ENABLED = True
    HIGHLIGHTER_RULES = [
        {
            "name": "number",
            "pattern": r"(?P<number>\b\d+(?:\.\d+)?\b)",
            "style": "highlight.number",
        },
        {
            "name": "string",
            "pattern": r"(?P<string>\"[^\"]+\")",
            "style": "highlight.string",
        },
        {
            "name": "ip",
            "pattern": r"(?P<ip>\b\d{1,3}(?:\.\d{1,3}){3}\b)",
            "style": "highlight.ip",
        },
    ]
    HIGHLIGHTER_STYLES = {
        "highlight.number": "bold cyan",
        "highlight.string": "bold green",
        "highlight.ip": "bold magenta",
    }

    DEFAULT_SHELL = (
        "/bin/bash" if os.name != "nt" else os.environ.get("COMSPEC", "cmd.exe")
    )

    @classmethod
    def ensure_directories(cls):
        cls.CONFIG_DIR.mkdir(exist_ok=True)
        if not cls.CONFIG_FILE.exists():
            cls._write_default_config()
        if not cls.SHELL_HISTORY_FILE.exists():
            cls.SHELL_HISTORY_FILE.touch()
        if not cls.ALIAS_FILE.exists():
            cls.ALIAS_FILE.write_text("{}", encoding="utf-8")
        cls._ensure_command_descriptions()

    @classmethod
    def get_api_key(cls):
        return os.getenv("FIREWORKS_API_KEY")

    @classmethod
    def get_model_name(cls):
        return os.getenv("FIREWORKS_MODEL", cls.DEFAULT_API_MODEL)

    @classmethod
    def get_ai_provider(cls) -> str:
        env_value = os.getenv("HYBRIDSHELL_AI_PROVIDER")
        if env_value:
            return env_value.strip().lower()
        return cls.AI_PROVIDER

    @classmethod
    def get_router_provider(cls) -> str:
        env_value = os.getenv("HYBRIDSHELL_ROUTER_PROVIDER")
        if env_value:
            return env_value.strip().lower()
        return cls.ROUTER_AI_PROVIDER

    @classmethod
    def get_router_model(cls):
        return os.getenv("FIREWORKS_ROUTER_MODEL", cls.get_model_name())

    @classmethod
    def is_router_enabled(cls) -> bool:
        env_value = os.getenv("FIREWORKS_ROUTER_ENABLED")
        if env_value is None:
            return cls.ROUTER_ENABLED

        normalized = env_value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    @classmethod
    def is_router_debug_enabled(cls) -> bool:
        env_value = os.getenv("HYBRIDSHELL_ROUTER_DEBUG")
        if env_value is None:
            return cls.ROUTER_DEBUG

        normalized = env_value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    @classmethod
    def get_shell(cls) -> str:
        env_shell = os.getenv("WRAPCLI_SHELL")
        if env_shell:
            return env_shell

        if os.name == "nt":
            return os.getenv("COMSPEC") or cls.DEFAULT_SHELL

        choice_shell = cls._resolve_shell_choice()
        if choice_shell:
            return choice_shell

        return os.getenv("SHELL") or cls.DEFAULT_SHELL

    @classmethod
    def _resolve_shell_choice(cls) -> str | None:
        choice = getattr(cls, "CHOICE_DEFAULT_SHELL", "auto")
        if not choice:
            return None

        normalized = choice.strip()
        if not normalized or normalized.lower() == "auto":
            return None

        expanded = os.path.expanduser(normalized)
        if os.path.isabs(expanded) and os.access(expanded, os.X_OK):
            return expanded

        resolved = shutil.which(normalized)
        if resolved:
            return resolved

        return None

    @classmethod
    def get_prompt_lexer_choice(cls) -> str:
        env_value = os.getenv("HYBRIDSHELL_PROMPT_LEXER")
        if env_value:
            return env_value.strip()
        return getattr(cls, "CHOICE_PROMPT_LEXER", "auto")

    @classmethod
    def get_gemini_api_key(cls) -> str | None:
        return os.getenv("GEMINI_API_KEY")

    @classmethod
    def get_gemini_model(cls) -> str:
        return os.getenv("GEMINI_MODEL", cls.GEMINI_MODEL)

    @classmethod
    def get_gemini_router_model(cls) -> str:
        return os.getenv("GEMINI_ROUTER_MODEL", cls.GEMINI_ROUTER_MODEL)

    @classmethod
    def is_shell_stream_summary_enabled(cls) -> bool:
        env_value = os.getenv("WRAPCLI_SHELL_STREAM_PANEL")
        if env_value is None:
            return cls.SHELL_STREAM_SUMMARY_PANEL

        normalized = env_value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    @classmethod
    def is_shell_stream_output_panel_enabled(cls) -> bool:
        env_value = os.getenv("WRAPCLI_SHELL_STREAM_OUTPUT_PANEL")
        if env_value is None:
            return cls.SHELL_STREAM_OUTPUT_PANEL

        normalized = env_value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    @classmethod
    def is_highlighter_enabled(cls) -> bool:
        env_value = os.getenv("HYBRIDSHELL_HIGHLIGHTER")
        if env_value is not None:
            normalized = env_value.strip().lower()
            if normalized in {"0", "false", "no", "off"}:
                return False
            if normalized in {"1", "true", "yes", "on"}:
                return True
        return cls.HIGHLIGHTER_ENABLED

    # ------------------------------------------------------------------
    # External configuration support (config.ini)
    # ------------------------------------------------------------------

    @classmethod
    def _write_default_config(cls) -> None:
        parser = configparser.ConfigParser()

        parser["general"] = {
            "default_api_model": cls.DEFAULT_API_MODEL,
            "api_base_url": cls.API_BASE_URL,
            "api_timeout": str(cls.API_TIMEOUT),
            "ai_provider": cls.DEFAULT_AI_PROVIDER,
            "router_ai_provider": cls.ROUTER_AI_PROVIDER,
            "router_enabled": str(cls.ROUTER_ENABLED),
            "welcome_message": cls.WELCOME_MESSAGE,
            "refresh_rate": str(cls.REFRESH_RATE),
        }

        parser["ai"] = {
            "ai_config": json.dumps(cls.AI_CONFIG),
        }

        parser["memory"] = {
            "memory_enabled": str(cls.MEMORY_ENABLED),
            "memory_top_k": str(cls.MEMORY_TOP_K),
            "memory_embedding_dim": str(cls.MEMORY_EMBEDDING_DIM),
            "memory_max_items": str(cls.MEMORY_MAX_ITEMS),
            "memory_path": str(cls.MEMORY_PATH),
        }

        parser["shell"] = {
            "max_shell_context": str(cls.MAX_SHELL_CONTEXT),
            "max_conversation_history": str(cls.MAX_CONVERSATION_HISTORY),
            "context_for_ai": str(cls.CONTEXT_FOR_AI),
            "interactive_commands": json.dumps(sorted(cls.INTERACTIVE_COMMANDS)),
            "streaming_commands": json.dumps(sorted(cls.STREAMING_COMMANDS)),
            "shell_stream_summary_panel": str(cls.SHELL_STREAM_SUMMARY_PANEL),
            "shell_stream_output_panel": str(cls.SHELL_STREAM_OUTPUT_PANEL),
            "default_shell": cls.DEFAULT_SHELL,
            "choice_default_shell": cls.CHOICE_DEFAULT_SHELL,
        }

        parser["ui"] = {
            "help_keybinds": json.dumps([list(item) for item in cls.HELP_KEYBINDS]),
            "help_special_commands": json.dumps(
                [list(item) for item in cls.HELP_SPECIAL_COMMANDS]
            ),
            "prompt_styles": json.dumps(cls.PROMPT_STYLES),
            "completion_styles": json.dumps(cls.COMPLETION_STYLES),
            "panel_styles": json.dumps(cls.PANEL_STYLES),
            "highlighter_enabled": str(cls.HIGHLIGHTER_ENABLED),
            "highlighter_rules": json.dumps(cls.HIGHLIGHTER_RULES),
            "highlighter_styles": json.dumps(cls.HIGHLIGHTER_STYLES),
            "choice_prompt_lexer": cls.CHOICE_PROMPT_LEXER,
        }

        parser["syntax"] = {
            "syntax_extensions": json.dumps(cls.SYNTAX_EXTENSIONS),
            "syntax_highlight_commands": json.dumps(cls.SYNTAX_HIGHLIGHT_COMMANDS),
            "ls_commands": json.dumps(cls.LS_COMMANDS),
            "file_icons": json.dumps(cls.FILE_ICONS),
            "file_colors": json.dumps(cls.FILE_COLORS),
            "file_extensions": json.dumps(cls.FILE_EXTENSIONS),
            "bash_completion_files": json.dumps(cls.BASH_COMPLETION_FILES),
            "bash_completion_dirs": json.dumps(cls.BASH_COMPLETION_DIRS),
        }

        parser["providers"] = {
            "gemini_model": cls.GEMINI_MODEL,
            "gemini_router_model": cls.GEMINI_ROUTER_MODEL,
        }

        with cls.CONFIG_FILE.open("w", encoding="utf-8") as config_handle:
            parser.write(config_handle)

    @classmethod
    def _load_external_config(cls) -> None:
        parser = configparser.ConfigParser()

        if not cls.CONFIG_FILE.exists():
            return

        parser.read(cls.CONFIG_FILE, encoding="utf-8")

        cls.DEFAULT_API_MODEL = parser.get(
            "general", "default_api_model", fallback=cls.DEFAULT_API_MODEL
        )
        cls.API_BASE_URL = parser.get(
            "general", "api_base_url", fallback=cls.API_BASE_URL
        )
        cls.API_TIMEOUT = parser.getint(
            "general", "api_timeout", fallback=cls.API_TIMEOUT
        )
        cls.AI_PROVIDER = (
            parser.get("general", "ai_provider", fallback=cls.AI_PROVIDER)
            .strip()
            .lower()
        )
        cls.ROUTER_AI_PROVIDER = (
            parser.get("general", "router_ai_provider", fallback=cls.ROUTER_AI_PROVIDER)
            .strip()
            .lower()
        )
        cls.ROUTER_ENABLED = parser.getboolean(
            "general", "router_enabled", fallback=cls.ROUTER_ENABLED
        )
        cls.WELCOME_MESSAGE = parser.get(
            "general", "welcome_message", fallback=cls.WELCOME_MESSAGE
        )
        cls.REFRESH_RATE = parser.getint(
            "general", "refresh_rate", fallback=cls.REFRESH_RATE
        )

        cls.AI_CONFIG = cls._json_override(parser, "ai", "ai_config", cls.AI_CONFIG)

        cls.MEMORY_ENABLED = parser.getboolean(
            "memory", "memory_enabled", fallback=cls.MEMORY_ENABLED
        )
        cls.MEMORY_TOP_K = parser.getint(
            "memory", "memory_top_k", fallback=cls.MEMORY_TOP_K
        )
        cls.MEMORY_EMBEDDING_DIM = parser.getint(
            "memory", "memory_embedding_dim", fallback=cls.MEMORY_EMBEDDING_DIM
        )
        cls.MEMORY_MAX_ITEMS = parser.getint(
            "memory", "memory_max_items", fallback=cls.MEMORY_MAX_ITEMS
        )
        memory_path = parser.get("memory", "memory_path", fallback=str(cls.MEMORY_PATH))
        cls.MEMORY_PATH = Path(memory_path).expanduser()

        cls.MAX_SHELL_CONTEXT = parser.getint(
            "shell", "max_shell_context", fallback=cls.MAX_SHELL_CONTEXT
        )
        cls.MAX_CONVERSATION_HISTORY = parser.getint(
            "shell", "max_conversation_history", fallback=cls.MAX_CONVERSATION_HISTORY
        )
        cls.CONTEXT_FOR_AI = parser.getint(
            "shell", "context_for_ai", fallback=cls.CONTEXT_FOR_AI
        )
        cls.INTERACTIVE_COMMANDS = set(
            cls._json_override(
                parser, "shell", "interactive_commands", list(cls.INTERACTIVE_COMMANDS)
            )
        )
        cls.STREAMING_COMMANDS = set(
            cls._json_override(
                parser, "shell", "streaming_commands", list(cls.STREAMING_COMMANDS)
            )
        )
        cls.SHELL_STREAM_SUMMARY_PANEL = parser.getboolean(
            "shell",
            "shell_stream_summary_panel",
            fallback=cls.SHELL_STREAM_SUMMARY_PANEL,
        )
        cls.SHELL_STREAM_OUTPUT_PANEL = parser.getboolean(
            "shell", "shell_stream_output_panel", fallback=cls.SHELL_STREAM_OUTPUT_PANEL
        )
        cls.DEFAULT_SHELL = parser.get(
            "shell", "default_shell", fallback=cls.DEFAULT_SHELL
        )
        cls.CHOICE_DEFAULT_SHELL = parser.get(
            "shell", "choice_default_shell", fallback=cls.CHOICE_DEFAULT_SHELL
        ).strip()

        cls.HELP_KEYBINDS = cls._tuple_list_override(
            parser, "ui", "help_keybinds", cls.HELP_KEYBINDS
        )
        cls.HELP_SPECIAL_COMMANDS = cls._tuple_list_override(
            parser, "ui", "help_special_commands", cls.HELP_SPECIAL_COMMANDS
        )
        cls.PROMPT_STYLES = cls._json_override(
            parser, "ui", "prompt_styles", cls.PROMPT_STYLES
        )
        cls.COMPLETION_STYLES = cls._json_override(
            parser, "ui", "completion_styles", cls.COMPLETION_STYLES
        )
        cls.PANEL_STYLES = cls._json_override(
            parser, "ui", "panel_styles", cls.PANEL_STYLES
        )
        cls.HIGHLIGHTER_ENABLED = parser.getboolean(
            "ui", "highlighter_enabled", fallback=cls.HIGHLIGHTER_ENABLED
        )
        cls.HIGHLIGHTER_RULES = cls._json_override(
            parser, "ui", "highlighter_rules", cls.HIGHLIGHTER_RULES
        )
        cls.HIGHLIGHTER_STYLES = cls._json_override(
            parser, "ui", "highlighter_styles", cls.HIGHLIGHTER_STYLES
        )
        cls.CHOICE_PROMPT_LEXER = parser.get(
            "ui", "choice_prompt_lexer", fallback=cls.CHOICE_PROMPT_LEXER
        ).strip()

        cls.SYNTAX_EXTENSIONS = cls._json_override(
            parser, "syntax", "syntax_extensions", cls.SYNTAX_EXTENSIONS
        )
        cls.SYNTAX_HIGHLIGHT_COMMANDS = cls._json_override(
            parser, "syntax", "syntax_highlight_commands", cls.SYNTAX_HIGHLIGHT_COMMANDS
        )
        cls.LS_COMMANDS = cls._json_override(
            parser, "syntax", "ls_commands", cls.LS_COMMANDS
        )
        cls.FILE_ICONS = cls._json_override(
            parser, "syntax", "file_icons", cls.FILE_ICONS
        )
        cls.FILE_COLORS = cls._json_override(
            parser, "syntax", "file_colors", cls.FILE_COLORS
        )
        cls.FILE_EXTENSIONS = cls._json_override(
            parser, "syntax", "file_extensions", cls.FILE_EXTENSIONS
        )
        cls.BASH_COMPLETION_FILES = cls._json_override(
            parser, "syntax", "bash_completion_files", cls.BASH_COMPLETION_FILES
        )
        cls.BASH_COMPLETION_DIRS = cls._json_override(
            parser, "syntax", "bash_completion_dirs", cls.BASH_COMPLETION_DIRS
        )

        cls.GEMINI_MODEL = parser.get(
            "providers", "gemini_model", fallback=cls.GEMINI_MODEL
        )
        cls.GEMINI_ROUTER_MODEL = parser.get(
            "providers", "gemini_router_model", fallback=cls.GEMINI_ROUTER_MODEL
        )

        cls.LOG_FILE = cls.CONFIG_DIR / "shell.log"
        cls.HISTORY_FILE = cls.CONFIG_DIR / "history.json"

    @staticmethod
    def _json_override(
        parser: configparser.ConfigParser, section: str, option: str, default
    ):
        if not parser.has_option(section, option):
            return default
        raw_value = parser.get(section, option)
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return default
        return parsed

    @staticmethod
    def _tuple_list_override(
        parser: configparser.ConfigParser, section: str, option: str, default
    ):
        fallback = [list(item) for item in default]
        raw = Config._json_override(parser, section, option, fallback)
        return [tuple(item) for item in raw]

    @classmethod
    def _ensure_command_descriptions(cls) -> None:
        refresh_env = os.getenv("WRAPCLI_REFRESH_COMMANDS_DESC", "").strip().lower()
        refresh_requested = refresh_env in {"1", "true", "yes", "on"}
        if cls.COMMANDS_DESC_FILE.exists() and not refresh_requested:
            return
        cls._generate_command_descriptions()

    @classmethod
    def _generate_command_descriptions(cls) -> None:
        try:
            result = subprocess.run(
                ["apropos", "-s", "1,8", "."],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError:
            return
        except subprocess.SubprocessError:
            return

        if result.returncode != 0 or not result.stdout:
            return

        pattern = re.compile(r"^(\S+)\s+\(.*\)\s+-\s+(.*)")
        commands = {}

        for line in result.stdout.splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            command = match.group(1).strip()
            description = match.group(2).strip()
            if not command or len(command) >= 50:
                continue
            commands[command] = description

        if not commands:
            return

        try:
            cls.COMMANDS_DESC_FILE.write_text(
                json.dumps(commands, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    @classmethod
    def reload(cls) -> bool:
        try:
            cls.ensure_directories()
            cls._load_external_config()
            cls._ensure_command_descriptions()
            return True
        except Exception:
            return False


Config.ensure_directories()
Config._load_external_config()
