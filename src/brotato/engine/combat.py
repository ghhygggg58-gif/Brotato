"""Real-time combat simulation step: movement, weapons, projectiles, AI, pickups."""

from __future__ import annotations

import math

from brotato.config import (
    ARENA_HEIGHT,
    ARENA_WALL_MARGIN,
    ARENA_WIDTH,
    PLAYER_INVULN_DURATION,
    PLAYER_RADIUS,
)
from brotato.engine.game_state import GameState
from brotato.engine.wave_director import create_enemy, step_wave_spawner
from brotato.models import (
    EnemyEntity,
    ExplosionVFX,
    FloatingText,
    MineEntity,
    Particle,
    PickupEntity,
    ProjectileEntity,
    TreeEntity,
    WeaponInstance,
)
from brotato.stats import (
    armor_damage_multiplier,
    attack_cooldown_sec,
    compute_weapon_effective_props,
    consumable_heal_amount,
    effective_dodge_pct,
    hp_regen_per_sec,
    movement_speed_px,
    pickup_radius_px,
)


def _clamp_arena(x: float, y: float, radius: float) -> tuple[float, float]:
    min_x = ARENA_WALL_MARGIN + radius
    max_x = ARENA_WIDTH - ARENA_WALL_MARGIN - radius
    min_y = ARENA_WALL_MARGIN + radius
    max_y = ARENA_HEIGHT - ARENA_WALL_MARGIN - radius
    return max(min_x, min(max_x, x)), max(min_y, min(max_y, y))


def _angle_diff(a: float, b: float) -> float:
    d = (a - b + math.pi) % (2.0 * math.pi) - math.pi
    return abs(d)


def _spawn_particles(state: GameState, x: float, y: float, color: tuple[int, int, int], count: int = 5, speed: float = 130.0) -> None:
    if len(state.particles) > 260:
        return
    rng = state.rng
    for _ in range(count):
        ang = rng.uniform(0.0, 2.0 * math.pi)
        spd = rng.uniform(speed * 0.35, speed)
        life = rng.uniform(0.18, 0.40)
        state.particles.append(
            Particle(
                x=x,
                y=y,
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd,
                life=life,
                max_life=life,
                radius=rng.uniform(2.0, 4.5),
                color=color,
            )
        )


def _apply_lifesteal(state: GameState, extra_chance: float = 0.0) -> None:
    if state.hp >= state.max_hp or state.lifesteal_budget < 1.0:
        return
    chance = max(0.0, state.stats.get("life_steal") + extra_chance) / 100.0
    if chance > 0.0 and state.rng.random() < chance:
        state.hp = min(state.max_hp, state.hp + 1.0)
        state.lifesteal_budget -= 1.0
        state.floating_texts.append(
            FloatingText(
                x=state.player_x + state.rng.uniform(-10, 10),
                y=state.player_y - 26,
                vy=-35.0,
                text="+1",
                color=(105, 245, 115),
                life=0.65,
                max_life=0.65,
                scale=0.95,
            )
        )


def _apply_burn(state: GameState, enemy: EnemyEntity, burn_dmg: float, burn_ticks: int) -> None:
    if burn_dmg <= 0 or burn_ticks <= 0:
        return
    if burn_dmg >= enemy.burn_dmg:
        enemy.burn_dmg = burn_dmg
    enemy.burn_ticks = max(enemy.burn_ticks, burn_ticks)
    if enemy.burn_timer <= 0.0:
        enemy.burn_timer = 0.75

    # Burn spread (Mage / Snake)
    spread = int(state.special_agg.get("burn_spread", 0))
    if spread > 0:
        nearby = state.enemy_grid.query_radius(enemy.x, enemy.y, 130.0)
        count = 0
        for other in nearby:
            if other.uid != enemy.uid and other.hp > 0 and other.burn_ticks == 0:
                if math.hypot(other.x - enemy.x, other.y - enemy.y) <= 130.0:
                    other.burn_dmg = burn_dmg
                    other.burn_ticks = burn_ticks
                    other.burn_timer = 0.75
                    count += 1
                    if count >= spread:
                        break


def _damage_enemy(
    state: GameState,
    enemy: EnemyEntity,
    raw_damage: float,
    is_crit: bool = False,
    knockback: float = 0.0,
    kb_dx: float = 0.0,
    kb_dy: float = 0.0,
    source_weapon: WeaponInstance | None = None,
    lifesteal_bonus: float = 0.0,
    allow_burn_proc: bool = True,
) -> bool:
    """Apply damage to an enemy. Returns True if the enemy died from this hit."""
    if enemy.hp <= 0:
        return False

    dmg = max(1.0, raw_damage)
    # Giant Belt crit bonus (% of enemy's current HP)
    if is_crit:
        crit_pct_hp = state.special_agg.get("crit_pct_enemy_hp", 0.0)
        if crit_pct_hp > 0:
            pct = 0.01 if (enemy.is_boss or enemy.is_elite) else crit_pct_hp
            dmg += enemy.hp * pct

    final_dmg = max(1, int(round(dmg)))
    enemy.hp -= final_dmg
    enemy.hit_flash = 0.10
    state.summary.total_damage_dealt += final_dmg
    if source_weapon is not None:
        source_weapon.total_damage += final_dmg

    # Knockback
    if knockback > 0 and enemy.knockback_resist < 1.0:
        eff_kb = knockback * (1.0 - enemy.knockback_resist) * 14.0
        enemy.vx += kb_dx * eff_kb
        enemy.vy += kb_dy * eff_kb

    # Floating damage number (cap list size for performance)
    if len(state.floating_texts) < 85:
        color = (255, 224, 72) if is_crit else (246, 248, 252)
        state.floating_texts.append(
            FloatingText(
                x=enemy.x + state.rng.uniform(-8, 8),
                y=enemy.y - enemy.radius - 4,
                vy=-42.0,
                text=f"{final_dmg}{'!' if is_crit else ''}",
                color=color,
                life=0.52,
                max_life=0.52,
                scale=1.2 if is_crit else 0.95,
            )
        )

    _apply_lifesteal(state, lifesteal_bonus)

    # Scared Sausage burn chance
    if allow_burn_proc:
        burn_chance = state.special_agg.get("burn_chance", 0.0)
        if burn_chance > 0 and state.rng.random() < burn_chance:
            b_dmg = max(1.0, 3.0 + state.stats.get("elemental_damage"))
            _apply_burn(state, enemy, b_dmg, 3)

    if is_crit:
        state.events.append(("crit", enemy.def_id))
    else:
        state.events.append(("hit", enemy.def_id))

    if enemy.hp <= 0:
        _on_enemy_killed(state, enemy, source_weapon)
        return True
    return False


def _on_enemy_killed(state: GameState, enemy: EnemyEntity, source_weapon: WeaponInstance | None) -> None:
    state.summary.enemies_killed += 1
    if enemy.is_elite:
        state.summary.elites_killed += 1
    if enemy.is_boss:
        state.summary.bosses_killed += 1

    edef = state.db.enemies[enemy.def_id]
    _spawn_particles(state, enemy.x, enemy.y, edef.color, count=7 if not enemy.is_boss else 24, speed=175.0)

    # Ethereal weapon kill scaling (Ghost Flint, Ghost Axe, Ghost Scepter)
    if source_weapon is not None:
        source_weapon.kills += 1
        wdef = state.db.weapons[source_weapon.def_id]
        if "kill_stat_every" in wdef.special:
            every = int(wdef.special["kill_stat_every"].get(str(source_weapon.tier), 20))
            if every > 0 and source_weapon.kills % every == 0:
                for sk, sv in wdef.special["kill_stat"].items():
                    state.bonus_stats.add(sk, float(sv))
                state.rebuild_stats()

    # Drops: Materials
    mat_val = max(1, enemy.materials)
    if len(state.pickups) < 360:
        state.pickups.append(
            PickupEntity(
                uid=state.alloc_uid(),
                kind="material",
                x=enemy.x + state.rng.uniform(-10, 10),
                y=enemy.y + state.rng.uniform(-10, 10),
                value=mat_val,
                bob_phase=state.rng.uniform(0.0, 6.28),
            )
        )
    else:
        # Fallback if floor saturated: auto-bank directly so nothing is lost
        state.bagged_materials += mat_val

    # Consumable drop scaled by Luck
    luck_mult = max(0.4, 1.0 + state.stats.get("luck") / 100.0)
    if state.rng.random() < enemy.consumable_chance * luck_mult:
        state.pickups.append(
            PickupEntity(
                uid=state.alloc_uid(),
                kind="consumable",
                x=enemy.x + state.rng.uniform(-14, 14),
                y=enemy.y + state.rng.uniform(-14, 14),
                value=1,
                bob_phase=state.rng.uniform(0.0, 6.28),
            )
        )

    # Crate drop (guaranteed on Elites/Loot Alien, small Luck-scaled chance on normal enemies)
    crate_chance = 0.006 * luck_mult
    if enemy.guaranteed_crate or state.rng.random() < crate_chance:
        state.pickups.append(
            PickupEntity(
                uid=state.alloc_uid(),
                kind="crate",
                x=enemy.x,
                y=enemy.y,
                value=1,
                bob_phase=state.rng.uniform(0.0, 6.28),
            )
        )

    # Cyberball passive: chance on kill to zap random enemy
    kill_chance = state.special_agg.get("kill_dmg_chance", 0.0)
    if kill_chance > 0 and state.rng.random() < kill_chance:
        luck_pct = state.special_agg.get("kill_dmg_luck_pct", 0.25)
        zap_dmg = max(1.0, state.stats.get("luck") * luck_pct)
        alive = [e for e in state.enemies if e.hp > 0 and e.uid != enemy.uid]
        if alive:
            target = state.rng.choice(alive)
            _damage_enemy(state, target, zap_dmg, allow_burn_proc=False)


def _trigger_explosion(
    state: GameState,
    x: float,
    y: float,
    radius: float,
    base_damage: float,
    source_weapon: WeaponInstance | None = None,
) -> None:
    exp_mult = max(0.5, 1.0 + state.stats.get("explosion_damage") / 100.0)
    dmg = base_damage * exp_mult
    state.explosions.append(ExplosionVFX(x=x, y=y, radius=radius, timer=0.28, duration=0.28, color=(255, 140, 52)))
    _spawn_particles(state, x, y, (255, 165, 70), count=10, speed=230.0)
    state.events.append(("explosion", radius))

    candidates = state.enemy_grid.query_radius(x, y, radius)
    for e in candidates:
        if e.hp <= 0:
            continue
        dist = math.hypot(e.x - x, e.y - y)
        if dist <= radius + e.radius:
            dx = (e.x - x) / max(1.0, dist)
            dy = (e.y - y) / max(1.0, dist)
            _damage_enemy(state, e, dmg, knockback=16.0, kb_dx=dx, kb_dy=dy, source_weapon=source_weapon)


def _damage_tree(state: GameState, tree: TreeEntity, dmg: float) -> None:
    if tree.hp <= 0:
        return
    tree.hp -= dmg
    tree.hit_flash = 0.10
    _spawn_particles(state, tree.x, tree.y, (112, 185, 86), count=3, speed=95.0)
    if tree.hp <= 0:
        state.summary.trees_chopped += 1
        _spawn_particles(state, tree.x, tree.y, (130, 92, 58), count=8, speed=140.0)
        # Trees drop 1 consumable, 3 materials, and Luck-scaled crate chance
        state.pickups.append(PickupEntity(uid=state.alloc_uid(), kind="consumable", x=tree.x - 8, y=tree.y, value=1))
        for _ in range(3):
            state.pickups.append(
                PickupEntity(
                    uid=state.alloc_uid(),
                    kind="material",
                    x=tree.x + state.rng.uniform(-16, 16),
                    y=tree.y + state.rng.uniform(-16, 16),
                    value=1,
                )
            )
        luck_mult = max(0.5, 1.0 + state.stats.get("luck") / 100.0)
        if state.rng.random() < 0.25 * luck_mult:
            state.pickups.append(PickupEntity(uid=state.alloc_uid(), kind="crate", x=tree.x, y=tree.y, value=1))


def _hurt_player(state: GameState, raw_damage: float) -> None:
    if state.invuln_timer > 0 or state.hp <= 0:
        return

    # Tardigrade shield check
    if state.wave_shields_left > 0:
        state.wave_shields_left -= 1
        state.invuln_timer = PLAYER_INVULN_DURATION
        state.floating_texts.append(
            FloatingText(x=state.player_x, y=state.player_y - 30, vy=-45.0, text="BLOCKED!", color=(130, 225, 255), life=0.8, max_life=0.8)
        )
        return

    # Dodge check
    dodge_pct = effective_dodge_pct(state.stats.get("dodge"), state.dodge_cap)
    if dodge_pct > 0 and state.rng.random() * 100.0 < dodge_pct:
        state.invuln_timer = PLAYER_INVULN_DURATION * 0.6
        state.summary.hits_dodged += 1
        state.floating_texts.append(
            FloatingText(x=state.player_x, y=state.player_y - 30, vy=-45.0, text="DODGE!", color=(185, 232, 255), life=0.75, max_life=0.75)
        )
        return

    dmg_mult = armor_damage_multiplier(state.stats.get("armor"))
    final_dmg = max(1, int(round(raw_damage * dmg_mult)))
    state.hp = max(0.0, state.hp - final_dmg)
    state.invuln_timer = PLAYER_INVULN_DURATION
    state.summary.damage_taken += final_dmg
    state.events.append(("hurt", final_dmg))

    state.floating_texts.append(
        FloatingText(x=state.player_x, y=state.player_y - 28, vy=-45.0, text=f"-{final_dmg}", color=(255, 72, 72), life=0.85, max_life=0.85, scale=1.15)
    )
    _spawn_particles(state, state.player_x, state.player_y, (235, 65, 65), count=8, speed=180.0)

    if state.hp <= 0:
        state.run_lost = True
        state.wave_active = False


def _step_weapons(state: GameState, dt: float, mouse_world_x: float | None, mouse_world_y: float | None) -> None:
    for w in state.weapons:
        wdef = state.db.weapons[w.def_id]
        props = compute_weapon_effective_props(w, wdef, state.stats, state.weapons, state.character)

        if w.swing_timer > 0:
            w.swing_timer = max(0.0, w.swing_timer - dt)

        # Screwdriver mine spawning
        tinfo = wdef.tiers[w.tier]
        if "mine_cooldown" in tinfo:
            w.mine_timer -= dt
            if w.mine_timer <= 0:
                eng_mult = max(0.5, 1.0 + state.stats.get("damage_pct") * 0.0)
                w.mine_timer = attack_cooldown_sec(float(tinfo["mine_cooldown"]), state.stats.get("attack_speed"))
                mine_dmg = max(5.0, (float(tinfo["mine_dmg"]) + state.stats.get("engineering") * 1.2) * eng_mult)
                exp_r = 105.0 * max(0.5, 1.0 + state.stats.get("explosion_size") / 100.0)
                mx, my = _clamp_arena(
                    state.player_x + state.rng.uniform(-45, 45),
                    state.player_y + state.rng.uniform(-45, 45),
                    16.0,
                )
                state.mines.append(MineEntity(uid=state.alloc_uid(), x=mx, y=my, damage=mine_dmg, explosion_radius=exp_r))

        w.cooldown_timer -= dt
        wx = state.player_x + w.slot_x
        wy = state.player_y + w.slot_y

        # Aim tracking
        eff_range = float(props["range"])
        target_enemy = state.enemy_grid.query_nearest(wx, wy, eff_range)
        target_tree = None if target_enemy is not None else state.tree_grid.query_nearest(wx, wy, eff_range)

        if state.manual_aim and mouse_world_x is not None and mouse_world_y is not None:
            w.aim_angle = math.atan2(mouse_world_y - wy, mouse_world_x - wx)
            should_fire = True
        else:
            target = target_enemy or target_tree
            if target is not None:
                w.aim_angle = math.atan2(target.y - wy, target.x - wx)
                should_fire = True
            else:
                should_fire = False

        if w.cooldown_timer > 0 or not should_fire:
            continue

        # Execute weapon attack!
        w.cooldown_timer = float(props["cooldown"])
        crit_chance = float(props["crit_chance"])
        crit_mult = float(props["crit_mult"])
        lifesteal_bonus = float(tinfo.get("lifesteal_bonus", 0.0))

        if wdef.type == "melee":
            w.swing_duration = min(0.20, float(props["cooldown"]) * 0.65)
            w.swing_timer = w.swing_duration
            w.swing_dir *= -1
            w.swing_hit_ids.clear()
            state.events.append(("melee", wdef.attack_style))

            aim_x = math.cos(w.aim_angle)
            aim_y = math.sin(w.aim_angle)
            is_sweep = wdef.attack_style == "sweep"
            arc_half = math.radians(78.0)

            for e in state.enemy_grid.query_radius(wx, wy, eff_range + 40.0):
                if e.hp <= 0 or e.uid in w.swing_hit_ids:
                    continue
                dx = e.x - wx
                dy = e.y - wy
                dist = math.hypot(dx, dy)
                if dist > eff_range + e.radius:
                    continue
                if is_sweep:
                    ang = math.atan2(dy, dx)
                    if dist > 26.0 + e.radius and _angle_diff(ang, w.aim_angle) > arc_half:
                        continue
                else:
                    # Thrust corridor check
                    proj = dx * aim_x + dy * aim_y
                    if proj < -12.0 or proj > eff_range + e.radius:
                        continue
                    perp = abs(dx * (-aim_y) + dy * aim_x)
                    if perp > 30.0 + e.radius:
                        continue

                w.swing_hit_ids.add(e.uid)
                is_crit = state.rng.random() * 100.0 < crit_chance
                dmg = float(props["damage"]) * (crit_mult if is_crit else 1.0)
                n_dist = max(1.0, dist)
                _damage_enemy(
                    state,
                    e,
                    dmg,
                    is_crit=is_crit,
                    knockback=float(props["knockback"]),
                    kb_dx=dx / n_dist,
                    kb_dy=dy / n_dist,
                    source_weapon=w,
                    lifesteal_bonus=lifesteal_bonus,
                )

                if props["burn_dmg"] > 0:
                    _apply_burn(state, e, float(props["burn_dmg"]), int(props["burn_ticks"]))

                if props["explosion_radius"] > 0 and state.rng.random() < float(props["explosion_chance"]):
                    _trigger_explosion(state, e.x, e.y, float(props["explosion_radius"]), dmg, source_weapon=w)

                # Lightning Shiv projectiles on hit
                if props["lightning_bolts"] > 0:
                    for b_idx in range(int(props["lightning_bolts"])):
                        b_ang = w.aim_angle + state.rng.uniform(-0.9, 0.9) + (b_idx * 0.35 - 0.35)
                        b_spd = 780.0
                        state.projectiles.append(
                            ProjectileEntity(
                                uid=state.alloc_uid(),
                                x=e.x,
                                y=e.y,
                                vx=math.cos(b_ang) * b_spd,
                                vy=math.sin(b_ang) * b_spd,
                                radius=5.0,
                                damage=float(props["lightning_dmg"]),
                                is_crit=False,
                                from_player=True,
                                color=(105, 225, 255),
                                range_left=260.0,
                                source_weapon_uid=w.uid,
                                hit_enemy_ids={e.uid},
                            )
                        )

            # Melee hits trees too!
            for tr in state.tree_grid.query_radius(wx, wy, eff_range + 20.0):
                if tr.hp <= 0:
                    continue
                if math.hypot(tr.x - wx, tr.y - wy) <= eff_range + tr.radius:
                    _damage_tree(state, tr, float(props["damage"]))

        else:
            # Ranged projectile weapon
            state.events.append(("shoot", w.def_id))
            pellets = int(props["pellets"])
            proj_cfg = wdef.projectile
            spd = float(proj_cfg.get("speed", 800.0))
            rad = float(proj_cfg.get("radius", 6.0))
            col = tuple(proj_cfg.get("color", (255, 220, 120)))
            spread_rad = math.radians(float(proj_cfg.get("spread_deg", 0.0)))

            for p_i in range(pellets):
                if pellets > 1:
                    offset = ((p_i / (pellets - 1)) - 0.5) * spread_rad + state.rng.uniform(-0.04, 0.04)
                else:
                    offset = state.rng.uniform(-spread_rad * 0.5, spread_rad * 0.5) if spread_rad > 0 else 0.0
                ang = w.aim_angle + offset
                is_crit = state.rng.random() * 100.0 < crit_chance
                dmg = float(props["damage"]) * (crit_mult if is_crit else 1.0)
                pierce = int(props["piercing"])
                if is_crit and wdef.special.get("crit_pierce"):
                    pierce += int(wdef.special["crit_pierce"])

                state.projectiles.append(
                    ProjectileEntity(
                        uid=state.alloc_uid(),
                        x=wx + math.cos(ang) * 16.0,
                        y=wy + math.sin(ang) * 16.0,
                        vx=math.cos(ang) * spd,
                        vy=math.sin(ang) * spd,
                        radius=rad,
                        damage=dmg,
                        is_crit=is_crit,
                        from_player=True,
                        color=col,  # type: ignore[arg-type]
                        range_left=eff_range + 50.0,
                        piercing_left=pierce,
                        bounces_left=int(props["bounces"]),
                        knockback=float(props["knockback"]),
                        lifesteal_chance=lifesteal_bonus,
                        explosion_radius=float(props["explosion_radius"]),
                        burn_dmg=float(props["burn_dmg"]),
                        burn_ticks=int(props["burn_ticks"]),
                        slow_pct=float(props["slow_pct"]),
                        source_weapon_uid=w.uid,
                    )
                )


def _step_turrets_and_mines(state: GameState, dt: float) -> None:
    eng = state.stats.get("engineering")
    atk_spd = state.stats.get("attack_speed")
    for t in state.turrets:
        t.cooldown_timer -= dt
        if t.cooldown_timer > 0:
            continue
        target = state.enemy_grid.query_nearest(t.x, t.y, t.range)
        if target is None:
            continue
        t.aim_angle = math.atan2(target.y - t.y, target.x - t.x)
        base_cd = max(0.32, 0.92 - (t.tier - 1) * 0.16)
        t.cooldown_timer = attack_cooldown_sec(base_cd, atk_spd * 0.35)
        dmg = max(4.0, (8.0 + (t.tier - 1) * 6.0) + eng * (0.8 + (t.tier - 1) * 0.2))
        spd = 780.0
        state.projectiles.append(
            ProjectileEntity(
                uid=state.alloc_uid(),
                x=t.x + math.cos(t.aim_angle) * 14.0,
                y=t.y + math.sin(t.aim_angle) * 14.0,
                vx=math.cos(t.aim_angle) * spd,
                vy=math.sin(t.aim_angle) * spd,
                radius=5.0,
                damage=dmg,
                is_crit=False,
                from_player=True,
                color=(125, 255, 190),
                range_left=t.range + 40.0,
                piercing_left=1 if t.tier >= 4 else 0,
            )
        )

    remaining_mines: list[MineEntity] = []
    for m in state.mines:
        m.armed_timer = max(0.0, m.armed_timer - dt)
        triggered = False
        if m.armed_timer <= 0:
            for e in state.enemy_grid.query_radius(m.x, m.y, 38.0):
                if e.hp > 0 and math.hypot(e.x - m.x, e.y - m.y) <= 28.0 + e.radius:
                    triggered = True
                    break
        if triggered:
            _trigger_explosion(state, m.x, m.y, m.explosion_radius, m.damage)
        else:
            remaining_mines.append(m)
    state.mines = remaining_mines


def _step_projectiles(state: GameState, dt: float) -> None:
    weapon_map = {w.uid: w for w in state.weapons}
    kept: list[ProjectileEntity] = []

    for p in state.projectiles:
        step_x = p.vx * dt
        step_y = p.vy * dt
        p.x += step_x
        p.y += step_y
        p.range_left -= math.hypot(step_x, step_y)

        if p.range_left <= 0 or p.x < ARENA_WALL_MARGIN or p.x > ARENA_WIDTH - ARENA_WALL_MARGIN or p.y < ARENA_WALL_MARGIN or p.y > ARENA_HEIGHT - ARENA_WALL_MARGIN:
            if p.explosion_radius > 0 and p.from_player:
                _trigger_explosion(state, p.x, p.y, p.explosion_radius, p.damage, weapon_map.get(p.source_weapon_uid or -1))
            continue

        if not p.from_player:
            # Enemy projectile vs player
            if math.hypot(p.x - state.player_x, p.y - state.player_y) <= p.radius + PLAYER_RADIUS * 0.85:
                _hurt_player(state, p.damage)
                continue
            kept.append(p)
            continue

        # Player projectile vs enemies
        hit_something = False
        for e in state.enemy_grid.query_radius(p.x, p.y, p.radius + 32.0):
            if e.hp <= 0 or e.uid in p.hit_enemy_ids:
                continue
            if math.hypot(e.x - p.x, e.y - p.y) <= p.radius + e.radius:
                p.hit_enemy_ids.add(e.uid)
                src_w = weapon_map.get(p.source_weapon_uid or -1)
                spd_len = max(1.0, math.hypot(p.vx, p.vy))

                if p.explosion_radius > 0:
                    _trigger_explosion(state, p.x, p.y, p.explosion_radius, p.damage, src_w)
                    hit_something = True
                    p.piercing_left = -1
                    break

                _damage_enemy(
                    state,
                    e,
                    p.damage,
                    is_crit=p.is_crit,
                    knockback=p.knockback,
                    kb_dx=p.vx / spd_len,
                    kb_dy=p.vy / spd_len,
                    source_weapon=src_w,
                    lifesteal_bonus=p.lifesteal_chance,
                )
                if p.burn_dmg > 0:
                    _apply_burn(state, e, p.burn_dmg, p.burn_ticks)
                if p.slow_pct > 0:
                    e.slow_pct = max(e.slow_pct, p.slow_pct)
                    e.slow_timer = 1.6

                hit_something = True
                if p.piercing_left > 0:
                    p.piercing_left -= 1
                    p.damage *= 0.90  # Slight Brotato pierce falloff
                elif p.bounces_left > 0:
                    p.bounces_left -= 1
                    nxt = state.enemy_grid.query_nearest(p.x, p.y, 320.0, exclude_ids=p.hit_enemy_ids)
                    if nxt is not None:
                        ang = math.atan2(nxt.y - p.y, nxt.x - p.x)
                        p.vx = math.cos(ang) * spd_len
                        p.vy = math.sin(ang) * spd_len
                        p.range_left = max(p.range_left, 260.0)
                    else:
                        p.piercing_left = -1
                else:
                    p.piercing_left = -1
                break

        if p.piercing_left < 0:
            continue

        # Also hit trees cleanly
        if not hit_something:
            for tr in state.tree_grid.query_radius(p.x, p.y, p.radius + 24.0):
                if tr.hp > 0 and math.hypot(tr.x - p.x, tr.y - p.y) <= p.radius + tr.radius:
                    _damage_tree(state, tr, p.damage)
                    hit_something = True
                    break
            if hit_something:
                continue

        kept.append(p)

    state.projectiles = kept


def _step_enemies(state: GameState, dt: float) -> None:
    px, py = state.player_x, state.player_y
    alive_enemies: list[EnemyEntity] = []

    for e in state.enemies:
        if e.hp <= 0:
            continue

        if e.hit_flash > 0:
            e.hit_flash = max(0.0, e.hit_flash - dt)
        if e.slow_timer > 0:
            e.slow_timer = max(0.0, e.slow_timer - dt)
            if e.slow_timer <= 0:
                e.slow_pct = 0.0

        # Burn DOT
        if e.burn_ticks > 0:
            e.burn_timer -= dt
            if e.burn_timer <= 0:
                e.burn_timer = 0.8
                e.burn_ticks -= 1
                died = _damage_enemy(state, e, e.burn_dmg, allow_burn_proc=False)
                _spawn_particles(state, e.x, e.y, (255, 120, 45), count=2, speed=60.0)
                if died:
                    continue

        dx = px - e.x
        dy = py - e.y
        dist = max(0.001, math.hypot(dx, dy))
        nx, ny = dx / dist, dy / dist
        spd = e.speed * max(0.35, 1.0 - e.slow_pct / 100.0)
        edef = state.db.enemies[e.def_id]

        # AI Behavior
        move_vx = 0.0
        move_vy = 0.0

        if e.behavior == "chase":
            move_vx = nx * spd
            move_vy = ny * spd
        elif e.behavior == "swarm":
            wobble = math.sin(state.wave_timer * 6.0 + e.uid) * 0.45
            move_vx = (nx - ny * wobble) * spd
            move_vy = (ny + nx * wobble) * spd
        elif e.behavior == "flee":
            # Loot Alien keeps distance / flees away from player while hugging arena
            if dist < 440.0:
                move_vx = -nx * spd
                move_vy = -ny * spd
            else:
                move_vx = -ny * spd * 0.6
                move_vy = nx * spd * 0.6
        elif e.behavior == "charger":
            e.ai_timer -= dt
            if e.ai_phase == 0:
                move_vx, move_vy = nx * spd, ny * spd
                if e.ai_timer <= 0 and dist < 380.0:
                    e.ai_phase = 1
                    e.ai_timer = 0.55
                    e.charge_dx, e.charge_dy = nx, ny
            elif e.ai_phase == 1:
                # Telegraph freeze before dash
                move_vx, move_vy = 0.0, 0.0
                if e.ai_timer <= 0:
                    e.ai_phase = 2
                    e.ai_timer = 0.52
            else:
                cspd = float(edef.extra.get("charge_speed", 460.0))
                move_vx, move_vy = e.charge_dx * cspd, e.charge_dy * cspd
                if e.ai_timer <= 0:
                    e.ai_phase = 0
                    e.ai_timer = state.rng.uniform(2.2, 3.3)
        elif e.behavior == "ranged":
            pref = float(edef.extra.get("preferred_dist", 280.0))
            if dist > pref + 30.0:
                move_vx, move_vy = nx * spd, ny * spd
            elif dist < pref - 50.0:
                move_vx, move_vy = -nx * spd * 0.75, -ny * spd * 0.75
            else:
                move_vx, move_vy = -ny * spd * 0.4, nx * spd * 0.4
            e.ai_timer -= dt
            if e.ai_timer <= 0 and dist < 520.0:
                e.ai_timer = float(edef.extra.get("fire_cooldown", 2.4))
                pspd = float(edef.extra.get("proj_speed", 280.0))
                state.projectiles.append(
                    ProjectileEntity(
                        uid=state.alloc_uid(),
                        x=e.x,
                        y=e.y,
                        vx=nx * pspd,
                        vy=ny * pspd,
                        radius=7.0,
                        damage=e.damage,
                        is_crit=False,
                        from_player=False,
                        color=(255, 72, 92),
                        range_left=560.0,
                    )
                )
        elif e.behavior == "healer":
            move_vx, move_vy = nx * spd * 0.85, ny * spd * 0.85
            e.ai_timer -= dt
            if e.ai_timer <= 0:
                e.ai_timer = 3.5
                for ally in state.enemy_grid.query_radius(e.x, e.y, 170.0):
                    if ally.hp > 0 and ally.hp < ally.max_hp:
                        ally.hp = min(ally.max_hp, ally.hp + ally.max_hp * 0.14)
                _spawn_particles(state, e.x, e.y, (95, 245, 145), count=6, speed=95.0)
        elif e.behavior == "egg":
            e.ai_timer += dt
            hatch_time = float(edef.extra.get("hatch_time", 6.5))
            if e.ai_timer >= hatch_time:
                _spawn_particles(state, e.x, e.y, (235, 185, 155), count=8, speed=120.0)
                for _ in range(2):
                    alive_enemies.append(
                        create_enemy(
                            state,
                            "baby_alien",
                            e.x + state.rng.uniform(-18, 18),
                            e.y + state.rng.uniform(-18, 18),
                        )
                    )
                continue
        elif e.behavior in ("elite", "boss_predator", "boss_watcher"):
            e.ai_timer -= dt
            cspd = float(edef.extra.get("charge_speed", 480.0))
            pspd = float(edef.extra.get("proj_speed", 310.0))

            if e.behavior == "boss_watcher":
                # Watcher orbits mid-range & fires spiral / radial bullet waves
                pref = 270.0
                radial = 0.6 if dist > pref else -0.4
                move_vx = (nx * radial - ny * 0.85) * spd
                move_vy = (ny * radial + nx * 0.85) * spd
                if e.ai_timer <= 0:
                    e.pattern_angle += 0.42
                    e.ai_timer = 0.85 if e.ai_phase % 4 != 3 else 1.65
                    e.ai_phase += 1
                    num_b = 10 if e.ai_phase % 4 == 0 else 6
                    for bi in range(num_b):
                        ang = e.pattern_angle + (2.0 * math.pi * bi) / num_b
                        state.projectiles.append(
                            ProjectileEntity(
                                uid=state.alloc_uid(),
                                x=e.x,
                                y=e.y,
                                vx=math.cos(ang) * pspd,
                                vy=math.sin(ang) * pspd,
                                radius=8.0,
                                damage=e.damage,
                                is_crit=False,
                                from_player=False,
                                color=(235, 95, 255),
                                range_left=750.0,
                            )
                        )
            else:
                # Elite & Boss Predator: chase -> telegraph charge -> bullet fan
                if e.ai_phase == 0:
                    move_vx, move_vy = nx * spd, ny * spd
                    if e.ai_timer <= 0:
                        e.ai_phase = 1
                        e.ai_timer = 0.65
                        e.charge_dx, e.charge_dy = nx, ny
                elif e.ai_phase == 1:
                    move_vx, move_vy = 0.0, 0.0
                    if e.ai_timer <= 0:
                        e.ai_phase = 2
                        e.ai_timer = 0.58
                elif e.ai_phase == 2:
                    move_vx, move_vy = e.charge_dx * cspd, e.charge_dy * cspd
                    if e.ai_timer <= 0:
                        e.ai_phase = 0
                        e.ai_timer = 2.0
                        # Fire radial / fan volley after dash
                        n_proj = 10 if e.is_boss else 8
                        base_ang = math.atan2(ny, nx)
                        for bi in range(n_proj):
                            ang = base_ang + (2.0 * math.pi * bi) / n_proj
                            state.projectiles.append(
                                ProjectileEntity(
                                    uid=state.alloc_uid(),
                                    x=e.x,
                                    y=e.y,
                                    vx=math.cos(ang) * pspd,
                                    vy=math.sin(ang) * pspd,
                                    radius=8.5,
                                    damage=e.damage,
                                    is_crit=False,
                                    from_player=False,
                                    color=(255, 75, 95),
                                    range_left=720.0,
                                )
                            )

        # Soft separation from nearby enemies via spatial grid
        sep_x = 0.0
        sep_y = 0.0
        if e.speed > 0:
            for other in state.enemy_grid.query_radius(e.x, e.y, e.radius + 26.0):
                if other.uid == e.uid or other.hp <= 0:
                    continue
                ox = e.x - other.x
                oy = e.y - other.y
                min_d = e.radius + other.radius
                d2 = ox * ox + oy * oy
                if 0.0001 < d2 < min_d * min_d:
                    od = math.sqrt(d2)
                    push = (min_d - od) / min_d
                    sep_x += (ox / od) * push * 130.0
                    sep_y += (oy / od) * push * 130.0

        # Apply knockback decay + movement
        e.vx *= max(0.0, 1.0 - 9.0 * dt)
        e.vy *= max(0.0, 1.0 - 9.0 * dt)

        e.x += (move_vx + sep_x + e.vx) * dt
        e.y += (move_vy + sep_y + e.vy) * dt
        e.x, e.y = _clamp_arena(e.x, e.y, e.radius)

        # Contact damage vs player
        if math.hypot(e.x - px, e.y - py) <= e.radius + PLAYER_RADIUS * 0.9:
            _hurt_player(state, e.damage)

        alive_enemies.append(e)

    state.enemies = alive_enemies


def _step_pickups(state: GameState, dt: float) -> None:
    px, py = state.player_x, state.player_y
    magnet_r = pickup_radius_px(state.stats.get("pickup_range"))
    kept: list[PickupEntity] = []

    for p in state.pickups:
        p.bob_phase += dt * 4.0
        dx = px - p.x
        dy = py - p.y
        dist = math.hypot(dx, dy)

        if p.kind in ("material", "consumable") and dist <= magnet_r:
            p.magnetized = True
        elif p.kind == "crate" and dist <= magnet_r * 0.65:
            p.magnetized = True

        if p.magnetized and dist > 1.0:
            pull_speed = 640.0
            p.x += (dx / dist) * pull_speed * dt
            p.y += (dy / dist) * pull_speed * dt
            dist = math.hypot(px - p.x, py - p.y)

        if dist <= PLAYER_RADIUS + 14.0:
            if p.kind == "material":
                # Bagged Materials mechanic: +1 extra material & XP from bag!
                bag_bonus = 0
                if state.bagged_materials > 0:
                    bag_bonus = min(p.value, state.bagged_materials)
                    state.bagged_materials -= bag_bonus
                gained = p.value + bag_bonus
                state.materials += gained
                state.summary.materials_collected += gained
                state.grant_xp(gained)
                state.events.append(("pickup", gained))

                # Lucky / Baby Elephant pickup zap
                zap_chance = state.special_agg.get("pickup_dmg_chance", 0.0)
                if zap_chance > 0 and state.rng.random() < zap_chance:
                    luck_pct = state.special_agg.get("pickup_dmg_luck_pct", 0.15)
                    zap_dmg = max(1.0, state.stats.get("luck") * luck_pct)
                    alive = [e for e in state.enemies if e.hp > 0]
                    if alive:
                        _damage_enemy(state, state.rng.choice(alive), zap_dmg, allow_burn_proc=False)
            elif p.kind == "consumable":
                heal = consumable_heal_amount(state.stats)
                state.hp = min(state.max_hp, state.hp + heal)
                state.floating_texts.append(
                    FloatingText(x=px, y=py - 28, vy=-38.0, text=f"+{heal}", color=(108, 248, 118), life=0.75, max_life=0.75)
                )
                state.events.append(("pickup", heal))
            elif p.kind == "crate":
                state.pending_crates += 1
                state.floating_texts.append(
                    FloatingText(x=px, y=py - 32, vy=-42.0, text="CRATE!", color=(255, 214, 72), life=1.0, max_life=1.0, scale=1.15)
                )
                state.events.append(("crate", 1))
            continue

        kept.append(p)

    state.pickups = kept


def _step_vfx(state: GameState, dt: float) -> None:
    kept_p: list[Particle] = []
    for p in state.particles:
        p.life -= dt
        if p.life > 0:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= max(0.0, 1.0 - 4.0 * dt)
            p.vy *= max(0.0, 1.0 - 4.0 * dt)
            kept_p.append(p)
    state.particles = kept_p

    kept_e: list[ExplosionVFX] = []
    for ex in state.explosions:
        ex.timer -= dt
        if ex.timer > 0:
            kept_e.append(ex)
    state.explosions = kept_e

    kept_ft: list[FloatingText] = []
    for ft in state.floating_texts:
        ft.life -= dt
        if ft.life > 0:
            ft.y += ft.vy * dt
            kept_ft.append(ft)
    state.floating_texts = kept_ft


def step_wave(
    state: GameState,
    dt: float,
    input_dx: float,
    input_dy: float,
    mouse_world_x: float | None = None,
    mouse_world_y: float | None = None,
) -> bool:
    """Advance combat simulation by `dt` seconds. Returns True when wave ends."""
    if not state.wave_active or state.run_lost:
        return False

    # 1. Player movement
    mag = math.hypot(input_dx, input_dy)
    if mag > 0.001:
        nx, ny = input_dx / mag, input_dy / mag
        spd = movement_speed_px(state.stats.get("speed"))
        state.player_vx = nx * spd
        state.player_vy = ny * spd
        if abs(nx) > 0.05:
            state.player_facing_x = 1.0 if nx > 0 else -1.0
    else:
        state.player_vx = 0.0
        state.player_vy = 0.0

    state.player_x += state.player_vx * dt
    state.player_y += state.player_vy * dt
    state.player_x, state.player_y = _clamp_arena(state.player_x, state.player_y, PLAYER_RADIUS)

    if state.invuln_timer > 0:
        state.invuln_timer = max(0.0, state.invuln_timer - dt)

    # 2. HP Regen & Life Steal budget
    regen_rate = hp_regen_per_sec(state.stats.get("hp_regen"))
    if regen_rate > 0 and state.hp < state.max_hp:
        state.regen_accum += regen_rate * dt
        if state.regen_accum >= 1.0:
            heal = int(state.regen_accum)
            state.regen_accum -= heal
            state.hp = min(state.max_hp, state.hp + heal)
    state.lifesteal_budget = min(10.0, state.lifesteal_budget + 10.0 * dt)

    # 3. Rebuild spatial grids in O(N)
    state.trees = [t for t in state.trees if t.hp > 0]
    for tr in state.trees:
        if tr.hit_flash > 0:
            tr.hit_flash = max(0.0, tr.hit_flash - dt)
    state.enemy_grid.clear()
    state.enemy_grid.insert_all(state.enemies)
    state.pickup_grid.clear()
    state.pickup_grid.insert_all(state.pickups)
    state.tree_grid.clear()
    state.tree_grid.insert_all(state.trees)

    # 4. Wave Spawner
    step_wave_spawner(state, dt)

    # 5. Weapons, Turrets, Mines, Projectiles, Enemies, Pickups, VFX
    _step_weapons(state, dt, mouse_world_x, mouse_world_y)
    _step_turrets_and_mines(state, dt)
    _step_projectiles(state, dt)
    _step_enemies(state, dt)
    _step_pickups(state, dt)
    _step_vfx(state, dt)

    if state.run_lost:
        return True

    # 6. Wave timer & Boss check
    state.wave_timer -= dt
    wave_finished = state.wave_timer <= 0.0

    # On Boss wave (Wave 20), also complete immediately if all bosses spawned & slain!
    if state.wave == 20 and state.boss_spawned:
        boss_pending = any("boss_" in t.def_id for t in state.telegraphs)
        boss_alive = any(e.is_boss and e.hp > 0 for e in state.enemies)
        if not boss_pending and not boss_alive:
            wave_finished = True

    if wave_finished:
        state.wave_timer = 0.0
        state.end_wave()
        return True

    return False
