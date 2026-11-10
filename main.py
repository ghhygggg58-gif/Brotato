"""Entry point for Brotato Python (Pygame-CE)."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Brotato Python (Pygame-CE Data-Driven Edition)")
    parser.add_argument("--width", type=int, default=1280, help="Window width (default 1280)")
    parser.add_argument("--height", type=int, default=720, help="Window height (default 720)")
    parser.add_argument("--fps", type=int, default=60, help="Target FPS (default 60)")
    parser.add_argument("--headless-smoke", action="store_true", help="Run a headless multi-screen smoke test & benchmark")
    parser.add_argument("--screenshots-dir", type=str, default="", help="Optional directory to save screenshots during --headless-smoke")
    return parser.parse_args()


def run_headless_smoke(width: int, height: int, screenshots_dir: str) -> None:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

    import pygame
    from brotato.app import BrotatoApp
    from brotato.config import FIXED_DT
    from brotato.engine.combat import step_wave
    from brotato.engine.level_up import generate_level_up_choices, pick_level_up_choice
    from brotato.engine.shop import buy_shop_offer, generate_shop

    app = BrotatoApp(width=width, height=height, headless=True)
    out_dir = Path(screenshots_dir) if screenshots_dir else None

    # 1. Title & Setup renders
    app.mode = "TITLE"
    app.render_frame(FIXED_DT)
    if out_dir:
        app.capture_screenshot(out_dir / "01_title.png")

    app.mode = "SETUP"
    app.render_frame(FIXED_DT)
    if out_dir:
        app.capture_screenshot(out_dir / "02_setup.png")

    # 2. Simulate full Wave 1 combat cleanly + measure throughput
    app.start_new_run(character_id="well_rounded", weapon_id="smg", danger_level=0, seed=42)
    assert app.state is not None
    app.state.add_weapon("pistol", tier=1)
    app.state.add_weapon("wand", tier=1)
    app.state.add_weapon("sword", tier=1)

    t0 = time.perf_counter()
    ticks = 0
    while app.state.wave_active and ticks < 1800:
        ang = ticks * 0.045
        import math
        step_wave(app.state, FIXED_DT, math.cos(ang), math.sin(ang))
        ticks += 1
        if ticks == 720 and out_dir:
            app.render_frame(FIXED_DT)
            app.capture_screenshot(out_dir / "03_combat_wave1.png")

    elapsed = time.perf_counter() - t0
    sim_fps = ticks / max(1e-6, elapsed)
    print(f"Wave 1 finished in {ticks} ticks ({elapsed:.3f}s -> {sim_fps:.1f} sim FPS), kills={app.state.summary.enemies_killed}, materials={app.state.materials}")

    # 3. Level-Up & Shop UI render
    if app.state.pending_level_ups == 0:
        app.state.grant_xp(100)
    app.mode = "LEVEL_UP"
    generate_level_up_choices(app.state)
    app.render_frame(FIXED_DT)
    if out_dir:
        app.capture_screenshot(out_dir / "04_levelup.png")
    while app.state.pending_level_ups > 0:
        pick_level_up_choice(app.state, 0)

    app.mode = "SHOP"
    generate_shop(app.state)
    buy_shop_offer(app.state, 0)
    app.render_frame(FIXED_DT)
    if out_dir:
        app.capture_screenshot(out_dir / "05_shop.png")

    # 4. Boss wave stress test render
    app.state.start_wave(20)
    for _ in range(180):
        step_wave(app.state, FIXED_DT, 0.7, 0.3)
    app.mode = "COMBAT"
    app.render_frame(FIXED_DT)
    if out_dir:
        app.capture_screenshot(out_dir / "06_boss_wave20.png")

    pygame.quit()
    print("Headless smoke test passed!")


def main() -> None:
    args = parse_args()
    if args.headless_smoke:
        run_headless_smoke(args.width, args.height, args.screenshots_dir)
        return

    from brotato.app import BrotatoApp
    app = BrotatoApp(width=args.width, height=args.height, fps=args.fps)
    app.run()


if __name__ == "__main__":
    main()
