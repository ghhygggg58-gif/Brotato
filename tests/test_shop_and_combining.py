"""Tests for shop generation, locking, rerolls, combining, recycling, and crates."""

from __future__ import annotations

from brotato.data_loader import load_database
from brotato.engine.game_state import GameState
from brotato.engine.shop import (
    buy_shop_offer,
    generate_shop,
    recycle_weapon,
    reroll_shop,
    resolve_crate,
    roll_crate_item,
    roll_offer_tier,
    shop_reroll_cost,
    toggle_lock_offer,
)


def test_tier_probabilities_respect_wave_unlocks() -> None:
    db = load_database()
    st = GameState(db, "well_rounded", "pistol", seed=123)
    for _ in range(50):
        assert roll_offer_tier(1, 200.0, st.rng) == 1
        assert roll_offer_tier(3, 200.0, st.rng) <= 2
        assert roll_offer_tier(6, 200.0, st.rng) <= 3


def test_shop_lock_reroll_and_item_caps() -> None:
    db = load_database()
    st = GameState(db, "well_rounded", "pistol", seed=77)
    st.wave = 3
    st.materials = 500
    st.bonus_stats.add("free_rerolls", 1)
    st.free_rerolls_left = 1
    st.rebuild_stats()

    offers = generate_shop(st)
    assert len(offers) == 4
    # Early wave guarantees at least 1 weapon
    assert any(o.kind == "weapon" for o in offers)

    # Lock slot 0 and reroll (free reroll consumed first)
    locked_id = offers[0].def_id
    locked_kind = offers[0].kind
    assert toggle_lock_offer(st, 0) is True
    assert shop_reroll_cost(st) == 0
    assert reroll_shop(st) is True
    assert st.free_rerolls_left == 0
    assert st.shop_offers[0].def_id == locked_id
    assert st.shop_offers[0].kind == locked_kind
    assert st.shop_offers[0].locked is True

    # Paid reroll deducts materials and raises subsequent reroll cost
    c1 = shop_reroll_cost(st)
    assert c1 > 0
    assert reroll_shop(st) is True
    c2 = shop_reroll_cost(st)
    assert c2 > c1

    # Unique item max_count=1 enforcement
    assert st.add_item("bandana") is True
    assert st.add_item("bandana") is False


def test_weapon_combining_auto_combine_and_recycle() -> None:
    db = load_database()
    st = GameState(db, "well_rounded", "pistol", seed=99)
    st.materials = 500

    # Manual combine T1 + T1 -> T2
    st.add_weapon("pistol", tier=1)
    assert st.can_combine_at(0) == 1
    assert st.combine_weapons(0, 1) is True
    assert len(st.weapons) == 1
    assert st.weapons[0].tier == 2

    # Cannot recycle last weapon
    assert recycle_weapon(st, 0) is False

    # Fill remaining 5 slots with sticks, then test auto-combine on full shop buy
    for _ in range(5):
        st.add_weapon("stick", tier=1)
    assert len(st.weapons) == 6

    from brotato.models import ShopOffer
    st.shop_offers = [ShopOffer(kind="weapon", def_id="stick", tier=1, price=10)]
    assert buy_shop_offer(st, 0) is True
    assert len(st.weapons) == 6
    assert any(w.def_id == "stick" and w.tier == 2 for w in st.weapons)

    # Recycling works when > 1 weapon
    mat_before = st.materials
    assert recycle_weapon(st, 1) is True
    assert len(st.weapons) == 5
    assert st.materials > mat_before


def test_crate_opening_take_and_recycle() -> None:
    db = load_database()
    st = GameState(db, "well_rounded", "pistol", seed=5)
    st.pending_crates = 2
    iid1 = roll_crate_item(st)
    assert iid1 is not None
    assert resolve_crate(st, take=True) is True
    assert iid1 in st.items
    assert st.pending_crates == 1
    assert st.current_crate_item is not None

    mat_before = st.materials
    assert resolve_crate(st, take=False) is True
    assert st.materials > mat_before
    assert st.pending_crates == 0
