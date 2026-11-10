"""Loads and validates JSON game definitions and optional custom asset overrides."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brotato.config import ASSETS_DIR, DATA_DIR
from brotato.models import (
    CharacterDef,
    EnemyDef,
    ItemDef,
    WeaponClassDef,
    WeaponDef,
)


@dataclass
class GameDatabase:
    stats_meta: dict[str, list[dict[str, Any]]]
    weapon_classes: dict[str, WeaponClassDef]
    characters: dict[str, CharacterDef]
    character_order: list[str]
    weapons: dict[str, WeaponDef]
    weapon_order: list[str]
    items: dict[str, ItemDef]
    item_order: list[str]
    enemies: dict[str, EnemyDef]
    waves_config: dict[str, Any]
    custom_assets: dict[str, Path]

    def get_danger(self, level: int) -> dict[str, Any]:
        dangers = self.waves_config["danger_levels"]
        idx = max(0, min(level, len(dangers) - 1))
        return dangers[idx]

    def get_wave_config(self, wave_num: int) -> dict[str, Any]:
        waves = self.waves_config["waves"]
        if 1 <= wave_num <= len(waves):
            return waves[wave_num - 1]
        # Endless scaling for Wave 21+
        base = dict(waves[-2])  # Wave 19 swarm template
        extra = wave_num - len(waves)
        base["wave"] = wave_num
        base["duration"] = 60
        base["spawn_rate"] = round(6.5 + extra * 0.45, 2)
        base["max_enemies"] = min(220, 120 + extra * 8)
        base["tag"] = "ENDLESS"
        return base


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _discover_custom_assets(assets_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not assets_dir.exists():
        return found
    for sub in ("sprites/characters", "sprites/weapons", "sprites/enemies", "sprites/items", "sprites/arena", "sounds", "fonts"):
        folder = assets_dir / sub
        if folder.is_dir():
            for file_path in folder.iterdir():
                if file_path.is_file() and not file_path.name.startswith("."):
                    key = f"{sub}/{file_path.stem}"
                    found[key] = file_path
    return found


def load_database(data_dir: Path | None = None, assets_dir: Path | None = None) -> GameDatabase:
    ddir = data_dir or DATA_DIR
    adir = assets_dir or ASSETS_DIR

    stats_meta = _load_json(ddir / "stats_meta.json")

    raw_classes = _load_json(ddir / "weapon_classes.json")
    weapon_classes: dict[str, WeaponClassDef] = {}
    for cid, cdata in raw_classes.items():
        bonuses = {int(k): v for k, v in cdata["bonuses_per_count"].items()}
        weapon_classes[cid] = WeaponClassDef(
            id=cid,
            name=cdata["name"],
            bonuses_per_count=bonuses,
            description=cdata["description"],
        )

    raw_chars = _load_json(ddir / "characters.json")
    characters: dict[str, CharacterDef] = {}
    character_order: list[str] = []
    for c in raw_chars:
        ch = CharacterDef(
            id=c["id"],
            name=c["name"],
            subtitle=c.get("subtitle", ""),
            description=c["description"],
            starting_weapons=list(c["starting_weapons"]),
            stats={k: float(v) for k, v in c.get("stats", {}).items()},
            effects_text=list(c.get("effects_text", [])),
            special=dict(c.get("special", {})),
            appearance=dict(c.get("appearance", {})),
        )
        characters[ch.id] = ch
        character_order.append(ch.id)

    raw_weapons = _load_json(ddir / "weapons.json")
    weapons: dict[str, WeaponDef] = {}
    weapon_order: list[str] = []
    for w in raw_weapons:
        tiers = {int(k): v for k, v in w["tiers"].items()}
        wd = WeaponDef(
            id=w["id"],
            name=w["name"],
            type=w["type"],
            attack_style=w["attack_style"],
            classes=list(w["classes"]),
            min_tier=int(w.get("min_tier", 1)),
            scaling={k: float(v) for k, v in w.get("scaling", {}).items()},
            tiers=tiers,
            projectile=dict(w.get("projectile", {})),
            special=dict(w.get("special", {})),
            description=w["description"],
        )
        weapons[wd.id] = wd
        weapon_order.append(wd.id)

    raw_items = _load_json(ddir / "items.json")
    items: dict[str, ItemDef] = {}
    item_order: list[str] = []
    for it in raw_items:
        idef = ItemDef(
            id=it["id"],
            name=it["name"],
            tier=int(it["tier"]),
            price=int(it["price"]),
            max_count=it.get("max_count"),
            stats={k: float(v) for k, v in it.get("stats", {}).items()},
            special=dict(it.get("special", {})),
            tags=list(it.get("tags", [])),
            description=it["description"],
        )
        items[idef.id] = idef
        item_order.append(idef.id)

    raw_enemies = _load_json(ddir / "enemies.json")
    enemies: dict[str, EnemyDef] = {}
    known_keys = {
        "id", "name", "behavior", "base_hp", "hp_per_wave",
        "base_damage", "damage_per_wave", "speed", "radius",
        "knockback_resist", "materials", "consumable_chance",
        "color", "accent", "shape",
    }
    for e in raw_enemies:
        extra = {k: v for k, v in e.items() if k not in known_keys}
        ed = EnemyDef(
            id=e["id"],
            name=e["name"],
            behavior=e["behavior"],
            base_hp=float(e["base_hp"]),
            hp_per_wave=float(e["hp_per_wave"]),
            base_damage=float(e["base_damage"]),
            damage_per_wave=float(e["damage_per_wave"]),
            speed=float(e["speed"]),
            radius=float(e["radius"]),
            knockback_resist=float(e["knockback_resist"]),
            materials=int(e["materials"]),
            consumable_chance=float(e["consumable_chance"]),
            color=tuple(e["color"]),
            accent=tuple(e["accent"]),
            shape=e["shape"],
            extra=extra,
        )
        enemies[ed.id] = ed

    waves_config = _load_json(ddir / "waves.json")
    custom_assets = _discover_custom_assets(adir)

    return GameDatabase(
        stats_meta=stats_meta,
        weapon_classes=weapon_classes,
        characters=characters,
        character_order=character_order,
        weapons=weapons,
        weapon_order=weapon_order,
        items=items,
        item_order=item_order,
        enemies=enemies,
        waves_config=waves_config,
        custom_assets=custom_assets,
    )
