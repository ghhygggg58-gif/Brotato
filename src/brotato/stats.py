"""Exact Brotato stat computation, scaling, and combat formulas."""

from __future__ import annotations

import math
from typing import Any

from brotato.config import BASE_CONSUMABLE_HEAL, DEFAULT_DODGE_CAP, PLAYER_BASE_PICKUP_RADIUS, PLAYER_BASE_SPEED
from brotato.data_loader import GameDatabase
from brotato.models import (
    ALL_STAT_KEYS,
    CharacterDef,
    StatBlock,
    WeaponDef,
    WeaponInstance,
)


def xp_for_next_level(level: int) -> int:
    """Brotato XP curve: (level + 3)^2."""
    return (max(1, level) + 3) ** 2


def armor_damage_multiplier(armor: float) -> float:
    """Brotato armor mitigation: 15 / (15 + armor) for positive armor."""
    if armor >= 0:
        return 15.0 / (15.0 + armor)
    neg = abs(armor)
    return 1.0 + (neg / (15.0 + neg))


def armor_reduction_pct(armor: float) -> int:
    mult = armor_damage_multiplier(armor)
    return int(round((1.0 - mult) * 100))


def hp_regen_per_sec(hp_regen: float) -> float:
    """Brotato HP regen: 1 = 0.20 HP/s, 10 = 1.00 HP/s, 20 = 1.89 HP/s."""
    if hp_regen <= 0:
        return 0.0
    return 0.20 + (hp_regen - 1.0) * (0.8 / 9.0)


def effective_dodge_pct(dodge: float, dodge_cap: float = DEFAULT_DODGE_CAP) -> float:
    return max(0.0, min(dodge, dodge_cap))


def movement_speed_px(speed_pct: float) -> float:
    """Movement speed in px/sec with a safe minimum floor."""
    mult = max(0.35, 1.0 + speed_pct / 100.0)
    return PLAYER_BASE_SPEED * mult


def pickup_radius_px(pickup_range_pct: float) -> float:
    mult = max(0.4, 1.0 + pickup_range_pct / 100.0)
    return PLAYER_BASE_PICKUP_RADIUS * mult


def attack_cooldown_sec(base_cooldown: float, attack_speed_pct: float) -> float:
    if attack_speed_pct >= 0:
        return max(0.05, base_cooldown / (1.0 + attack_speed_pct / 100.0))
    return base_cooldown * (1.0 + abs(attack_speed_pct) / 100.0)


def apply_stat_gain_mult(
    stat_key: str,
    delta: float,
    gain_mults: dict[str, float],
) -> float:
    """Apply character modification multipliers (e.g. Ranger +50% Ranged Damage gains).

    In Brotato, stat modification multipliers apply to positive gains (and for
    complete nullifiers like 0.0, to gains/modifiers as configured).
    """
    mult = gain_mults.get(stat_key, 1.0)
    if mult == 0.0 and delta > 0:
        return 0.0
    if delta > 0:
        return delta * mult
    return delta


def compute_weapon_class_counts(
    weapons: list[WeaponInstance],
    db: GameDatabase,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for w in weapons:
        wdef = db.weapons[w.def_id]
        for cls_id in wdef.classes:
            counts[cls_id] = counts.get(cls_id, 0) + 1
    return counts


def compute_effective_stats(
    db: GameDatabase,
    character: CharacterDef,
    level: int,
    upgrade_stats: StatBlock,
    bonus_stats: StatBlock,
    items: list[str],
    weapons: list[WeaponInstance],
) -> tuple[StatBlock, dict[str, int], dict[str, Any]]:
    """Compute final aggregated primary/secondary stats plus active synergies & passives."""
    result = StatBlock()
    # Base Brotato stats: 10 Max HP at level 1 + 1 per level gained
    result.add("max_hp", 10.0 + max(0, level - 1))

    gain_mults: dict[str, float] = dict(character.special.get("stat_gain_mults", {}))

    # Character innate starting stats (not multiplied by gain_mults, exact to Brotato)
    for k, v in character.stats.items():
        result.add(k, v)

    # Level-up & permanent bonuses (ethereal weapon kills, wave passives like Loud/Vigilante)
    for k in ALL_STAT_KEYS:
        val = upgrade_stats.get(k) + bonus_stats.get(k)
        if val != 0:
            result.add(k, apply_stat_gain_mult(k, val, gain_mults))

    # Purchased items
    t1_count = 0
    special_agg: dict[str, float] = {
        "burn_chance": 0.0,
        "burn_spread": float(character.special.get("burn_spread", 0)),
        "interest_pct": 0.0,
        "pickup_dmg_chance": float(character.special.get("lucky_pickup_chance", 0.0)),
        "pickup_dmg_luck_pct": float(character.special.get("lucky_pickup_luck_pct", 0.0)),
        "kill_dmg_chance": 0.0,
        "kill_dmg_luck_pct": 0.0,
        "turrets": float(character.special.get("starting_turrets", 0)),
        "wave_shield": 0.0,
        "harvesting_growth_bonus": 0.0,
        "damage_per_wave": 0.0,
        "crit_pct_enemy_hp": 0.0,
    }
    speed_to_dmg_pct = 0.0
    fairy_regen_per_t1 = 0.0

    for item_id in items:
        idef = db.items.get(item_id)
        if not idef:
            continue
        if idef.tier == 1:
            t1_count += 1
        for k, v in idef.stats.items():
            result.add(k, apply_stat_gain_mult(k, v, gain_mults))
        sp = idef.special
        if sp:
            if "burn_chance" in sp:
                special_agg["burn_chance"] = min(1.0, special_agg["burn_chance"] + float(sp["burn_chance"]))
            if "burn_spread" in sp:
                special_agg["burn_spread"] += float(sp["burn_spread"])
            if "interest_pct" in sp:
                special_agg["interest_pct"] += float(sp["interest_pct"])
            if "pickup_dmg_chance" in sp:
                special_agg["pickup_dmg_chance"] = min(1.0, special_agg["pickup_dmg_chance"] + float(sp["pickup_dmg_chance"]))
                special_agg["pickup_dmg_luck_pct"] = max(special_agg["pickup_dmg_luck_pct"], float(sp["pickup_dmg_luck_pct"]))
            if "kill_dmg_chance" in sp:
                special_agg["kill_dmg_chance"] = min(1.0, special_agg["kill_dmg_chance"] + float(sp["kill_dmg_chance"]))
                special_agg["kill_dmg_luck_pct"] = max(special_agg["kill_dmg_luck_pct"], float(sp["kill_dmg_luck_pct"]))
            if "turrets" in sp:
                special_agg["turrets"] += float(sp["turrets"])
            if "wave_shield" in sp:
                special_agg["wave_shield"] += float(sp["wave_shield"])
            if "harvesting_growth_bonus" in sp:
                special_agg["harvesting_growth_bonus"] += float(sp["harvesting_growth_bonus"])
            if "damage_per_wave" in sp:
                special_agg["damage_per_wave"] += float(sp["damage_per_wave"])
            if "crit_pct_enemy_hp" in sp:
                special_agg["crit_pct_enemy_hp"] += float(sp["crit_pct_enemy_hp"])
            if "speed_to_damage_pct" in sp:
                speed_to_dmg_pct += float(sp["speed_to_damage_pct"])
            if "hp_regen_per_t1_item" in sp:
                fairy_regen_per_t1 += float(sp["hp_regen_per_t1_item"])

    # Passive stats from equipped weapons (Rock, Pruner, Scissors, Chopper)
    for w in weapons:
        wdef = db.weapons[w.def_id]
        tinfo = wdef.tiers[w.tier]
        if "bonus_armor" in tinfo:
            result.add("armor", apply_stat_gain_mult("armor", float(tinfo["bonus_armor"]), gain_mults))
        if "bonus_hp" in tinfo:
            result.add("max_hp", apply_stat_gain_mult("max_hp", float(tinfo["bonus_hp"]), gain_mults))
        if "bonus_harvesting" in tinfo:
            result.add("harvesting", apply_stat_gain_mult("harvesting", float(tinfo["bonus_harvesting"]), gain_mults))
        if "lifesteal_bonus" in tinfo:
            result.add("life_steal", apply_stat_gain_mult("life_steal", float(tinfo["lifesteal_bonus"]), gain_mults))
        if "consumable_heal_bonus" in tinfo:
            result.add("consumable_heal", float(tinfo["consumable_heal_bonus"]))

    # Weapon class synergies (2..6 equipped)
    class_counts = compute_weapon_class_counts(weapons, db)
    for cls_id, count in class_counts.items():
        if count < 2:
            continue
        cdef = db.weapon_classes.get(cls_id)
        if not cdef:
            continue
        capped = min(6, count)
        bonus_dict = cdef.bonuses_per_count.get(capped, {})
        for k, v in bonus_dict.items():
            result.add(k, apply_stat_gain_mult(k, float(v), gain_mults))

    # Dynamic scaling passives
    if fairy_regen_per_t1 > 0 and t1_count > 0:
        result.add("hp_regen", apply_stat_gain_mult("hp_regen", fairy_regen_per_t1 * t1_count, gain_mults))

    if speed_to_dmg_pct > 0:
        spd_val = max(0.0, result.get("speed"))
        result.add("damage_pct", apply_stat_gain_mult("damage_pct", spd_val * speed_to_dmg_pct, gain_mults))

    if "damage_per_weapon" in character.special:
        result.add("damage_pct", float(character.special["damage_per_weapon"]) * len(weapons))

    if "hp_to_damage_pct" in character.special:
        hp_val = max(1.0, result.get("max_hp"))
        bonus_dmg = math.floor(hp_val * float(character.special["hp_to_damage_pct"]))
        result.add("damage_pct", apply_stat_gain_mult("damage_pct", bonus_dmg, gain_mults))

    # Minimum Max HP is 1
    if result.get("max_hp") < 1:
        result.values["max_hp"] = 1.0

    # Clamp items_price discount floor (-50% max discount)
    if result.get("items_price") < -50:
        result.values["items_price"] = -50.0

    return result, class_counts, special_agg


def compute_weapon_effective_props(
    weapon: WeaponInstance,
    wdef: WeaponDef,
    stats: StatBlock,
    all_weapons: list[WeaponInstance],
    character: CharacterDef,
) -> dict[str, Any]:
    """Compute exact effective damage, cooldown, range, crit, etc. for one weapon."""
    tinfo = wdef.tiers[weapon.tier]
    base_dmg = float(tinfo["damage"])

    # Stick special: bonus damage per other Stick equipped
    if "stick_bonus" in tinfo:
        other_sticks = sum(1 for w in all_weapons if w.def_id == "stick" and w.uid != weapon.uid)
        base_dmg += other_sticks * float(tinfo["stick_bonus"])

    # Stat scaling
    scaled_add = 0.0
    for stat_key, ratio in wdef.scaling.items():
        scaled_add += stats.get(stat_key) * ratio

    dmg_pct = stats.get("damage_pct")
    # Character tag-specific damage bonus (e.g. Ghost +10% Ethereal)
    dmg_with_tag = character.special.get("damage_with_tag", {})
    for cls_id in wdef.classes:
        if cls_id in dmg_with_tag:
            dmg_pct += float(dmg_with_tag[cls_id])

    dmg_mult = max(0.1, 1.0 + dmg_pct / 100.0)
    raw_damage = max(1.0, (base_dmg + scaled_add) * dmg_mult)

    # Attack speed & character tag-specific attack speed bonus (e.g. Brawler +50% Unarmed)
    atk_spd = stats.get("attack_speed")
    atk_with_tag = character.special.get("attack_speed_with_tag", {})
    for cls_id in wdef.classes:
        if cls_id in atk_with_tag:
            atk_spd += float(atk_with_tag[cls_id])
    cooldown = attack_cooldown_sec(float(tinfo["cooldown"]), atk_spd)

    # Range: +50% of Range for melee, +100% for ranged, plus character tag range bonus
    extra_range = stats.get("range")
    range_with_tag = character.special.get("range_with_tag", {})
    for cls_id in wdef.classes:
        if cls_id in range_with_tag:
            extra_range += float(range_with_tag[cls_id])

    base_range = float(tinfo["range"])
    if wdef.type == "melee":
        eff_range = max(60.0, base_range + extra_range * 0.5)
    else:
        eff_range = max(110.0, base_range + extra_range)

    crit_chance = max(0.0, min(100.0, float(tinfo["crit_chance"]) + stats.get("crit_chance")))
    crit_mult = float(tinfo.get("crit_mult", 2.0))
    knockback = max(0.0, float(tinfo.get("knockback", 0.0)) + stats.get("knockback"))
    piercing = int(tinfo.get("piercing", 0)) + max(0, int(round(stats.get("piercing"))))
    bounces = int(tinfo.get("bounces", 0)) + max(0, int(round(stats.get("bounces"))))

    burn_dmg = float(tinfo.get("burn_dmg", 0.0))
    if burn_dmg > 0:
        burn_dmg = max(1.0, burn_dmg + stats.get("elemental_damage"))

    exp_radius = float(tinfo.get("explosion_radius", 0.0))
    if exp_radius > 0:
        exp_radius *= max(0.5, 1.0 + stats.get("explosion_size") / 100.0)

    return {
        "damage": raw_damage,
        "cooldown": cooldown,
        "range": eff_range,
        "crit_chance": crit_chance,
        "crit_mult": crit_mult,
        "knockback": knockback,
        "piercing": piercing,
        "bounces": bounces,
        "pellets": int(tinfo.get("pellets", 1)),
        "burn_dmg": burn_dmg,
        "burn_ticks": int(tinfo.get("burn_ticks", 0)),
        "slow_pct": float(tinfo.get("slow_pct", 0.0)),
        "explosion_radius": exp_radius,
        "explosion_chance": float(tinfo.get("explosion_chance", 1.0 if exp_radius > 0 else 0.0)),
        "lightning_bolts": int(tinfo.get("lightning_bolts", 0)),
        "lightning_dmg": float(tinfo.get("lightning_dmg", 0.0)) + stats.get("elemental_damage"),
    }


def consumable_heal_amount(stats: StatBlock) -> int:
    return max(1, BASE_CONSUMABLE_HEAL + int(round(stats.get("consumable_heal"))))


def shop_item_price(base_price: int, wave_num: int, stats: StatBlock) -> int:
    """Brotato shop pricing scales slightly with wave and Items Price stat."""
    wave_inflation = 1.0 + (max(1, wave_num) - 1) * 0.055
    price_mult = max(0.5, 1.0 + stats.get("items_price") / 100.0)
    return max(1, int(round(base_price * wave_inflation * price_mult)))
