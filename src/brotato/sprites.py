"""Procedural vector-surface sprite & icon atlas with custom asset pack overrides."""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, Tuple

import pygame

from brotato.config import COLOR_ARENA_FLOOR_A, COLOR_ARENA_FLOOR_B, TIER_COLORS
from brotato.data_loader import GameDatabase
from brotato.models import CharacterDef, EnemyDef, ItemDef, WeaponDef


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return (
        max(0, min(255, int(color[0] * factor))),
        max(0, min(255, int(color[1] * factor))),
        max(0, min(255, int(color[2] * factor))),
    )


class SpriteAtlas:
    """Caches procedural sprites, custom asset overrides, and quantized weapon rotations."""

    def __init__(self, db: GameDatabase) -> None:
        self.db = db
        self._characters: Dict[str, pygame.Surface] = {}
        self._weapons: Dict[str, pygame.Surface] = {}
        self._weapon_rot_cache: Dict[Tuple[str, int, int], pygame.Surface] = {}
        self._enemies: Dict[str, pygame.Surface] = {}
        self._enemy_flash: Dict[str, pygame.Surface] = {}
        self._items: Dict[str, pygame.Surface] = {}
        self._misc: Dict[str, pygame.Surface] = {}
        self._floor_tile: pygame.Surface | None = None

        self._build_all()

    def _try_load_custom(self, key: str, size: tuple[int, int]) -> pygame.Surface | None:
        path = self.db.custom_assets.get(key)
        if not path:
            return None
        try:
            img = pygame.image.load(str(path)).convert_alpha()
            if img.get_size() != size:
                img = pygame.transform.smoothscale(img, size)
            return img
        except Exception:
            return None

    def _build_all(self) -> None:
        for cid, cdef in self.db.characters.items():
            custom = self._try_load_custom(f"sprites/characters/{cid}", (64, 64))
            self._characters[cid] = custom or self._draw_character(cdef)

        for wid, wdef in self.db.weapons.items():
            custom = self._try_load_custom(f"sprites/weapons/{wid}", (56, 40))
            self._weapons[wid] = custom or self._draw_weapon(wdef)

        for eid, edef in self.db.enemies.items():
            diam = int(edef.radius * 2.4)
            custom = self._try_load_custom(f"sprites/enemies/{eid}", (diam, diam))
            surf = custom or self._draw_enemy(edef)
            self._enemies[eid] = surf
            self._enemy_flash[eid] = self._make_white_flash(surf)

        for iid, idef in self.db.items.items():
            custom = self._try_load_custom(f"sprites/items/{iid}", (48, 48))
            self._items[iid] = custom or self._draw_item(idef)

        self._misc["material"] = self._draw_material()
        self._misc["consumable"] = self._draw_consumable()
        self._misc["crate"] = self._draw_crate()
        self._misc["tree"] = self._draw_tree()
        self._misc["tree_flash"] = self._make_white_flash(self._misc["tree"])
        self._misc["turret"] = self._draw_turret()
        self._misc["mine"] = self._draw_mine()

        custom_floor = self._try_load_custom("sprites/arena/floor", (256, 256))
        self._floor_tile = custom_floor or self._draw_floor_tile()

    def get_character(self, char_id: str) -> pygame.Surface:
        return self._characters[char_id]

    def get_weapon_icon(self, weapon_id: str) -> pygame.Surface:
        return self._weapons[weapon_id]

    def get_weapon_rotated(self, weapon_id: str, angle_rad: float, flip_y: bool = False) -> pygame.Surface:
        deg = int(round(math.degrees(angle_rad) / 4.0) * 4) % 360
        key = (weapon_id, deg, 1 if flip_y else 0)
        cached = self._weapon_rot_cache.get(key)
        if cached is None:
            base = self._weapons[weapon_id]
            if flip_y:
                base = pygame.transform.flip(base, False, True)
            cached = pygame.transform.rotozoom(base, -deg, 1.0)
            if len(self._weapon_rot_cache) > 4000:
                self._weapon_rot_cache.clear()
            self._weapon_rot_cache[key] = cached
        return cached

    def get_enemy(self, enemy_id: str, flash: bool = False) -> pygame.Surface:
        return self._enemy_flash[enemy_id] if flash else self._enemies[enemy_id]

    def get_item(self, item_id: str) -> pygame.Surface:
        return self._items[item_id]

    def get_misc(self, name: str) -> pygame.Surface:
        return self._misc[name]

    def get_floor_tile(self) -> pygame.Surface:
        assert self._floor_tile is not None
        return self._floor_tile

    def _make_white_flash(self, surf: pygame.Surface) -> pygame.Surface:
        out = surf.copy()
        w, h = out.get_size()
        px = pygame.PixelArray(out)
        for x in range(w):
            for y in range(h):
                c = out.unmap_rgb(px[x, y])
                if c.a > 20:
                    px[x, y] = (255, 255, 255, c.a)
        del px
        return out

    def _draw_character(self, cdef: CharacterDef) -> pygame.Surface:
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        col = tuple(cdef.appearance.get("color", (214, 168, 108)))
        hat = cdef.appearance.get("hat", "none")
        eyes = cdef.appearance.get("eyes", "happy")
        outline = (24, 20, 24)

        # Potato body (lumpy oval)
        pygame.draw.ellipse(s, outline, (11, 14, 42, 46))
        pygame.draw.ellipse(s, col, (14, 17, 36, 40))
        pygame.draw.ellipse(s, _shade(col, 1.14), (18, 20, 18, 14))
        # Subtle potato freckles
        pygame.draw.circle(s, _shade(col, 0.78), (21, 44), 2)
        pygame.draw.circle(s, _shade(col, 0.78), (42, 41), 2)

        # Eyes
        if eyes == "crazy":
            pygame.draw.circle(s, (255, 255, 255), (25, 31), 5)
            pygame.draw.circle(s, (255, 255, 255), (39, 31), 6)
            pygame.draw.circle(s, (20, 20, 25), (26, 31), 2)
            pygame.draw.circle(s, (20, 20, 25), (39, 30), 2)
        elif eyes == "fierce":
            pygame.draw.circle(s, (25, 20, 25), (25, 32), 3)
            pygame.draw.circle(s, (25, 20, 25), (39, 32), 3)
            pygame.draw.line(s, (25, 20, 25), (20, 27), (28, 30), 3)
            pygame.draw.line(s, (25, 20, 25), (44, 27), (36, 30), 3)
        elif eyes == "glow":
            pygame.draw.circle(s, (110, 245, 255), (25, 32), 4)
            pygame.draw.circle(s, (110, 245, 255), (39, 32), 4)
            pygame.draw.circle(s, (255, 255, 255), (25, 31), 2)
            pygame.draw.circle(s, (255, 255, 255), (39, 31), 2)
        elif eyes == "spooky":
            pygame.draw.ellipse(s, (25, 35, 48), (21, 28, 7, 9))
            pygame.draw.ellipse(s, (25, 35, 48), (36, 28, 7, 9))
        else:
            pygame.draw.circle(s, (25, 22, 25), (25, 32), 3)
            pygame.draw.circle(s, (25, 22, 25), (39, 32), 3)
            pygame.draw.circle(s, (255, 255, 255), (24, 31), 1)
            pygame.draw.circle(s, (255, 255, 255), (38, 31), 1)

        # Mouth
        if eyes in ("fierce", "crazy"):
            pygame.draw.arc(s, (30, 22, 22), (24, 38, 16, 8), 0.1, 3.0, 2)
        elif eyes == "spooky":
            pygame.draw.circle(s, (25, 35, 48), (32, 43), 3)
        else:
            pygame.draw.arc(s, (30, 22, 22), (26, 36, 12, 8), 3.2, 6.2, 2)

        # Accessories / Hats
        if hat == "headband":
            pygame.draw.rect(s, (218, 56, 62), (13, 21, 38, 6), border_radius=2)
        elif hat == "bandana":
            pygame.draw.rect(s, (65, 130, 220), (13, 20, 38, 7), border_radius=2)
            pygame.draw.polygon(s, (65, 130, 220), [(49, 22), (58, 18), (55, 27)])
        elif hat == "cowboy":
            pygame.draw.ellipse(s, (118, 76, 42), (7, 15, 50, 10))
            pygame.draw.rect(s, (138, 92, 52), (18, 6, 28, 13), border_radius=4)
            pygame.draw.rect(s, (65, 42, 24), (18, 14, 28, 3))
        elif hat == "wizard":
            pygame.draw.polygon(s, (78, 56, 158), [(12, 20), (52, 20), (34, 2)])
            pygame.draw.rect(s, (245, 205, 78), (18, 16, 28, 3))
        elif hat == "helmet":
            pygame.draw.arc(s, (150, 160, 172), (12, 8, 40, 28), 0, 3.14, 6)
            pygame.draw.rect(s, (150, 160, 172), (14, 12, 36, 10), border_radius=5)
        elif hat == "goggles":
            pygame.draw.rect(s, (80, 62, 46), (14, 19, 36, 6))
            pygame.draw.circle(s, (95, 220, 245), (24, 22), 6)
            pygame.draw.circle(s, (95, 220, 245), (40, 22), 6)
            pygame.draw.circle(s, outline, (24, 22), 6, 2)
            pygame.draw.circle(s, outline, (40, 22), 6, 2)
        elif hat == "halo":
            pygame.draw.ellipse(s, (245, 238, 140), (18, 5, 28, 8), 3)
        elif hat == "crown":
            pygame.draw.polygon(s, (245, 204, 64), [(18, 18), (20, 6), (26, 13), (32, 4), (38, 13), (44, 6), (46, 18)])
        elif hat == "spiky":
            pygame.draw.polygon(s, (235, 85, 65), [(18, 18), (23, 5), (28, 15), (33, 3), (38, 15), (44, 6), (46, 18)])
        elif hat == "clover":
            pygame.draw.circle(s, (75, 205, 85), (29, 10), 4)
            pygame.draw.circle(s, (75, 205, 85), (35, 10), 4)
            pygame.draw.circle(s, (75, 205, 85), (32, 6), 4)
        elif hat == "megaphone":
            pygame.draw.polygon(s, (245, 195, 70), [(42, 16), (56, 10), (56, 24)])

        return s

    def _draw_weapon(self, wdef: WeaponDef) -> pygame.Surface:
        s = pygame.Surface((56, 40), pygame.SRCALPHA)
        wid = wdef.id
        outline = (22, 20, 26)

        if wid in ("pistol",):
            pygame.draw.rect(s, outline, (16, 14, 24, 9), border_radius=2)
            pygame.draw.rect(s, outline, (16, 20, 8, 11), border_radius=2)
            pygame.draw.rect(s, (175, 182, 196), (18, 16, 20, 5))
            pygame.draw.rect(s, (125, 92, 62), (18, 21, 5, 8))
        elif wid == "smg":
            pygame.draw.rect(s, outline, (10, 14, 34, 10), border_radius=2)
            pygame.draw.rect(s, outline, (24, 22, 7, 12), border_radius=2)
            pygame.draw.rect(s, (90, 98, 112), (12, 16, 30, 6))
            pygame.draw.rect(s, (65, 70, 80), (25, 23, 5, 9))
        elif wid == "shotgun":
            pygame.draw.rect(s, outline, (8, 15, 38, 9), border_radius=2)
            pygame.draw.rect(s, (138, 86, 50), (10, 17, 14, 6))
            pygame.draw.rect(s, (155, 162, 175), (22, 16, 22, 5))
        elif wid == "laser_gun":
            pygame.draw.rect(s, outline, (10, 12, 36, 14), border_radius=4)
            pygame.draw.rect(s, (130, 145, 175), (12, 14, 30, 10), border_radius=3)
            pygame.draw.rect(s, (75, 240, 255), (26, 16, 18, 5))
        elif wid == "rocket_launcher":
            pygame.draw.rect(s, outline, (6, 11, 40, 16), border_radius=3)
            pygame.draw.rect(s, (96, 118, 84), (8, 13, 34, 12), border_radius=2)
            pygame.draw.circle(s, (255, 105, 55), (44, 19), 5)
        elif wid == "slingshot":
            pygame.draw.line(s, (145, 96, 52), (16, 30), (26, 20), 5)
            pygame.draw.line(s, (145, 96, 52), (26, 20), (35, 10), 4)
            pygame.draw.line(s, (145, 96, 52), (26, 20), (35, 28), 4)
            pygame.draw.circle(s, (220, 210, 185), (32, 19), 4)
        elif wid == "crossbow":
            pygame.draw.rect(s, (135, 86, 52), (12, 18, 28, 5))
            pygame.draw.arc(s, (180, 195, 210), (24, 6, 16, 28), -1.5, 1.5, 4)
            pygame.draw.line(s, (220, 245, 255), (18, 20), (46, 20), 2)
        elif wid == "wand":
            pygame.draw.line(s, (140, 90, 52), (10, 22), (38, 18), 5)
            pygame.draw.circle(s, (255, 130, 55), (41, 18), 7)
            pygame.draw.circle(s, (255, 235, 130), (41, 18), 3)
        elif wid == "taser":
            pygame.draw.rect(s, (55, 125, 215), (14, 14, 24, 11), border_radius=3)
            pygame.draw.line(s, (140, 235, 255), (38, 16), (48, 15), 3)
            pygame.draw.line(s, (140, 235, 255), (38, 22), (48, 23), 3)
        elif wid == "ghost_scepter":
            pygame.draw.line(s, (130, 195, 215), (10, 21), (38, 19), 4)
            pygame.draw.circle(s, (165, 248, 255), (41, 19), 7)
        elif wid in ("knife", "scissors"):
            pygame.draw.rect(s, (130, 82, 48), (12, 17, 12, 6), border_radius=2)
            pygame.draw.polygon(s, (205, 215, 228), [(24, 16), (48, 20), (24, 24)])
        elif wid == "lightning_shiv":
            pygame.draw.rect(s, (70, 90, 135), (12, 17, 12, 6), border_radius=2)
            pygame.draw.polygon(s, (115, 230, 255), [(24, 15), (49, 20), (24, 25)])
        elif wid == "spear":
            pygame.draw.rect(s, (138, 92, 50), (4, 18, 36, 4))
            pygame.draw.polygon(s, (210, 220, 235), [(38, 14), (54, 20), (38, 26)])
        elif wid == "stick":
            pygame.draw.line(s, outline, (8, 23), (48, 17), 9)
            pygame.draw.line(s, (148, 102, 58), (10, 23), (46, 17), 5)
        elif wid == "sword":
            pygame.draw.rect(s, (128, 82, 48), (8, 18, 10, 4))
            pygame.draw.rect(s, (215, 185, 78), (17, 13, 4, 14))
            pygame.draw.polygon(s, (212, 222, 236), [(21, 16), (50, 20), (21, 24)])
        elif wid == "chopper":
            pygame.draw.rect(s, (135, 86, 52), (10, 18, 12, 5))
            pygame.draw.rect(s, (195, 204, 215), (22, 11, 24, 15), border_radius=2)
        elif wid == "fist":
            pygame.draw.circle(s, outline, (32, 20), 11)
            pygame.draw.circle(s, (224, 172, 124), (32, 20), 9)
        elif wid == "claw":
            for yoff in (-6, 0, 6):
                pygame.draw.line(s, (225, 235, 245), (18, 20 + yoff), (46, 20 + yoff), 3)
        elif wid == "ghost_flint":
            pygame.draw.polygon(s, (165, 240, 255), [(14, 18), (46, 15), (40, 25), (14, 23)])
        elif wid == "ghost_axe":
            pygame.draw.rect(s, (125, 195, 215), (10, 18, 28, 4))
            pygame.draw.polygon(s, (175, 248, 255), [(30, 8), (46, 14), (42, 26), (30, 24)])
        elif wid == "wrench":
            pygame.draw.rect(s, (165, 172, 185), (12, 17, 26, 6))
            pygame.draw.circle(s, (165, 172, 185), (40, 20), 8)
            pygame.draw.rect(s, (0, 0, 0, 0), (40, 17, 10, 6))
        elif wid == "screwdriver":
            pygame.draw.rect(s, (218, 72, 62), (10, 16, 14, 8), border_radius=3)
            pygame.draw.rect(s, (195, 204, 215), (24, 18, 22, 4))
        elif wid == "pruner":
            pygame.draw.rect(s, (80, 175, 92), (10, 15, 14, 10), border_radius=2)
            pygame.draw.polygon(s, (205, 215, 225), [(24, 15), (44, 18), (24, 22)])
            pygame.draw.polygon(s, (180, 190, 200), [(24, 20), (42, 25), (24, 26)])
        elif wid == "plank":
            pygame.draw.rect(s, outline, (10, 13, 38, 14), border_radius=2)
            pygame.draw.rect(s, (158, 106, 60), (12, 15, 34, 10))
            pygame.draw.circle(s, (220, 220, 230), (41, 18), 2)
        elif wid == "torch":
            pygame.draw.rect(s, (140, 92, 50), (10, 18, 24, 5))
            pygame.draw.circle(s, (255, 118, 42), (39, 20), 8)
            pygame.draw.circle(s, (255, 225, 95), (40, 20), 4)
        else:  # rock
            pygame.draw.circle(s, outline, (30, 20), 12)
            pygame.draw.circle(s, (132, 136, 145), (30, 20), 10)
            pygame.draw.circle(s, (165, 170, 178), (27, 17), 4)
        return s

    def _draw_enemy(self, edef: EnemyDef) -> pygame.Surface:
        size = int(edef.radius * 2.4)
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        r = int(edef.radius)
        col = edef.color
        acc = edef.accent
        outline = (22, 16, 20)

        if edef.shape == "fly":
            pygame.draw.ellipse(s, (220, 235, 255, 180), (cx - r - 5, cy - r + 1, r, r // 2 + 4))
            pygame.draw.ellipse(s, (220, 235, 255, 180), (cx + 5, cy - r + 1, r, r // 2 + 4))
        if edef.shape in ("horned", "boss"):
            pygame.draw.polygon(s, acc, [(cx - r + 4, cy - r // 2), (cx - r - 6, cy - r - 4), (cx - 4, cy - r + 2)])
            pygame.draw.polygon(s, acc, [(cx + r - 4, cy - r // 2), (cx + r + 6, cy - r - 4), (cx + 4, cy - r + 2)])

        pygame.draw.circle(s, outline, (cx, cy), r + 2)
        pygame.draw.circle(s, col, (cx, cy), r)
        pygame.draw.circle(s, _shade(col, 1.18), (cx - r // 3, cy - r // 3), max(3, r // 2))

        if edef.shape == "spiky":
            for ang in range(0, 360, 45):
                rad = math.radians(ang)
                px = cx + int(math.cos(rad) * (r + 4))
                py = cy + int(math.sin(rad) * (r + 4))
                pygame.draw.circle(s, acc, (px, py), 3)
        elif edef.shape == "egg":
            pygame.draw.ellipse(s, outline, (cx - r + 2, cy - r - 2, r * 2 - 4, r * 2 + 4))
            pygame.draw.ellipse(s, col, (cx - r + 4, cy - r, r * 2 - 8, r * 2))
            pygame.draw.circle(s, acc, (cx - 4, cy - 3), 4)
            pygame.draw.circle(s, acc, (cx + 5, cy + 4), 3)
            return s
        elif edef.shape == "watcher":
            pygame.draw.circle(s, (255, 240, 255), (cx, cy), max(8, r // 2))
            pygame.draw.circle(s, (165, 25, 185), (cx, cy), max(4, r // 4))
            pygame.draw.circle(s, (20, 10, 30), (cx, cy), max(2, r // 7))
            return s
        elif edef.shape == "loot":
            pygame.draw.circle(s, acc, (cx, cy - 4), max(4, r // 2), 2)

        # Angry alien eyes
        ex_off = max(4, int(r * 0.36))
        ey_off = max(2, int(r * 0.16))
        eye_r = max(2, int(r * 0.17))
        pygame.draw.circle(s, (255, 245, 245), (cx - ex_off, cy - ey_off), eye_r + 1)
        pygame.draw.circle(s, (255, 245, 245), (cx + ex_off, cy - ey_off), eye_r + 1)
        pygame.draw.circle(s, (20, 12, 16), (cx - ex_off, cy - ey_off), eye_r)
        pygame.draw.circle(s, (20, 12, 16), (cx + ex_off, cy - ey_off), eye_r)
        return s

    def _draw_item(self, idef: ItemDef) -> pygame.Surface:
        s = pygame.Surface((48, 48), pygame.SRCALPHA)
        tcol = TIER_COLORS[idef.tier]
        pygame.draw.circle(s, _shade(tcol, 0.35), (24, 24), 20)
        pygame.draw.circle(s, tcol, (24, 24), 20, 2)

        iid = idef.id
        if "tree" in iid:
            pygame.draw.rect(s, (125, 84, 52), (21, 26, 6, 12))
            pygame.draw.circle(s, (86, 195, 92), (24, 19), 10)
        elif "lemonade" in iid:
            pygame.draw.rect(s, (245, 224, 82), (16, 15, 16, 20), border_radius=3)
            pygame.draw.line(s, (255, 120, 120), (26, 15), (32, 9), 3)
        elif "coffee" in iid:
            pygame.draw.rect(s, (235, 235, 240), (15, 18, 16, 16), border_radius=3)
            pygame.draw.rect(s, (105, 65, 38), (17, 20, 12, 4))
        elif "glasses" in iid or "sunglasses" in iid or "lens" in iid:
            col = (40, 42, 52) if "sun" in iid else (150, 225, 255)
            pygame.draw.circle(s, col, (17, 24), 6)
            pygame.draw.circle(s, col, (31, 24), 6)
            pygame.draw.circle(s, (240, 240, 245), (17, 24), 6, 2)
            pygame.draw.circle(s, (240, 240, 245), (31, 24), 6, 2)
        elif "mushroom" in iid:
            pygame.draw.rect(s, (235, 225, 205), (20, 24, 8, 12))
            pygame.draw.ellipse(s, (220, 72, 72), (12, 13, 24, 14))
            pygame.draw.circle(s, (255, 245, 245), (19, 19), 2)
            pygame.draw.circle(s, (255, 245, 245), (28, 18), 2)
        elif "piggy" in iid:
            pygame.draw.ellipse(s, (245, 152, 175), (12, 16, 24, 17))
            pygame.draw.circle(s, (225, 115, 145), (34, 24), 4)
        elif "crown" in iid:
            pygame.draw.polygon(s, (255, 212, 65), [(12, 32), (14, 15), (20, 23), (24, 13), (28, 23), (34, 15), (36, 32)])
        elif "turret" in iid or "cog" in iid:
            pygame.draw.circle(s, (165, 176, 190), (24, 24), 10)
            pygame.draw.circle(s, (75, 220, 175), (24, 24), 5)
        elif "bandana" in iid:
            pygame.draw.rect(s, (225, 68, 72), (12, 19, 24, 10), border_radius=3)
        elif "sausage" in iid:
            pygame.draw.arc(s, (220, 105, 85), (12, 14, 24, 20), 0.3, 2.8, 7)
        elif "snake" in iid:
            pygame.draw.arc(s, (96, 205, 98), (12, 14, 24, 20), 0.1, 4.5, 5)
        elif "duck" in iid:
            pygame.draw.circle(s, (248, 214, 68), (24, 26), 9)
            pygame.draw.circle(s, (248, 214, 68), (28, 17), 6)
            pygame.draw.polygon(s, (245, 130, 45), [(33, 16), (39, 18), (33, 20)])
        elif "ricochet" in iid:
            pygame.draw.lines(s, (125, 240, 255), False, [(13, 30), (24, 14), (35, 30)], 3)
        elif "fairy" in iid:
            pygame.draw.ellipse(s, (185, 245, 255), (11, 16, 12, 16))
            pygame.draw.ellipse(s, (185, 245, 255), (25, 16, 12, 16))
            pygame.draw.circle(s, (255, 215, 240), (24, 24), 6)
        else:
            # Clean iconic badge using tag color
            pygame.draw.polygon(s, tcol, [(24, 11), (36, 24), (24, 37), (12, 24)])
            pygame.draw.circle(s, (245, 248, 252), (24, 24), 5)
        return s

    def _draw_material(self) -> pygame.Surface:
        s = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.polygon(s, (18, 52, 24), [(9, 1), (16, 8), (12, 16), (5, 16), (2, 8)])
        pygame.draw.polygon(s, (78, 238, 118), [(9, 3), (14, 8), (11, 14), (6, 14), (4, 8)])
        pygame.draw.circle(s, (195, 255, 205), (7, 7), 2)
        return s

    def _draw_consumable(self) -> pygame.Surface:
        s = pygame.Surface((22, 22), pygame.SRCALPHA)
        pygame.draw.circle(s, (22, 54, 28), (11, 12), 8)
        pygame.draw.circle(s, (118, 245, 92), (11, 12), 6)
        pygame.draw.ellipse(s, (56, 175, 58), (10, 2, 7, 5))
        return s

    def _draw_crate(self) -> pygame.Surface:
        s = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.rect(s, (28, 22, 16), (2, 2, 24, 24), border_radius=4)
        pygame.draw.rect(s, (188, 132, 54), (4, 4, 20, 20), border_radius=3)
        pygame.draw.rect(s, (250, 206, 82), (4, 11, 20, 5))
        pygame.draw.rect(s, (250, 206, 82), (11, 4, 5, 20))
        return s

    def _draw_tree(self) -> pygame.Surface:
        s = pygame.Surface((60, 68), pygame.SRCALPHA)
        # Trunk
        pygame.draw.rect(s, (24, 18, 16), (23, 36, 14, 24), border_radius=3)
        pygame.draw.rect(s, (124, 82, 48), (25, 38, 10, 20), border_radius=2)
        # Canopy
        pygame.draw.circle(s, (22, 34, 22), (30, 26), 22)
        pygame.draw.circle(s, (66, 148, 72), (30, 26), 19)
        pygame.draw.circle(s, (92, 185, 88), (24, 20), 12)
        pygame.draw.circle(s, (92, 185, 88), (36, 22), 11)
        return s

    def _draw_turret(self) -> pygame.Surface:
        s = pygame.Surface((36, 36), pygame.SRCALPHA)
        pygame.draw.circle(s, (24, 26, 30), (18, 18), 13)
        pygame.draw.circle(s, (112, 132, 148), (18, 18), 11)
        pygame.draw.circle(s, (92, 242, 175), (18, 18), 5)
        return s

    def _draw_mine(self) -> pygame.Surface:
        s = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(s, (28, 22, 24), (12, 12), 9)
        pygame.draw.circle(s, (96, 102, 115), (12, 12), 7)
        pygame.draw.circle(s, (255, 76, 76), (12, 12), 3)
        return s

    def _draw_floor_tile(self) -> pygame.Surface:
        s = pygame.Surface((256, 256))
        s.fill(COLOR_ARENA_FLOOR_A)
        rng = random.Random(1337)
        for gx in range(0, 256, 64):
            for gy in range(0, 256, 64):
                if ((gx // 64) + (gy // 64)) % 2 == 0:
                    pygame.draw.rect(s, COLOR_ARENA_FLOOR_B, (gx, gy, 64, 64))
        for _ in range(90):
            px = rng.randint(0, 254)
            py = rng.randint(0, 254)
            r = rng.randint(1, 3)
            c = (32, 34, 40) if rng.random() < 0.5 else (52, 55, 63)
            pygame.draw.circle(s, c, (px, py), r)
        return s
