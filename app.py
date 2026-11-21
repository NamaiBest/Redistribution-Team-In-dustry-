"""Interactive replay of a hypothetical cross-state tomato dispatch."""
import pydeck as pdk
import streamlit as st

from model import arrival_signals, load_routes, read_rows, scenario_balances, solve

st.set_page_config(page_title="Interstate Tomato Redistribution", layout="wide")
st.title("Interstate tomato redistribution")
st.caption(
    "August 2025 AGMARKNET replay · Seven Indian states · Simulated shipments and losses"
)

with st.sidebar:
    st.header("Scenario assumptions")
    scale = st.slider("Share of arrival gap available to the pilot (%)",
                      0.0, 1.0, 0.1, 0.05)
    shelf_hours = st.slider("Remaining shelf life at dispatch (hours)", 0, 48, 24)
    transit_rate = st.slider("Transit loss per hour (%)", 0.0, 2.0, 0.25, 0.05)
    local_rate = st.slider("Unshipped surplus expected to spoil (%)", 0, 100, 50)
    loss_penalty = st.number_input("Spoilage penalty (₹/t)", min_value=0, value=5000, step=500)
    shortage_penalty = st.number_input("Unmet target penalty (₹/t)", min_value=0,
                                       value=8000, step=500)

states = {row["state"]: row for row in read_rows("states.csv")}
surplus, deficit = scenario_balances(scale / 100)
parameters = dict(
    shelf_hours=shelf_hours, transit_loss_per_hour=transit_rate / 100,
    local_loss_rate=local_rate / 100, loss_penalty=loss_penalty,
    shortage_penalty=shortage_penalty,
)
routes = load_routes()
baseline = solve(surplus, deficit, [], **parameters)
plan = solve(surplus, deficit, routes, **parameters)

col1, col2, col3 = st.columns(3)
col1.metric("Delivered", f"{sum(t.delivered_t for t in plan.transfers):.2f} t")
col2.metric("Modeled spoilage", f"{plan.total_loss_t:.2f} t",
            f"{plan.total_loss_t - baseline.total_loss_t:+.2f} t vs no transfer",
            delta_color="inverse")
col3.metric("Unmet arrival target", f"{sum(plan.unmet_t.values()):.2f} t",
            f"{sum(plan.unmet_t.values()) - sum(baseline.unmet_t.values()):+.2f} t vs no transfer",
            delta_color="inverse")

st.subheader("Dispatch map")
st.caption("Green hubs have simulated excess arrivals. Orange hubs are below their arrival target.")
hubs, arcs, shipments, balances = [], [], [], []
for signal in arrival_signals():
    state = signal["state"]
    hub = states[state]
    net_t = surplus.get(state, 0) - deficit.get(state, 0)
    color = [19, 112, 91] if net_t > 0 else [184, 91, 40] if net_t < 0 else [115, 120, 130]
    local_loss = plan.local_loss_t.get(state, 0)
    survey_loss = hub["historical_loss_percent"]
    hubs.append({
        "position": [float(hub["longitude"]), float(hub["latitude"])], "color": color,
        "label": f"{hub['hub']}, {state}",
        "detail": f"Scenario balance {net_t:+.2f} t · Local spoilage {local_loss:.2f} t",
    })
    balances.append({
        "State": state, "Aug 2025 arrivals (t)": round(signal["reported"], 2),
        "Aug 2022–24 median (t)": round(signal["typical"], 2),
        "Scenario balance (t)": round(net_t, 2),
        "Historical survey loss (%)": float(survey_loss) if survey_loss else None,
        "Modeled local spoilage (t)": round(local_loss, 2),
        "Remaining usable surplus (t)": round(plan.remaining_usable_t.get(state, 0), 2),
        "Unmet arrival target (t)": round(plan.unmet_t.get(state, 0), 2),
    })
positions = {state: [float(hub["longitude"]), float(hub["latitude"])]
             for state, hub in states.items()}
for transfer in plan.transfers:
    route = transfer.route
    arcs.append({
        "start": positions[route.origin], "end": positions[route.destination],
        "width": max(2, min(8, transfer.sent_t)),
        "label": f"{route.origin} → {route.destination}",
        "detail": f"{transfer.sent_t:.2f} t sent · {transfer.delivered_t:.2f} t delivered",
    })
    shipments.append({
        "Origin": route.origin, "Destination": route.destination,
        "Travel (h)": route.hours, "Capacity (t)": route.capacity_t,
        "Sent (t)": round(transfer.sent_t, 2), "Received (t)": round(transfer.delivered_t, 2),
    })

layers = []
if arcs:
    layers.append(pdk.Layer(
        "ArcLayer", arcs, get_source_position="start", get_target_position="end",
        get_source_color=[19, 112, 91], get_target_color=[184, 91, 40],
        get_width="width", pickable=True,
    ))
layers.append(pdk.Layer(
    "ScatterplotLayer", hubs, get_position="position", get_fill_color="color",
    get_radius=11500, radius_min_pixels=6, pickable=True,
))
st.pydeck_chart(pdk.Deck(
    layers=layers,
    initial_view_state=pdk.ViewState(latitude=19.2, longitude=78.4, zoom=4.55),
    map_style=pdk.map_styles.LIGHT,
    tooltip={"text": "{label}\n{detail}"},
), height=490)

dispatch, data = st.tabs(["Shipment plan", "State inputs and losses"])
with dispatch:
    if shipments:
        st.dataframe(shipments, hide_index=True)
    else:
        st.info("No shipments are feasible or economical under these assumptions.")
    st.caption(
        f"Transport cost ₹{plan.transport_cost:,.0f} · "
        f"Transit spoilage {plan.transit_loss_t:.2f} t · "
        f"Modeled objective ₹{plan.objective_cost:,.0f} "
        f"(₹{baseline.objective_cost:,.0f} with no transfers)"
    )
with data:
    st.dataframe(balances, hide_index=True)
    st.caption("Blank survey values indicate missing or conflicting state estimates.")

with st.expander("How to interpret this demo"):
    st.markdown(
        "Reported arrivals come from [AGMARKNET](https://agmarknet.gov.in/home). "
        "The pilot uses a small, adjustable share of each state's departure from its "
        "historical August median. These departures are a market-activity signal. "
        "Sellable inventory and buyer orders would be needed for real dispatch. "
        "Travel time, capacity, cost and spoilage are scenario inputs. The historical "
        "survey estimates cover multiple supply-chain stages and are displayed for context."
    )
