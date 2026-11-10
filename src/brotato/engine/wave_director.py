"""Wave Director: telegraphed spawns, hordes, elites, bosses, and danger scaling."""

from __future__ import annotations

import math

from brotato.config import ARENA_HEIGHT, ARENA_WALL_MARGIN, ARENA_WIDTH
from brotato.engine.game_state import GameState
from brotato.models import EnemyEntity, SpawnTelegraph


def _pick_spawn_position(state: GameState, min_dist_from_player: float = 210.0) -> tuple[float, float]:
    margin = ARENA_WALL_MARGIN + 36.0
    for _ in range(16):
        x = state.rng.uniform(margin, ARENA_WIDTH - margin)
        y = state.rng.uniform(margin, ARENA_HEIGHT - margin)
        if math.hypot(x - state.player_x, y - state.player_y) >= min_dist_from_player:
            return x, y
    # Fallback corner away from player
    fx = margin if state.player_x > ARENA_WIDTH * 0.5 else ARENA_WIDTH - margin
    fy = margin if state.player_y > ARENA_HEIGHT * 0.5 else ARENA_HEIGHT - margin
    return fx, fy


def _pick_weighted_enemy(pool: dict[str, float], rng) -> str:
    total = sum(pool.values())
    r = rng.uniform(0.0, total)
    acc = 0.0
    for eid, weight in pool.items():
        acc += weight
        if r <= acc:
            return eid
    return next(iter(pool.keys()))


def create_enemy(state: GameState, enemy_id: str, x: float, y: float) -> EnemyEntity:
    edef = state.db.enemies[enemy_id]
    danger = state.db.get_danger(state.danger_level)
    w = max(1, state.wave)

    # Wave scaling + Endless exponential boost after wave 20
    wave_factor = float(w - 1)
    endless_mult = 1.0
    if w > 20:
        endless_mult = 1.0 + (w - 20) * 0.35 + ((w - 20) ** 1.35) * 0.08

    hp = (edef.base_hp + edef.hp_per_wave * wave_factor) * float(danger["hp_mult"]) * endless_mult
    dmg = (edef.base_damage + edef.damage_per_wave * wave_factor) * float(danger["dmg_mult"]) * (1.0 + max(0, w - 20) * 0.12)
    spd_mod = max(0.5, 1.0 + state.stats.get("enemy_speed_pct") / 100.0)
    spd = edef.speed * float(danger["speed_mult"]) * spd_mod

    return EnemyEntity(
        uid=state.alloc_uid(),
        def_id=enemy_id,
        x=x,
        y=y,
        vx=0.0,
        vy=0.0,
        hp=hp,
        max_hp=hp,
        damage=dmg,
        speed=spd,
        radius=edef.radius,
        knockback_resist=edef.knockback_resist,
        materials=edef.materials,
        consumable_chance=edef.consumable_chance,
        behavior=edef.behavior,
        is_elite=bool(edef.extra.get("is_elite", False)),
        is_boss=bool(edef.extra.get("is_boss", False)),
        guaranteed_crate=bool(edef.extra.get("guaranteed_crate", False)),
        ai_timer=state.rng.uniform(0.6, 1.8),
    )


def step_wave_spawner(state: GameState, dt: float) -> None:
    if not state.wave_active:
        return

    wcfg = state.db.get_wave_config(state.wave)
    danger = state.db.get_danger(state.danger_level)

    # Wave 20 Boss Spawn
    if state.wave == 20 and not state.boss_spawned:
        state.boss_spawned = True
        boss_count = int(danger.get("boss_count", 1))
        bx1, by1 = _pick_spawn_position(state, 340.0)
        state.telegraphs.append(SpawnTelegraph(uid=state.alloc_uid(), def_id="boss_predator", x=bx1, y=by1, timer=1.2, duration=1.2))
        if boss_count >= 2:
            bx2, by2 = ARENA_WIDTH - bx1, ARENA_HEIGHT - by1
            state.telegraphs.append(SpawnTelegraph(uid=state.alloc_uid(), def_id="boss_watcher", x=bx2, y=by2, timer=1.2, duration=1.2))
        state.events.append(("boss", state.wave))

    # Elite Wave Spawn (Waves in danger.elite_waves or Endless multiples of 5)
    elite_waves = danger.get("elite_waves", [])
    is_elite_wave = (state.wave in elite_waves) or (state.wave > 20 and state.wave % 3 == 0)
    if is_elite_wave and not state.elite_spawned and state.wave_timer <= state.wave_duration - 4.0:
        state.elite_spawned = True
        ex, ey = _pick_spawn_position(state, 300.0)
        state.telegraphs.append(SpawnTelegraph(uid=state.alloc_uid(), def_id="elite_colossus", x=ex, y=ey, timer=1.2, duration=1.2))
        state.events.append(("boss", state.wave))

    # Rare Loot Alien spawn on Wave >= 3
    if state.wave >= 3 and not state.loot_alien_spawned and state.wave_timer <= state.wave_duration * 0.65:
        state.loot_alien_spawned = True
        if state.rng.random() < 0.38:
            lx, ly = _pick_spawn_position(state, 260.0)
            state.telegraphs.append(SpawnTelegraph(uid=state.alloc_uid(), def_id="loot_alien", x=lx, y=ly, timer=0.9, duration=0.9))

    # Regular enemy spawning modulated by Enemies % stat & Danger count_mult
    enemy_count_mult = max(0.5, 1.0 + state.stats.get("enemies_pct") / 100.0) * float(danger["count_mult"])
    max_enemies = int(round(wcfg["max_enemies"] * enemy_count_mult))
    spawn_rate = float(wcfg["spawn_rate"]) * enemy_count_mult

    # Ramp slightly over the course of the wave
    elapsed_ratio = 1.0 - (state.wave_timer / max(1.0, state.wave_duration))
    ramp = 0.75 + 0.65 * elapsed_ratio

    state.spawn_accum += spawn_rate * ramp * dt
    total_active = len(state.enemies) + len(state.telegraphs)

    while state.spawn_accum >= 1.0 and total_active < max_enemies:
        state.spawn_accum -= 1.0
        # Occasionally spawn small clusters on horde waves
        cluster = 2 if (state.wave_tag in ("HORDE", "SWARM", "ENDLESS") and state.rng.random() < 0.35) else 1
        cx, cy = _pick_spawn_position(state, 200.0)
        for c_idx in range(cluster):
            if total_active >= max_enemies:
                break
            eid = _pick_weighted_enemy(wcfg["pool"], state.rng)
            ox = cx + (c_idx * state.rng.uniform(-35, 35))
            oy = cy + (c_idx * state.rng.uniform(-35, 35))
            ox = max(ARENA_WALL_MARGIN + 30, min(ARENA_WIDTH - ARENA_WALL_MARGIN - 30, ox))
            oy = max(ARENA_WALL_MARGIN + 30, min(ARENA_HEIGHT - ARENA_WALL_MARGIN - 30, oy))
            state.telegraphs.append(SpawnTelegraph(uid=state.alloc_uid(), def_id=eid, x=ox, y=oy, timer=0.85, duration=0.85))
            total_active += 1

    # Advance telegraphs & materialize enemies
    remaining_telegraphs: list[SpawnTelegraph] = []
    for tel in state.telegraphs:
        tel.timer -= dt
        if tel.timer <= 0.0:
            state.enemies.append(create_enemy(state, tel.def_id, tel.x, tel.y))
        else:
            remaining_telegraphs.append(tel)
    state.telegraphs = remaining_telegraphs
