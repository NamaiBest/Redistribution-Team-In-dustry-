# Interstate tomato redistribution

**Research question.** Under what shelf-life, route-capacity, and transport-cost conditions can direct transfers of surplus tomatoes between selected Indian states reduce modeled spoilage and shortfalls compared with keeping stock local?

This is a reproducible Industry 4.0 proof of concept for one crop, one dispatch window, and seven representative state hubs. It connects to inventory optimization and logistics in the [IIT Madras course outline](https://study.iitm.ac.in/ds/course_pages/BSMS4001.html).

## Run the demo

From the repository root with Python 3.12:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The solver and data load from local files. The map background uses online tiles. The route lines connect representative hubs and show transfer direction by color. Distances and travel times are scenario inputs.

## What the data supports

| Source | Use in this project |
| --- | --- |
| [AGMARKNET](https://agmarknet.gov.in/home) | Primary source. Reported tomato arrivals for August 2022–2025 in metric tonnes. The August 2025 gap from the previous three Augusts supplies the replay signal. |
| [MoFPI/NABCONS loss survey](https://www.mofpi.gov.in/api/documents/file/phl_study_final_report_07.12.2022_2.pdf) and [Lok Sabha annexure, Q2998](https://sansad.in/getFile/dms/fetch/2c9e315f-5d5e-4a39-8b63-cba3dfdfbdfe?source=dsp2) | Historical loss estimates for selected states, displayed separately. The national tomato estimate was 11.61%. These figures span several harvest and post-harvest stages. Karnataka is blank because the study text and the Lok Sabha table disagree. |
| [DA&FW horticulture estimates, IASRI Table 4.13](https://www.iasri.res.in/uploads/IASRI%20Data%20Book%20-2025%20_low.pdf) | Annual production context. Annual output does not identify short-term stock available for transfer. |
| [DGCI&S e-way bills report](https://www.dgciskol.gov.in/writereaddata/Downloads/20260116130259Draft_Final_report_23_24.pdf) | Historical trade context. The published 2023–24 road report leaves out quantity analysis because the units are inconsistent. |
| [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K) and [Retail Transactions and Stocks](https://data.mendeley.com/datasets/27x8mjm8k4/1) | Relevant to store stockouts and retail inventory allocation. This project's decision is a shipment between state hubs, which requires a different data model. |

The snapshot in `data/arrivals.csv` comes from AGMARKNET's state-wise price/arrival dashboard, tomato commodity ID 65, for 1–31 August 2025 and the same month in the three preceding years. To reproduce the extraction, run `python fetch_arrivals.py`. Inspect the diff before replacing the snapshot if the source revises its history.

A positive arrival gap may reflect market reporting, changed trade flows, or normal variation. The pilot assumes 0.1% of each absolute gap represents a transferable supply quantity or a receiver's target shortfall. That percentage is adjustable. The model can be used with confirmed hub inventory and buyer orders as inputs when those records are available. The historical rates do not drive the dispatch or loss calculation.

## How the optimization works

- **Decision.** Choose tonnes to send on each listed origin-to-destination route.
- **Constraints.** Gross shipments cannot exceed origin supply or lane capacity. Edible receipts cannot exceed the receiver's modeled gap. The route must fit within remaining shelf life. The receiver is assumed to use the delivered quantity immediately.
- **Loss.** Transit loss is gross tonnes sent × trip hours × loss rate per hour. Local spoilage is the assumed spoilage fraction × unshipped surplus. Remaining stock and unmet targets are tracked separately.
- **Objective.** Minimize transport spend plus the assumed penalties for spoilage and unmet targets. The objective compares scenarios under the same weights. Its rupee value does not measure financial savings. The linear program uses continuous tonnes and permits zero shipments when every lane is infeasible or uneconomical.

## Three-minute walkthrough

1. Open **State inputs and losses**. Show that historical mandi arrivals supply the starting signal and that survey losses have a separate column. Explain why a lower loss percentage alone does not make a state a suitable receiver.
2. Open **Shipment plan**. With the default assumptions, the optimizer delivers **17.80 t** on four lanes. Modeled spoilage falls from **11.86 t to 3.43 t**. The unmet arrival target falls from **79.45 t to 61.66 t**. For example, Maharashtra can ship 10 t to Karnataka on a 19-hour lane and deliver about 9.53 t given the assumed transit loss.
3. Reduce remaining shelf life from **24 to 12 hours**. Every modeled trip becomes too long and the plan returns zero shipments. Explain that stock can move only while there is buyer capacity and enough shelf life to arrive.

The comparison demonstrates the solver on one historical replay under hypothetical operating conditions. The scenario does not establish measured waste reduction, real unmet demand, or a forecast for a current dispatch. The benchmark does not include processing, storage, or other local options.

## Validate locally

```sh
python -m unittest -v
```

The checks cover a shipment whose receiving target binds, an uneconomical lane, the original data replay and its shipment constraints, and an interactive dashboard smoke test.
