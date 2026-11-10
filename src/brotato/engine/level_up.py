"""Level-up upgrade card generation and selection."""

from __future__ import annotations

from dataclasses import dataclass

from brotato.engine.game_state import GameState
from brotato.engine.shop import roll_offer_tier
from brotato.models import LevelUpOption


@dataclass(frozen=True)
class _UpgradeTemplate:
    id: str
    name: str
    stat_key: str
    values_by_tier: tuple[float, float, float, float]
    suffix: str


UPGRADE_TEMPLATES: tuple[_UpgradeTemplate, ...] = (
    _UpgradeTemplate("upg_max_hp", "Max HP", "max_hp", (3, 6, 9, 12), ""),
    _UpgradeTemplate("upg_hp_regen", "HP Regeneration", "hp_regen", (2, 3, 4, 5), ""),
    _UpgradeTemplate("upg_life_steal", "Life Steal", "life_steal", (1, 2, 3, 4), "%"),
    _UpgradeTemplate("upg_damage_pct", "% Damage", "damage_pct", (5, 8, 12, 16), "%"),
    _UpgradeTemplate("upg_melee_dmg", "Melee Damage", "melee_damage", (2, 3, 4, 5), ""),
    _UpgradeTemplate("upg_ranged_dmg", "Ranged Damage", "ranged_damage", (1, 2, 3, 4), ""),
    _UpgradeTemplate("upg_elem_dmg", "Elemental Damage", "elemental_damage", (1, 2, 3, 4), ""),
    _UpgradeTemplate("upg_atk_spd", "Attack Speed", "attack_speed", (5, 10, 15, 20), "%"),
    _UpgradeTemplate("upg_crit", "Crit Chance", "crit_chance", (3, 5, 7, 9), "%"),
    _UpgradeTemplate("upg_eng", "Engineering", "engineering", (2, 3, 4, 5), ""),
    _UpgradeTemplate("upg_range", "Range", "range", (15, 30, 45, 60), ""),
    _UpgradeTemplate("upg_armor", "Armor", "armor", (1, 2, 3, 4), ""),
    _UpgradeTemplate("upg_dodge", "Dodge", "dodge", (3, 6, 9, 12), "%"),
    _UpgradeTemplate("upg_speed", "Speed", "speed", (3, 6, 9, 12), "%"),
    _UpgradeTemplate("upg_luck", "Luck", "luck", (5, 10, 15, 20), ""),
    _UpgradeTemplate("upg_harvesting", "Harvesting", "harvesting", (5, 8, 10, 12), ""),
)


def upgrade_reroll_cost(state: GameState) -> int:
    return max(2, int(round(1 + state.wave * 0.6))) + state.upgrade_rerolls_used * max(1, state.wave // 3)


def generate_level_up_choices(state: GameState) -> list[LevelUpOption]:
    if state.pending_level_ups <= 0:
        state.current_level_choices = []
        return []

    rng = state.rng
    # Filter out stats completely nullified by character (e.g. Mage melee/ranged 0.0) if possible
    gain_mults = state.character.special.get("stat_gain_mults", {})
    valid = [t for t in UPGRADE_TEMPLATES if gain_mults.get(t.stat_key, 1.0) > 0.0]
    if len(valid) < 4:
        valid = list(UPGRADE_TEMPLATES)

    chosen_templates = rng.sample(valid, k=4)
    options: list[LevelUpOption] = []
    luck = state.stats.get("luck")

    for tmpl in chosen_templates:
        tier = roll_offer_tier(state.wave, luck, rng, min_tier=1, max_tier=4)
        val = tmpl.values_by_tier[tier - 1]
        val_str = f"+{int(val)}{tmpl.suffix}"
        options.append(
            LevelUpOption(
                id=tmpl.id,
                name=tmpl.name,
                tier=tier,
                stat_key=tmpl.stat_key,
                stat_value=val,
                description=f"{val_str} {tmpl.name}",
            )
        )

    state.current_level_choices = options
    return options


def pick_level_up_choice(state: GameState, index: int) -> bool:
    if state.pending_level_ups <= 0 or not (0 <= index < len(state.current_level_choices)):
        return False
    opt = state.current_level_choices[index]
    state.upgrade_stats.add(opt.stat_key, opt.stat_value)
    state.pending_level_ups -= 1
    state.rebuild_stats()
    state.events.append(("buy", opt.id))

    if state.pending_level_ups > 0:
        generate_level_up_choices(state)
    else:
        state.current_level_choices = []
    return True


def reroll_level_up_choices(state: GameState) -> bool:
    if state.pending_level_ups <= 0:
        return False
    cost = upgrade_reroll_cost(state)
    if state.materials < cost:
        return False
    state.materials -= cost
    state.upgrade_rerolls_used += 1
    generate_level_up_choices(state)
    state.events.append(("reroll", cost))
    return True
