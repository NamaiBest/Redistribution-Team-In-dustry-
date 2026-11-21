"""Interactive scenario analysis for interstate transfers of fresh produce."""
import streamlit as st

from map_view import dispatch_map, read_boundaries
from model import arrival_signals, load_routes, read_rows, scenario_balances, solve

st.set_page_config(page_title="Interstate Perishable Produce", layout="wide")
st.title("Interstate perishable produce")
st.caption(
    "August 2025 AGMARKNET replay · Seven Indian states · Simulated shipments and spoilage"
)

crops = {row["crop"]: row for row in read_rows("crops.csv")}
product = st.segmented_control("Crop", list(crops), default="Tomato", selection_mode="single")
if product is None:
    st.info("Select a crop to view its dispatch plan.")
    st.stop()
profile = crops[product]

with st.sidebar:
    st.header("Dispatch assumptions")
    shelf_hours = st.slider("Remaining shelf life (hours)", 0, 72, int(profile["shelf_hours"]),
                           key=f"shelf_{product}", help="A lane must fit within these hours.")
    transit_rate = st.slider(
        "Transit spoilage per hour (%)", 0.0, 2.0,
        float(profile["transit_loss_percent_per_hour"]), 0.05, key=f"transit_{product}",
    )
    local_rate = st.slider("Unshipped surplus expected to spoil (%)", 0, 100, 50)
    with st.expander("Pilot size and cost assumptions"):
        scale = st.slider("Share of arrival gap used by pilot (%)", 0.0, 1.0, 0.1, 0.05)
        loss_penalty = st.number_input("Spoilage penalty (₹/t)", min_value=0, value=5000, step=500)
        shortage_penalty = st.number_input("Unmet target penalty (₹/t)", min_value=0,
                                           value=8000, step=500)
    st.caption("Shelf life, spoilage, and costs are scenario inputs.")

states = {row["state"]: row for row in read_rows("states.csv")}
survey = {row["state"]: float(row["loss_percent"]) for row in read_rows("survey_losses.csv")
          if row["crop"] == product}
surplus, deficit = scenario_balances(scale / 100, product)
parameters = dict(
    shelf_hours=shelf_hours, transit_loss_per_hour=transit_rate / 100,
    local_loss_rate=local_rate / 100, loss_penalty=loss_penalty,
    shortage_penalty=shortage_penalty,
)
routes = load_routes()
baseline = solve(surplus, deficit, [], **parameters)
plan = solve(surplus, deficit, routes, **parameters)
delivered = sum(t.delivered_t for t in plan.transfers)
unmet = sum(plan.unmet_t.values())

col1, col2, col3 = st.columns(3)
col1.metric("Delivered", f"{delivered:.2f} t", border=True)
col2.metric("Modeled spoilage", f"{plan.total_loss_t:.2f} t",
            f"{plan.total_loss_t - baseline.total_loss_t:+.2f} t vs no transfer",
            delta_color="inverse", border=True)
col3.metric("Unfilled pilot target", f"{unmet:.2f} t",
            f"{unmet - sum(baseline.unmet_t.values()):+.2f} t vs no transfer",
            delta_color="inverse", border=True)

balances = []
for signal in arrival_signals(product):
    state = signal["state"]
    has_scenario = signal["gap"] is not None
    balances.append({
        "State": state,
        "Aug 2025 arrivals (t)": signal["reported"],
        "Aug 2022–24 median (t)": signal["typical"],
        "Scenario balance (t)": round(surplus.get(state, 0) - deficit.get(state, 0), 2)
        if has_scenario else None,
        "Survey loss (%)": survey.get(state),
        "Local spoilage (t)": round(plan.local_loss_t.get(state, 0), 2) if has_scenario else None,
        "Usable surplus left (t)": round(plan.remaining_usable_t.get(state, 0), 2)
        if has_scenario else None,
        "Unfilled pilot target (t)": round(plan.unmet_t.get(state, 0), 2) if has_scenario else None,
    })

st.subheader(f"{product} dispatch map")
map_controls, lane_controls = st.columns([3, 1], vertical_alignment="bottom")
with map_controls:
    mode = st.radio("Color states by", ["Scenario balance", "Modeled spoilage", "Survey loss"],
                    horizontal=True)
with lane_controls:
    show_lanes = st.checkbox("Show routes", value=True)
if mode == "Scenario balance":
    st.caption("Green: modeled surplus · Orange: modeled shortfall · Gray: incomplete history")
elif mode == "Modeled spoilage":
    max_loss = max(plan.local_loss_t.values(), default=0)
    st.caption(f"Light to dark purple: 0 to {max_loss:.2f} t lost at origin after dispatch · "
               "Gray: incomplete history")
else:
    st.caption(f"Light to dark purple: 0 to 15% historical loss · Gray: no comparable survey estimate · "
               f"India estimate: {float(profile['national_loss_percent']):.2f}%")
if show_lanes:
    st.caption("Route lines run from blue origins to pink destinations. Hover for tonnage and hours.")

boundaries = st.cache_data(read_boundaries)()
st.pydeck_chart(dispatch_map(boundaries, states, balances, plan, mode, show_lanes), height=500)
st.caption("State boundaries: geoBoundaries / DataMeet India and Election Commission of India.")

dispatch, data, comparison, sources = st.tabs(
    ["Shipment plan", "State data", "Compare crops", "Sources and method"]
)
with dispatch:
    if plan.transfers:
        st.dataframe([
            {
                "Origin": t.route.origin, "Destination": t.route.destination,
                "Travel (h)": t.route.hours, "Hours to spare": shelf_hours - t.route.hours,
                "Capacity (t)": t.route.capacity_t, "Sent (t)": round(t.sent_t, 2),
                "Received (t)": round(t.delivered_t, 2), "Transit loss (t)": round(t.sent_t - t.delivered_t, 2),
            }
            for t in plan.transfers
        ], hide_index=True)
    else:
        st.info("No shipments are feasible or economical under these assumptions.")
    st.caption(
        f"Transport cost ₹{plan.transport_cost:,.0f} · Transit spoilage {plan.transit_loss_t:.2f} t · "
        f"Modeled objective ₹{plan.objective_cost:,.0f} "
        f"(₹{baseline.objective_cost:,.0f} with no transfers)"
    )
with data:
    st.dataframe(balances, hide_index=True)
    st.caption("A state needs Aug 2025 and all three comparison years to enter the dispatch plan. "
               "The historical survey values are independent of the simulation.")
with comparison:
    st.caption("Independent crop scenarios using each crop’s default shelf life and transit spoilage. "
               "Each row has the full route capacity available.")
    comparison_rows = []
    for crop, settings in crops.items():
        crop_surplus, crop_deficit = scenario_balances(scale / 100, crop)
        defaults = {
            **parameters, "shelf_hours": int(settings["shelf_hours"]),
            "transit_loss_per_hour": float(settings["transit_loss_percent_per_hour"]) / 100,
        }
        crop_plan = solve(crop_surplus, crop_deficit, routes, **defaults)
        comparison_rows.append({
            "Crop": crop, "Shelf life (h)": defaults["shelf_hours"],
            "Delivered (t)": round(sum(t.delivered_t for t in crop_plan.transfers), 2),
            "Spoilage without transfer (t)": round(sum(crop_surplus.values()) * local_rate / 100, 2),
            "Spoilage with transfer (t)": round(crop_plan.total_loss_t, 2),
        })
    st.dataframe(comparison_rows, hide_index=True)
with sources:
    st.markdown(
        "- [AGMARKNET](https://agmarknet.gov.in/home) supplies reported mandi arrivals. "
        "The pilot scales each state’s difference from its previous three Augusts. "
        "Real dispatch needs confirmed saleable quantities and buyer orders.\n"
        "- [The historical loss survey](https://www.mofpi.gov.in/api/documents/file/"
        "phl_study_final_report_07.12.2022_2.pdf) measures loss over several stages. "
        "The solver uses the spoilage settings in the sidebar.\n"
        "- [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K) "
        "covers hourly sales and stockouts in stores. "
        "[Favorita](https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data) "
        "covers sales by store and product family in Ecuador. Both fit forecasting questions.\n"
        "- [geoBoundaries](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/) "
        "provides the simplified state layer under CC BY 2.5 India."
    )
