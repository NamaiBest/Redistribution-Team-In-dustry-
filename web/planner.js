import solver from "javascript-lp-solver"

// Daytime hours 06:00-21:59, matching redistribution.py.
export const HOURS = Array.from({ length: 16 }, (_, i) => i + 6)

// Estimated demand in a store's stockout hours at or after fromHour (mirrors estimate_lost).
export function estimateNeed(store, profile, fromHour) {
  let seen = 0, expected = 0, lost = 0
  HOURS.forEach((hour, i) => {
    if (store.out[i] === 0) { seen += store.sales[i]; expected += profile[i] }
  })
  const scale = expected > 0 ? Math.min(4, Math.max(0.25, seen / expected)) : 1
  HOURS.forEach((hour, i) => {
    if (store.out[i] === 1 && hour >= fromHour) lost += profile[i]
  })
  return lost * scale
}

// One city, product and day: send end-of-day unsold stock to stores that ran out.
export function planDay(example, profiles, { share, hour, cost }) {
  const stores = example.stores.map(store => {
    const profile = profiles[`${store.store_id}-${example.product_id}`]
    const stockedAllDay = store.out.every(flag => flag === 0)
    return {
      ...store,
      unsold: stockedAllDay ? share * store.sales.reduce((a, b) => a + b, 0) : 0,
      need: estimateNeed(store, profile, hour),
    }
  })
  const senders = stores.filter(s => s.unsold > 0)
  const receivers = stores.filter(s => s.need > 0)
  const constraints = {}
  const variables = {}
  senders.forEach((s, i) => { constraints[`send${i}`] = { max: s.unsold } })
  receivers.forEach((r, j) => { constraints[`recv${j}`] = { max: r.need } })
  senders.forEach((s, i) => receivers.forEach((r, j) => {
    if (r.discount <= cost) return
    variables[`x${i}_${j}`] = { gain: r.discount - cost, [`send${i}`]: 1, [`recv${j}`]: 1 }
  }))
  const solution = Object.keys(variables).length
    ? solver.Solve({ optimize: "gain", opType: "max", constraints, variables }) : {}
  const lanes = []
  senders.forEach((s, i) => receivers.forEach((r, j) => {
    const units = solution[`x${i}_${j}`] ?? 0
    if (units > 1e-7) lanes.push({ from: s.store_id, to: r.store_id, units })
  }))
  const sum = values => values.reduce((a, b) => a + b, 0)
  return {
    stores, lanes,
    unsold: sum(senders.map(s => s.unsold)),
    need: sum(receivers.map(r => r.need)),
    moved: sum(lanes.map(l => l.units)),
  }
}

export function scenario(rows, city, share, hour) {
  return rows.find(r => r.city_id === city && r.leftover_share === share && r.arrival_hour === hour)
}
