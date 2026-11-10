"""Typed dataclasses and game entity definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PRIMARY_STAT_KEYS = (
    "max_hp",
    "hp_regen",
    "life_steal",
    "damage_pct",
    "melee_damage",
    "ranged_damage",
    "elemental_damage",
    "attack_speed",
    "crit_chance",
    "engineering",
    "range",
    "armor",
    "dodge",
    "speed",
    "luck",
    "harvesting",
)

SECONDARY_STAT_KEYS = (
    "consumable_heal",
    "xp_gain",
    "pickup_range",
    "items_price",
    "explosion_damage",
    "explosion_size",
    "piercing",
    "bounces",
    "knockback",
    "enemies_pct",
    "enemy_speed_pct",
    "trees",
    "free_rerolls",
)

ALL_STAT_KEYS = PRIMARY_STAT_KEYS + SECONDARY_STAT_KEYS


@dataclass
class StatBlock:
    """Mutable dictionary-like container for all player stats."""

    values: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in ALL_STAT_KEYS})

    def get(self, key: str, default: float = 0.0) -> float:
        return self.values.get(key, default)

    def add(self, key: str, delta: float) -> None:
        self.values[key] = self.values.get(key, 0.0) + delta

    def copy(self) -> StatBlock:
        return StatBlock(values=dict(self.values))

    def to_int_dict(self) -> dict[str, int]:
        return {k: int(round(v)) for k, v in self.values.items()}


@dataclass(frozen=True)
class CharacterDef:
    id: str
    name: str
    subtitle: str
    description: str
    starting_weapons: list[str]
    stats: dict[str, float]
    effects_text: list[str]
    special: dict[str, Any]
    appearance: dict[str, Any]


@dataclass(frozen=True)
class WeaponDef:
    id: str
    name: str
    type: str  # "melee" | "ranged"
    attack_style: str  # "thrust" | "sweep" | "projectile"
    classes: list[str]
    min_tier: int
    scaling: dict[str, float]
    tiers: dict[int, dict[str, Any]]
    projectile: dict[str, Any]
    special: dict[str, Any]
    description: str


@dataclass(frozen=True)
class ItemDef:
    id: str
    name: str
    tier: int
    price: int
    max_count: int | None
    stats: dict[str, float]
    special: dict[str, Any]
    tags: list[str]
    description: str


@dataclass(frozen=True)
class EnemyDef:
    id: str
    name: str
    behavior: str
    base_hp: float
    hp_per_wave: float
    base_damage: float
    damage_per_wave: float
    speed: float
    radius: float
    knockback_resist: float
    materials: int
    consumable_chance: float
    color: tuple[int, int, int]
    accent: tuple[int, int, int]
    shape: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WeaponClassDef:
    id: str
    name: str
    bonuses_per_count: dict[int, dict[str, float]]
    description: str


@dataclass(slots=True)
class WeaponInstance:
    uid: int
    def_id: str
    tier: int
    cooldown_timer: float = 0.0
    aim_angle: float = 0.0
    swing_timer: float = 0.0
    swing_duration: float = 0.18
    swing_dir: int = 1
    swing_hit_ids: set[int] = field(default_factory=set)
    kills: int = 0
    total_damage: int = 0
    mine_timer: float = 1.5
    slot_x: float = 0.0
    slot_y: float = 0.0


@dataclass(slots=True)
class EnemyEntity:
    uid: int
    def_id: str
    x: float
    y: float
    vx: float
    vy: float
    hp: float
    max_hp: float
    damage: float
    speed: float
    radius: float
    knockback_resist: float
    materials: int
    consumable_chance: float
    behavior: str
    is_elite: bool = False
    is_boss: bool = False
    guaranteed_crate: bool = False
    # Status effects
    burn_dmg: float = 0.0
    burn_ticks: int = 0
    burn_timer: float = 0.0
    slow_pct: float = 0.0
    slow_timer: float = 0.0
    hit_flash: float = 0.0
    # AI state
    ai_timer: float = 0.0
    ai_phase: int = 0
    charge_dx: float = 0.0
    charge_dy: float = 0.0
    pattern_angle: float = 0.0


@dataclass(slots=True)
class SpawnTelegraph:
    uid: int
    def_id: str
    x: float
    y: float
    timer: float
    duration: float = 1.0


@dataclass(slots=True)
class ProjectileEntity:
    uid: int
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    damage: float
    is_crit: bool
    from_player: bool
    color: tuple[int, int, int]
    range_left: float
    piercing_left: int = 0
    bounces_left: int = 0
    knockback: float = 0.0
    lifesteal_chance: float = 0.0
    explosion_radius: float = 0.0
    burn_dmg: float = 0.0
    burn_ticks: int = 0
    slow_pct: float = 0.0
    source_weapon_uid: int | None = None
    hit_enemy_ids: set[int] = field(default_factory=set)


@dataclass(slots=True)
class PickupEntity:
    uid: int
    kind: str  # "material" | "consumable" | "crate"
    x: float
    y: float
    value: int = 1
    tier: int = 1
    magnetized: bool = False
    vx: float = 0.0
    vy: float = 0.0
    bob_phase: float = 0.0


@dataclass(slots=True)
class TreeEntity:
    uid: int
    x: float
    y: float
    hp: float
    max_hp: float
    radius: float = 24.0
    hit_flash: float = 0.0


@dataclass(slots=True)
class TurretEntity:
    uid: int
    x: float
    y: float
    tier: int
    cooldown_timer: float = 0.2
    aim_angle: float = 0.0
    range: float = 380.0


@dataclass(slots=True)
class MineEntity:
    uid: int
    x: float
    y: float
    damage: float
    explosion_radius: float
    armed_timer: float = 0.35


@dataclass(slots=True)
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    radius: float
    color: tuple[int, int, int]


@dataclass(slots=True)
class ExplosionVFX:
    x: float
    y: float
    radius: float
    timer: float
    duration: float
    color: tuple[int, int, int]


@dataclass(slots=True)
class FloatingText:
    x: float
    y: float
    vy: float
    text: str
    color: tuple[int, int, int]
    life: float
    max_life: float
    scale: float = 1.0


@dataclass
class ShopOffer:
    kind: str  # "weapon" | "item"
    def_id: str
    tier: int
    price: int
    locked: bool = False
    purchased: bool = False


@dataclass
class LevelUpOption:
    id: str
    name: str
    tier: int
    stat_key: str
    stat_value: float
    description: str
