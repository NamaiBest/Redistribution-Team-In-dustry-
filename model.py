"""Single-window, direct-transfer linear program in metric tonnes and rupees."""
from collections import defaultdict
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from scipy.optimize import linprog

DATA = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Route:
    origin: str
    destination: str
    hours: float
    capacity_t: float
    cost_per_t: float


@dataclass(frozen=True)
class Transfer:
    route: Route
    sent_t: float
    delivered_t: float


@dataclass(frozen=True)
class Plan:
    transfers: list[Transfer]
    local_loss_t: dict[str, float]
    remaining_usable_t: dict[str, float]
    unmet_t: dict[str, float]
    transit_loss_t: float
    transport_cost: float
    objective_cost: float

    @property
    def total_loss_t(self):
        return sum(self.local_loss_t.values()) + self.transit_loss_t


def read_rows(filename):
    with (DATA / filename).open(newline="") as file:
        return list(csv.DictReader(file))


def arrival_signals(crop="Tomato"):
    signals = []
    for row in read_rows("arrivals.csv"):
        if row["crop"] != crop:
            continue
        actual = float(row["aug_2025_t"]) if row["aug_2025_t"] else None
        history = [float(row[f"aug_{year}_t"]) for year in (2022, 2023, 2024)
                   if row[f"aug_{year}_t"]]
        typical = median(history) if len(history) == 3 else None
        gap = actual - typical if actual is not None and typical is not None else None
        signals.append({"state": row["state"], "reported": actual, "typical": typical, "gap": gap})
    return signals


def scenario_balances(scale, crop="Tomato"):
    gaps = {row["state"]: row["gap"] * scale for row in arrival_signals(crop)
            if row["gap"] is not None}
    surplus = {state: gap for state, gap in gaps.items() if gap > 0}
    deficit = {state: -gap for state, gap in gaps.items() if gap < 0}
    return surplus, deficit


def load_routes():
    routes = []
    for row in read_rows("routes.csv"):
        a, b = row["origin"], row["destination"]
        assumptions = float(row["hours"]), float(row["capacity_t"]), float(row["cost_per_t"])
        routes.extend([Route(a, b, *assumptions), Route(b, a, *assumptions)])
    return routes


def solve(surplus, deficit, routes, *, shelf_hours, transit_loss_per_hour, local_loss_rate,
          loss_penalty, shortage_penalty):
    """Choose gross tonnes sent on each eligible route. A zero-flow plan is always feasible."""
    eligible = [
        route for route in routes
        if route.origin in surplus and route.destination in deficit
        and route.hours <= shelf_hours and route.capacity_t > 0
        and route.hours * transit_loss_per_hour < 1
    ]
    survival = [1 - route.hours * transit_loss_per_hour for route in eligible]
    transfers = []
    if eligible:
        # Subtract the loss and shortage penalties avoided by shipping one extra tonne.
        marginal_costs = [
            route.cost_per_t + loss_penalty * (1 - fraction - local_loss_rate)
            - shortage_penalty * fraction
            for route, fraction in zip(eligible, survival)
        ]
        origin_limits = [[int(route.origin == state) for route in eligible] for state in surplus]
        destination_limits = [
            [fraction if route.destination == state else 0
             for route, fraction in zip(eligible, survival)]
            for state in deficit
        ]
        solution = linprog(
            marginal_costs,
            A_ub=origin_limits + destination_limits,
            b_ub=[*surplus.values(), *deficit.values()],
            bounds=[(0, route.capacity_t) for route in eligible],
            method="highs",
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        transfers = [
            Transfer(route, amount, amount * fraction)
            for route, fraction, amount in zip(eligible, survival, solution.x.tolist())
            if amount > 1e-8
        ]

    dispatched = defaultdict(float)
    received = defaultdict(float)
    for transfer in transfers:
        dispatched[transfer.route.origin] += transfer.sent_t
        received[transfer.route.destination] += transfer.delivered_t
    unshipped = {
        state: max(0, amount - dispatched[state])
        for state, amount in surplus.items()
    }
    local_loss = {state: amount * local_loss_rate for state, amount in unshipped.items()}
    remaining_usable = {state: amount - local_loss[state] for state, amount in unshipped.items()}
    unmet = {state: max(0, amount - received[state]) for state, amount in deficit.items()}
    transit_loss = sum(transfer.sent_t - transfer.delivered_t for transfer in transfers)
    transport = sum(transfer.sent_t * transfer.route.cost_per_t for transfer in transfers)
    score = transport + loss_penalty * (sum(local_loss.values()) + transit_loss)
    score += shortage_penalty * sum(unmet.values())
    return Plan(transfers, local_loss, remaining_usable, unmet, transit_loss, transport, score)
