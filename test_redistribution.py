import unittest

import numpy as np
import pandas as pd

import redistribution as R


def day(store, product, sales, out, city=1, discount=1.0, dt="2024-04-01"):
    row = {"city_id": city, "store_id": store, "management_group_id": 0, "first_category_id": 1,
           "product_id": product, "dt": dt, "sale_amount": sum(sales), "discount": discount,
           "activity_flag": 0, "holiday_flag": 0}
    row.update({f"s{h}": s for h, s in zip(R.HOURS, sales)})
    row.update({f"o{h}": o for h, o in zip(R.HOURS, out)})
    return row


class ProfileTests(unittest.TestCase):
    def test_profile_ignores_stockout_hours(self):
        days = pd.DataFrame([day(1, 9, [1.0] * 16, [0] * 16), day(1, 9, [0.0] * 16, [1] * 16)])
        profile = R.hourly_profiles(days)
        self.assertTrue(np.allclose(profile.loc[(1, 9)].to_numpy(), 1.0))

    def test_lost_demand_recovers_hidden_hours_when_profile_is_exact(self):
        history = pd.DataFrame([day(1, 9, [float(h) for h in R.HOURS], [0] * 16)])
        profile = R.hourly_profiles(history)
        # Same shape at twice the level, out of stock from 14:00.
        sales = [2.0 * h if h < 14 else 0.0 for h in R.HOURS]
        out = [0 if h < 14 else 1 for h in R.HOURS]
        target = pd.DataFrame([day(1, 9, sales, out)])
        expected = sum(2.0 * h for h in R.HOURS if h >= 14)
        self.assertAlmostEqual(R.estimate_lost(target, profile).iloc[0], expected, places=4)
        later = sum(2.0 * h for h in R.HOURS if h >= 18)
        self.assertAlmostEqual(R.estimate_lost(target, profile, 18).iloc[0], later, places=4)


class PlanTests(unittest.TestCase):
    def test_pooled_rule_matches_linear_program(self):
        rng = np.random.default_rng(7)
        for _ in range(200):
            surplus = rng.uniform(0, 3, rng.integers(1, 6))
            need = rng.uniform(0, 3, rng.integers(1, 6))
            value = rng.uniform(0.1, 1.0, len(need))
            lp = R.plan_transfers(surplus, need, value, 0.15)
            pooled = R.pooled_plan(surplus.sum(), need, value, 0.15)
            gain = value - 0.15
            self.assertAlmostEqual((lp.sum(axis=0) * gain).sum(), (pooled * gain).sum(), places=6)
            self.assertTrue(np.all(lp.sum(axis=1) <= surplus + 1e-9))
            self.assertTrue(np.all(lp.sum(axis=0) <= need + 1e-9))

    def test_replay_only_sends_from_fully_stocked_stores(self):
        flat = [1.0] * 16
        history = pd.DataFrame([day(s, 9, flat, [0] * 16) for s in (1, 2, 3)])
        profile = R.hourly_profiles(history)
        out_late = [0 if h < 14 else 1 for h in R.HOURS]
        today = pd.DataFrame([
            day(1, 9, flat, [0] * 16),                                  # sender: 16 sold, 1.6 left over
            day(2, 9, [1.0 if h < 14 else 0.0 for h in R.HOURS], out_late, discount=0.9),
            day(3, 9, [1.0 if h < 14 else 0.0 for h in R.HOURS], out_late, discount=0.6),
        ])
        frame = R.replay(today, profile, R.Scenario(leftover_share=0.1, arrival_hour=14))
        self.assertAlmostEqual(frame["surplus"].sum(), 1.6, places=5)
        self.assertAlmostEqual(frame.loc[1, "received"], 1.6, places=5)  # higher price store filled first
        self.assertEqual(frame.loc[2, "received"], 0.0)
        self.assertLessEqual(frame["received"].sum(), frame["surplus"].sum() + 1e-9)

    def test_no_transfers_across_cities(self):
        flat = [1.0] * 16
        history = pd.DataFrame([day(s, 9, flat, [0] * 16) for s in (1, 2)])
        profile = R.hourly_profiles(history)
        today = pd.DataFrame([day(1, 9, flat, [0] * 16, city=1),
                              day(2, 9, [0.0] * 16, [1] * 16, city=2)])
        frame = R.replay(today, profile, R.Scenario())
        self.assertEqual(frame["received"].sum(), 0.0)


if __name__ == "__main__":
    unittest.main()
