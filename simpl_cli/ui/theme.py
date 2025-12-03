#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Any, Dict, Optional
from rich.panel import Panel
from rich.text import Text
from ..config import Config


@dataclass(frozen=True)
class PanelStyle:
    border_style: str
    padding: Optional[tuple[int, int]] = (0, 1)
    title_style: Optional[str] = None


class PanelTheme:

    @staticmethod
    def get_style(name: str) -> PanelStyle:
        theme = Config.PANEL_STYLES.get(name, Config.PANEL_STYLES["default"])
        default_theme = Config.PANEL_STYLES["default"]

        border_style = theme.get("border_style", default_theme.get("border_style", "#888888"))
        padding = theme.get("padding", default_theme.get("padding"))
        title_style = theme.get("title_style")

        return PanelStyle(border_style=border_style, padding=padding, title_style=title_style)

    @staticmethod
    def build(renderable: Any, title: str | Text = "", style: str = "default", *, fit: bool = False, **overrides: Any) -> Panel:
        panel_style = PanelTheme.get_style(style)

        panel_kwargs: Dict[str, Any] = {"border_style": panel_style.border_style}
        if panel_style.padding is not None:
            panel_kwargs["padding"] = panel_style.padding

        panel_kwargs.update(overrides)
        panel_kwargs.setdefault("title_align", "left")

        title_value = title
        if isinstance(title, str) and panel_style.title_style:
            title_value = Text(title, style=panel_style.title_style)

        if fit:
            return Panel.fit(renderable, title=title_value, **panel_kwargs)

        return Panel(renderable, title=title_value, **panel_kwargs)
