"""Store-to-store redistribution of perishable stock on FreshRetailNet-50K.

Question: when one store in a city runs out of a product and another store in the
same city ends the day with that product unsold, how much lost demand could a
same-day transfer recover?

Pipeline
1. Hourly demand profile per store-product, learned only from in-stock hours.
2. Lost (censored) demand on a stockout day = profile over the stockout hours,
   scaled to that day's level using the hours the product was in stock.
3. Transfer plan per city, product and day: a linear program that sends
   end-of-day surplus from fully stocked stores to stores that run out after the
   transfer can arrive.

Sales in FreshRetailNet are normalised units, so every quantity here is in the
same normalised units. Daytime means 06:00-21:59, the window the dataset uses for
stock_hour6_22_cnt.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog

HOURS = list(range(6, 22))
SALE_COLS = [f"s{h}" for h in HOURS]
OUT_COLS = [f"o{h}" for h in HOURS]
KEY = ["store_id", "product_id"]
DATASET = "https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K/resolve/main/data/{split}.parquet"
BASE_COLS = ["city_id", "store_id", "management_group_id", "first_category_id", "product_id",
             "dt", "sale_amount", "discount", "activity_flag", "holiday_flag"]


@dataclass(frozen=True)
class Scenario:
    """Assumptions a user can change. None of these are in the dataset."""

    leftover_share: float = 0.10  # end-of-day unsold stock at fully stocked stores, as a share of their daytime sales
    arrival_hour: int = 14        # first hour a same-day transfer is on the receiving shelf
    handling_cost: float = 0.15   # cost of moving one unit, in units of full price


def load_split(split: str = "train", cache: Path | None = None) -> pd.DataFrame:
    """Download a split and flatten the daytime hourly arrays into columns."""
    import pyarrow.parquet as pq

    source = DATASET.format(split=split)
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        local = cache / f"{split}.parquet"
        if not local.exists():
            import urllib.request
            urllib.request.urlretrieve(source, local)
        source = str(local)
    table = pq.ParquetFile(source)
    parts = []
    for group in range(table.num_row_groups):
        chunk = table.read_row_group(group, columns=BASE_COLS + ["hours_sale", "hours_stock_status"])
        n = chunk.num_rows
        sales = chunk.column("hours_sale").combine_chunks().flatten().to_numpy().reshape(n, 24)
        stock = chunk.column("hours_stock_status").combine_chunks().flatten().to_numpy().reshape(n, 24)
        frame = chunk.drop(["hours_sale", "hours_stock_status"]).to_pandas()
        frame[SALE_COLS] = sales[:, HOURS].astype("float32")
        frame[OUT_COLS] = stock[:, HOURS].astype("int8")
        parts.append(frame)
    return pd.concat(parts, ignore_index=True)


def hourly_profiles(days: pd.DataFrame) -> pd.DataFrame:
    """Mean sales per daytime hour for each store-product, using in-stock hours only."""
    sales = days[SALE_COLS].to_numpy()
    instock = days[OUT_COLS].to_numpy() == 0
    num = pd.DataFrame(np.where(instock, sales, 0.0), columns=HOURS)
    den = pd.DataFrame(instock.astype(float), columns=HOURS)
    num[KEY] = days[KEY].to_numpy()
    den[KEY] = days[KEY].to_numpy()
    total = num.groupby(KEY).sum()
    count = den.groupby(KEY).sum()
    # Hours never observed in stock borrow the store-product's mean in-stock hourly rate.
    fallback = total.sum(axis=1) / count.sum(axis=1).replace(0, np.nan)
    profile = (total / count.replace(0, np.nan)).apply(lambda col: col.fillna(fallback)).fillna(0.0)
    profile.columns = [f"p{h}" for h in HOURS]
    return profile.astype("float32")


def estimate_lost(days: pd.DataFrame, profiles: pd.DataFrame, from_hour: int = 6) -> pd.Series:
    """Estimated demand in stockout hours at or after from_hour.

    The store-product profile is scaled by that day's sales in its in-stock hours,
    clipped to 0.25x-4x so a single quiet or busy hour cannot dominate.
    """
    prof = profiles.reindex(pd.MultiIndex.from_frame(days[KEY])).to_numpy()
    prof = np.nan_to_num(prof)
    sales = days[SALE_COLS].to_numpy()
    out = days[OUT_COLS].to_numpy() == 1
    seen = (~out).astype(float)
    expected_seen = (prof * seen).sum(axis=1)
    scale = np.where(expected_seen > 0, (sales * seen).sum(axis=1) / np.where(expected_seen > 0, expected_seen, 1), 1.0)
    scale = np.clip(scale, 0.25, 4.0)
    window = np.array(HOURS) >= from_hour
    lost = (prof * out * window).sum(axis=1) * scale
    return pd.Series(lost, index=days.index)


def plan_transfers(surplus: np.ndarray, need: np.ndarray, value: np.ndarray, handling_cost: float) -> np.ndarray:
    """Linear program for one city, product and day.

    x[i, j] = units sent from store i to store j.
    maximise   sum_ij (value_j - handling_cost) * x_ij
    subject to sum_j x_ij <= surplus_i,  sum_i x_ij <= need_j,  x >= 0
    """
    s, r = len(surplus), len(need)
    if s == 0 or r == 0:
        return np.zeros((s, r))
    gain = np.tile(np.asarray(value, float) - handling_cost, s)
    a_send = np.kron(np.eye(s), np.ones(r))
    a_recv = np.kron(np.ones(s), np.eye(r))
    result = linprog(-gain, A_ub=np.vstack([a_send, a_recv]), b_ub=np.concatenate([surplus, need]),
                     bounds=(0, None), method="highs")
    return result.x.reshape(s, r)


def pooled_plan(surplus_total: float, need: np.ndarray, value: np.ndarray, handling_cost: float) -> np.ndarray:
    """Closed-form optimum of plan_transfers when every lane costs the same.

    The LP then only decides which receivers to fill, so it fills the highest
    value receivers first. tests/test_redistribution.py checks this against linprog.
    """
    order = np.argsort(-np.asarray(value))
    received = np.zeros(len(need))
    left = surplus_total
    for j in order:
        if value[j] <= handling_cost or left <= 0:
            break
        received[j] = min(need[j], left)
        left -= received[j]
    return received


def replay(days: pd.DataFrame, profiles: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    """Run the transfer plan on every city, product and day. Returns one row per receiving store-day."""
    out = days[OUT_COLS].to_numpy() == 1
    daytime_sales = days[SALE_COLS].to_numpy().sum(axis=1)
    frame = days[["city_id", "product_id", "dt", "store_id", "first_category_id", "discount"]].copy()
    frame["lost_all"] = estimate_lost(days, profiles, 6).to_numpy()
    frame["need"] = estimate_lost(days, profiles, scenario.arrival_hour).to_numpy()
    frame["surplus"] = np.where(out.any(axis=1), 0.0, scenario.leftover_share * daytime_sales)

    group = ["city_id", "product_id", "dt"]
    frame["pool"] = frame.groupby(group)["surplus"].transform("sum")
    receivers = frame[(frame["need"] > 0) & (frame["pool"] > 0) & (frame["discount"] > scenario.handling_cost)].copy()
    # Fill highest-price receivers first within each pool (same optimum as the LP).
    receivers = receivers.sort_values(group + ["discount"], ascending=[True, True, True, False])
    before = receivers.groupby(group)["need"].cumsum() - receivers["need"]
    receivers["received"] = np.clip(receivers["pool"] - before, 0, receivers["need"])
    frame["received"] = 0.0
    frame.loc[receivers.index, "received"] = receivers["received"]
    return frame


def summarise(frame: pd.DataFrame) -> dict:
    lost = frame["lost_all"].sum()
    received = frame["received"].sum()
    sent_pairs = frame[frame["received"] > 0].groupby(["city_id", "product_id", "dt"]).ngroups
    return {
        "lost_demand": round(float(lost), 1),
        "recoverable_after_arrival": round(float(frame["need"].sum()), 1),
        "surplus_available": round(float(frame["surplus"].sum()), 1),
        "recovered": round(float(received), 1),
        "recovered_share_of_lost": round(float(received / lost), 4) if lost else 0.0,
        "transfer_days": int(sent_pairs),
        "receiving_store_days": int((frame["received"] > 0).sum()),
    }
