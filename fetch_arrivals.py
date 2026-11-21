"""Refresh the August arrival and wholesale-price replay from AGMARKNET."""
from calendar import monthrange
import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen

DATA = Path(__file__).resolve().parent / "data"
YEAR, MONTH = 2025, 8
SOURCE = "https://api.agmarknet.gov.in/v1/dashboard-data/"
FIELDS = ("as_on", "one_yr_ago", "two_yr_ago", "three_yr_ago")


def fetch_report(commodity_ids, report_type, unit_field, expected_unit):
    payload = {
        "dashboard": "statewise_price_arrival_sp",
        "commodity": commodity_ids,
        "type": report_type,
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
    rows = {}
    for row in dashboard["data"]["records"]:
        key = (row["cmdt_name"], row["state_name"])
        if row[unit_field] != expected_unit or key in rows:
            raise ValueError(f"Unexpected unit or duplicate for {key}")
        rows[key] = tuple(float(row[field]) if row[field] not in (None, "") else "" for field in FIELDS)
    return rows


def main():
    with (DATA / "states.csv").open(newline="") as file:
        states = sorted(row["state"] for row in csv.DictReader(file))
    with (DATA / "crops.csv").open(newline="") as file:
        crops = {row["crop"]: int(row["agmarknet_id"]) for row in csv.DictReader(file)}
    arrivals = fetch_report(list(crops.values()), 100017, "unit_name_arrival", "Metric Tonnes")
    prices = fetch_report(list(crops.values()), 100016, "unit_name_price", "Rs./Quintal")
    missing = ("",) * len(FIELDS)
    for crop in crops:
        complete = sum(all(value != "" for value in arrivals.get((crop, state), missing))
                       for state in states)
        if complete < 2:
            raise ValueError(f"Insufficient arrivals data for {crop}")
    years = range(YEAR, YEAR - 4, -1)
    with (DATA / "arrivals.csv").open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["crop", "state", *(f"aug_{year}_t" for year in years)])
        writer.writerows([crop, state, *arrivals.get((crop, state), missing)]
                         for crop in crops for state in states)
    with (DATA / "market_context.csv").open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["crop", "state", *(f"arrival_{year}_t" for year in years),
                         *(f"price_{year}_rs_per_quintal" for year in years)])
        for crop, state in sorted(arrivals.keys() | prices.keys()):
            writer.writerow([crop, state, *arrivals.get((crop, state), missing),
                             *prices.get((crop, state), missing)])


if __name__ == "__main__":
    main()
