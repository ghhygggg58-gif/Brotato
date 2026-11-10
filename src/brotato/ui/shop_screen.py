"""Between-wave Crate, Level-Up Upgrade, and Shop screens."""

from __future__ import annotations

import pygame

from brotato.config import (
    COLOR_BG,
    COLOR_GOLD,
    COLOR_GOOD,
    COLOR_MATERIAL,
    COLOR_MUTED,
    COLOR_WHITE,
    TIER_BG_COLORS,
    TIER_COLORS,
    TIER_ROMAN,
)
from brotato.engine.game_state import GameState
from brotato.engine.level_up import upgrade_reroll_cost
from brotato.engine.shop import can_buy_offer, shop_reroll_cost, weapon_recycle_value
from brotato.sprites import SpriteAtlas
from brotato.stats import armor_reduction_pct, compute_weapon_effective_props
from brotato.ui.theme import UITheme


def _draw_stats_sidebar(
    surface: pygame.Surface,
    theme: UITheme,
    state: GameState,
    rect: pygame.Rect,
    tab: str,
    mouse_pos: tuple[int, int],
) -> tuple[pygame.Rect, pygame.Rect]:
    theme.draw_panel(surface, rect, bg=(26, 28, 36), border=(68, 74, 92), radius=12)
    theme.draw_text(surface, "STATS", rect.left + 16, rect.top + 14, size=22, color=COLOR_GOLD)

    p_tab = pygame.Rect(rect.right - 178, rect.top + 10, 82, 28)
    s_tab = pygame.Rect(rect.right - 92, rect.top + 10, 82, 28)
    theme.draw_button(surface, p_tab, "Primary", hovered=p_tab.collidepoint(mouse_pos), bg=(54, 72, 98) if tab == "primary" else (36, 39, 48), text_size=14)
    theme.draw_button(surface, s_tab, "Secondary", hovered=s_tab.collidepoint(mouse_pos), bg=(54, 72, 98) if tab == "secondary" else (36, 39, 48), text_size=14)

    meta_list = state.db.stats_meta[tab]
    y = rect.top + 48
    row_h = 26 if tab == "primary" else 28
    for entry in meta_list:
        key = entry["key"]
        val = state.stats.get(key)
        is_pct = entry["is_percent"]
        higher_good = entry["higher_is_better"]

        disp_val = int(round(val))
        if key == "dodge":
            cap = int(state.dodge_cap)
            val_str = f"{disp_val}%" + (f" (max {cap}%)" if disp_val > cap else "")
        elif key == "armor":
            dr = armor_reduction_pct(val)
            val_str = f"{disp_val} ({dr}%)"
        elif is_pct:
            val_str = f"{disp_val}%"
        else:
            val_str = f"{disp_val}"

        col = theme.stat_color(val, higher_is_better=higher_good)
        theme.draw_text(surface, entry["name"], rect.left + 14, y, size=16, color=COLOR_MUTED)
        theme.draw_text(surface, val_str, rect.right - 14, y, size=16, color=col, align="topright")
        y += row_h

    return p_tab, s_tab


class CrateModal:
    def __init__(self, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.atlas = atlas
        self.theme = theme
        self.take_rect = pygame.Rect(0, 0, 0, 0)
        self.recycle_rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface, state: GameState, mouse_pos: tuple[int, int]) -> None:
        sw, sh = surface.get_size()
        surface.fill(COLOR_BG)
        iid = state.current_crate_item
        if not iid:
            return
        idef = state.db.items[iid]

        modal = pygame.Rect(sw // 2 - 230, sh // 2 - 190, 460, 380)
        self.theme.draw_tier_card(surface, modal, idef.tier)
        self.theme.draw_text(surface, f"LOOT CRATE ({state.pending_crates} left)", modal.centerx, modal.top + 28, size=24, color=COLOR_GOLD, align="center", shadow=True)

        icon = pygame.transform.smoothscale(self.atlas.get_item(iid), (72, 72))
        surface.blit(icon, icon.get_rect(center=(modal.centerx, modal.top + 96)))

        self.theme.draw_text(surface, f"{idef.name}  [Tier {TIER_ROMAN[idef.tier]}]", modal.centerx, modal.top + 150, size=26, color=TIER_COLORS[idef.tier], align="center", shadow=True)
        self.theme.draw_wrapped(surface, idef.description, modal.left + 32, modal.top + 186, modal.width - 64, size=18, color=COLOR_WHITE)

        recycle_val = max(5, int(round(idef.price * 0.5)))
        self.take_rect = pygame.Rect(modal.left + 32, modal.bottom - 72, 185, 46)
        self.recycle_rect = pygame.Rect(modal.right - 217, modal.bottom - 72, 185, 46)
        self.theme.draw_button(surface, self.take_rect, "Take Item", hovered=self.take_rect.collidepoint(mouse_pos), bg=(48, 120, 72))
        self.theme.draw_button(surface, self.recycle_rect, f"Recycle (+{recycle_val})", hovered=self.recycle_rect.collidepoint(mouse_pos), bg=(112, 74, 42))


class LevelUpScreen:
    def __init__(self, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.atlas = atlas
        self.theme = theme
        self.stats_tab: str = "primary"
        self.card_rects: list[pygame.Rect] = []
        self.reroll_rect = pygame.Rect(0, 0, 0, 0)
        self.primary_tab_rect = pygame.Rect(0, 0, 0, 0)
        self.secondary_tab_rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface, state: GameState, mouse_pos: tuple[int, int]) -> None:
        sw, sh = surface.get_size()
        surface.fill(COLOR_BG)

        self.theme.draw_text(
            surface,
            f"LEVEL UP!  (Level {state.level}  •  {state.pending_level_ups} Upgrade{'s' if state.pending_level_ups > 1 else ''} Left)",
            36,
            24,
            size=32,
            color=COLOR_GOLD,
            shadow=True,
        )
        mat_surf = self.atlas.get_misc("material")
        surface.blit(mat_surf, (36, 68))
        self.theme.draw_text(surface, f"{state.materials}", 60, 77, size=22, color=COLOR_MATERIAL, align="midleft")

        cost = upgrade_reroll_cost(state)
        self.reroll_rect = pygame.Rect(700, 26, 200, 44)
        self.theme.draw_button(
            surface,
            self.reroll_rect,
            f"Reroll ({cost})",
            hovered=self.reroll_rect.collidepoint(mouse_pos),
            enabled=state.materials >= cost,
            bg=(56, 70, 96),
        )

        # 4 Upgrade Cards
        self.card_rects = []
        cw, ch = 205, 290
        gap = 18
        x0 = 36
        y0 = 140
        for idx, opt in enumerate(state.current_level_choices):
            rect = pygame.Rect(x0 + idx * (cw + gap), y0, cw, ch)
            self.card_rects.append(rect)
            hov = rect.collidepoint(mouse_pos)
            self.theme.draw_tier_card(surface, rect, opt.tier, hovered=hov)

            self.theme.draw_text(surface, f"Tier {TIER_ROMAN[opt.tier]}", rect.centerx, rect.top + 22, size=18, color=TIER_COLORS[opt.tier], align="center")
            self.theme.draw_text(surface, opt.name, rect.centerx, rect.top + 78, size=22, color=COLOR_WHITE, align="center", shadow=True)
            val_txt = opt.description.split()[0]
            self.theme.draw_text(surface, val_txt, rect.centerx, rect.top + 148, size=44, color=COLOR_GOOD, align="center", shadow=True)
            self.theme.draw_text(surface, "Click or [1-4]", rect.centerx, rect.bottom - 26, size=15, color=COLOR_MUTED, align="center")

        # Stats Sidebar on the right
        sidebar = pygame.Rect(sw - 332, 24, 304, 510)
        self.primary_tab_rect, self.secondary_tab_rect = _draw_stats_sidebar(
            surface, self.theme, state, sidebar, self.stats_tab, mouse_pos
        )


class ShopScreen:
    def __init__(self, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.atlas = atlas
        self.theme = theme
        self.stats_tab: str = "primary"
        self.selected_weapon_idx: int | None = None

        self.buy_rects: list[pygame.Rect] = []
        self.lock_rects: list[pygame.Rect] = []
        self.weapon_rects: list[pygame.Rect] = []
        self.item_rects: list[tuple[pygame.Rect, str]] = []
        self.combine_rect = pygame.Rect(0, 0, 0, 0)
        self.recycle_rect = pygame.Rect(0, 0, 0, 0)
        self.reroll_rect = pygame.Rect(0, 0, 0, 0)
        self.go_rect = pygame.Rect(0, 0, 0, 0)
        self.primary_tab_rect = pygame.Rect(0, 0, 0, 0)
        self.secondary_tab_rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface: pygame.Surface, state: GameState, mouse_pos: tuple[int, int]) -> None:
        sw, sh = surface.get_size()
        surface.fill(COLOR_BG)

        # --- Top Header ---
        self.theme.draw_text(surface, f"SHOP  (Wave {state.wave} Cleared)", 26, 20, size=32, color=COLOR_WHITE, shadow=True)
        mat_surf = self.atlas.get_misc("material")
        surface.blit(mat_surf, (380, 26))
        mat_label = f"{state.materials}"
        if state.bagged_materials > 0:
            mat_label += f"  (+{state.bagged_materials} in bag)"
        self.theme.draw_text(surface, mat_label, 404, 35, size=24, color=COLOR_MATERIAL, align="midleft")

        r_cost = shop_reroll_cost(state)
        r_label = "Reroll (FREE!)" if r_cost == 0 else f"Reroll ({r_cost})"
        self.reroll_rect = pygame.Rect(730, 16, 200, 42)
        self.theme.draw_button(
            surface,
            self.reroll_rect,
            r_label,
            hovered=self.reroll_rect.collidepoint(mouse_pos),
            enabled=state.materials >= r_cost,
            bg=(56, 70, 96),
        )

        # --- 4 Shop Offer Cards ---
        self.buy_rects = []
        self.lock_rects = []
        cw, ch = 216, 285
        gap = 14
        x0 = 26
        y0 = 72
        for idx, offer in enumerate(state.shop_offers):
            card = pygame.Rect(x0 + idx * (cw + gap), y0, cw, ch)
            if offer.purchased:
                self.theme.draw_panel(surface, card, bg=(24, 25, 31), border=(46, 48, 56), radius=10)
                self.theme.draw_text(surface, "SOLD", card.centerx, card.centery, size=24, color=(82, 86, 98), align="center")
                self.buy_rects.append(pygame.Rect(0, 0, 0, 0))
                self.lock_rects.append(pygame.Rect(0, 0, 0, 0))
                continue

            self.theme.draw_tier_card(surface, card, offer.tier, hovered=card.collidepoint(mouse_pos))

            # Header: Icon + Name + Tier
            if offer.kind == "weapon":
                wdef = state.db.weapons[offer.def_id]
                icon = self.atlas.get_weapon_icon(offer.def_id)
                surface.blit(icon, icon.get_rect(center=(card.left + 38, card.top + 38)))
                name_txt = wdef.name
                sub_txt = f"{wdef.type.title()} • {', '.join(c.title() for c in wdef.classes)}"
                tinfo = wdef.tiers[offer.tier]
                desc_txt = f"Dmg {tinfo['damage']} | CD {tinfo['cooldown']}s | Rng {tinfo['range']}\n{wdef.description}"
            else:
                idef = state.db.items[offer.def_id]
                icon = self.atlas.get_item(offer.def_id)
                surface.blit(icon, icon.get_rect(center=(card.left + 38, card.top + 38)))
                name_txt = idef.name
                sub_txt = f"Item • Tier {TIER_ROMAN[offer.tier]}"
                desc_txt = idef.description

            self.theme.draw_wrapped(surface, name_txt, card.left + 72, card.top + 14, card.width - 102, size=18, color=TIER_COLORS[offer.tier], line_gap=1)
            self.theme.draw_text(surface, TIER_ROMAN[offer.tier], card.right - 10, card.top + 12, size=16, color=TIER_COLORS[offer.tier], align="topright")
            self.theme.draw_text(surface, sub_txt, card.left + 12, card.top + 68, size=14, color=COLOR_MUTED)

            # Description lines
            cy = card.top + 92
            for part in desc_txt.split("\n"):
                cy = self.theme.draw_wrapped(surface, part, card.left + 12, cy, card.width - 24, size=15, color=COLOR_WHITE, line_gap=2)
                cy += 4

            # Lock & Buy buttons
            can_buy, note = can_buy_offer(state, offer)
            buy_r = pygame.Rect(card.left + 12, card.bottom - 82, card.width - 24, 36)
            lock_r = pygame.Rect(card.left + 12, card.bottom - 40, card.width - 24, 30)
            self.buy_rects.append(buy_r)
            self.lock_rects.append(lock_r)

            buy_label = f"Combine ({offer.price})" if note == "Auto-combines!" else f"Buy ({offer.price})"
            self.theme.draw_button(
                surface,
                buy_r,
                buy_label,
                hovered=buy_r.collidepoint(mouse_pos),
                enabled=can_buy,
                bg=(48, 118, 72),
                text_size=17,
            )
            lock_label = "UNLOCK" if offer.locked else "Lock"
            self.theme.draw_button(
                surface,
                lock_r,
                lock_label,
                hovered=lock_r.collidepoint(mouse_pos),
                bg=(126, 92, 42) if offer.locked else (44, 48, 58),
                border=COLOR_GOLD if offer.locked else (82, 88, 104),
                text_size=15,
            )

        # --- Bottom Left: Equipped Weapons & Class Synergies ---
        weap_panel = pygame.Rect(26, 372, 460, 326)
        self.theme.draw_panel(surface, weap_panel, bg=(26, 28, 36), border=(66, 72, 88))
        self.theme.draw_text(
            surface,
            f"WEAPONS ({len(state.weapons)}/{state.max_weapons})",
            weap_panel.left + 14,
            weap_panel.top + 12,
            size=19,
            color=COLOR_GOLD,
        )

        self.weapon_rects = []
        slot_w, slot_h = 66, 62
        cols = 6
        for i, w in enumerate(state.weapons):
            r = i // cols
            c = i % cols
            wrect = pygame.Rect(weap_panel.left + 14 + c * (slot_w + 8), weap_panel.top + 42 + r * (slot_h + 8), slot_w, slot_h)
            self.weapon_rects.append(wrect)
            sel = self.selected_weapon_idx == i
            self.theme.draw_tier_card(surface, wrect, w.tier, hovered=wrect.collidepoint(mouse_pos), selected=sel)
            wicon = self.atlas.get_weapon_icon(w.def_id)
            surface.blit(wicon, wicon.get_rect(center=(wrect.centerx, wrect.centery - 4)))
            self.theme.draw_text(surface, TIER_ROMAN[w.tier], wrect.right - 6, wrect.bottom - 5, size=14, color=TIER_COLORS[w.tier], align="bottomright")

        # Selected weapon Combine / Recycle action bar
        self.combine_rect = pygame.Rect(0, 0, 0, 0)
        self.recycle_rect = pygame.Rect(0, 0, 0, 0)
        act_y = weap_panel.top + 180
        if self.selected_weapon_idx is not None and 0 <= self.selected_weapon_idx < len(state.weapons):
            sw_inst = state.weapons[self.selected_weapon_idx]
            wdef = state.db.weapons[sw_inst.def_id]
            props = compute_weapon_effective_props(sw_inst, wdef, state.stats, state.weapons, state.character)
            self.theme.draw_text(
                surface,
                f"{wdef.name} ({TIER_ROMAN[sw_inst.tier]}): Dmg {int(round(props['damage']))} | CD {props['cooldown']:.2f}s | Kills {sw_inst.kills}",
                weap_panel.left + 14,
                act_y,
                size=16,
                color=TIER_COLORS[sw_inst.tier],
            )
            partner = state.can_combine_at(self.selected_weapon_idx)
            self.combine_rect = pygame.Rect(weap_panel.left + 14, act_y + 26, 195, 34)
            self.recycle_rect = pygame.Rect(weap_panel.left + 220, act_y + 26, 195, 34)
            self.theme.draw_button(
                surface,
                self.combine_rect,
                f"Combine -> {TIER_ROMAN[min(4, sw_inst.tier + 1)]}" if partner is not None else "No Pair to Combine",
                hovered=self.combine_rect.collidepoint(mouse_pos),
                enabled=partner is not None,
                bg=(58, 102, 146),
                text_size=15,
            )
            rec_val = weapon_recycle_value(state, self.selected_weapon_idx)
            self.theme.draw_button(
                surface,
                self.recycle_rect,
                f"Recycle (+{rec_val})",
                hovered=self.recycle_rect.collidepoint(mouse_pos),
                enabled=len(state.weapons) > 1,
                bg=(118, 66, 48),
                text_size=15,
            )
        else:
            self.theme.draw_text(surface, "Click a weapon to inspect, Combine, or Recycle.", weap_panel.left + 14, act_y + 10, size=15, color=COLOR_MUTED)

        # Active Weapon Class Synergies
        syn_y = weap_panel.top + 252
        self.theme.draw_text(surface, "CLASS SYNERGIES", weap_panel.left + 14, syn_y, size=15, color=COLOR_GOLD)
        active_syns = [
            f"{state.db.weapon_classes[cid].name} ({cnt}): {state.db.weapon_classes[cid].description}"
            for cid, cnt in state.class_counts.items()
            if cnt >= 2 and cid in state.db.weapon_classes
        ]
        if active_syns:
            self.theme.draw_wrapped(surface, " • ".join(active_syns), weap_panel.left + 14, syn_y + 22, weap_panel.width - 28, size=14, color=COLOR_GOOD)
        else:
            self.theme.draw_text(surface, "Equip 2+ weapons of a matching class for set bonuses.", weap_panel.left + 14, syn_y + 24, size=14, color=COLOR_MUTED)

        # --- Bottom Center: Collected Items ---
        item_panel = pygame.Rect(500, 372, 434, 326)
        self.theme.draw_panel(surface, item_panel, bg=(26, 28, 36), border=(66, 72, 88))
        self.theme.draw_text(surface, f"ITEMS ({len(state.items)})", item_panel.left + 14, item_panel.top + 12, size=19, color=COLOR_GOLD)

        self.item_rects = []
        unique_items: list[tuple[str, int]] = []
        seen: set[str] = set()
        for iid in state.items:
            if iid not in seen:
                seen.add(iid)
                unique_items.append((iid, state.item_counts.get(iid, 1)))

        ix0 = item_panel.left + 14
        iy0 = item_panel.top + 42
        ib_size = 46
        igap = 7
        icols = 8
        hovered_item: str | None = None
        for idx, (iid, cnt) in enumerate(unique_items[:32]):
            r = idx // icols
            c = idx % icols
            irect = pygame.Rect(ix0 + c * (ib_size + igap), iy0 + r * (ib_size + igap), ib_size, ib_size)
            self.item_rects.append((irect, iid))
            idef = state.db.items[iid]
            hov = irect.collidepoint(mouse_pos)
            if hov:
                hovered_item = iid
            self.theme.draw_tier_card(surface, irect, idef.tier, hovered=hov)
            icon = pygame.transform.smoothscale(self.atlas.get_item(iid), (36, 36))
            surface.blit(icon, icon.get_rect(center=irect.center))
            if cnt > 1:
                self.theme.draw_text(surface, f"x{cnt}", irect.right - 3, irect.bottom - 2, size=13, color=COLOR_WHITE, align="bottomright", shadow=True)

        if hovered_item:
            idef = state.db.items[hovered_item]
            tip_y = item_panel.bottom - 62
            self.theme.draw_text(surface, f"{idef.name} (x{state.item_counts.get(hovered_item, 1)})", item_panel.left + 14, tip_y, size=16, color=TIER_COLORS[idef.tier])
            self.theme.draw_wrapped(surface, idef.description, item_panel.left + 14, tip_y + 20, item_panel.width - 28, size=14, color=COLOR_WHITE)
        else:
            self.theme.draw_text(surface, "Hover any item icon to inspect effects.", item_panel.left + 14, item_panel.bottom - 32, size=14, color=COLOR_MUTED)

        # --- Right Sidebar: Stats Inspector + GO! Button ---
        sidebar = pygame.Rect(sw - 332, 16, 306, 594)
        self.primary_tab_rect, self.secondary_tab_rect = _draw_stats_sidebar(
            surface, self.theme, state, sidebar, self.stats_tab, mouse_pos
        )

        self.go_rect = pygame.Rect(sw - 332, 624, 306, 74)
        next_w = state.wave + 1
        self.theme.draw_button(
            surface,
            self.go_rect,
            f"GO!  (Wave {next_w})",
            hovered=self.go_rect.collidepoint(mouse_pos),
            bg=(48, 126, 72),
            border=(112, 232, 142),
            text_size=26,
        )
