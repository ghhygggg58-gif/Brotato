"""Shop generation, tier probabilities, locking, rerolling, combining, and crates."""

from __future__ import annotations

import math

from brotato.engine.game_state import GameState
from brotato.models import ShopOffer
from brotato.stats import shop_item_price


def roll_offer_tier(wave: int, luck: float, rng, min_tier: int = 1, max_tier: int = 4) -> int:
    """Compute Brotato-style Tier I-IV drop probabilities scaled by Wave and Luck."""
    luck_pos = max(0.0, luck)
    t4_chance = 0.0
    t3_chance = 0.0
    t2_chance = 0.0

    if wave >= 2:
        t2_chance = min(0.55, (0.06 + (wave - 2) * 0.028) * (1.0 + luck_pos * 0.008))
    if wave >= 4:
        t3_chance = min(0.35, (0.02 + (wave - 4) * 0.015) * (1.0 + luck_pos * 0.01))
    if wave >= 8:
        t4_chance = min(0.18, (0.008 + (wave - 8) * 0.008) * (1.0 + luck_pos * 0.012))

    # Clamp total non-T1 probability so T1 remains reasonable early on
    total_high = t2_chance + t3_chance + t4_chance
    if total_high > 0.90:
        scale = 0.90 / total_high
        t2_chance *= scale
        t3_chance *= scale
        t4_chance *= scale

    r = rng.random()
    if r < t4_chance:
        tier = 4
    elif r < t4_chance + t3_chance:
        tier = 3
    elif r < t4_chance + t3_chance + t2_chance:
        tier = 2
    else:
        tier = 1
    return max(min_tier, min(max_tier, tier))


def shop_reroll_cost(state: GameState) -> int:
    if state.free_rerolls_left > 0:
        return 0
    base = max(2, int(round(1 + state.wave * 0.65)))
    step = max(1, int(math.ceil(state.wave * 0.35)))
    return base + state.shop_rerolls_used * step


def _eligible_weapon_ids(state: GameState) -> list[str]:
    return [wid for wid in state.db.weapon_order if state.can_equip_weapon(wid)]


def _eligible_item_ids(state: GameState, target_tier: int) -> list[str]:
    out: list[str] = []
    for iid in state.db.item_order:
        idef = state.db.items[iid]
        if idef.tier != target_tier:
            continue
        if idef.max_count is not None and state.item_counts.get(iid, 0) >= idef.max_count:
            continue
        out.append(iid)
    return out


def _pick_weapon_for_shop(state: GameState) -> tuple[str, int] | None:
    eligible = _eligible_weapon_ids(state)
    if not eligible:
        return None

    rng = state.rng
    chosen_id: str | None = None

    # Brotato weapon bias: ~20% chance to match equipped weapon, ~20% chance to share class
    if state.weapons and rng.random() < 0.40:
        if rng.random() < 0.50:
            pool = [w.def_id for w in state.weapons if w.def_id in eligible]
            if pool:
                chosen_id = rng.choice(pool)
        if chosen_id is None:
            equipped_classes = {
                cls_id
                for w in state.weapons
                for cls_id in state.db.weapons[w.def_id].classes
            }
            pool = [
                wid for wid in eligible
                if any(c in equipped_classes for c in state.db.weapons[wid].classes)
            ]
            if pool:
                chosen_id = rng.choice(pool)

    if chosen_id is None:
        chosen_id = rng.choice(eligible)

    wdef = state.db.weapons[chosen_id]
    tier = roll_offer_tier(state.wave, state.stats.get("luck"), rng, min_tier=wdef.min_tier)
    # Keep trying if chosen weapon doesn't have tier (usually 1..4 exists except rocket_launcher min_tier=2)
    while tier not in wdef.tiers and tier < 4:
        tier += 1
    return chosen_id, tier


def _pick_item_for_shop(state: GameState) -> tuple[str, int] | None:
    rng = state.rng
    tier = roll_offer_tier(state.wave, state.stats.get("luck"), rng, min_tier=1, max_tier=4)
    for t in (tier, max(1, tier - 1), 1, 2, 3, 4):
        pool = _eligible_item_ids(state, t)
        if pool:
            return rng.choice(pool), t
    return None


def generate_shop(state: GameState, preserve_locked: bool = True) -> list[ShopOffer]:
    """Generate 4 shop offers while keeping any locked unpurchased slots."""
    rng = state.rng
    existing = list(state.shop_offers) if preserve_locked else []
    new_offers: list[ShopOffer | None] = [None, None, None, None]

    locked_weapons = 0
    for idx in range(min(4, len(existing))):
        old = existing[idx]
        if old.locked and not old.purchased:
            # Refresh dynamic price with current wave & items_price stat
            if old.kind == "weapon":
                base_p = int(state.db.weapons[old.def_id].tiers[old.tier]["price"])
                locked_weapons += 1
            else:
                base_p = state.db.items[old.def_id].price
            old.price = shop_item_price(base_p, state.wave, state.stats)
            new_offers[idx] = old

    open_indices = [i for i, o in enumerate(new_offers) if o is None]
    min_weapons_wanted = 2 if state.wave <= 2 else (1 if state.wave <= 5 else 0)
    weapons_needed = max(0, min_weapons_wanted - locked_weapons)
    if state.max_weapons <= 1 and len(state.weapons) >= 1:
        weapons_needed = 0

    seen_items: set[str] = {
        o.def_id for o in new_offers if o is not None and o.kind == "item"
    }

    for pos_idx, slot_idx in enumerate(open_indices):
        want_weapon = False
        if pos_idx < weapons_needed:
            want_weapon = True
        elif state.max_weapons > 1 or len(state.weapons) == 0:
            weapon_prob = 0.48 if state.wave <= 4 else 0.35
            want_weapon = rng.random() < weapon_prob

        offer: ShopOffer | None = None
        if want_weapon:
            wp = _pick_weapon_for_shop(state)
            if wp is not None:
                wid, tier = wp
                base_p = int(state.db.weapons[wid].tiers[tier]["price"])
                offer = ShopOffer(
                    kind="weapon",
                    def_id=wid,
                    tier=tier,
                    price=shop_item_price(base_p, state.wave, state.stats),
                )
        if offer is None:
            for _attempt in range(6):
                ip = _pick_item_for_shop(state)
                if ip is None:
                    break
                iid, tier = ip
                if iid not in seen_items or _attempt == 5:
                    seen_items.add(iid)
                    base_p = state.db.items[iid].price
                    offer = ShopOffer(
                        kind="item",
                        def_id=iid,
                        tier=tier,
                        price=shop_item_price(base_p, state.wave, state.stats),
                    )
                    break

        if offer is not None:
            new_offers[slot_idx] = offer

    state.shop_offers = [o for o in new_offers if o is not None]
    return state.shop_offers


def reroll_shop(state: GameState) -> bool:
    cost = shop_reroll_cost(state)
    if state.materials < cost:
        return False
    state.materials -= cost
    if state.free_rerolls_left > 0:
        state.free_rerolls_left -= 1
    else:
        state.shop_rerolls_used += 1
    generate_shop(state, preserve_locked=True)
    state.events.append(("reroll", cost))
    return True


def can_buy_offer(state: GameState, offer: ShopOffer) -> tuple[bool, str]:
    if offer.purchased:
        return False, "Already purchased"
    if state.materials < offer.price:
        return False, "Not enough Materials"
    if offer.kind == "weapon":
        if not state.can_equip_weapon(offer.def_id):
            return False, "Character restriction"
        if len(state.weapons) < state.max_weapons:
            return True, ""
        # Check auto-combine with an identical weapon of same tier (< 4)
        if offer.tier < 4:
            for w in state.weapons:
                if w.def_id == offer.def_id and w.tier == offer.tier:
                    return True, "Auto-combines!"
        return False, f"Weapon slots full ({state.max_weapons}/{state.max_weapons})"
    else:
        idef = state.db.items[offer.def_id]
        if idef.max_count is not None and state.item_counts.get(offer.def_id, 0) >= idef.max_count:
            return False, "Max owned"
        return True, ""


def buy_shop_offer(state: GameState, index: int) -> bool:
    if not (0 <= index < len(state.shop_offers)):
        return False
    offer = state.shop_offers[index]
    ok, _ = can_buy_offer(state, offer)
    if not ok:
        return False

    state.materials -= offer.price
    offer.purchased = True
    offer.locked = False

    if offer.kind == "weapon":
        if len(state.weapons) < state.max_weapons:
            state.add_weapon(offer.def_id, offer.tier)
        else:
            # Auto-combine directly with matching weapon
            for w in state.weapons:
                if w.def_id == offer.def_id and w.tier == offer.tier and w.tier < 4:
                    w.tier += 1
                    state.rebuild_stats()
                    break
    else:
        state.add_item(offer.def_id)

    state.events.append(("buy", offer.def_id))
    return True


def toggle_lock_offer(state: GameState, index: int) -> bool:
    if not (0 <= index < len(state.shop_offers)):
        return False
    offer = state.shop_offers[index]
    if offer.purchased:
        return False
    offer.locked = not offer.locked
    return True


def weapon_recycle_value(state: GameState, index: int) -> int:
    if not (0 <= index < len(state.weapons)):
        return 0
    w = state.weapons[index]
    base_price = int(state.db.weapons[w.def_id].tiers[w.tier]["price"])
    return max(4, int(round(base_price * 0.45)))


def recycle_weapon(state: GameState, index: int) -> bool:
    if len(state.weapons) <= 1 or not (0 <= index < len(state.weapons)):
        return False
    val = weapon_recycle_value(state, index)
    state.weapons.pop(index)
    state.materials += val
    state._reposition_weapon_slots()
    state.rebuild_stats()
    state.events.append(("buy", "recycle"))
    return True


def roll_crate_item(state: GameState) -> str | None:
    if state.pending_crates <= 0:
        state.current_crate_item = None
        return None
    picked = _pick_item_for_shop(state)
    state.current_crate_item = picked[0] if picked else None
    return state.current_crate_item


def resolve_crate(state: GameState, take: bool) -> bool:
    if state.pending_crates <= 0:
        return False
    iid = state.current_crate_item
    state.pending_crates -= 1
    state.current_crate_item = None
    if iid:
        if take:
            state.add_item(iid)
            state.summary.crates_opened += 1
        else:
            # Recycle crate item for materials
            idef = state.db.items[iid]
            val = max(5, int(round(shop_item_price(idef.price, state.wave, state.stats) * 0.5)))
            state.materials += val
            state.summary.crates_opened += 1
    state.events.append(("crate", iid))
    if state.pending_crates > 0:
        roll_crate_item(state)
    return True
