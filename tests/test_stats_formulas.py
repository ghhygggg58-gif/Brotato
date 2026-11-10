"""Tests for data integrity, exact Brotato stat formulas, and synergies."""

from __future__ import annotations

import pytest

from brotato.data_loader import load_database
from brotato.engine.game_state import GameState
from brotato.stats import (
    armor_damage_multiplier,
    attack_cooldown_sec,
    compute_weapon_effective_props,
    effective_dodge_pct,
    hp_regen_per_sec,
    xp_for_next_level,
)


def test_database_integrity() -> None:
    db = load_database()
    assert len(db.characters) >= 12
    assert len(db.weapons) >= 20
    assert len(db.items) >= 35
    assert len(db.enemies) >= 12
    assert len(db.waves_config["waves"]) == 20
    assert len(db.waves_config["danger_levels"]) == 6

    for c in db.characters.values():
        assert c.starting_weapons, f"{c.id} must have starting weapons"
        for wid in c.starting_weapons:
            assert wid in db.weapons, f"{c.id} references unknown weapon {wid}"

    for w in db.weapons.values():
        assert w.min_tier in w.tiers
        for cls_id in w.classes:
            assert cls_id in db.weapon_classes, f"{w.id} references unknown class {cls_id}"


def test_core_formulas() -> None:
    assert xp_for_next_level(1) == 16
    assert xp_for_next_level(2) == 25
    assert xp_for_next_level(5) == 64

    assert pytest.approx(armor_damage_multiplier(0), rel=1e-4) == 1.0
    assert pytest.approx(armor_damage_multiplier(15), rel=1e-4) == 0.5
    assert pytest.approx(armor_damage_multiplier(30), rel=1e-4) == 1.0 / 3.0
    assert armor_damage_multiplier(-5) > 1.0

    assert hp_regen_per_sec(0) == 0.0
    assert pytest.approx(hp_regen_per_sec(1), rel=1e-3) == 0.20
    assert pytest.approx(hp_regen_per_sec(10), rel=1e-3) == 1.00
    assert pytest.approx(hp_regen_per_sec(20), rel=1e-3) == 1.889

    assert effective_dodge_pct(75, 60) == 60
    assert effective_dodge_pct(75, 90) == 75
    assert effective_dodge_pct(-10, 60) == 0

    assert pytest.approx(attack_cooldown_sec(1.0, 100), rel=1e-4) == 0.5
    assert pytest.approx(attack_cooldown_sec(1.0, -50), rel=1e-4) == 1.5


def test_character_restrictions_and_gain_multipliers() -> None:
    db = load_database()

    # Ranger cannot equip melee weapons and gets +50% Ranged Damage gains
    ranger = GameState(db, "ranger", "pistol")
    assert ranger.add_weapon("sword", tier=1) is None
    assert ranger.add_weapon("smg", tier=1) is not None
    ranger.upgrade_stats.add("ranged_damage", 4)
    ranger.rebuild_stats()
    assert pytest.approx(ranger.stats.get("ranged_damage")) == 6.0

    # Ghost raises dodge cap to 90%
    ghost = GameState(db, "ghost", "ghost_flint")
    assert ghost.dodge_cap == 90.0

    # One-Armed max 1 weapon
    oa = GameState(db, "one_armed", "smg")
    assert oa.max_weapons == 1
    assert oa.add_weapon("pistol", tier=1) is None

    # Multitasker max 12 weapons and -5% Damage per weapon
    mt = GameState(db, "multitasker", "stick")
    assert mt.max_weapons == 12
    assert pytest.approx(mt.stats.get("damage_pct")) == 15.0  # +20 base - 5 * 1 weapon
    mt.add_weapon("stick", tier=1)
    assert pytest.approx(mt.stats.get("damage_pct")) == 10.0  # +20 base - 5 * 2 weapons


def test_weapon_synergies_and_stick_scaling() -> None:
    db = load_database()
    st = GameState(db, "well_rounded", "stick")
    st.add_weapon("stick", tier=1)
    st.add_weapon("stick", tier=1)

    # 3 Primitive weapons -> +6 Max HP synergy (10 base + 5 char + 6 primitive = 21)
    assert st.class_counts["primitive"] == 3
    assert pytest.approx(st.stats.get("max_hp")) == 21.0

    # Stick deals +4 damage per OTHER Stick equipped (2 other sticks = +8 -> 8 + 8 = 16)
    w0 = st.weapons[0]
    props = compute_weapon_effective_props(w0, db.weapons["stick"], st.stats, st.weapons, st.character)
    assert pytest.approx(props["damage"]) == 16.0
