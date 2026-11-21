"""Refresh the fixed August replay from the public AGMARKNET dashboard."""
from calendar import monthrange
import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen

DATA = Path(__file__).resolve().parent / "data"
YEAR, MONTH = 2025, 8
SOURCE = "https://api.agmarknet.gov.in/v1/dashboard-data/"


def main():
    with (DATA / "states.csv").open(newline="") as file:
        states = {row["state"] for row in csv.DictReader(file)}
    with (DATA / "crops.csv").open(newline="") as file:
        crops = {row["crop"]: int(row["agmarknet_id"]) for row in csv.DictReader(file)}
    payload = {
        "dashboard": "statewise_price_arrival_sp",
        "commodity": list(crops.values()),
        "type": 100017,
        "from_date": f"{YEAR}-{MONTH:02}-01",
        "to_date": f"{YEAR}-{MONTH:02}-{monthrange(YEAR, MONTH)[1]}",
        "limit": 500,
        "page": 1,
        "format": "json",
    }
    request = Request(
        SOURCE, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=30) as response:
        dashboard = json.load(response)
    if dashboard["pagination"]["next_page"]:
        raise ValueError("The API response exceeds the expected single page.")
    fields = ("as_on", "one_yr_ago", "two_yr_ago", "three_yr_ago")
    rows = {}
    for row in dashboard["data"]["records"]:
        crop, state = row["cmdt_name"], row["state_name"]
        if crop not in crops or state not in states:
            continue
        if row["unit_name_arrival"] != "Metric Tonnes" or (crop, state) in rows:
            raise ValueError(f"Unexpected unit or duplicate for {crop}, {state}")
        rows[crop, state] = [float(row[field]) if row[field] is not None else "" for field in fields]
    for crop in crops:
        complete_states = sum(
            all(value != "" for value in rows.get((crop, state), ("",))) for state in states
        )
        if complete_states < 2:
            raise ValueError(f"Insufficient arrivals data for {crop}")
    with (DATA / "arrivals.csv").open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["crop", "state", *(f"aug_{year}_t" for year in range(YEAR, YEAR - 4, -1))])
        for crop in crops:
            for state in sorted(states):
                writer.writerow([crop, state, *rows.get((crop, state), ("",) * len(fields))])


if __name__ == "__main__":
    main()
