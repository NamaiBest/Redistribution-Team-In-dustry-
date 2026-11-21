import solver from "javascript-lp-solver"

export function typical(values) {
  if (values.length !== 4 || values.slice(1).some(value => value === null)) return null
  return values.slice(1).sort((a, b) => a - b)[1]
}

export function historicalBalances(bundle, crop, fraction) {
  return Object.fromEntries(Object.entries(bundle.hubs).map(([state, hub]) => {
    const arrival = bundle.market[crop][hub.code]?.arrival
    const reference = arrival && typical(arrival)
    const balance = arrival?.[0] != null && reference != null ? (arrival[0] - reference) * fraction : null
    return [state, balance]
  }))
}

export function planTransfers(balances, lanes, assumptions) {
  const states = Object.keys(balances)
  const supply = Object.fromEntries(states.map(state => [state, Math.max(0, balances[state] ?? 0)]))
  const demand = Object.fromEntries(states.map(state => [state, Math.max(0, -(balances[state] ?? 0))]))
  const constraints = {}
  const variables = {}
  const eligible = []
  states.forEach((state, index) => {
    constraints[`out${index}`] = { max: supply[state] }
    constraints[`in${index}`] = { max: demand[state] }
  })
  for (const lane of lanes) {
    for (const [from, to] of [[lane.a, lane.b], [lane.b, lane.a]]) {
      const life = assumptions.originShelf?.[from] ?? assumptions.shelf
      const survival = 1 - (lane.hours * assumptions.transit / 100)
      if (!supply[from] || !demand[to] || lane.hours > life || lane.capacity <= 0 || survival <= 0) continue
      const index = eligible.length
      const capacityKey = `lane${index}`
      constraints[capacityKey] = { max: lane.capacity }
      variables[`ship${index}`] = {
        [capacityKey]: 1,
        [`out${states.indexOf(from)}`]: 1,
        [`in${states.indexOf(to)}`]: survival,
        cost: lane.cost + assumptions.lossPenalty * (1 - survival - assumptions.localLoss / 100)
          - assumptions.shortagePenalty * survival,
      }
      eligible.push({ ...lane, from, to, survival, headroom: life - lane.hours })
    }
  }
  const solution = eligible.length ? solver.Solve({ optimize: "cost", opType: "min", constraints, variables }) : {}
  if (eligible.length && (!solution.feasible || solution.bounded === false)) {
    throw new Error("This dispatch could not be calculated.")
  }
  const shipments = eligible.map((lane, index) => {
    const sent = solution[`ship${index}`] ?? 0
    return { ...lane, sent, delivered: sent * lane.survival }
  }).filter(lane => lane.sent > 1e-7)

  const unmet = { ...demand }
  const unsent = { ...supply }
  for (const lane of shipments) {
    unsent[lane.from] -= lane.sent
    unmet[lane.to] -= lane.delivered
  }
  const local = Object.fromEntries(states.map(state => [state, Math.max(0, unsent[state]) * assumptions.localLoss / 100]))
  const sum = values => values.reduce((a, b) => a + b, 0)
  return {
    shipments, unmet, local, eligibleCount: eligible.length,
    baselineWaste: sum(Object.values(supply)) * assumptions.localLoss / 100,
    waste: sum(Object.values(local)) + sum(shipments.map(lane => lane.sent - lane.delivered)),
    baselineUnmet: sum(Object.values(demand)),
    remainingUnmet: sum(Object.values(unmet).map(value => Math.max(0, value))),
    delivered: sum(shipments.map(lane => lane.delivered)),
    cost: sum(shipments.map(lane => lane.sent * lane.cost)),
  }
}
