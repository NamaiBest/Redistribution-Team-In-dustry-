"""Rebuild every table in data/ from FreshRetailNet-50K.

    python run_analysis.py            # downloads ~115 MB into .cache/ on first run

Needs about 4 GB of free memory.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import redistribution as R

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CACHE = ROOT / ".cache"
LEFTOVER = [0.05, 0.10, 0.20, 0.30]
ARRIVAL = [10, 12, 14, 16, 18]


def validate(evaluation: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    """Hide the later hours of fully stocked evaluation days and predict their sales.

    Profiles come from the training period (28 Mar - 25 Jun 2024) and are tested on
    the held-out week (26 Jun - 2 Jul 2024), so the check is chronological.
    """
    full = evaluation[(evaluation[R.OUT_COLS].to_numpy() == 0).all(axis=1)]
    rows = []
    for start in [10, 12, 14, 16, 18]:
        days = full.copy()
        hidden = np.array(R.HOURS) >= start
        sales = days[R.SALE_COLS].to_numpy()
        truth, seen = sales[:, hidden].sum(axis=1), sales[:, ~hidden].sum(axis=1)
        for hour in np.array(R.HOURS)[hidden]:
            days[f"o{hour}"] = 1
        methods = {
            "report 50% rule": seen / (1 - 0.5 * hidden.sum() / len(R.HOURS)) - seen,
            "flat in-stock rate": seen / (~hidden).sum() * hidden.sum(),
            "hourly profile (ours)": R.estimate_lost(days, profiles, 6).to_numpy(),
        }
        for name, guess in methods.items():
            rows.append({
                "censored_from": f"{start}:00",
                "method": name,
                "bias_pct": round(100 * (guess.sum() - truth.sum()) / truth.sum(), 1),
                "mae_pct": round(100 * np.abs(guess - truth).mean() / truth.mean(), 1),
            })
    return pd.DataFrame(rows)


def sensitivity(train: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for share in LEFTOVER:
        for hour in ARRIVAL:
            frame = R.replay(train, profiles, R.Scenario(leftover_share=share, arrival_hour=hour))
            cols = ["lost_all", "need", "surplus", "received"]
            grouped = frame.groupby("city_id")[cols].sum()
            grouped.loc["all"] = frame[cols].sum()
            for city, r in grouped.iterrows():
                rows.append({"city_id": city, "leftover_share": share, "arrival_hour": hour,
                             "lost": round(r.lost_all, 1), "need": round(r.need, 1),
                             "surplus": round(r.surplus, 1), "recovered": round(r.received, 1)})
    return pd.DataFrame(rows)


def main() -> None:
    train = R.load_split("train", CACHE)
    evaluation = R.load_split("eval", CACHE)
    profiles = R.hourly_profiles(train)

    validate(evaluation, profiles).to_csv(DATA / "validation.csv", index=False)
    sensitivity(train, profiles).to_csv(DATA / "sensitivity_city.csv", index=False)

    base = R.replay(train, profiles, R.Scenario())
    print(json.dumps(R.summarise(base), indent=2))
    city = base.groupby("city_id")[["lost_all", "surplus", "received"]].sum().rename(columns={"lost_all": "lost"})
    city["stores"] = base.groupby("city_id")["store_id"].nunique()
    city["recovered_pct"] = 100 * city["received"] / city["lost"]
    city.reset_index()[["city_id", "stores", "lost", "surplus", "received", "recovered_pct"]].round(1).to_csv(DATA / "by_city.csv", index=False)
    cat = base.groupby("first_category_id")[["lost_all", "received"]].sum().rename(columns={"lost_all": "lost"})
    cat["recovered_pct"] = 100 * cat["received"] / cat["lost"]
    cat.reset_index().round(1).to_csv(DATA / "by_category.csv", index=False)


if __name__ == "__main__":
    main()
