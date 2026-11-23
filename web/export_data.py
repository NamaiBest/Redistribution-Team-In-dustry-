"""Bundle the result tables in ../data into public/results.json for the site."""
import csv
import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
OUT = Path(__file__).parent / "public" / "results.json"


def rows(name):
    with (DATA / name).open(newline="") as file:
        return [{k: (v if k in ("city_id", "censored_from", "method") else float(v)) for k, v in row.items()}
                for row in csv.DictReader(file)]


bundle = {
    "sensitivity": rows("sensitivity_city.csv"),
    "cities": rows("by_city.csv"),
    "validation": rows("validation.csv"),
    **json.loads((DATA / "examples.json").read_text()),
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(bundle, separators=(",", ":")))
