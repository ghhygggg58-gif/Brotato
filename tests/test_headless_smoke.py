"""Headless Pygame-CE multi-screen integration & performance test."""

from __future__ import annotations

import math
import time

import pygame

from brotato.app import BrotatoApp
from brotato.config import FIXED_DT
from brotato.engine.combat import step_wave
from brotato.engine.level_up import generate_level_up_choices, pick_level_up_choice
from brotato.engine.shop import buy_shop_offer, generate_shop


def test_headless_full_ui_and_combat_loop() -> None:
    app = BrotatoApp(width=1280, height=720, headless=True)
    try:
        # Render Title & cycle every character on Setup screen to verify zero layout crashes
        app.mode = "TITLE"
        app.render_frame(FIXED_DT)

        app.mode = "SETUP"
        for idx in range(len(app.db.character_order)):
            app.setup_screen.select_character(idx)
            app.render_frame(FIXED_DT)

        # Start run with Mage & run Wave 1 simulation + render
        app.start_new_run(character_id="mage", weapon_id="wand", danger_level=5, seed=101)
        assert app.state is not None
        app.state.add_weapon("lightning_shiv", tier=2)
        app.state.add_weapon("taser", tier=1)

        t0 = time.perf_counter()
        steps = 0
        while app.state.wave_active and steps < 1500:
            ang = steps * 0.05
            step_wave(app.state, FIXED_DT, math.cos(ang), math.sin(ang))
            steps += 1
        elapsed = time.perf_counter() - t0
        # Ensure pure simulation easily beats 60 FPS by >10x
        assert (steps / max(1e-6, elapsed)) > 600.0

        app.render_frame(FIXED_DT)

        # Level up + Shop + Summary renders
        app.state.grant_xp(80)
        generate_level_up_choices(app.state)
        app.mode = "LEVEL_UP"
        app.render_frame(FIXED_DT)
        pick_level_up_choice(app.state, 0)

        generate_shop(app.state)
        app.state.materials += 200
        buy_shop_offer(app.state, 0)
        app.mode = "SHOP"
        app.render_frame(FIXED_DT)

        app.state.run_won = True
        app.mode = "SUMMARY"
        app.render_frame(FIXED_DT)
    finally:
        pygame.quit()
