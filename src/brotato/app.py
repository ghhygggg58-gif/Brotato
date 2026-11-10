"""Main Pygame-CE application loop and screen state controller."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import pygame

from brotato.audio import SoundBank
from brotato.config import DEFAULT_HEIGHT, DEFAULT_WIDTH, FIXED_DT, TARGET_FPS
from brotato.data_loader import GameDatabase, load_database
from brotato.engine.combat import step_wave
from brotato.engine.game_state import GameState
from brotato.engine.level_up import (
    generate_level_up_choices,
    pick_level_up_choice,
    reroll_level_up_choices,
)
from brotato.engine.shop import (
    buy_shop_offer,
    generate_shop,
    recycle_weapon,
    reroll_shop,
    resolve_crate,
    roll_crate_item,
    toggle_lock_offer,
)
from brotato.sprites import SpriteAtlas
from brotato.ui.hud import CombatHUD
from brotato.ui.menus import SetupScreen, SummaryScreen, TitleScreen
from brotato.ui.renderer import ArenaRenderer
from brotato.ui.shop_screen import CrateModal, LevelUpScreen, ShopScreen
from brotato.ui.theme import UITheme

ScreenMode = Literal["TITLE", "SETUP", "COMBAT", "CRATE", "LEVEL_UP", "SHOP", "SUMMARY"]


class BrotatoApp:
    """Top-level interactive Pygame-CE game controller."""

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        headless: bool = False,
        fps: int = TARGET_FPS,
    ) -> None:
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

        pygame.init()
        flags = pygame.RESIZABLE if not headless else 0
        self.screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption("Brotato Python")
        self.clock = pygame.time.Clock()
        self.target_fps = fps
        self.running = True

        self.db: GameDatabase = load_database()
        custom_font = self.db.custom_assets.get("fonts/main")
        self.theme = UITheme(custom_font_path=custom_font)
        self.atlas = SpriteAtlas(self.db)
        self.sfx = SoundBank(self.db.custom_assets, enabled=not headless)

        self.renderer = ArenaRenderer(self.atlas, self.theme)
        self.hud = CombatHUD(self.atlas, self.theme)
        self.title_screen = TitleScreen(self.atlas, self.theme)
        self.setup_screen = SetupScreen(self.db, self.atlas, self.theme)
        self.crate_modal = CrateModal(self.atlas, self.theme)
        self.levelup_screen = LevelUpScreen(self.atlas, self.theme)
        self.shop_screen = ShopScreen(self.atlas, self.theme)
        self.summary_screen = SummaryScreen(self.atlas, self.theme)

        self.mode: ScreenMode = "TITLE"
        self.paused: bool = False
        self.state: GameState | None = None
        self.anim_t: float = 0.0
        self._cam_offset: tuple[float, float] = (0.0, 0.0)

    def start_new_run(
        self,
        character_id: str | None = None,
        weapon_id: str | None = None,
        danger_level: int | None = None,
        seed: int | None = None,
    ) -> None:
        cid = character_id or self.setup_screen.current_char_id
        wid = weapon_id or self.setup_screen.current_weapon_id
        dlvl = self.setup_screen.danger_level if danger_level is None else danger_level
        self.state = GameState(self.db, cid, wid, danger_level=dlvl, seed=seed)
        self.state.start_wave(1)
        self.renderer.snap_camera(self.state)
        self.paused = False
        self.mode = "COMBAT"

    def _advance_post_wave_phase(self) -> None:
        assert self.state is not None
        st = self.state
        if st.run_lost or (st.run_won and not st.endless_mode):
            self.mode = "SUMMARY"
            return
        if st.pending_crates > 0:
            roll_crate_item(st)
            self.mode = "CRATE"
            return
        if st.pending_level_ups > 0:
            generate_level_up_choices(st)
            self.mode = "LEVEL_UP"
            return
        self.shop_screen.selected_weapon_idx = None
        generate_shop(st, preserve_locked=True)
        self.mode = "SHOP"

    def _consume_audio_events(self) -> None:
        if self.state is None or not self.state.events:
            return
        for ev, _payload in self.state.events:
            self.sfx.play(ev)
        self.state.events.clear()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            self.sfx.muted = not self.sfx.muted
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self.hud.show_debug = not self.hud.show_debug
            return

        if self.mode == "TITLE":
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.mode = "SETUP"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.title_screen.start_rect.collidepoint(event.pos):
                    self.sfx.play("buy")
                    self.mode = "SETUP"
                elif self.title_screen.quit_rect.collidepoint(event.pos):
                    self.running = False

        elif self.mode == "SETUP":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.mode = "TITLE"
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.sfx.play("buy")
                    self.start_new_run()
                elif event.key == pygame.K_RIGHT:
                    self.setup_screen.select_character(self.setup_screen.selected_char_idx + 1)
                elif event.key == pygame.K_LEFT:
                    self.setup_screen.select_character(self.setup_screen.selected_char_idx - 1)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                for idx, rect in enumerate(self.setup_screen.char_rects):
                    if rect.collidepoint(pos):
                        self.setup_screen.select_character(idx)
                        self.sfx.play("pickup")
                        return
                for w_idx, rect in enumerate(self.setup_screen.weapon_rects):
                    if rect.collidepoint(pos):
                        self.setup_screen.selected_weapon_idx = w_idx
                        self.sfx.play("pickup")
                        return
                for d_idx, rect in enumerate(self.setup_screen.danger_rects):
                    if rect.collidepoint(pos):
                        self.setup_screen.danger_level = d_idx
                        self.sfx.play("pickup")
                        return
                if self.setup_screen.back_rect.collidepoint(pos):
                    self.mode = "TITLE"
                elif self.setup_screen.go_rect.collidepoint(pos):
                    self.sfx.play("buy")
                    self.start_new_run()

        elif self.mode == "COMBAT" and self.state is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif event.key == pygame.K_m and not self.paused:
                    self.state.manual_aim = not self.state.manual_aim
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.paused:
                    pr = self.hud.pause_rects
                    if pr.get("resume") and pr["resume"].collidepoint(pos):
                        self.paused = False
                    elif pr.get("aim") and pr["aim"].collidepoint(pos):
                        self.state.manual_aim = not self.state.manual_aim
                    elif pr.get("mute") and pr["mute"].collidepoint(pos):
                        self.sfx.muted = not self.sfx.muted
                    elif pr.get("quit") and pr["quit"].collidepoint(pos):
                        self.paused = False
                        self.mode = "TITLE"
                elif self.hud.aim_btn_rect.collidepoint(pos):
                    self.state.manual_aim = not self.state.manual_aim

        elif self.mode == "CRATE" and self.state is not None:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_RETURN):
                    resolve_crate(self.state, take=True)
                    self._consume_audio_events()
                    self._advance_post_wave_phase()
                elif event.key == pygame.K_2:
                    resolve_crate(self.state, take=False)
                    self._consume_audio_events()
                    self._advance_post_wave_phase()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.crate_modal.take_rect.collidepoint(event.pos):
                    resolve_crate(self.state, take=True)
                    self._consume_audio_events()
                    self._advance_post_wave_phase()
                elif self.crate_modal.recycle_rect.collidepoint(event.pos):
                    resolve_crate(self.state, take=False)
                    self._consume_audio_events()
                    self._advance_post_wave_phase()

        elif self.mode == "LEVEL_UP" and self.state is not None:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    idx = event.key - pygame.K_1
                    if pick_level_up_choice(self.state, idx):
                        self._consume_audio_events()
                        if self.state.pending_level_ups <= 0:
                            self._advance_post_wave_phase()
                elif event.key == pygame.K_r:
                    reroll_level_up_choices(self.state)
                    self._consume_audio_events()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.levelup_screen.primary_tab_rect.collidepoint(pos):
                    self.levelup_screen.stats_tab = "primary"
                elif self.levelup_screen.secondary_tab_rect.collidepoint(pos):
                    self.levelup_screen.stats_tab = "secondary"
                elif self.levelup_screen.reroll_rect.collidepoint(pos):
                    reroll_level_up_choices(self.state)
                    self._consume_audio_events()
                else:
                    for idx, rect in enumerate(self.levelup_screen.card_rects):
                        if rect.collidepoint(pos):
                            if pick_level_up_choice(self.state, idx):
                                self._consume_audio_events()
                                if self.state.pending_level_ups <= 0:
                                    self._advance_post_wave_phase()
                            break

        elif self.mode == "SHOP" and self.state is not None:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.state.start_wave(self.state.wave + 1)
                    self.renderer.snap_camera(self.state)
                    self.mode = "COMBAT"
                elif event.key == pygame.K_r:
                    reroll_shop(self.state)
                    self._consume_audio_events()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                ss = self.shop_screen
                if ss.primary_tab_rect.collidepoint(pos):
                    ss.stats_tab = "primary"
                elif ss.secondary_tab_rect.collidepoint(pos):
                    ss.stats_tab = "secondary"
                elif ss.reroll_rect.collidepoint(pos):
                    reroll_shop(self.state)
                    self._consume_audio_events()
                elif ss.go_rect.collidepoint(pos):
                    self.state.start_wave(self.state.wave + 1)
                    self.renderer.snap_camera(self.state)
                    self.mode = "COMBAT"
                elif ss.combine_rect.collidepoint(pos) and ss.selected_weapon_idx is not None:
                    partner = self.state.can_combine_at(ss.selected_weapon_idx)
                    if partner is not None and self.state.combine_weapons(ss.selected_weapon_idx, partner):
                        ss.selected_weapon_idx = None
                        self.sfx.play("levelup")
                elif ss.recycle_rect.collidepoint(pos) and ss.selected_weapon_idx is not None:
                    if recycle_weapon(self.state, ss.selected_weapon_idx):
                        ss.selected_weapon_idx = None
                        self._consume_audio_events()
                else:
                    for idx, rect in enumerate(ss.buy_rects):
                        if rect.collidepoint(pos):
                            buy_shop_offer(self.state, idx)
                            self._consume_audio_events()
                            return
                    for idx, rect in enumerate(ss.lock_rects):
                        if rect.collidepoint(pos):
                            toggle_lock_offer(self.state, idx)
                            self.sfx.play("pickup")
                            return
                    for idx, rect in enumerate(ss.weapon_rects):
                        if rect.collidepoint(pos):
                            ss.selected_weapon_idx = None if ss.selected_weapon_idx == idx else idx
                            return

        elif self.mode == "SUMMARY" and self.state is not None:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.summary_screen.endless_rect.collidepoint(pos) and self.state.run_won:
                    self.state.endless_mode = True
                    self.state.run_won = False
                    self._advance_post_wave_phase()
                elif self.summary_screen.restart_rect.collidepoint(pos):
                    self.mode = "SETUP"
                elif self.summary_screen.title_rect.collidepoint(pos):
                    self.mode = "TITLE"

    def step_frame(self, dt: float) -> None:
        self.anim_t += dt
        if self.mode == "COMBAT" and self.state is not None and not self.paused:
            keys = pygame.key.get_pressed()
            dx = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(keys[pygame.K_w] or keys[pygame.K_UP])
            mx_scr, my_scr = pygame.mouse.get_pos()
            mwx = mx_scr + self._cam_offset[0]
            mwy = my_scr + self._cam_offset[1]

            ended = step_wave(self.state, dt, dx, dy, mwx, mwy)
            self._consume_audio_events()
            if ended:
                self._advance_post_wave_phase()

    def render_frame(self, dt: float) -> None:
        mouse_pos = pygame.mouse.get_pos()
        if self.mode == "TITLE":
            self.title_screen.draw(self.screen, self.db, mouse_pos, self.anim_t)
        elif self.mode == "SETUP":
            self.setup_screen.draw(self.screen, mouse_pos)
        elif self.mode == "COMBAT" and self.state is not None:
            self._cam_offset = self.renderer.render(self.screen, self.state, dt)
            self.hud.draw(self.screen, self.state, self.clock.get_fps(), self.sfx.muted, self.paused, mouse_pos)
        elif self.mode == "CRATE" and self.state is not None:
            self.crate_modal.draw(self.screen, self.state, mouse_pos)
        elif self.mode == "LEVEL_UP" and self.state is not None:
            self.levelup_screen.draw(self.screen, self.state, mouse_pos)
        elif self.mode == "SHOP" and self.state is not None:
            self.shop_screen.draw(self.screen, self.state, mouse_pos)
        elif self.mode == "SUMMARY" and self.state is not None:
            self.summary_screen.draw(self.screen, self.state, mouse_pos)

        pygame.display.flip()

    def run(self) -> None:
        accum = 0.0
        while self.running:
            frame_dt = min(0.05, self.clock.tick(self.target_fps) / 1000.0)
            for event in pygame.event.get():
                self.handle_event(event)

            accum += frame_dt
            while accum >= FIXED_DT:
                self.step_frame(FIXED_DT)
                accum -= FIXED_DT

            self.render_frame(frame_dt)

        pygame.quit()

    def capture_screenshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.screen, str(path))
