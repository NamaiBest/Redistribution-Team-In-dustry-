# Interstate redistribution of perishable produce

**Research question.** Under what shelf-life, lane-capacity, and transport-cost conditions can interstate transfers of perishable produce reduce modeled spoilage and unfilled receiving targets compared with keeping stock local?

The demo covers **tomato, banana, brinjal, cabbage, and cauliflower** across seven representative state hubs. It applies inventory optimization and logistics from the [IIT Madras Industry 4.0 course outline](https://study.iitm.ac.in/ds/course_pages/BSMS4001.html).

## Run the demo

From the repository root with Python 3.12:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Select a crop. The dispatch map supports three views: starting surplus or shortfall, modeled local spoilage after transfers, and published survey loss percentages. Hover on states for values or on paths for shipment details. Paths connect representative hubs and are schematic. **Compare crops** runs each crop independently using its own shelf-life and transit-spoilage presets. A combined multi-crop dispatch would need shared vehicle capacity and compatibility constraints.

## Dataset review

| Source | What it supports |
| --- | --- |
| [AGMARKNET](https://agmarknet.gov.in/home) | Primary dataset. Public mandi arrivals in tonnes for five crops. The replay uses August 2025 and the previous three Augusts as its comparison period. Arrivals can change because of market reporting or changing trade patterns. |
| [MoFPI/NABCONS study](https://www.mofpi.gov.in/api/documents/file/phl_study_final_report_07.12.2022_2.pdf) and [Lok Sabha Q2998, state table](https://sansad.in/getFile/dms/fetch/2c9e315f-5d5e-4a39-8b63-cba3dfdfbdfe?source=dsp2) | Historical crop loss estimates for India and selected states. These figures span multiple harvest and post-harvest stages and are displayed as context. Missing or conflicting estimates are left blank. The study narrative and the Lok Sabha table disagree for Karnataka tomato. |
| [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K) | Hourly store–product sales and stockout annotations from Dingdong. It fits the earlier retail stockout question. Its normalized sales and encoded locations cannot supply shipment quantities for Indian states. |
| [Kaggle Favorita store sales](https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data) | Grocery sales and promotions by store and product family in Ecuador. It fits sales forecasting. The fields do not measure spoilage or interstate shipment quantities. |
| [Retail Transactions and Stocks](https://data.mendeley.com/datasets/27x8mjm8k4/1) | Store-level sales and stock on hand. Useful for retail allocation across stores. |
| [DA&FW horticulture estimates, IASRI data book](https://www.iasri.res.in/uploads/IASRI%20Data%20Book%20-2025%20_low.pdf) and [DGCI&S e-way bill report](https://www.dgciskol.gov.in/writereaddata/Downloads/20260116130259Draft_Final_report_23_24.pdf) | Annual production and historic trade context. The 2023–24 road freight report omits volume analysis because reported units were inconsistent. |

`data/arrivals.csv` includes the observed amounts and retains missing values. Run `python fetch_arrivals.py` to repeat the query for the same window and selected commodity IDs. Inspect the diff for historical revisions. A crop-state pair enters dispatch only if the 2025 value and all three comparison years are present. The dashboard shows missing data separately from a zero balance.

The simplified state geometries come from [geoBoundaries gbOpen India ADM1](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/), sourced from DataMeet India community and the Election Commission of India under [CC BY 2.5 India](https://creativecommons.org/licenses/by/2.5/in/). This repo further simplifies the published geometries for display and retains the source names and codes.

## How the optimizer works

1. Subtract each state's median arrivals for August 2022–24 from August 2025 arrivals for the chosen crop. In the default scenario, use **0.1% of the gap** as a pilot-scale excess or receiving target. These arrivals are proxies. A real dispatch needs confirmed usable stock at the source and buyer orders at the destination.
2. Allow a transfer only between a surplus and a receiver with an unfilled target. Each lane uses assumed travel time, capacity, and cost. The reverse direction uses the same assumptions. Crop shelf-life and hourly spoilage presets are adjustable scenario inputs. The model assumes delivered produce is used immediately.
3. Choose tonnes sent using a linear program. It minimizes transport spend plus assumed penalties for spoilage and unfilled targets. Gross dispatch is capped by source stock and lane capacity. Edible receipts after transit spoilage are capped by the receiving target.
4. Compare with zero transfers under the same assumptions. Modeled spoilage is the sum of transit loss and the assumed loss on unsent surplus. The historic survey percentages are never applied as route loss rates.

## Three-minute walkthrough

1. Start with **Tomato** and show **Scenario balance**. With the defaults, 17.80 t arrive on four lanes and modeled spoilage changes from 11.86 t with no transfer to 3.43 t with transfers. Change shelf life from 24 to 12 hours and the tomato shipments drop to zero.
2. Switch to **Banana**. Under its default assumptions, Madhya Pradesh becomes a receiver and 7.96 t are delivered. Use the **Survey loss** map to show the historical survey values and where the survey has gaps. Use **State data** to explain why missing arrival history blocks a state from dispatch.
3. Open **Compare crops**. The rows show separate decisions under the same pilot share and cost weights. The cauliflower example has substantial modeled spoilage remaining because the excess-arrivals proxy is much larger than the receiving targets and network can absorb.

The comparisons demonstrate model behavior under hypothetical operating conditions. They do not estimate observed waste reductions or predict an actual dispatch. Production use would require time-stamped inventory, freshness, buyer orders, route quotes, and loading and receiving times.

## Validate locally

```sh
python -m unittest -v
```
