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
        selected = {row["state"] for row in csv.DictReader(file)}
    last_day = monthrange(YEAR, MONTH)[1]
    payload = {
        "dashboard": "statewise_price_arrival_sp",
        "commodity": [65],
        "type": 100017,
        "from_date": f"{YEAR}-{MONTH:02}-01",
        "to_date": f"{YEAR}-{MONTH:02}-{last_day}",
        "limit": 100,
        "page": 1,
        "format": "json",
    }
    request = Request(
        SOURCE, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=30) as response:
        dashboard = json.load(response)
    fields = ("as_on", "one_yr_ago", "two_yr_ago", "three_yr_ago")
    rows = []
    for row in dashboard["data"]["records"]:
        if row["state_name"] not in selected:
            continue
        if row["cmdt_name"] != "Tomato" or row["unit_name_arrival"] != "Metric Tonnes":
            raise ValueError(f"Unexpected commodity or unit for {row['state_name']}")
        rows.append((row["state_name"], *(float(row[field]) for field in fields)))
    if len(rows) != len(selected) or {row[0] for row in rows} != selected:
        raise ValueError("The dashboard returned missing or duplicate states.")
    with (DATA / "arrivals.csv").open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["state", *(f"aug_{year}_t" for year in range(YEAR, YEAR - 4, -1))])
        writer.writerows(sorted(rows))


if __name__ == "__main__":
    main()
