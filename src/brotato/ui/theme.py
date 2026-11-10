"""UI theme, cached font/text rendering, word wrapping, and reusable widgets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pygame

from brotato.config import COLOR_BAD, COLOR_GOOD, COLOR_MUTED, COLOR_WHITE, TIER_BG_COLORS, TIER_COLORS


class UITheme:
    """Manages fonts, cached text surfaces, and shared panel/button rendering."""

    def __init__(self, custom_font_path: Path | None = None) -> None:
        self._font_path = str(custom_font_path) if custom_font_path else None
        self._fonts: dict[int, pygame.font.Font] = {}
        self._text_cache: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}

    def font(self, size: int) -> pygame.font.Font:
        f = self._fonts.get(size)
        if f is None:
            try:
                f = pygame.font.Font(self._font_path, size)
            except Exception:
                f = pygame.font.Font(None, size)
            self._fonts[size] = f
        return f

    def text_surface(self, text: str, size: int, color: tuple[int, int, int] = COLOR_WHITE) -> pygame.Surface:
        key = (text, size, color)
        surf = self._text_cache.get(key)
        if surf is None:
            if len(self._text_cache) > 2000:
                self._text_cache.clear()
            surf = self.font(size).render(text, True, color)
            self._text_cache[key] = surf
        return surf

    def draw_text(
        self,
        target: pygame.Surface,
        text: str,
        x: float,
        y: float,
        size: int = 20,
        color: tuple[int, int, int] = COLOR_WHITE,
        align: str = "topleft",
        shadow: bool = False,
    ) -> pygame.Rect:
        if shadow:
            sh = self.text_surface(text, size, (10, 10, 14))
            r_sh = sh.get_rect(**{align: (int(x) + 1, int(y) + 2)})
            target.blit(sh, r_sh)
        surf = self.text_surface(text, size, color)
        rect = surf.get_rect(**{align: (int(x), int(y))})
        target.blit(surf, rect)
        return rect

    def wrap_lines(self, text: str, size: int, max_width: int) -> list[str]:
        f = self.font(size)
        words = text.split()
        lines: list[str] = []
        cur = ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if f.size(trial)[0] <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw_wrapped(
        self,
        target: pygame.Surface,
        text: str,
        x: int,
        y: int,
        max_width: int,
        size: int = 17,
        color: tuple[int, int, int] = COLOR_MUTED,
        line_gap: int = 3,
    ) -> int:
        cur_y = y
        for line in self.wrap_lines(text, size, max_width):
            r = self.draw_text(target, line, x, cur_y, size=size, color=color)
            cur_y = r.bottom + line_gap
        return cur_y

    def draw_panel(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        bg: tuple[int, int, int] = (30, 32, 40),
        border: tuple[int, int, int] = (72, 78, 94),
        border_width: int = 2,
        radius: int = 10,
    ) -> None:
        pygame.draw.rect(target, bg, rect, border_radius=radius)
        if border_width > 0:
            pygame.draw.rect(target, border, rect, width=border_width, border_radius=radius)

    def draw_tier_card(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        tier: int,
        hovered: bool = False,
        selected: bool = False,
    ) -> None:
        bg = TIER_BG_COLORS.get(tier, (36, 38, 46))
        border = TIER_COLORS.get(tier, (150, 156, 168))
        if hovered or selected:
            bg = (min(255, bg[0] + 18), min(255, bg[1] + 18), min(255, bg[2] + 18))
        bw = 3 if (hovered or selected) else 2
        self.draw_panel(target, rect, bg=bg, border=border, border_width=bw, radius=10)

    def draw_button(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        hovered: bool = False,
        enabled: bool = True,
        bg: tuple[int, int, int] = (54, 62, 80),
        border: tuple[int, int, int] = (118, 128, 150),
        text_size: int = 20,
    ) -> None:
        if not enabled:
            draw_bg = (38, 40, 48)
            draw_border = (62, 66, 76)
            tcol = (105, 110, 122)
        else:
            draw_bg = (min(255, bg[0] + 22), min(255, bg[1] + 22), min(255, bg[2] + 22)) if hovered else bg
            draw_border = (230, 236, 245) if hovered else border
            tcol = COLOR_WHITE
        self.draw_panel(target, rect, bg=draw_bg, border=draw_border, border_width=2, radius=8)
        self.draw_text(target, label, rect.centerx, rect.centery, size=text_size, color=tcol, align="center", shadow=True)

    @staticmethod
    def stat_color(val: float, higher_is_better: bool = True) -> tuple[int, int, int]:
        if abs(val) < 0.01:
            return COLOR_WHITE
        good = (val > 0) if higher_is_better else (val < 0)
        return COLOR_GOOD if good else COLOR_BAD
