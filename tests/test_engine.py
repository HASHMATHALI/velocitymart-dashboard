import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine


@pytest.fixture(scope="module")
def wh():
    return engine.load()


def tiny():
    slots = pd.DataFrame({
        "slot_id": ["A01-A-01", "A01-F-01", "C01-B-01", "C01-B-02"],
        "zone": ["A", "A", "C", "C"], "aisle_id": ["A01", "A01", "C01", "C01"],
        "shelf_level": ["A", "F", "B", "B"], "temp_zone": ["Ambient", "Ambient", "Refrigerated", "Refrigerated"],
        "max_weight_kg": [150, 25, 150, 150], "aisle_width_m": [2.0, 2.0, 2.0, 2.0],
    })
    skus = pd.DataFrame({
        "sku_id": ["S1", "S2"], "category": ["Dairy", "Snacks"], "weight_kg": [5.0, 40.0],
        "temp_req": ["Refrigerated", "Ambient"], "is_fragile": [False, False], "current_slot": ["A01-A-01", "A01-F-01"],
    })
    orders = pd.DataFrame({
        "sku_id": ["S1"] * 14 + ["S2"] * 7, "picker_id": "P1", "travel_distance_m": 10.0,
        "order_timestamp": pd.date_range("2024-01-01", periods=21, freq="8h"),
    })
    return engine.build(skus, orders, slots)


def test_flags_on_known_cases():
    w = tiny().skus.set_index("sku_id")
    assert w.loc["S1", "temp"] and not w.loc["S1", "overweight"]
    assert w.loc["S2", "overweight"] and w.loc["S2", "heavy_high"] and not w.loc["S2", "temp"]


def test_plan_fixes_what_it_can_and_never_breaks_rules():
    w = tiny()
    plan = engine.plan_moves(w)
    # S1 has a valid refrigerated slot. S2's only free ambient slot is S1's old one, which
    # is still occupied when the plan is drawn up, so it must not be offered.
    assert plan.set_index("sku_id").loc["S1", "to_slot"].startswith("C01")
    assert "S2" not in set(plan.sku_id)
    after = engine.apply_moves(w, plan).skus.set_index("sku_id")
    assert after.loc["S1", "issue_count"] == 0


def test_real_data_counts(wh):
    s = engine.issue_summary(wh).set_index("key").skus
    assert s["temp"] == 490 and s["overweight"] == 6
    # 800 SKUs occupy 740 distinct slots, so 60 SKUs have no slot of their own.
    assert len(wh.skus) - wh.skus.current_slot.nunique() == 60
    assert int(wh.skus.double_booked.sum()) == 73


def test_real_plan_targets_are_unique_empty_and_compliant(wh):
    plan = engine.plan_moves(wh)
    assert plan.to_slot.is_unique
    assert not set(plan.to_slot) & set(wh.skus.current_slot)
    moved = engine.apply_moves(wh, plan).skus
    assert (moved[moved.sku_id.isin(plan.sku_id)].issue_count == 0).all()
    assert engine.compliance_rate(moved) > engine.compliance_rate(wh.skus)


def test_budget_spends_moves_on_highest_exposure_first(wh):
    plan = engine.plan_moves(wh, budget=10)
    assert len(plan) == 10
    assert plan.exposure_removed.is_monotonic_decreasing


def test_picker_outlier_is_found(wh):
    flagged = engine.picker_anomalies(wh).query("flag").picker_id.tolist()
    assert flagged == ["PICKER-07"]
