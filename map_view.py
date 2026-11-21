"""State-level map layers and hover details for the dispatch dashboard."""
import json

import pydeck as pdk

from model import DATA

SURPLUS = [33, 150, 124, 210]
SHORTFALL = [222, 113, 66, 210]
OUTSIDE_PILOT = [235, 239, 244, 210]
MISSING = [152, 161, 176, 175]
NEUTRAL = [201, 213, 224, 210]


def shade(value, maximum):
    intensity = min(1, value / maximum) if maximum else 0
    light, dark = [240, 231, 251], [111, 53, 167]
    return [round(a + intensity * (b - a)) for a, b in zip(light, dark)] + [225]


def dispatch_map(boundaries, states, balances, plan, layer_mode, show_lanes):
    by_code = {states[row["State"]]["code"]: row for row in balances}
    positions = {state: [float(hub["longitude"]), float(hub["latitude"])]
                 for state, hub in states.items()}
    features, markers = [], []
    max_spoilage = max(plan.local_loss_t.values(), default=0)
    for feature in boundaries["features"]:
        properties = feature["properties"]
        code = properties["shapeISO"]
        row = by_code.get(code)
        if row is None:
            color, title, detail = OUTSIDE_PILOT, properties["shapeName"], "Outside the pilot"
        else:
            title = row["State"]
            net = row["Scenario balance (t)"]
            loss = row["Survey loss (%)"]
            local = row["Local spoilage (t)"]
            if layer_mode == "Survey loss":
                color = MISSING if loss is None else shade(loss, 15)
            elif net is None:
                color = MISSING
            elif layer_mode == "Modeled spoilage":
                color = shade(local, max_spoilage)
            elif net > 0:
                color = SURPLUS
            elif net < 0:
                color = SHORTFALL
            else:
                color = NEUTRAL
            balance = "Unavailable" if net is None else f"{net:+.2f} t"
            loss_label = "Unavailable" if loss is None else f"{loss:.2f}%"
            spoilage = "Unavailable" if local is None else f"{local:.2f} t"
            detail = f"Scenario balance {balance} · Historical survey loss {loss_label}"
            detail += f"\nModeled local spoilage {spoilage}"
            markers.append({"position": positions[title], "name": states[title]["hub"],
                            "label": title, "detail": detail})
        features.append({
            **feature,
            "properties": {"color": color, "label": title, "detail": detail},
        })

    layers = [pdk.Layer(
        "GeoJsonLayer", {"type": "FeatureCollection", "features": features},
        get_fill_color="properties.color", get_line_color=[112, 126, 148],
        get_line_width=1, line_width_units="pixels", pickable=True, auto_highlight=True,
    )]
    if show_lanes and plan.transfers:
        arcs = [
            {
                "start": positions[transfer.route.origin], "end": positions[transfer.route.destination],
                "width": max(2, min(9, transfer.sent_t)),
                "label": f"{transfer.route.origin} → {transfer.route.destination}",
                "detail": (
                    f"{transfer.sent_t:.2f} t sent · {transfer.delivered_t:.2f} t delivered"
                    f"\n{transfer.route.hours:g} hours · ₹{transfer.route.cost_per_t:,.0f}/t"
                ),
            }
            for transfer in plan.transfers
        ]
        layers.append(pdk.Layer(
            "ArcLayer", arcs, get_source_position="start", get_target_position="end",
            get_source_color=[23, 77, 151], get_target_color=[180, 51, 108],
            get_width="width", get_height=0.35, pickable=True,
        ))
    layers.extend([
        pdk.Layer(
            "ScatterplotLayer", markers, get_position="position", get_fill_color=[20, 41, 70],
            get_line_color=[255, 255, 255], stroked=True, line_width_min_pixels=1,
            get_radius=10500, radius_min_pixels=4, pickable=True,
        ),
        pdk.Layer(
            "TextLayer", markers, get_position="position", get_text="name",
            get_color=[15, 37, 68], get_size=12, get_pixel_offset=[10, -8],
            get_text_anchor="'start'", get_alignment_baseline="'bottom'",
            get_background_color=[255, 255, 255, 210], background=True,
            background_padding=[2, 1], font_weight=650,
        ),
    ])
    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=20.2, longitude=79.3, zoom=4.55),
        map_style=None,
        tooltip={"text": "{label}\n{detail}"},
    )


def read_boundaries():
    return json.loads((DATA / "india-states.geojson").read_text())
