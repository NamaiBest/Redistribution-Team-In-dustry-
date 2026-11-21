"""Package the checked-in datasets for the static, browser-only planner."""
import csv
import json
from pathlib import Path
from shutil import copyfile
from unicodedata import normalize

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PUBLIC = ROOT / "web" / "public"
YEARS = (2025, 2024, 2023, 2022)


def rows(name):
    with (DATA / f"{name}.csv").open(newline="") as file:
        return list(csv.DictReader(file))


def normalize_state(name):
    return normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()


def values(row, fields):
    return [float(row[field]) if row[field] else None for field in fields]


def main():
    geometry = DATA / "india-states.geojson"
    boundaries = json.loads(geometry.read_text())
    map_names = {normalize_state(f["properties"]["shapeName"]): f["properties"]["shapeISO"]
                 for f in boundaries["features"]}
    aliases = {
        "andaman and nicobar": "IN-AN", "chattisgarh": "IN-CT",
        "keralam": "IN-KL", "nct of delhi": "IN-DL",
    }
    market = {}
    for row in rows("market_context"):
        name = normalize_state(row["state"])
        code = aliases.get(name, map_names.get(name))
        if code is None:
            raise ValueError(f"No map boundary for {row['state']}")
        market.setdefault(row["crop"], {})[code] = {
            "arrival": values(row, [f"arrival_{y}_t" for y in YEARS]),
            "price": values(row, [f"price_{y}_rs_per_quintal" for y in YEARS]),
        }
    bundle = {
        "years": YEARS,
        "crops": {r["crop"]: {
            "shelf": int(r["shelf_hours"]),
            "transit": float(r["transit_loss_percent_per_hour"]),
            "survey": float(r["national_loss_percent"]),
        } for r in rows("crops")},
        "hubs": {r["state"]: {
            "code": r["code"], "hub": r["hub"],
            "position": [float(r["latitude"]), float(r["longitude"])],
        } for r in rows("states")},
        "lanes": [{
            "a": r["origin"], "b": r["destination"],
            "hours": float(r["hours"]), "capacity": float(r["capacity_t"]),
            "cost": float(r["cost_per_t"]),
        } for r in rows("routes")],
        "losses": rows("survey_losses"),
        "market": market,
    }
    (PUBLIC / "market.json").write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")))
    copyfile(geometry, PUBLIC / "boundaries.json")


if __name__ == "__main__":
    main()
