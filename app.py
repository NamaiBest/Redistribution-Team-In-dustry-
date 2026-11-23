"""Streamlit view of the FreshRetailNet redistribution results.

    python -m streamlit run app.py

Reads the tables in data/ (rebuild them with run_analysis.py).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import redistribution as R

DATA = Path(__file__).parent / "data"
st.set_page_config(page_title="Store Relay · FreshRetailNet", layout="wide")

sens = pd.read_csv(DATA / "sensitivity_city.csv", dtype={"city_id": str})
validation = pd.read_csv(DATA / "validation.csv")
cities = pd.read_csv(DATA / "by_city.csv")
cases = json.loads((DATA / "examples.json").read_text())

st.title("Store Relay")
st.caption("Same-day transfers of perishable stock between stores in one city · FreshRetailNet-50K, 28 Mar – 25 Jun 2024")

with st.sidebar:
    st.header("Scenario")
    city = st.selectbox("City", ["all"] + sorted({c for c in sens.city_id if c != "all"}, key=int))
    share = st.select_slider("Unsold stock at fully stocked stores (% of their sales)", [0.05, 0.10, 0.20, 0.30], 0.10,
                             format_func=lambda v: f"{v:.0%}")
    hour = st.select_slider("Transfer on the shelf by", [10, 12, 14, 16, 18], 14, format_func=lambda h: f"{h}:00")
    st.caption("Both are assumptions: the dataset records sales and stockout hours, not stock on hand.")

row = sens[(sens.city_id == city) & (sens.leftover_share == share) & (sens.arrival_hour == hour)].iloc[0]
a, b, c, d = st.columns(4)
a.metric("Lost demand (stockout hours)", f"{row.lost:,.0f}")
b.metric("Still sellable after arrival", f"{row.need:,.0f}")
c.metric("Unsold stock elsewhere", f"{row.surplus:,.0f}")
d.metric("Recovered by transfers", f"{row.recovered:,.0f}", f"{row.recovered / row.lost:.1%} of lost demand")
st.caption("Normalised sales units, summed over the 90 training days.")

st.subheader("What limits recovery")
grid = sens[sens.city_id == city].assign(pct=lambda f: 100 * f.recovered / f.lost)
st.dataframe(grid.pivot(index="leftover_share", columns="arrival_hour", values="pct").round(1)
             .rename(index=lambda v: f"{v:.0%} unsold", columns=lambda h: f"by {h}:00"), width="stretch")
st.write("Recovery rises almost in step with unsold stock and falls with later arrival. "
         "Unsold stock is the binding constraint, so measuring it is the first thing a pilot should do.")

st.subheader("Cities")
st.dataframe(cities.rename(columns={"city_id": "City", "stores": "Stores", "lost": "Lost demand", "surplus": "Unsold stock",
                                   "received": "Recovered", "recovered_pct": "Recovered %"}),
             hide_index=True, width="stretch")
st.caption("At 10% unsold stock and 14:00 arrival. Cities with more stores per product recover more: a sender is more likely to exist.")

st.subheader("Is the lost-demand estimate any good?")
st.write("On fully stocked days in the held-out week, we hid the later hours and predicted their sales from profiles learned on the training period.")
st.dataframe(validation.pivot(index="method", columns="censored_from", values="bias_pct"), width="stretch")
st.caption("Aggregate bias, % of true hidden sales. Negative means lost demand is understated.")

st.subheader("One day, solved as a linear program")
labels = [f"City {e['city_id']} · product {e['product_id']} · {e['dt']}" for e in cases["examples"]]
case = cases["examples"][st.selectbox("Case", range(len(labels)), format_func=labels.__getitem__)]
cost = st.slider("Handling cost per unit (share of full price)", 0.0, 0.8, 0.15, 0.05)
days = pd.DataFrame([{"store_id": s["store_id"], "product_id": case["product_id"], "discount": s["discount"],
                      **{f"s{h}": v for h, v in zip(R.HOURS, s["sales"])}, **{f"o{h}": v for h, v in zip(R.HOURS, s["out"])}}
                     for s in case["stores"]])
profiles = pd.DataFrame([cases["profiles"][f"{s['store_id']}-{case['product_id']}"] for s in case["stores"]],
                        index=pd.MultiIndex.from_frame(days[R.KEY]), columns=[f"p{h}" for h in R.HOURS])
out = days[R.OUT_COLS].to_numpy() == 1
days["unsold"] = np.where(out.any(axis=1), 0.0, share * days[R.SALE_COLS].sum(axis=1))
days["need"] = R.estimate_lost(days, profiles, hour)
senders, receivers = days[days.unsold > 0], days[days.need > 0]
plan = R.plan_transfers(senders.unsold.to_numpy(), receivers.need.to_numpy(), receivers.discount.to_numpy(), cost)
lanes = [{"From store": senders.store_id.iloc[i], "To store": receivers.store_id.iloc[j], "Units": round(plan[i, j], 2)}
         for i in range(len(senders)) for j in range(len(receivers)) if plan[i, j] > 1e-6]
left, right = st.columns(2)
left.dataframe(days[["store_id", "discount", "unsold", "need"]].round(2), hide_index=True, width="stretch")
right.dataframe(pd.DataFrame(lanes), hide_index=True, width="stretch")
st.caption("unsold = stock a fully stocked store would bin at closing. need = estimated demand in its stockout hours after the transfer arrives.")
