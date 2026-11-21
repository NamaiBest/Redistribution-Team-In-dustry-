import assert from "node:assert/strict"
import test from "node:test"
import { readFileSync } from "node:fs"
import { historicalBalances, planTransfers } from "./planner.js"

const bundle = JSON.parse(readFileSync(new URL("./public/market.json", import.meta.url)))
const defaults = { shelf: 24, transit: 0.25, localLoss: 50, lossPenalty: 5000, shortagePenalty: 8000 }
const approx = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-5,
  `${actual} should be close to ${expected}`)

test("stock, received quantity and per-origin shelf life constrain a dispatch", () => {
  const lanes = [{ a: "A", b: "B", hours: 10, capacity: 10, cost: 100 }]
  const balances = { A: 8, B: -4 }
  const plan = planTransfers(balances, lanes, { ...defaults, transit: 1 })
  approx(plan.delivered, 4)
  approx(plan.shipments[0].sent, 4 / .9)
  approx(plan.remainingUnmet, 0)
  assert.equal(planTransfers(balances, lanes, { ...defaults, originShelf: { A: 9 } }).shipments.length, 0)
  assert.equal(planTransfers(balances, [{ ...lanes[0], cost: 50000 }], defaults).shipments.length, 0)
})

test("all seven browser scenarios agree with the reference Python optimizer", () => {
  const expected = {
    Tomato: [17.7964, 3.428123], Banana: [7.960703, 2.950337],
    Brinjal: [2.86983, 4.349358], Cabbage: [4.83678, 5.893136],
    Cauliflower: [2.63555, 52.156081], Onion: [16.949374, 25.764436],
    Potato: [17.223286, 7.5895],
  }
  assert.deepEqual(Object.keys(bundle.crops), Object.keys(expected))
  for (const [crop, profile] of Object.entries(bundle.crops)) {
    const balances = historicalBalances(bundle, crop, .001)
    const plan = planTransfers(balances, bundle.lanes, {
      ...defaults, shelf: profile.shelf, transit: profile.transit,
    })
    approx(plan.delivered, expected[crop][0])
    approx(plan.waste, expected[crop][1])
    approx(plan.baselineUnmet - plan.delivered, plan.remainingUnmet)
  }
})

test("a missing historical value stays out of dispatch while observed data remains visible", () => {
  assert.equal(bundle.market.Banana["IN-KA"].arrival[0], 2684)
  assert.equal(historicalBalances(bundle, "Banana", .001).Karnataka, null)
  assert.equal(bundle.market.Tomato["IN-KA"].price[0], 1952.23)
})
