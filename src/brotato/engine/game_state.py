"""Central simulation state for an active Brotato run."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from brotato.config import (
    ARENA_HEIGHT,
    ARENA_WALL_MARGIN,
    ARENA_WIDTH,
    DEFAULT_DODGE_CAP,
    PLAYER_RADIUS,
    SPATIAL_CELL_SIZE,
)
from brotato.data_loader import GameDatabase
from brotato.models import (
    CharacterDef,
    EnemyEntity,
    ExplosionVFX,
    FloatingText,
    LevelUpOption,
    MineEntity,
    Particle,
    PickupEntity,
    ProjectileEntity,
    ShopOffer,
    SpawnTelegraph,
    StatBlock,
    TreeEntity,
    TurretEntity,
    WeaponInstance,
)
from brotato.spatial_grid import SpatialHashGrid
from brotato.stats import compute_effective_stats, xp_for_next_level


@dataclass
class RunStatsSummary:
    enemies_killed: int = 0
    elites_killed: int = 0
    bosses_killed: int = 0
    total_damage_dealt: int = 0
    materials_collected: int = 0
    trees_chopped: int = 0
    crates_opened: int = 0
    damage_taken: int = 0
    hits_dodged: int = 0


class GameState:
    """Holds all state for a single Brotato run (combat, shop, upgrades, stats)."""

    def __init__(
        self,
        db: GameDatabase,
        character_id: str,
        starting_weapon_id: str,
        danger_level: int = 0,
        seed: int | None = None,
    ) -> None:
        self.db = db
        self.rng = random.Random(seed)
        self.character: CharacterDef = db.characters[character_id]
        self.danger_level: int = max(0, min(5, danger_level))

        self._next_uid: int = 1

        # Progression & Economy
        self.wave: int = 1
        self.endless_mode: bool = False
        self.level: int = 1
        self.xp: float = 0.0
        self.xp_needed: int = xp_for_next_level(1)
        self.pending_level_ups: int = 0
        self.pending_crates: int = 0
        self.materials: int = 0
        self.bagged_materials: int = 0

        # Stat layers
        self.upgrade_stats = StatBlock()
        self.bonus_stats = StatBlock()  # Permanent gains (Ghost weapons, Vigilante Ring, Loud)
        self.items: list[str] = []
        self.item_counts: dict[str, int] = {}
        self.weapons: list[WeaponInstance] = []

        # Effective computed stats
        self.stats = StatBlock()
        self.class_counts: dict[str, int] = {}
        self.special_agg: dict[str, float] = {}
        self.hp: float = 10.0

        # Equip starting weapon
        self.add_weapon(starting_weapon_id, tier=1)
        self.rebuild_stats()

        # Player runtime state
        self.player_x: float = ARENA_WIDTH * 0.5
        self.player_y: float = ARENA_HEIGHT * 0.5
        self.player_vx: float = 0.0
        self.player_vy: float = 0.0
        self.player_facing_x: float = 1.0
        self.hp: float = self.max_hp
        self.invuln_timer: float = 0.0
        self.regen_accum: float = 0.0
        self.wave_shields_left: int = 0
        self.lifesteal_budget: float = 0.0
        self.manual_aim: bool = False

        # Wave runtime state
        self.wave_active: bool = False
        self.wave_timer: float = 0.0
        self.wave_duration: float = 20.0
        self.spawn_accum: float = 0.0
        self.loot_alien_spawned: bool = False
        self.elite_spawned: bool = False
        self.boss_spawned: bool = False
        self.wave_tag: str = ""
        self.run_won: bool = False
        self.run_lost: bool = False

        # Entities
        self.enemies: list[EnemyEntity] = []
        self.telegraphs: list[SpawnTelegraph] = []
        self.projectiles: list[ProjectileEntity] = []
        self.pickups: list[PickupEntity] = []
        self.trees: list[TreeEntity] = []
        self.turrets: list[TurretEntity] = []
        self.mines: list[MineEntity] = []
        self.particles: list[Particle] = []
        self.explosions: list[ExplosionVFX] = []
        self.floating_texts: list[FloatingText] = []

        # Spatial grids
        self.enemy_grid: SpatialHashGrid[EnemyEntity] = SpatialHashGrid(SPATIAL_CELL_SIZE)
        self.pickup_grid: SpatialHashGrid[PickupEntity] = SpatialHashGrid(SPATIAL_CELL_SIZE)
        self.tree_grid: SpatialHashGrid[TreeEntity] = SpatialHashGrid(SPATIAL_CELL_SIZE)

        # Shop / Upgrades state
        self.shop_offers: list[ShopOffer] = []
        self.shop_rerolls_used: int = 0
        self.free_rerolls_left: int = 0
        self.current_level_choices: list[LevelUpOption] = []
        self.current_crate_item: str | None = None
        self.upgrade_rerolls_used: int = 0

        # Audio/visual event queue (consumed by renderer/audio system)
        self.events: list[tuple[str, Any]] = []
        self.summary = RunStatsSummary()

    def alloc_uid(self) -> int:
        uid = self._next_uid
        self._next_uid += 1
        return uid

    @property
    def max_hp(self) -> float:
        return max(1.0, round(self.stats.get("max_hp", 10.0)))

    @property
    def max_weapons(self) -> int:
        return int(self.character.special.get("max_weapons", 6))

    @property
    def dodge_cap(self) -> float:
        return float(self.character.special.get("dodge_cap", DEFAULT_DODGE_CAP))

    def can_equip_weapon(self, weapon_id: str) -> bool:
        wdef = self.db.weapons[weapon_id]
        if wdef.type == "melee" and not self.character.special.get("can_equip_melee", True):
            return False
        if wdef.type == "ranged" and not self.character.special.get("can_equip_ranged", True):
            return False
        return True

    def rebuild_stats(self) -> None:
        self.stats, self.class_counts, self.special_agg = compute_effective_stats(
            db=self.db,
            character=self.character,
            level=self.level,
            upgrade_stats=self.upgrade_stats,
            bonus_stats=self.bonus_stats,
            items=self.items,
            weapons=self.weapons,
        )
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def add_weapon(self, weapon_id: str, tier: int = 1) -> WeaponInstance | None:
        if not self.can_equip_weapon(weapon_id):
            return None
        if len(self.weapons) >= self.max_weapons:
            return None
        wdef = self.db.weapons[weapon_id]
        tier = max(wdef.min_tier, min(4, tier))
        inst = WeaponInstance(uid=self.alloc_uid(), def_id=weapon_id, tier=tier)
        self.weapons.append(inst)
        self._reposition_weapon_slots()
        self.rebuild_stats()
        return inst

    def _reposition_weapon_slots(self) -> None:
        n = max(1, len(self.weapons))
        orbit_r = 34.0
        for idx, w in enumerate(self.weapons):
            ang = (2.0 * math.pi * idx) / n - math.pi * 0.5
            w.slot_x = math.cos(ang) * orbit_r
            w.slot_y = math.sin(ang) * orbit_r

    def can_combine_at(self, index: int) -> int | None:
        """Return partner weapon index if weapons[index] can be combined to next tier."""
        if not (0 <= index < len(self.weapons)):
            return None
        w = self.weapons[index]
        if w.tier >= 4:
            return None
        for j, other in enumerate(self.weapons):
            if j != index and other.def_id == w.def_id and other.tier == w.tier:
                return j
        return None

    def combine_weapons(self, idx_a: int, idx_b: int) -> bool:
        if idx_a == idx_b or not (0 <= idx_a < len(self.weapons)) or not (0 <= idx_b < len(self.weapons)):
            return False
        wa = self.weapons[idx_a]
        wb = self.weapons[idx_b]
        if wa.def_id != wb.def_id or wa.tier != wb.tier or wa.tier >= 4:
            return False
        wa.tier += 1
        wa.kills += wb.kills
        wa.total_damage += wb.total_damage
        self.weapons.pop(idx_b)
        self._reposition_weapon_slots()
        self.rebuild_stats()
        return True

    def add_item(self, item_id: str) -> bool:
        idef = self.db.items[item_id]
        count = self.item_counts.get(item_id, 0)
        if idef.max_count is not None and count >= idef.max_count:
            return False
        self.items.append(item_id)
        self.item_counts[item_id] = count + 1
        self.rebuild_stats()
        return True

    def grant_xp(self, amount: float) -> int:
        """Add XP scaled by XP Gain stat and process level ups. Returns levels gained."""
        xp_mult = max(0.25, 1.0 + self.stats.get("xp_gain") / 100.0)
        self.xp += amount * xp_mult
        gained = 0
        while self.xp >= self.xp_needed:
            self.xp -= self.xp_needed
            self.level += 1
            self.xp_needed = xp_for_next_level(self.level)
            self.pending_level_ups += 1
            gained += 1
            self.rebuild_stats()
            self.hp = min(self.max_hp, self.hp + 1.0)
            self.floating_texts.append(
                FloatingText(
                    x=self.player_x,
                    y=self.player_y - 38,
                    vy=-45.0,
                    text="LEVEL UP!",
                    color=(255, 224, 92),
                    life=1.4,
                    max_life=1.4,
                    scale=1.35,
                )
            )
            self.events.append(("levelup", self.level))
        return gained

    def start_wave(self, wave_num: int | None = None) -> None:
        if wave_num is not None:
            self.wave = wave_num

        # Piggy Bank interest at start of wave
        interest_pct = self.special_agg.get("interest_pct", 0.0)
        if interest_pct > 0 and self.materials > 0:
            bonus_mat = int(math.floor(self.materials * interest_pct))
            self.materials += bonus_mat

        self.rebuild_stats()
        wcfg = self.db.get_wave_config(self.wave)
        self.wave_duration = float(wcfg["duration"])
        self.wave_timer = self.wave_duration
        self.wave_tag = str(wcfg.get("tag", ""))
        self.wave_active = True
        self.spawn_accum = 0.4
        self.loot_alien_spawned = False
        self.elite_spawned = False
        self.boss_spawned = False

        # Reset player to center & full HP (exact Brotato behavior)
        self.player_x = ARENA_WIDTH * 0.5
        self.player_y = ARENA_HEIGHT * 0.5
        self.player_vx = 0.0
        self.player_vy = 0.0
        self.hp = self.max_hp
        self.invuln_timer = 0.5
        self.wave_shields_left = int(self.special_agg.get("wave_shield", 0))
        self.lifesteal_budget = 10.0

        # Clear transient wave entities
        self.enemies.clear()
        self.telegraphs.clear()
        self.projectiles.clear()
        self.pickups.clear()
        self.trees.clear()
        self.turrets.clear()
        self.mines.clear()
        self.particles.clear()
        self.explosions.clear()
        self.floating_texts.clear()

        for w in self.weapons:
            w.cooldown_timer = self.rng.uniform(0.05, 0.25)
            w.swing_timer = 0.0
            w.mine_timer = 1.2

        # Spawn initial trees (base 2-3 + Trees stat)
        num_trees = max(0, 2 + int(round(self.stats.get("trees"))))
        margin = ARENA_WALL_MARGIN + 70.0
        for _ in range(num_trees):
            for _attempt in range(12):
                tx = self.rng.uniform(margin, ARENA_WIDTH - margin)
                ty = self.rng.uniform(margin, ARENA_HEIGHT - margin)
                if math.hypot(tx - self.player_x, ty - self.player_y) > 160.0:
                    self.trees.append(TreeEntity(uid=self.alloc_uid(), x=tx, y=ty, hp=12.0 + self.wave * 3.0, max_hp=12.0 + self.wave * 3.0))
                    break

        # Spawn Engineering turrets from Wrenches + Pocket Turrets + Engineer passive
        turret_tiers: list[int] = []
        for w in self.weapons:
            tinfo = self.db.weapons[w.def_id].tiers[w.tier]
            if "turret_tier" in tinfo:
                turret_tiers.append(int(tinfo["turret_tier"]))
        item_turrets = int(self.special_agg.get("turrets", 0))
        for _ in range(item_turrets):
            turret_tiers.append(1)

        if turret_tiers:
            spread = 95.0 if self.character.id == "engineer" else 185.0
            for idx, tt in enumerate(turret_tiers):
                ang = (2.0 * math.pi * idx) / len(turret_tiers) + self.rng.uniform(-0.25, 0.25)
                dist = self.rng.uniform(75.0, spread)
                tx = max(margin, min(ARENA_WIDTH - margin, self.player_x + math.cos(ang) * dist))
                ty = max(margin, min(ARENA_HEIGHT - margin, self.player_y + math.sin(ang) * dist))
                self.turrets.append(TurretEntity(uid=self.alloc_uid(), x=tx, y=ty, tier=tt))

    def end_wave(self) -> None:
        """Resolve wave end: bag uncollected materials, apply Harvesting & wave passives."""
        self.wave_active = False

        # Any uncollected materials left on the floor go into the Material Bag for next wave!
        for p in self.pickups:
            if p.kind == "material":
                self.bagged_materials += p.value

        self.enemies.clear()
        self.telegraphs.clear()
        self.projectiles.clear()
        self.pickups.clear()
        self.mines.clear()

        # Harvesting payout (Materials + XP)
        harv = int(round(self.stats.get("harvesting")))
        if harv > 0:
            self.materials += harv
            self.grant_xp(harv)
            # Harvesting compounds by +5% (+Crown bonus) before Wave 20
            if self.wave < 20:
                growth = 0.05 + self.special_agg.get("harvesting_growth_bonus", 0.0)
                added = max(1, int(math.ceil(harv * growth)))
                self.bonus_stats.add("harvesting", added)

        # Per-wave character/item effects (Loud -3 Harvesting/wave, Vigilante Ring +3% Damage/wave)
        harv_per_wave = self.character.special.get("harvesting_per_wave", 0)
        if harv_per_wave:
            self.bonus_stats.add("harvesting", float(harv_per_wave))

        dmg_per_wave = self.special_agg.get("damage_per_wave", 0.0)
        if dmg_per_wave:
            self.bonus_stats.add("damage_pct", dmg_per_wave)

        self.rebuild_stats()

        # Check Wave 20 victory!
        if self.wave == 20 and not self.endless_mode:
            self.run_won = True

        self.free_rerolls_left = max(0, int(round(self.stats.get("free_rerolls"))))
        self.shop_rerolls_used = 0
        self.upgrade_rerolls_used = 0
