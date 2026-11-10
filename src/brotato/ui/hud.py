"""In-wave HUD and Pause overlay."""

from __future__ import annotations

import math

import pygame

from brotato.config import (
    COLOR_GOLD,
    COLOR_HP,
    COLOR_HP_BG,
    COLOR_MATERIAL,
    COLOR_MUTED,
    COLOR_WHITE,
    COLOR_XP,
    COLOR_XP_BG,
    TIER_BG_COLORS,
    TIER_COLORS,
)
from brotato.engine.game_state import GameState
from brotato.sprites import SpriteAtlas
from brotato.ui.theme import UITheme


class CombatHUD:
    """Draws the in-wave status bars, wave timer, boss bar, and pause menu."""

    def __init__(self, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.atlas = atlas
        self.theme = theme
        self.show_debug: bool = False
        self.pause_rects: dict[str, pygame.Rect] = {}
        self.aim_btn_rect = pygame.Rect(0, 0, 0, 0)

    def draw(
        self,
        surface: pygame.Surface,
        state: GameState,
        fps: float,
        muted: bool,
        paused: bool,
        mouse_pos: tuple[int, int],
    ) -> None:
        sw, sh = surface.get_size()

        # --- Top-left: HP, XP, Materials ---
        bar_x, bar_y = 18, 16
        bar_w, bar_h = 240, 22

        # HP Bar
        hp_ratio = max(0.0, min(1.0, state.hp / max(1.0, state.max_hp)))
        pygame.draw.rect(surface, (16, 16, 20), (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4), border_radius=6)
        pygame.draw.rect(surface, COLOR_HP_BG, (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        if hp_ratio > 0:
            pygame.draw.rect(surface, COLOR_HP, (bar_x, bar_y, int(bar_w * hp_ratio), bar_h), border_radius=5)
        self.theme.draw_text(
            surface,
            f"{int(math.ceil(state.hp))} / {int(round(state.max_hp))}",
            bar_x + bar_w // 2,
            bar_y + bar_h // 2,
            size=18,
            color=COLOR_WHITE,
            align="center",
            shadow=True,
        )

        # XP Bar
        xp_y = bar_y + 28
        xp_h = 16
        xp_ratio = max(0.0, min(1.0, state.xp / max(1, state.xp_needed)))
        pygame.draw.rect(surface, (16, 16, 20), (bar_x - 2, xp_y - 2, bar_w + 4, xp_h + 4), border_radius=5)
        pygame.draw.rect(surface, COLOR_XP_BG, (bar_x, xp_y, bar_w, xp_h), border_radius=4)
        if xp_ratio > 0:
            pygame.draw.rect(surface, COLOR_XP, (bar_x, xp_y, int(bar_w * xp_ratio), xp_h), border_radius=4)
        self.theme.draw_text(
            surface,
            f"LV. {state.level}",
            bar_x + bar_w + 12,
            xp_y + xp_h // 2,
            size=19,
            color=COLOR_WHITE,
            align="midleft",
            shadow=True,
        )

        # Materials & Bagged Materials (subtle dark pill for guaranteed contrast over enemies)
        mat_y = xp_y + 26
        mat_text = f"{state.materials}"
        if state.bagged_materials > 0:
            mat_text += f"  (+{state.bagged_materials} bag)"
        mat_pill_w = max(92, 42 + len(mat_text) * 11)
        pill = pygame.Surface((mat_pill_w, 26), pygame.SRCALPHA)
        pygame.draw.rect(pill, (14, 16, 22, 165), (0, 0, mat_pill_w, 26), border_radius=6)
        surface.blit(pill, (bar_x - 4, mat_y - 3))
        mat_surf = self.atlas.get_misc("material")
        surface.blit(mat_surf, (bar_x, mat_y))
        self.theme.draw_text(surface, mat_text, bar_x + 24, mat_y + 9, size=21, color=COLOR_MATERIAL, align="midleft", shadow=True)

        # Pending crates / levelups indicators
        badge_x = bar_x
        badge_y = mat_y + 28
        if state.pending_level_ups > 0:
            r = self.theme.draw_text(surface, f"LvUp x{state.pending_level_ups}", badge_x, badge_y, size=17, color=COLOR_GOLD, shadow=True)
            badge_x = r.right + 14
        if state.pending_crates > 0:
            self.theme.draw_text(surface, f"Crates x{state.pending_crates}", badge_x, badge_y, size=17, color=(255, 196, 86), shadow=True)

        # --- Top-center: Wave & Timer + Boss Bar ---
        wave_title = f"WAVE {state.wave}"
        if state.wave_tag:
            wave_title += f" - {state.wave_tag}"
        self.theme.draw_text(surface, wave_title, sw // 2, 18, size=24, color=COLOR_WHITE, align="midtop", shadow=True)

        secs = max(0, int(math.ceil(state.wave_timer)))
        timer_col = (255, 86, 86) if secs <= 5 else COLOR_WHITE
        self.theme.draw_text(surface, f"{secs}", sw // 2, 46, size=40, color=timer_col, align="midtop", shadow=True)

        bosses = [e for e in state.enemies if e.is_boss and e.hp > 0]
        if bosses:
            by = 92
            for b in bosses[:2]:
                bw = 340
                bx = sw // 2 - bw // 2
                edef = state.db.enemies[b.def_id]
                ratio = max(0.0, b.hp / max(1.0, b.max_hp))
                pygame.draw.rect(surface, (20, 14, 18), (bx - 2, by - 2, bw + 4, 18), border_radius=5)
                pygame.draw.rect(surface, (56, 22, 28), (bx, by, bw, 14), border_radius=4)
                pygame.draw.rect(surface, (228, 52, 74), (bx, by, int(bw * ratio), 14), border_radius=4)
                self.theme.draw_text(surface, f"{edef.name}: {int(b.hp)}/{int(b.max_hp)}", sw // 2, by + 7, size=15, color=COLOR_WHITE, align="center", shadow=True)
                by += 22

        # --- Top-right: Controls / Aim Toggle / Debug ---
        aim_label = "Manual Aim [M]" if state.manual_aim else "Auto-Aim [M]"
        self.aim_btn_rect = pygame.Rect(sw - 170, 14, 152, 30)
        self.theme.draw_button(
            surface,
            self.aim_btn_rect,
            aim_label,
            hovered=self.aim_btn_rect.collidepoint(mouse_pos),
            bg=(46, 56, 72) if not state.manual_aim else (88, 58, 44),
            text_size=16,
        )
        sfx_txt = "SFX: OFF [N]" if muted else "SFX: ON [N]"
        self.theme.draw_text(surface, f"{sfx_txt}   Pause [ESC]", sw - 18, 52, size=16, color=COLOR_MUTED, align="topright", shadow=True)

        if self.show_debug:
            dbg = f"FPS: {fps:.0f} | Enemies: {len(state.enemies)} | Proj: {len(state.projectiles)} | Pickups: {len(state.pickups)}"
            self.theme.draw_text(surface, dbg, sw - 18, 74, size=15, color=(140, 235, 175), align="topright", shadow=True)

        # --- Bottom-left: Compact Weapon Bar ---
        slot_size = 42
        gap = 6
        wx0 = 18
        wy0 = sh - slot_size - 16
        for i, w in enumerate(state.weapons):
            rx = wx0 + i * (slot_size + gap)
            rect = pygame.Rect(rx, wy0, slot_size, slot_size)
            pygame.draw.rect(surface, TIER_BG_COLORS[w.tier], rect, border_radius=7)
            pygame.draw.rect(surface, TIER_COLORS[w.tier], rect, width=2, border_radius=7)
            icon = pygame.transform.smoothscale(self.atlas.get_weapon_icon(w.def_id), (36, 26))
            surface.blit(icon, icon.get_rect(center=rect.center))

        # --- Pause Overlay ---
        if paused:
            dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
            dim.fill((10, 12, 16, 180))
            surface.blit(dim, (0, 0))

            pw, ph = 360, 320
            modal = pygame.Rect((sw - pw) // 2, (sh - ph) // 2, pw, ph)
            self.theme.draw_panel(surface, modal, bg=(30, 33, 42), border=(110, 120, 145), border_width=2, radius=14)
            self.theme.draw_text(surface, "PAUSED", modal.centerx, modal.top + 32, size=34, color=COLOR_WHITE, align="center", shadow=True)

            bx = modal.left + 40
            bw = pw - 80
            bh = 44
            self.pause_rects = {
                "resume": pygame.Rect(bx, modal.top + 78, bw, bh),
                "aim": pygame.Rect(bx, modal.top + 134, bw, bh),
                "mute": pygame.Rect(bx, modal.top + 190, bw, bh),
                "quit": pygame.Rect(bx, modal.top + 246, bw, bh),
            }
            self.theme.draw_button(surface, self.pause_rects["resume"], "Resume Game", hovered=self.pause_rects["resume"].collidepoint(mouse_pos), bg=(48, 108, 68))
            self.theme.draw_button(surface, self.pause_rects["aim"], f"Aim: {'Manual' if state.manual_aim else 'Auto'}", hovered=self.pause_rects["aim"].collidepoint(mouse_pos))
            self.theme.draw_button(surface, self.pause_rects["mute"], f"Sound: {'OFF' if muted else 'ON'}", hovered=self.pause_rects["mute"].collidepoint(mouse_pos))
            self.theme.draw_button(surface, self.pause_rects["quit"], "Return to Title", hovered=self.pause_rects["quit"].collidepoint(mouse_pos), bg=(112, 46, 52))
