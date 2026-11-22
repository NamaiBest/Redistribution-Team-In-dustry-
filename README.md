# Interstate redistribution of perishable produce

**Research question.** Under what shelf-life, lane-capacity, and transport-cost conditions can interstate transfers of perishable produce reduce modeled spoilage and unfilled receiving targets compared with keeping stock local?

The demo covers **tomato, banana, brinjal, cabbage, cauliflower, onion, and potato** across seven representative state hubs. It applies inventory optimization and logistics from the [IIT Madras Industry 4.0 course outline](https://study.iitm.ac.in/ds/course_pages/BSMS4001.html).

## Team quick start

[Open Produce Relay](https://namaibest.github.io/Redistribution-Team-In-dustry-/). No installation or sign-in is needed. The site answers a dispatch question: which hub should send produce, which receiving hub can use it, and how much should move before it spoils?

### Try it in three minutes

1. Under **Perishable crop**, choose **Tomato**. Keep **Historical replay** and select **Dispatch balance** under **Map shading**. Green indicates modeled surplus and orange indicates a modeled shortfall. Click a state to inspect its arrivals, wholesale price, and dispatch balance.
2. Scroll to **Proposed shipments**. The default replay delivers **17.80 t** across four lanes. Modeled spoilage falls from **11.86 t to 3.43 t** compared with zero transfers under the same settings. Set shelf life to **12 hours** and the tomato shipments drop to zero. Restore **24 hours** before the next step.
3. Switch **Planning data** to **Enter hub stock & orders**. Enter **10 t saleable stock in Maharashtra** and **5 t confirmed orders in Karnataka**. With the default lane settings, the planner sends about **5.25 t** to deliver **5.00 t** after transit loss. Use **Download CSV** to see the proposed shipment in a shareable format.
4. Return to **Historical replay** and try **Banana** or **Onion**. Choose **Wholesale price** to inspect a different market signal. For banana, Madhya Pradesh becomes a receiver. Each run uses one crop.

### What to explain in the viva

- **Why this problem matters.** India used interstate tomato procurement in 2023 to supply markets facing rising retail prices. Our tool tests how a coordinator could evaluate transfers when stock and orders are known. [Government announcement](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1938858&lang=2&reg=48)
- **What the data actually measures.** AGMARKNET records arrivals at reporting mandis and weighted wholesale prices. The replay uses the arrival gap as a proxy for available stock or an unfilled receiving target. The national map can show observations beyond the seven hubs in the dispatch model. Survey loss is a separate historical measure.
- **Why use a linear program.** The decision variable is tonnes to send on each lane. Cost and modeled losses scale with tonnes. Supply, buyer orders, travel time, and lane capacity constrain the plan. This makes it possible to explain each proposed transfer and compare it with zero transfers.
- **What our results establish.** The numbers are outputs of a simulation, using assumed costs and spoilage rates. A field pilot would use time-stamped stock, buyer orders, route quotes, and measured edible weights at dispatch and receipt. Single-crop runs do not share vehicle capacity.
- **What to prepare.** The course calls for a two-page Week 8 summary, a three-page final group report, a 15-minute viva presentation with 5 minutes of Q&A, and a team contribution record. Use the [operational-application passage](report/operational-application.md) in the managerial implications section.

## Run the browser planner locally

Use Node.js 24 and Python 3. The browser runs the optimization locally. Entered quantities stay in the open session.

```sh
cd web
npm ci
npm test
npm run dev
```

The site uses [Leaflet](https://github.com/Leaflet/Leaflet) for the map, [Scrollama](https://github.com/russellsamora/scrollama) for the scroll-driven walkthrough, and [javascript-lp-solver](https://github.com/JWally/jsLPSolver) for the linear program. The visual pacing follows the [ScrollCraft](https://github.com/singhharsh1708/scrollcraft) approach. The produce photo is illustrative.

## Run the Python demo

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
| [AGMARKNET](https://agmarknet.gov.in/home) | Primary dataset. Public mandi arrivals in tonnes and a separate wholesale-price series in ₹/quintal for seven crops. Exact-price data is market context, not a solver input. The replay uses August 2025 and the previous three Augusts as its comparison period. Arrivals can change because of market reporting or changing trade patterns. |
| [MoFPI/NABCONS study](https://www.mofpi.gov.in/api/documents/file/phl_study_final_report_07.12.2022_2.pdf) and [Lok Sabha Q2998, state table](https://sansad.in/getFile/dms/fetch/2c9e315f-5d5e-4a39-8b63-cba3dfdfbdfe?source=dsp2) | Historical crop loss estimates for India and selected states. These figures span multiple harvest and post-harvest stages and are displayed as context. Missing or conflicting estimates are left blank. The study narrative and the Lok Sabha table disagree for Karnataka tomato. |
| [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K) | Hourly store–product sales and stockout annotations from Dingdong. It fits the earlier retail stockout question. Its normalized sales and encoded locations cannot supply shipment quantities for Indian states. |
| [Kaggle Favorita store sales](https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data) | Grocery sales and promotions by store and product family in Ecuador. It fits sales forecasting. The fields do not measure spoilage or interstate shipment quantities. |
| [Retail Transactions and Stocks](https://data.mendeley.com/datasets/27x8mjm8k4/1) | Store-level sales and stock on hand. Useful for retail allocation across stores. |
| [DA&FW horticulture estimates, IASRI data book](https://www.iasri.res.in/uploads/IASRI%20Data%20Book%20-2025%20_low.pdf) and [DGCI&S e-way bill report](https://www.dgciskol.gov.in/writereaddata/Downloads/20260116130259Draft_Final_report_23_24.pdf) | Annual production and historic trade context. The 2023–24 road freight report omits volume analysis because reported units were inconsistent. |

`data/arrivals.csv` retains the arrival values for dispatch hubs. `data/market_context.csv` keeps volume and weighted wholesale prices for all available reporting states. Run `python fetch_arrivals.py` to repeat the query for the same window and selected commodity IDs. Inspect the diff for historical revisions. A crop-state pair enters dispatch only if the 2025 value and all three comparison years are present. The dashboard shows missing data separately from a zero balance.

The simplified state geometries come from [geoBoundaries gbOpen India ADM1](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/), sourced from DataMeet India community and the Election Commission of India under [CC BY 2.5 India](https://creativecommons.org/licenses/by/2.5/in/). This repo further simplifies the published geometries for display and retains the source names and codes.

## How the optimizer works

1. Subtract each state's median arrivals for August 2022–24 from August 2025 arrivals for the chosen crop. In the default scenario, use **0.1% of the gap** as a pilot-scale excess or receiving target. These arrivals are proxies. A real dispatch needs confirmed usable stock at the source and buyer orders at the destination.
2. Allow a transfer only between a surplus and a receiver with an unfilled target. Each lane uses assumed travel time, capacity, and cost. The reverse direction uses the same assumptions. Crop shelf-life and hourly spoilage presets are adjustable scenario inputs. The model assumes delivered produce is used immediately.
3. Choose tonnes sent using a linear program. It minimizes transport spend plus assumed penalties for spoilage and unfilled targets. Gross dispatch is capped by source stock and lane capacity. Edible receipts after transit spoilage are capped by the receiving target.
4. Compare with zero transfers under the same assumptions. Modeled spoilage is the sum of transit loss and the assumed loss on unsent surplus. The historic survey percentages are never applied as route loss rates.

## Validate locally

```sh
python -m unittest -v
```
