"""Arena world & combat entity renderer."""

from __future__ import annotations

import math

import pygame

from brotato.config import (
    ARENA_HEIGHT,
    ARENA_WALL_MARGIN,
    ARENA_WIDTH,
    COLOR_ARENA_BORDER,
    COLOR_ARENA_WALL,
    TIER_COLORS,
)
from brotato.engine.game_state import GameState
from brotato.sprites import SpriteAtlas
from brotato.ui.theme import UITheme


class ArenaRenderer:
    """Renders the 2D arena, camera tracking, entities, VFX, and floating text."""

    def __init__(self, atlas: SpriteAtlas, theme: UITheme) -> None:
        self.atlas = atlas
        self.theme = theme
        self.cam_x: float = ARENA_WIDTH * 0.5
        self.cam_y: float = ARENA_HEIGHT * 0.5

    def snap_camera(self, state: GameState) -> None:
        self.cam_x = state.player_x
        self.cam_y = state.player_y

    def get_camera_offset(self, state: GameState, screen_w: int, screen_h: int, dt: float) -> tuple[float, float]:
        # Smooth camera follow clamped nicely near arena borders
        alpha = min(1.0, dt * 10.0)
        self.cam_x += (state.player_x - self.cam_x) * alpha
        self.cam_y += (state.player_y - self.cam_y) * alpha

        pad = 90.0
        half_w = screen_w * 0.5
        half_h = screen_h * 0.5
        if ARENA_WIDTH + pad * 2 > screen_w:
            self.cam_x = max(half_w - pad, min(ARENA_WIDTH + pad - half_w, self.cam_x))
        else:
            self.cam_x = ARENA_WIDTH * 0.5

        if ARENA_HEIGHT + pad * 2 > screen_h:
            self.cam_y = max(half_h - pad, min(ARENA_HEIGHT + pad - half_h, self.cam_y))
        else:
            self.cam_y = ARENA_HEIGHT * 0.5

        return self.cam_x - half_w, self.cam_y - half_h

    def render(self, surface: pygame.Surface, state: GameState, dt: float) -> tuple[float, float]:
        sw, sh = surface.get_size()
        ox, oy = self.get_camera_offset(state, sw, sh, dt)

        # Outer dark wall backdrop
        surface.fill(COLOR_ARENA_WALL)

        # Arena interior floor tiles clipped cleanly to arena rect
        arena_screen_rect = pygame.Rect(
            int(ARENA_WALL_MARGIN - ox),
            int(ARENA_WALL_MARGIN - oy),
            int(ARENA_WIDTH - ARENA_WALL_MARGIN * 2),
            int(ARENA_HEIGHT - ARENA_WALL_MARGIN * 2),
        )
        tile = self.atlas.get_floor_tile()
        tw, th = tile.get_size()

        prev_clip = surface.get_clip()
        vis_arena = arena_screen_rect.clip(pygame.Rect(0, 0, sw, sh))
        if vis_arena.width > 0 and vis_arena.height > 0:
            surface.set_clip(vis_arena)
            start_tx = int(math.floor((vis_arena.left + ox) / tw) * tw)
            start_ty = int(math.floor((vis_arena.top + oy) / th) * th)
            end_tx = int(vis_arena.right + ox)
            end_ty = int(vis_arena.bottom + oy)
            for wx in range(start_tx, end_tx + tw, tw):
                for wy in range(start_ty, end_ty + th, th):
                    surface.blit(tile, (int(wx - ox), int(wy - oy)))
            surface.set_clip(prev_clip)

        # Crisp stone border around arena
        pygame.draw.rect(surface, COLOR_ARENA_BORDER, arena_screen_rect, width=6, border_radius=4)

        # Spawn telegraphs ('X' markers)
        for tel in state.telegraphs:
            sx, sy = int(tel.x - ox), int(tel.y - oy)
            if -40 <= sx <= sw + 40 and -40 <= sy <= sh + 40:
                pulse = 0.55 + 0.45 * math.sin((tel.duration - tel.timer) * 14.0)
                sz = int(10 + 4 * pulse)
                col = (255, 70, 82) if "boss" not in tel.def_id else (255, 210, 75)
                pygame.draw.line(surface, col, (sx - sz, sy - sz), (sx + sz, sy + sz), 4)
                pygame.draw.line(surface, col, (sx - sz, sy + sz), (sx + sz, sy - sz), 4)

        # Charger / Boss dash warning lanes
        for e in state.enemies:
            if e.ai_phase == 1 and e.behavior in ("charger", "elite", "boss_predator"):
                sx, sy = int(e.x - ox), int(e.y - oy)
                ex = int(sx + e.charge_dx * 360)
                ey = int(sy + e.charge_dy * 360)
                pygame.draw.line(surface, (255, 70, 70), (sx, sy), (ex, ey), 3)

        # Ground shadows (fast ellipse blit)
        shadow_color = (18, 19, 24)
        for tr in state.trees:
            sx, sy = int(tr.x - ox), int(tr.y - oy)
            if -80 <= sx <= sw + 80 and -80 <= sy <= sh + 80:
                pygame.draw.ellipse(surface, shadow_color, (sx - 20, sy + 14, 40, 14))
        for e in state.enemies:
            sx, sy = int(e.x - ox), int(e.y - oy)
            if -80 <= sx <= sw + 80 and -80 <= sy <= sh + 80:
                r = int(e.radius * 0.9)
                pygame.draw.ellipse(surface, shadow_color, (sx - r, sy + int(e.radius * 0.55), r * 2, max(8, r // 2)))

        # Mines
        mine_surf = self.atlas.get_misc("mine")
        for m in state.mines:
            sx, sy = int(m.x - ox), int(m.y - oy)
            surface.blit(mine_surf, mine_surf.get_rect(center=(sx, sy)))

        # Pickups (materials, consumables, crates)
        mat_surf = self.atlas.get_misc("material")
        cons_surf = self.atlas.get_misc("consumable")
        crate_surf = self.atlas.get_misc("crate")
        for p in state.pickups:
            sx = int(p.x - ox)
            sy = int(p.y - oy + math.sin(p.bob_phase) * 3.0)
            if -32 <= sx <= sw + 32 and -32 <= sy <= sh + 32:
                if p.kind == "material":
                    surface.blit(mat_surf, mat_surf.get_rect(center=(sx, sy)))
                elif p.kind == "consumable":
                    surface.blit(cons_surf, cons_surf.get_rect(center=(sx, sy)))
                else:
                    surface.blit(crate_surf, crate_surf.get_rect(center=(sx, sy)))

        # Trees
        for tr in state.trees:
            sx, sy = int(tr.x - ox), int(tr.y - oy)
            if -80 <= sx <= sw + 80 and -80 <= sy <= sh + 80:
                tsurf = self.atlas.get_misc("tree_flash" if tr.hit_flash > 0 else "tree")
                surface.blit(tsurf, tsurf.get_rect(center=(sx, sy - 6)))

        # Turrets
        turret_surf = self.atlas.get_misc("turret")
        for t in state.turrets:
            sx, sy = int(t.x - ox), int(t.y - oy)
            surface.blit(turret_surf, turret_surf.get_rect(center=(sx, sy)))
            bx = sx + int(math.cos(t.aim_angle) * 16)
            by = sy + int(math.sin(t.aim_angle) * 16)
            pygame.draw.line(surface, (185, 215, 225), (sx, sy), (bx, by), 5)

        # Enemies
        for e in state.enemies:
            sx, sy = int(e.x - ox), int(e.y - oy)
            if -90 <= sx <= sw + 90 and -90 <= sy <= sh + 90:
                esurf = self.atlas.get_enemy(e.def_id, flash=(e.hit_flash > 0))
                surface.blit(esurf, esurf.get_rect(center=(sx, sy)))
                if e.burn_ticks > 0:
                    pygame.draw.circle(surface, (255, 130, 45), (sx, sy), int(e.radius + 3), 2)
                if e.is_elite and not e.is_boss:
                    # Mini HP bar above Elites
                    bw = 54
                    ratio = max(0.0, e.hp / max(1.0, e.max_hp))
                    pygame.draw.rect(surface, (30, 16, 18), (sx - bw // 2, sy - int(e.radius) - 14, bw, 6))
                    pygame.draw.rect(surface, (235, 65, 75), (sx - bw // 2, sy - int(e.radius) - 14, int(bw * ratio), 6))

        # Player & Potato shadow + bob + i-frames
        px_scr = int(state.player_x - ox)
        py_scr = int(state.player_y - oy)
        pygame.draw.ellipse(surface, shadow_color, (px_scr - 18, py_scr + 16, 36, 12))
        blink_skip = state.invuln_timer > 0 and int(state.invuln_timer * 24) % 2 == 0
        if not blink_skip:
            char_surf = self.atlas.get_character(state.character.id)
            if state.player_facing_x < 0:
                char_surf = pygame.transform.flip(char_surf, True, False)
            bob = 0.0
            if abs(state.player_vx) > 5 or abs(state.player_vy) > 5:
                bob = math.sin(state.wave_timer * 18.0) * 3.0
            surface.blit(char_surf, char_surf.get_rect(center=(px_scr, int(py_scr - 4 + bob))))

        # Equipped Orbiting Weapons + Melee animations
        for w in state.weapons:
            wdef = state.db.weapons[w.def_id]
            wx = state.player_x + w.slot_x - ox
            wy = state.player_y + w.slot_y - oy

            anim_angle = w.aim_angle
            thrust_off = 0.0
            if w.swing_timer > 0 and w.swing_duration > 0:
                p = 1.0 - (w.swing_timer / w.swing_duration)
                if wdef.attack_style == "thrust":
                    thrust_off = math.sin(p * math.pi) * 34.0
                else:
                    sweep_span = math.radians(135.0)
                    anim_angle = w.aim_angle + w.swing_dir * ((p - 0.5) * sweep_span)
                    # Draw subtle slash trail arc
                    arc_r = 46
                    p1 = (wx + math.cos(anim_angle) * arc_r, wy + math.sin(anim_angle) * arc_r)
                    p2 = (wx + math.cos(anim_angle - w.swing_dir * 0.45) * arc_r, wy + math.sin(anim_angle - w.swing_dir * 0.45) * arc_r)
                    pygame.draw.line(surface, TIER_COLORS[w.tier], p1, p2, 3)

            draw_x = wx + math.cos(anim_angle) * thrust_off
            draw_y = wy + math.sin(anim_angle) * thrust_off
            flip_y = math.cos(anim_angle) < 0
            wsurf = self.atlas.get_weapon_rotated(w.def_id, anim_angle, flip_y=flip_y)
            surface.blit(wsurf, wsurf.get_rect(center=(int(draw_x), int(draw_y))))

        # Projectiles
        for p in state.projectiles:
            sx, sy = int(p.x - ox), int(p.y - oy)
            if -30 <= sx <= sw + 30 and -30 <= sy <= sh + 30:
                rad = int(p.radius)
                pygame.draw.circle(surface, (18, 16, 22), (sx, sy), rad + 2)
                pygame.draw.circle(surface, p.color, (sx, sy), rad)
                if not p.from_player:
                    pygame.draw.circle(surface, (255, 225, 225), (sx, sy), max(2, rad // 2))

        # Explosions
        for ex in state.explosions:
            sx, sy = int(ex.x - ox), int(ex.y - oy)
            prog = 1.0 - (ex.timer / ex.duration)
            cur_r = int(ex.radius * (0.35 + 0.65 * prog))
            width = max(2, int(8 * (1.0 - prog)))
            pygame.draw.circle(surface, ex.color, (sx, sy), cur_r, width)
            if prog < 0.35:
                pygame.draw.circle(surface, (255, 235, 160), (sx, sy), max(4, int(cur_r * 0.45)))

        # Particles
        for pt in state.particles:
            sx, sy = int(pt.x - ox), int(pt.y - oy)
            if 0 <= sx <= sw and 0 <= sy <= sh:
                r = max(1, int(pt.radius * (pt.life / pt.max_life)))
                pygame.draw.circle(surface, pt.color, (sx, sy), r)

        # Floating Damage Numbers & Alerts (cached surfaces!)
        for ft in state.floating_texts:
            sx, sy = int(ft.x - ox), int(ft.y - oy)
            if -40 <= sx <= sw + 40 and -40 <= sy <= sh + 40:
                sz = max(15, int(20 * ft.scale))
                self.theme.draw_text(surface, ft.text, sx, sy, size=sz, color=ft.color, align="center", shadow=True)

        return ox, oy
