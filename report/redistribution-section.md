# Report section: store-to-store redistribution (final solution)

*Drop-in text for the report. It can replace the LP part of RQ4 or sit after it as the final solution. Numbers come from `run_analysis.py`.*

**Redistribution model.** RQ1 showed that stockouts hide demand. We asked how much of it a same-day transfer between stores in the same city could recover. For each store-product we learned an hourly demand profile from in-stock hours only, and estimated lost demand on stockout days by applying that profile to the empty hours. On fully stocked days in the held-out week, with later hours deliberately hidden, this estimate was within ±3% of true total sales. The 50% correction used earlier understated hidden sales by 23–78%. For each city, product and day, a linear program then sends unsold stock from stores that never ran out to stores that run out after the transfer can arrive, filling higher-price stores first and skipping moves whose handling cost exceeds the sale.

**Results.** Over 90 days, stockouts hid an estimated 1.30 million units of demand, about 29% of observed sales. With unsold stock at fully stocked stores set to 10% of their sales and transfers on the shelf by 14:00, the model recovers 148,122 units, or 11.4% of lost demand. Recovery is limited by stock, not speed: it rises to 23.6% at 30% unsold stock, while moving arrival from 18:00 to 10:00 only lifts it from 9.1% to 12.0%. Dense cities gain most (City 0, 290 stores: 13.8%).

**Managerial implications.** Start in the densest city, where a sender for the same product exists most often. The dataset records stockouts but not leftovers, so a pilot should first log end-of-day unsold stock per store for two weeks; that one figure sets the value of the programme. The results are an upper bound for each scenario because the replay knows in hindsight which stores run out. A live system would need same-day stockout forecasts, which the hourly profiles provide.

**Limitations.** Sales are normalised units, not currency or weight. Store locations and transfer costs are not in the data, so every pair of stores in a city is treated as equally reachable.
