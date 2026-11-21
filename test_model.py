from collections import defaultdict
import unittest

from streamlit.testing.v1 import AppTest

from model import Route, load_routes, scenario_balances, solve


DEFAULT = dict(
    shelf_hours=24, transit_loss_per_hour=0.0025, local_loss_rate=0.5,
    loss_penalty=5000, shortage_penalty=8000,
)


class RoutingTests(unittest.TestCase):
    def test_delivered_quantity_limits_the_route(self):
        plan = solve(
            {"A": 10}, {"B": 4}, [Route("A", "B", 10, 10, 100)],
            **{**DEFAULT, "transit_loss_per_hour": 0.01},
        )
        (transfer,) = plan.transfers
        self.assertAlmostEqual(transfer.sent_t, 4 / 0.9)
        self.assertAlmostEqual(transfer.delivered_t, 4)
        self.assertAlmostEqual(transfer.sent_t, transfer.delivered_t + plan.transit_loss_t)
        self.assertAlmostEqual(plan.unmet_t["B"], 0)

    def test_dispatch_can_be_unprofitable(self):
        plan = solve({"A": 10}, {"B": 4}, [Route("A", "B", 5, 100, 20_000)], **DEFAULT)
        self.assertEqual(plan.transfers, [])
        self.assertEqual(plan.total_loss_t, 5)
        self.assertEqual(plan.unmet_t["B"], 4)

    def test_observed_replay_constraints_and_shelf_life(self):
        surplus, deficit = scenario_balances(0.001)
        routes = load_routes()
        baseline = solve(surplus, deficit, [], **DEFAULT)
        plan = solve(surplus, deficit, routes, **DEFAULT)
        sent, received = defaultdict(float), defaultdict(float)
        for transfer in plan.transfers:
            route = transfer.route
            self.assertLessEqual(transfer.sent_t, route.capacity_t + 1e-8)
            self.assertLessEqual(route.hours, DEFAULT["shelf_hours"])
            sent[route.origin] += transfer.sent_t
            received[route.destination] += transfer.delivered_t
        for state, quantity in sent.items():
            self.assertLessEqual(quantity, surplus[state] + 1e-8)
        for state, quantity in received.items():
            self.assertLessEqual(quantity, deficit[state] + 1e-8)
        self.assertAlmostEqual(sum(sent.values()), sum(received.values()) + plan.transit_loss_t)
        self.assertAlmostEqual(
            sum(surplus.values()),
            sum(received.values()) + plan.total_loss_t + sum(plan.remaining_usable_t.values()),
        )
        self.assertLess(plan.objective_cost, baseline.objective_cost)
        self.assertAlmostEqual(plan.total_loss_t, 3.42812345, places=6)
        short_life = solve(surplus, deficit, routes, **{**DEFAULT, "shelf_hours": 12})
        self.assertEqual(short_life, baseline)

    def test_dashboard_loads_and_updates(self):
        app = AppTest.from_file("app.py").run(timeout=20)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, "17.80 t")
        app.slider[1].set_value(12).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, "0.00 t")


if __name__ == "__main__":
    unittest.main()
