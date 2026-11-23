# Store Relay: same-day transfers between stores on FreshRetailNet-50K

**Research question.** When a store runs out of a fresh product and another store in the same city ends the day with that product unsold, how much of the lost demand could a same-day transfer recover?

Everything in this repository uses one dataset: [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K) (Dingdong fresh retail; 18 cities, 898 stores, 865 products, hourly sales and hourly stockout flags; 90 training days, 28 Mar – 25 Jun 2024, and a 7-day evaluation week, 26 Jun – 2 Jul 2024).

- `artifacts/`: the team notebook with EDA and research questions RQ1–RQ4.
- `redistribution.py`, `run_analysis.py`, `app.py`, `web/`: the redistribution model built on RQ1's finding that stockouts hide demand.

[Open Store Relay](https://namaibest.github.io/Redistribution-Team-In-dustry-/). No installation needed.

## Results

| | Value |
| --- | --- |
| Lost demand in stockout hours, 90 days, all cities | 1,300,872 units |
| Still sellable after a transfer lands at 14:00 | 912,106 units |
| Unsold stock at stores that never ran out (10% scenario) | 231,805 units |
| **Recovered by transfers** | **148,122 units, 11.4% of lost demand** |

Units are FreshRetailNet's normalised sales. Total observed sales over the same days are 4,493,661 units, so stockouts hide demand equal to about 29% of what was sold.

1. **Stock left over elsewhere is the binding constraint.** At every setting, unsold stock is smaller than the demand still sellable. Recovery rises from 6.5% to 23.6% as unsold stock goes from 5% to 30% of sales (14:00 arrival).
2. **Speed matters less than stock.** At 10% unsold stock, moving arrival from 18:00 to 10:00 lifts recovery from 9.1% to 12.0%.
3. **Dense cities gain most.** City 0 (290 stores) recovers 13.8%. Cities with fewer than 10 stores recover 3.7–6.4%, because there is often no fully stocked store for the same product that day.

### The lost-demand estimate, tested

The report's RQ4 used `D = S / (1 − 0.5·f)`. We tested it against an hourly-profile estimate on days we can check: fully stocked days in the held-out week, with later hours hidden on purpose.

| Hidden from | 50% rule | Flat in-stock rate | Hourly profile (ours) |
| --- | --- | --- | --- |
| 10:00 | −77.9% | +10.7% | +2.6% |
| 14:00 | −60.5% | +18.5% | +0.3% |
| 18:00 | −22.7% | +80.3% | −2.6% |

Values are the bias in total hidden sales. The profile is learned only from the training period, so the test is chronological. Per-day errors are still large (mean absolute error 54–70% of a day's hidden sales), because single store-product-days are noisy. The estimate is reliable in aggregate and should not be used to plan one shelf.

## How the model works

1. **Hourly demand profile.** For each store-product, average sales in every daytime hour (06:00–21:59), using only hours when the product was in stock.
2. **Lost demand.** On a stockout day, apply the profile to the empty hours, scaled by that day's sales in its stocked hours (scale clipped to 0.25–4×).
3. **Transfer plan.** For each city, product and day, a linear program:
   - decision: `x[i,j]`, units sent from store *i* to store *j* in the same city
   - maximise `Σ (price_j − handling cost) · x[i,j]`, where `price_j` is the receiver's `discount` multiplier
   - subject to: sent ≤ unsold stock at *i*, received ≤ demand at *j* in stockout hours after the transfer arrives
   - only stores that never ran out that day can send

   With equal costs on every lane, the LP fills the highest-price receivers first. The replay uses that closed form for speed, and `test_redistribution.py` checks it against `scipy.optimize.linprog` on 200 random cases.
4. **Baseline.** No transfers: fulfilled demand equals observed sales.

### Assumptions, stated

- **Unsold stock** at fully stocked stores (default 10% of their daytime sales). The dataset has no stock on hand.
- **Arrival hour** of a transfer (default 14:00).
- **Handling cost** per unit (default 15% of full price).
- Any two stores in a city are reachable at the same cost. The dataset has no locations.
- The replay knows in hindsight which stores run out, so results are an upper bound for each scenario.

## What to say in the viva

- **Why it matters.** RQ1 shows stockouts climb to 42% of products by 22:00. Lost sales and waste happen in the same city on the same day.
- **What the model adds.** It turns RQ1's censoring finding into a decision: which store sends how much to which store.
- **What it can't claim.** Unsold stock and travel are assumptions. A pilot would log end-of-day leftovers at each store for two weeks in one dense city (City 0), then run transfers on alternate days and compare fill rates.

## Run it

```sh
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest -v            # model tests
python run_analysis.py           # rebuilds data/ (downloads ~115 MB, needs ~4 GB RAM)
python -m streamlit run app.py   # local dashboard
```

Website:

```sh
cd web && npm ci && npm test && npm run dev
```

The site uses [javascript-lp-solver](https://github.com/JWally/jsLPSolver) to solve each day's plan in the browser. The produce photo is illustrative.
