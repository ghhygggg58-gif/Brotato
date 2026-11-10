"""Tests for SpatialHashGrid, combat simulation, material bag, and Boss victory."""

from __future__ import annotations

from brotato.config import FIXED_DT
from brotato.data_loader import load_database
from brotato.engine.combat import step_wave
from brotato.engine.game_state import GameState
from brotato.engine.wave_director import create_enemy
from brotato.models import PickupEntity, TreeEntity
from brotato.spatial_grid import SpatialHashGrid


def test_spatial_grid_queries() -> None:
    grid: SpatialHashGrid[TreeEntity] = SpatialHashGrid(cell_size=96.0)
    t1 = TreeEntity(uid=1, x=100, y=100, hp=10, max_hp=10)
    t2 = TreeEntity(uid=2, x=180, y=110, hp=10, max_hp=10)
    t3 = TreeEntity(uid=3, x=900, y=900, hp=10, max_hp=10)
    grid.insert_all([t1, t2, t3])

    near = grid.query_radius(110, 100, 100)
    assert t1 in near
    assert t3 not in near

    nearest = grid.query_nearest(110, 100, 150)
    assert nearest is t1
    nearest_excl = grid.query_nearest(110, 100, 150, exclude_ids={1})
    assert nearest_excl is t2


def test_material_bag_and_engineering_turrets() -> None:
    db = load_database()
    st = GameState(db, "engineer", "wrench", seed=12)
    st.start_wave(1)
    # Engineer starts with 1 passive turret + 1 Wrench turret = 2 turrets
    assert len(st.turrets) == 2

    # Leave 5 materials uncollected at wave end -> goes to Material Bag
    st.pickups.append(PickupEntity(uid=st.alloc_uid(), kind="material", x=200, y=200, value=5))
    st.end_wave()
    assert st.bagged_materials == 5

    # Next wave collecting a 1-value material pulls +1 from bag -> gains 2!
    st.start_wave(2)
    st.pickups.append(PickupEntity(uid=st.alloc_uid(), kind="material", x=st.player_x, y=st.player_y, value=1))
    mat_before = st.materials
    step_wave(st, FIXED_DT, 0.0, 0.0)
    assert st.materials - mat_before == 2
    assert st.bagged_materials == 4


def test_tardigrade_shield_and_boss_victory_endless() -> None:
    db = load_database()
    st = GameState(db, "well_rounded", "rocket_launcher", seed=17)
    st.add_item("tardigrade")
    st.start_wave(20)
    assert st.wave_shields_left == 1

    # Spawn a boss right on player to trigger hit -> absorbed by Tardigrade shield!
    st.invuln_timer = 0.0
    boss = create_enemy(st, "boss_predator", st.player_x, st.player_y)
    st.enemies.append(boss)
    hp_before = st.hp
    step_wave(st, FIXED_DT, 0.0, 0.0)
    assert st.wave_shields_left == 0
    assert st.hp == hp_before

    # Slay boss -> Wave 20 completes & marks run_won!
    st.boss_spawned = True
    st.telegraphs.clear()
    boss.hp = 0
    step_wave(st, FIXED_DT, 0.0, 0.0)
    assert st.wave_active is False
    assert st.run_won is True

    # Transition to Endless Wave 21
    st.endless_mode = True
    st.run_won = False
    st.start_wave(21)
    assert st.wave == 21
    assert st.wave_tag == "ENDLESS"
