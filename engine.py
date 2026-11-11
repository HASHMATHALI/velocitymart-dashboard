"""SlotSense engine: pure-pandas warehouse analysis with no UI dependencies.

Everything the dashboard shows is computed here so it can be unit-tested.

Conventions taken from the data:
* slot ids look like ``A01-C-07``  ->  aisle ``A01``, shelf level ``C``, position 07
* shelf level A is the floor, F is the top shelf
* each slot holds exactly one SKU
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent
SHELF_LEVELS = list("ABCDEF")
TOP_SHELVES = {"E", "F"}        # above shoulder height
REACH_SHELVES = {"B", "C", "D"}  # waist-to-shoulder "golden zone"
HEAVY_KG = 20.0                 # manual-handling threshold for top shelves

ISSUES = {
    "temp": "Wrong temperature zone",
    "overweight": "Over shelf weight limit",
    "double_booked": "Slot shared with another SKU",
    "fragile_high": "Fragile item on a top shelf",
    "heavy_high": "Heavy item on a top shelf",
}
# How bad one pick from a non-compliant slot is. Product safety and structural
# limits outrank ergonomics; a shared slot is mostly a data-integrity problem.
ISSUE_WEIGHT = {"temp": 5.0, "overweight": 4.0, "fragile_high": 2.0, "heavy_high": 2.0, "double_booked": 1.0}


@dataclass
class Warehouse:
    skus: pd.DataFrame       # one row per SKU with slot attributes, velocity and issue flags
    slots: pd.DataFrame      # one row per slot
    orders: pd.DataFrame     # one row per pick
    weeks: float             # length of the order history in weeks


def load(base_dir: Path = BASE_DIR) -> Warehouse:
    skus = pd.read_csv(base_dir / "sku_master_converted.xlsx.csv")
    orders = pd.read_csv(base_dir / "order_transactions_converted.xlsx.csv", parse_dates=["order_timestamp"])
    slots = pd.read_csv(base_dir / "warehouse_constraints_converted.xlsx.csv")
    return build(skus, orders, slots)


def build(skus: pd.DataFrame, orders: pd.DataFrame, slots: pd.DataFrame) -> Warehouse:
    """Join the three sources and flag every rule a SKU's current slot breaks."""
    span = orders["order_timestamp"].max() - orders["order_timestamp"].min()
    weeks = max(span.total_seconds() / (7 * 24 * 3600), 1e-9)

    df = skus.merge(slots, left_on="current_slot", right_on="slot_id", how="left")
    picks = orders.groupby("sku_id").size()
    df["picks"] = df["sku_id"].map(picks).fillna(0).astype(int)
    df["picks_per_week"] = df["picks"] / weeks

    occupants = df.groupby("current_slot")["sku_id"].transform("size")
    df["temp"] = df["temp_req"] != df["temp_zone"]
    df["overweight"] = df["weight_kg"] > df["max_weight_kg"]
    df["double_booked"] = occupants > 1
    df["fragile_high"] = df["is_fragile"] & df["shelf_level"].isin(TOP_SHELVES)
    df["heavy_high"] = (df["weight_kg"] >= HEAVY_KG) & df["shelf_level"].isin(TOP_SHELVES)

    issue_cols = list(ISSUES)
    df["issue_count"] = df[issue_cols].sum(axis=1)
    df["severity"] = sum(df[c] * ISSUE_WEIGHT[c] for c in issue_cols)
    # Exposure: how often per week somebody handles this SKU while it is in a bad slot.
    df["exposure"] = df["severity"] * df["picks_per_week"]
    df["issues"] = df[issue_cols].apply(lambda r: [ISSUES[c] for c in issue_cols if r[c]], axis=1)
    return Warehouse(skus=df, slots=slots, orders=orders, weeks=weeks)


def issue_summary(wh: Warehouse) -> pd.DataFrame:
    rows = [
        {
            "issue": ISSUES[c],
            "key": c,
            "skus": int(wh.skus[c].sum()),
            "picks_per_week": float(wh.skus.loc[wh.skus[c], "picks_per_week"].sum()),
        }
        for c in ISSUES
    ]
    return pd.DataFrame(rows)


def compliance_rate(skus: pd.DataFrame) -> float:
    return float((skus["issue_count"] == 0).mean()) if len(skus) else 1.0


# --------------------------------------------------------------------------- moves
def _slot_is_valid(sku: pd.Series, slots: pd.DataFrame) -> pd.Series:
    """Boolean mask over ``slots``: which of them satisfy every rule for ``sku``."""
    ok = (slots["temp_zone"] == sku["temp_req"]) & (slots["max_weight_kg"] >= sku["weight_kg"])
    if sku["is_fragile"] or sku["weight_kg"] >= HEAVY_KG:
        ok &= ~slots["shelf_level"].isin(TOP_SHELVES)
    return ok


def plan_moves(wh: Warehouse, budget: int | None = None) -> pd.DataFrame:
    """Greedy re-slotting plan, worst exposure first.

    Every move puts one SKU into an empty slot that satisfies all rules. Among
    valid slots it prefers the reachable shelf levels (B-D), then wide aisles,
    then the aisle that is currently emptiest so load spreads out. When SKUs
    share a slot, the one with the highest velocity keeps it and the others move.
    """
    skus = wh.skus
    free = wh.slots[~wh.slots["slot_id"].isin(skus["current_slot"])].copy()
    aisle_load = skus.groupby("aisle_id").size()
    free["aisle_load"] = free["aisle_id"].map(aisle_load).fillna(0)
    free["rank"] = (
        (~free["shelf_level"].isin(REACH_SHELVES)).astype(int) * 1000
        + (free["aisle_width_m"] < 2.0).astype(int) * 100
        + free["aisle_load"]
    )
    free = free.sort_values(["rank", "slot_id"])
    taken: set[str] = set()

    candidates = skus[skus["issue_count"] > 0].sort_values(["exposure", "sku_id"], ascending=[False, True])
    # A shared slot only needs all-but-one occupant to leave.
    keepers = set(
        skus[skus["double_booked"]].sort_values("picks", ascending=False).groupby("current_slot")["sku_id"].first()
    )

    moves = []
    for _, sku in candidates.iterrows():
        only_shared = sku["issue_count"] == 1 and sku["double_booked"]
        if only_shared and sku["sku_id"] in keepers:
            continue
        valid = free[_slot_is_valid(sku, free) & ~free["slot_id"].isin(taken)]
        if valid.empty:
            continue
        target = valid.iloc[0]
        taken.add(target["slot_id"])
        moves.append(
            {
                "sku_id": sku["sku_id"],
                "category": sku["category"],
                "weight_kg": sku["weight_kg"],
                "from_slot": sku["current_slot"],
                "to_slot": target["slot_id"],
                "to_zone": target["temp_zone"],
                "fixes": ", ".join(sku["issues"]),
                "exposure_removed": round(float(sku["exposure"]), 1),
                "picks_per_week": round(float(sku["picks_per_week"]), 1),
            }
        )
        if budget is not None and len(moves) >= budget:
            break
    return pd.DataFrame(moves)


def apply_moves(wh: Warehouse, moves: pd.DataFrame) -> Warehouse:
    """Return the warehouse as it would look after ``moves`` (what-if)."""
    if moves.empty:
        return wh
    new_slot = dict(zip(moves["sku_id"], moves["to_slot"]))
    base_cols = ["sku_id", "category", "weight_kg", "temp_req", "is_fragile", "current_slot"]
    skus = wh.skus[base_cols].copy()
    skus["current_slot"] = skus["sku_id"].map(new_slot).fillna(skus["current_slot"])
    return build(skus, wh.orders, wh.slots)


# ------------------------------------------------------------------- floor and flow
def floor_grid(wh: Warehouse, metric: str = "exposure") -> pd.DataFrame:
    """Aisle x shelf-level matrix for the floor map."""
    agg = {"exposure": "sum", "issue_count": "sum", "picks_per_week": "sum", "sku_id": "count"}[metric]
    grid = wh.skus.pivot_table(index="shelf_level", columns="aisle_id", values=metric, aggfunc=agg, fill_value=0)
    return grid.reindex(index=SHELF_LEVELS[::-1], fill_value=0)


def shift_pressure(wh: Warehouse) -> pd.DataFrame:
    """Average picks per hour for each weekday x hour cell."""
    ts = wh.orders["order_timestamp"]
    days = ts.dt.normalize().nunique() / 7  # occurrences of each weekday
    counts = wh.orders.groupby([ts.dt.dayofweek, ts.dt.hour]).size().unstack(fill_value=0)
    counts.index = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i] for i in counts.index]
    return (counts / max(days, 1)).round(1)


def narrow_aisle_pressure(wh: Warehouse) -> pd.DataFrame:
    """Peak-hour picks landing in aisles too narrow for two pickers to pass."""
    orders = wh.orders.merge(wh.skus[["sku_id", "aisle_id", "aisle_width_m"]], on="sku_id")
    hour_volume = orders.groupby(orders["order_timestamp"].dt.hour).size()
    peak_hours = hour_volume[hour_volume >= hour_volume.quantile(0.75)].index
    peak = orders[orders["order_timestamp"].dt.hour.isin(peak_hours) & (orders["aisle_width_m"] < 2.0)]
    peak_slots = peak["order_timestamp"].dt.floor("h").nunique()
    out = peak.groupby("aisle_id").size().rename("peak_picks").reset_index()
    out["picks_per_peak_hour"] = (out["peak_picks"] / max(peak_slots, 1)).round(2)
    return out.sort_values("peak_picks", ascending=False).reset_index(drop=True)


def picker_anomalies(wh: Warehouse, threshold: float = 3.5) -> pd.DataFrame:
    """Flag pickers whose logged travel per pick is far from their peers.

    Uses the modified z-score (median / MAD), which is not distorted by the
    outlier it is trying to find. |z| > 3.5 is the usual cut-off.
    """
    stats = wh.orders.groupby("picker_id").agg(
        picks=("sku_id", "size"), avg_travel_m=("travel_distance_m", "mean")
    )
    median = stats["avg_travel_m"].median()
    mad = (stats["avg_travel_m"] - median).abs().median()
    stats["z"] = 0.6745 * (stats["avg_travel_m"] - median) / (mad if mad > 0 else np.nan)
    stats["z"] = stats["z"].fillna(0.0)
    stats["flag"] = stats["z"].abs() > threshold
    return stats.round({"avg_travel_m": 2, "z": 1}).reset_index().sort_values("z")
