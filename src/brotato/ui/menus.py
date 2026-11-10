"""Title screen, Character/Weapon/Danger selection, and Victory/Defeat summary screens."""

from __future__ import annotations

import pygame

from brotato.config import (
    COLOR_BAD,
    COLOR_BG,
    COLOR_GOLD,
    COLOR_GOOD,
    COLOR_MATERIAL,
    COLOR_MUTED,
    COLOR_WHITE,
    TIER_COLORS,
)
from brotato.data_loader import GameDatabase
from brotato.engine.game_state import GameState
from brotato.sprites import SpriteAtlas
from brotato.ui.theme import UITheme


class TitleScreen:
    def __init__(self, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.atlas = atlas
        self.theme = theme
        self.start_rect = pygame.Rect(0, 0, 0, 0)
        self.quit_rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface, db: GameDatabase, mouse_pos: tuple[int, int], anim_t: float) -> None:
        sw, sh = surface.get_size()
        surface.fill(COLOR_BG)

        # Decorative arena vignette banner
        banner = pygame.Rect(sw // 2 - 420, 62, 840, 220)
        self.theme.draw_panel(surface, banner, bg=(30, 32, 42), border=(84, 92, 114), border_width=2, radius=18)

        # Showcase cute potatoes flanking title
        left_p = pygame.transform.smoothscale(self.atlas.get_character("well_rounded"), (96, 96))
        right_p = pygame.transform.smoothscale(self.atlas.get_character("mage"), (96, 96))
        surface.blit(left_p, left_p.get_rect(center=(banner.left + 96, banner.centery)))
        surface.blit(right_p, right_p.get_rect(center=(banner.right - 96, banner.centery)))

        self.theme.draw_text(surface, "BROTATO", sw // 2, banner.top + 68, size=72, color=COLOR_GOLD, align="center", shadow=True)
        self.theme.draw_text(surface, "Python & Pygame-CE Data-Driven Edition", sw // 2, banner.top + 132, size=24, color=COLOR_WHITE, align="center", shadow=True)
        self.theme.draw_text(
            surface,
            f"{len(db.characters)} Characters  •  {len(db.weapons)} Weapons  •  {len(db.items)} Items  •  Waves 1-20 + Endless",
            sw // 2,
            banner.top + 174,
            size=18,
            color=COLOR_MUTED,
            align="center",
        )

        bw, bh = 280, 56
        self.start_rect = pygame.Rect(sw // 2 - bw // 2, 340, bw, bh)
        self.quit_rect = pygame.Rect(sw // 2 - bw // 2, 414, bw, bh)
        self.theme.draw_button(
            surface,
            self.start_rect,
            "START RUN  [Enter]",
            hovered=self.start_rect.collidepoint(mouse_pos),
            bg=(48, 122, 72),
            border=(112, 225, 138),
            text_size=24,
        )
        self.theme.draw_button(
            surface,
            self.quit_rect,
            "Quit",
            hovered=self.quit_rect.collidepoint(mouse_pos),
            bg=(62, 46, 52),
            text_size=22,
        )

        # Quick controls card
        ctrl = pygame.Rect(sw // 2 - 360, 510, 720, 150)
        self.theme.draw_panel(surface, ctrl, bg=(27, 29, 36), border=(58, 62, 76), border_width=2, radius=12)
        self.theme.draw_text(surface, "CONTROLS", ctrl.centerx, ctrl.top + 22, size=20, color=COLOR_GOLD, align="center")
        lines = [
            "Move: WASD or Arrow Keys     |     Weapons fire automatically at nearest enemy",
            "Aim Mode: Press [M] to toggle Auto-Aim / Manual Mouse Aim     |     Pause: [ESC]",
            "Sound Toggle: [N]     |     Performance / Entity Debug HUD: [F3]",
        ]
        for idx, line in enumerate(lines):
            self.theme.draw_text(surface, line, ctrl.centerx, ctrl.top + 56 + idx * 28, size=18, color=COLOR_MUTED, align="center")


class SetupScreen:
    """Character, Starting Weapon, and Danger Level selection screen."""

    def __init__(self, db: GameDatabase, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.db = db
        self.atlas = atlas
        self.theme = theme
        self.selected_char_idx: int = 0
        self.selected_weapon_idx: int = 0
        self.danger_level: int = 0

        self.char_rects: list[pygame.Rect] = []
        self.weapon_rects: list[pygame.Rect] = []
        self.danger_rects: list[pygame.Rect] = []
        self.go_rect = pygame.Rect(0, 0, 0, 0)
        self.back_rect = pygame.Rect(0, 0, 0, 0)

    @property
    def current_char_id(self) -> str:
        return self.db.character_order[self.selected_char_idx]

    @property
    def current_weapon_id(self) -> str:
        cdef = self.db.characters[self.current_char_id]
        idx = max(0, min(self.selected_weapon_idx, len(cdef.starting_weapons) - 1))
        return cdef.starting_weapons[idx]

    def select_character(self, idx: int) -> None:
        self.selected_char_idx = idx % len(self.db.character_order)
        self.selected_weapon_idx = 0

    def draw(self, surface: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        sw, sh = surface.get_size()
        surface.fill(COLOR_BG)

        self.theme.draw_text(surface, "CHOOSE YOUR POTATO & LOADOUT", sw // 2, 24, size=34, color=COLOR_WHITE, align="midtop", shadow=True)

        # --- Left panel: Character Grid (3 columns x 4 rows) ---
        grid_panel = pygame.Rect(28, 76, 460, 540)
        self.theme.draw_panel(surface, grid_panel, bg=(28, 30, 38), border=(66, 72, 88))
        self.theme.draw_text(surface, "CHARACTERS", grid_panel.left + 16, grid_panel.top + 14, size=20, color=COLOR_GOLD)

        self.char_rects = []
        cols = 4
        cell_w, cell_h = 98, 108
        gap = 12
        start_x = grid_panel.left + 18
        start_y = grid_panel.top + 48
        for idx, cid in enumerate(self.db.character_order):
            cdef = self.db.characters[cid]
            r = idx // cols
            c = idx % cols
            rect = pygame.Rect(start_x + c * (cell_w + gap), start_y + r * (cell_h + gap), cell_w, cell_h)
            self.char_rects.append(rect)
            sel = idx == self.selected_char_idx
            hov = rect.collidepoint(mouse_pos)
            bg = (52, 62, 86) if sel else ((42, 46, 58) if hov else (34, 36, 44))
            border = COLOR_GOLD if sel else ((145, 155, 175) if hov else (64, 68, 82))
            self.theme.draw_panel(surface, rect, bg=bg, border=border, border_width=3 if sel else 2, radius=10)

            icon = pygame.transform.smoothscale(self.atlas.get_character(cid), (56, 56))
            surface.blit(icon, icon.get_rect(center=(rect.centerx, rect.top + 38)))
            self.theme.draw_text(surface, cdef.name, rect.centerx, rect.bottom - 18, size=15, color=COLOR_WHITE, align="center")

        # --- Center panel: Selected Character Details & Starting Weapon ---
        cdef = self.db.characters[self.current_char_id]
        detail = pygame.Rect(508, 76, 410, 540)
        self.theme.draw_panel(surface, detail, bg=(28, 30, 38), border=(66, 72, 88))

        portrait = pygame.transform.smoothscale(self.atlas.get_character(cdef.id), (74, 74))
        surface.blit(portrait, (detail.left + 18, detail.top + 16))
        self.theme.draw_text(surface, cdef.name, detail.left + 104, detail.top + 22, size=28, color=COLOR_GOLD, shadow=True)
        self.theme.draw_text(surface, cdef.subtitle, detail.left + 104, detail.top + 54, size=17, color=COLOR_MUTED)

        cur_y = self.theme.draw_wrapped(surface, cdef.description, detail.left + 18, detail.top + 100, detail.width - 36, size=17, color=COLOR_WHITE)
        cur_y += 12

        self.theme.draw_text(surface, "CHARACTER TRAITS", detail.left + 18, cur_y, size=18, color=COLOR_GOLD)
        cur_y += 26
        for eff in cdef.effects_text:
            col = COLOR_BAD if (eff.startswith("-") or "reduced" in eff.lower() or "cannot" in eff.lower()) else COLOR_GOOD
            cur_y = self.theme.draw_wrapped(surface, f"• {eff}", detail.left + 18, cur_y, detail.width - 36, size=16, color=col, line_gap=2)
            cur_y += 3

        # Starting weapon selector (always anchored cleanly below traits)
        weap_top = max(cur_y + 10, detail.bottom - 190)
        self.theme.draw_text(surface, "STARTING WEAPON", detail.left + 18, weap_top, size=18, color=COLOR_GOLD)
        self.weapon_rects = []
        wx0 = detail.left + 18
        wy0 = weap_top + 26
        wbtn_w, wbtn_h = 84, 68
        for w_idx, wid in enumerate(cdef.starting_weapons):
            wdef = self.db.weapons[wid]
            col_i = w_idx % 4
            row_i = w_idx // 4
            wrect = pygame.Rect(wx0 + col_i * (wbtn_w + 10), wy0 + row_i * (wbtn_h + 10), wbtn_w, wbtn_h)
            self.weapon_rects.append(wrect)
            sel = w_idx == self.selected_weapon_idx
            hov = wrect.collidepoint(mouse_pos)
            self.theme.draw_panel(
                surface,
                wrect,
                bg=(50, 62, 82) if sel else (36, 38, 46),
                border=COLOR_GOLD if sel else ((140, 150, 170) if hov else (64, 68, 82)),
                border_width=3 if sel else 2,
                radius=8,
            )
            wicon = self.atlas.get_weapon_icon(wid)
            surface.blit(wicon, wicon.get_rect(center=(wrect.centerx, wrect.top + 28)))
            self.theme.draw_text(surface, wdef.name.split()[0], wrect.centerx, wrect.bottom - 14, size=14, color=COLOR_WHITE, align="center")

        # --- Right panel: Selected Weapon Info & Danger Selector ---
        right_panel = pygame.Rect(938, 76, 314, 540)
        self.theme.draw_panel(surface, right_panel, bg=(28, 30, 38), border=(66, 72, 88))

        cur_wdef = self.db.weapons[self.current_weapon_id]
        t_start = cur_wdef.min_tier
        tinfo = cur_wdef.tiers[t_start]
        self.theme.draw_text(surface, cur_wdef.name, right_panel.left + 16, right_panel.top + 16, size=24, color=TIER_COLORS[t_start], shadow=True)
        self.theme.draw_text(
            surface,
            f"{cur_wdef.type.title()} • {', '.join(c.title() for c in cur_wdef.classes)}",
            right_panel.left + 16,
            right_panel.top + 46,
            size=16,
            color=COLOR_MUTED,
        )
        wy = self.theme.draw_wrapped(surface, cur_wdef.description, right_panel.left + 16, right_panel.top + 74, right_panel.width - 32, size=16, color=COLOR_WHITE)
        wy += 10
        stats_lines = [
            f"Damage: {tinfo['damage']}",
            f"Cooldown: {tinfo['cooldown']}s",
            f"Range: {tinfo['range']}",
            f"Crit: {tinfo['crit_chance']}% (x{tinfo.get('crit_mult', 2.0)})",
        ]
        for sl in stats_lines:
            self.theme.draw_text(surface, sl, right_panel.left + 16, wy, size=16, color=(190, 210, 230))
            wy += 22

        # Danger Selector
        dy_top = right_panel.top + 260
        self.theme.draw_text(surface, "DANGER LEVEL", right_panel.left + 16, dy_top, size=20, color=COLOR_GOLD)
        self.danger_rects = []
        d_btn_w = 42
        for d_i in range(6):
            drect = pygame.Rect(right_panel.left + 16 + d_i * (d_btn_w + 6), dy_top + 32, d_btn_w, 42)
            self.danger_rects.append(drect)
            sel = d_i == self.danger_level
            hov = drect.collidepoint(mouse_pos)
            self.theme.draw_button(
                surface,
                drect,
                str(d_i),
                hovered=hov,
                bg=(145, 58, 58) if sel else (44, 48, 58),
                border=COLOR_GOLD if sel else (84, 90, 108),
                text_size=20,
            )
        dcfg = self.db.get_danger(self.danger_level)
        self.theme.draw_text(surface, dcfg["name"], right_panel.left + 16, dy_top + 88, size=19, color=COLOR_WHITE)
        self.theme.draw_wrapped(surface, dcfg["description"], right_panel.left + 16, dy_top + 114, right_panel.width - 32, size=16, color=COLOR_MUTED)

        # --- Bottom Footer Buttons ---
        self.back_rect = pygame.Rect(28, sh - 76, 170, 50)
        self.go_rect = pygame.Rect(sw - 290, sh - 76, 262, 50)
        self.theme.draw_button(surface, self.back_rect, "Back [ESC]", hovered=self.back_rect.collidepoint(mouse_pos))
        self.theme.draw_button(
            surface,
            self.go_rect,
            "ENTER ARENA  [Enter]",
            hovered=self.go_rect.collidepoint(mouse_pos),
            bg=(48, 122, 72),
            border=(112, 225, 138),
            text_size=22,
        )


class SummaryScreen:
    """Victory or Defeat screen with run statistics and Endless Mode continuation."""

    def __init__(self, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.atlas = atlas
        self.theme = theme
        self.endless_rect = pygame.Rect(0, 0, 0, 0)
        self.restart_rect = pygame.Rect(0, 0, 0, 0)
        self.title_rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface, state: GameState, mouse_pos: tuple[int, int]) -> None:
        sw, sh = surface.get_size()
        surface.fill(COLOR_BG)

        panel = pygame.Rect(sw // 2 - 390, 62, 780, 580)
        is_win = state.run_won and not state.run_lost
        border = COLOR_GOLD if is_win else COLOR_BAD
        self.theme.draw_panel(surface, panel, bg=(28, 30, 38), border=border, border_width=3, radius=16)

        title = "RUN WON!" if is_win else "YOU WERE OVERWHELMED"
        self.theme.draw_text(surface, title, panel.centerx, panel.top + 38, size=44, color=border, align="center", shadow=True)
        sub = f"{state.character.name}  •  Wave {state.wave}  •  Danger {state.danger_level}  •  Level {state.level}"
        self.theme.draw_text(surface, sub, panel.centerx, panel.top + 84, size=21, color=COLOR_WHITE, align="center")

        portrait = pygame.transform.smoothscale(self.atlas.get_character(state.character.id), (76, 76))
        surface.blit(portrait, portrait.get_rect(center=(panel.centerx, panel.top + 144)))

        s = state.summary
        rows = [
            ("Enemies Defeated", f"{s.enemies_killed}"),
            ("Elites / Bosses Defeated", f"{s.elites_killed} / {s.bosses_killed}"),
            ("Total Damage Dealt", f"{s.total_damage_dealt:,}"),
            ("Materials Collected", f"{s.materials_collected:,}"),
            ("Trees Chopped", f"{s.trees_chopped}"),
            ("Crates Opened", f"{s.crates_opened}"),
            ("Damage Taken / Dodged", f"{s.damage_taken} / {s.hits_dodged}"),
            ("Weapons / Items", f"{len(state.weapons)} / {len(state.items)}"),
        ]
        ry = panel.top + 205
        for label, val in rows:
            self.theme.draw_text(surface, label, panel.left + 80, ry, size=20, color=COLOR_MUTED)
            self.theme.draw_text(surface, val, panel.right - 80, ry, size=20, color=COLOR_WHITE, align="topright")
            pygame.draw.line(surface, (48, 52, 64), (panel.left + 80, ry + 28), (panel.right - 80, ry + 28), 1)
            ry += 34

        btn_y = panel.bottom - 76
        if is_win:
            self.endless_rect = pygame.Rect(panel.left + 44, btn_y, 210, 48)
            self.restart_rect = pygame.Rect(panel.centerx - 105, btn_y, 210, 48)
            self.title_rect = pygame.Rect(panel.right - 254, btn_y, 210, 48)
            self.theme.draw_button(surface, self.endless_rect, "Go Endless!", hovered=self.endless_rect.collidepoint(mouse_pos), bg=(108, 62, 138), border=(195, 130, 245))
        else:
            self.endless_rect = pygame.Rect(0, 0, 0, 0)
            self.restart_rect = pygame.Rect(panel.left + 120, btn_y, 240, 48)
            self.title_rect = pygame.Rect(panel.right - 360, btn_y, 240, 48)

        self.theme.draw_button(surface, self.restart_rect, "New Run", hovered=self.restart_rect.collidepoint(mouse_pos), bg=(48, 118, 72))
        self.theme.draw_button(surface, self.title_rect, "Title Screen", hovered=self.title_rect.collidepoint(mouse_pos))
