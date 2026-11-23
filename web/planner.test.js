import assert from "node:assert/strict"
import test from "node:test"
import { readFileSync } from "node:fs"
import { estimateNeed, planDay, scenario } from "./planner.js"

const bundle = JSON.parse(readFileSync(new URL("./public/results.json", import.meta.url)))
const approx = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-4,
  `${actual} should be close to ${expected}`)

test("each example day matches the Python linear program", () => {
  // [unsold, need after 14:00, moved] from redistribution.plan_transfers at 10% unsold, cost 0.15.
  const expected = {
    "14-4-2024-05-18": [3.65, 4.365954, 3.65],
    "11-70-2024-04-21": [3.28, 4.304839, 3.28],
    "0-546-2024-04-21": [2.928, 10.597605, 2.928],
    "2-4-2024-05-19": [2.75, 10.196661, 2.75],
    "1-580-2024-03-30": [2.33, 5.558535, 2.33],
    "9-4-2024-05-25": [2.21, 3.997941, 2.21],
  }
  for (const example of bundle.examples) {
    const plan = planDay(example, bundle.profiles, { share: 0.1, hour: 14, cost: 0.15 })
    const [unsold, need, moved] = expected[`${example.city_id}-${example.product_id}-${example.dt}`]
    approx(plan.unsold, unsold)
    approx(plan.need, need)
    approx(plan.moved, moved)
  }
})

test("a transfer never exceeds a sender's unsold stock or a receiver's need", () => {
  for (const example of bundle.examples) {
    const plan = planDay(example, bundle.profiles, { share: 0.3, hour: 10, cost: 0 })
    for (const store of plan.stores) {
      const sent = plan.lanes.filter(l => l.from === store.store_id).reduce((a, l) => a + l.units, 0)
      const got = plan.lanes.filter(l => l.to === store.store_id).reduce((a, l) => a + l.units, 0)
      assert.ok(sent <= store.unsold + 1e-6)
      assert.ok(got <= store.need + 1e-6)
    }
  }
})

test("stockout hours before arrival are not counted as recoverable", () => {
  const store = { sales: Array(16).fill(1), out: Array(16).fill(0).map((_, i) => (i >= 8 ? 1 : 0)) }
  const profile = Array(16).fill(1)
  approx(estimateNeed(store, profile, 6), 8)
  approx(estimateNeed(store, profile, 18), 4)
})

test("the headline scenario is in the bundle", () => {
  const row = scenario(bundle.sensitivity, "all", 0.1, 14)
  approx(row.recovered / row.lost, 0.1139)
})
