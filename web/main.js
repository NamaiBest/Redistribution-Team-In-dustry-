import "./style.css"
import { HOURS, planDay, scenario } from "./planner.js"

const $ = id => document.getElementById(id)
const fmt = (value, digits = 0) => value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits })
const pct = value => `${fmt(100 * value, 1)}%`
const option = (value, label) => Object.assign(document.createElement("option"), { value, textContent: label })
const cell = (tag, text) => Object.assign(document.createElement(tag), { textContent: text })
const row = (values, tag = "td") => { const tr = document.createElement("tr"); values.forEach(v => tr.append(cell(tag, v))); return tr }

const SHARES = [0.05, 0.1, 0.2, 0.3]
const ARRIVALS = [10, 12, 14, 16, 18]
let bundle
let lastPlan

function renderScenario() {
  const city = $("city").value
  const share = Number($("share").value)
  const hour = Number($("hour").value)
  const r = scenario(bundle.sensitivity, city, share, hour)
  $("lost").textContent = fmt(r.lost)
  $("need").textContent = fmt(r.need)
  $("need-note").textContent = `Stockout hours from ${hour}:00 onward`
  $("surplus").textContent = fmt(r.surplus)
  $("recovered").textContent = fmt(r.recovered)
  $("recovered-note").textContent = `${pct(r.recovered / r.lost)} of lost demand`

  const grid = $("grid")
  grid.replaceChildren(row(["Unsold stock", ...ARRIVALS.map(h => `By ${h}:00`)], "th"))
  for (const s of SHARES) {
    grid.append(row([`${s * 100}%`, ...ARRIVALS.map(h => {
      const x = scenario(bundle.sensitivity, city, s, h)
      return pct(x.recovered / x.lost)
    })]))
  }
  const binding = r.surplus < r.need
  $("grid-note").textContent = binding
    ? `Unsold stock (${fmt(r.surplus)}) is smaller than the demand still sellable (${fmt(r.need)}). Recovery is limited by stock, so measuring end-of-day leftovers is the first step for a pilot.`
    : `Unsold stock exceeds what is still sellable after ${hour}:00. Faster transfers would recover more.`
  renderDay()
}

function renderDay() {
  const example = bundle.examples[Number($("case").value)]
  const cost = Number($("cost").value)
  if (!(cost >= 0 && cost <= 1)) return
  const plan = planDay(example, bundle.profiles, {
    share: Number($("share").value), hour: Number($("hour").value), cost,
  })
  lastPlan = { example, plan }
  $("day-unsold").textContent = fmt(plan.unsold, 2)
  $("day-need").textContent = fmt(plan.need, 2)
  $("day-moved").textContent = fmt(plan.moved, 2)
  $("store-rows").replaceChildren(...plan.stores.map(s => {
    const first = s.out.indexOf(1)
    return row([s.store_id, fmt(s.discount, 2), first < 0 ? "Stocked all day" : `${HOURS[first]}:00`,
      s.unsold ? fmt(s.unsold, 2) : "–", s.need ? fmt(s.need, 2) : "–"])
  }))
  $("lane-rows").replaceChildren(...(plan.lanes.length
    ? plan.lanes.map(l => row([l.from, l.to, fmt(l.units, 2)]))
    : [row(["No transfer pays off under these settings.", "", ""])]))
}

function exportCsv() {
  const { example, plan } = lastPlan
  const lines = [["city_id", "product_id", "date", "from_store", "to_store", "units"],
    ...plan.lanes.map(l => [example.city_id, example.product_id, example.dt, l.from, l.to, l.units.toFixed(4)])]
  const link = document.createElement("a")
  link.href = URL.createObjectURL(new Blob([lines.map(l => l.join(",")).join("\n")], { type: "text/csv;charset=utf-8" }))
  link.download = `store-relay-city${example.city_id}-product${example.product_id}-${example.dt}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

async function start() {
  try {
    bundle = await (await fetch("./results.json")).json()
  } catch {
    $("initial-status").textContent = "The results could not be loaded. Refresh the page to try again."
    return
  }
  const cities = [...new Set(bundle.sensitivity.map(r => r.city_id))].filter(c => c !== "all").sort((a, b) => a - b)
  $("city").append(option("all", "All 18 cities"), ...cities.map(c => option(c, `City ${c}`)))
  $("share").append(...SHARES.map(s => option(s, `${s * 100}% of their sales`)))
  $("share").value = "0.1"
  $("hour").append(...ARRIVALS.map(h => option(h, `${h}:00`)))
  $("hour").value = "14"
  $("case").append(...bundle.examples.map((e, i) => option(i, `City ${e.city_id} · product ${e.product_id} · ${e.dt}`)))
  $("city-rows").append(...bundle.cities.map(c => row([c.city_id, fmt(c.stores), fmt(c.lost), fmt(c.surplus), fmt(c.received), `${fmt(c.recovered_pct, 1)}%`])))

  const methods = [...new Set(bundle.validation.map(v => v.method))]
  const cuts = [...new Set(bundle.validation.map(v => v.censored_from))]
  const table = $("validation")
  table.append(row(["Method", ...cuts.map(c => `Hidden from ${c}`)], "th"))
  methods.forEach(m => table.append(row([m, ...cuts.map(c => {
    const v = bundle.validation.find(x => x.method === m && x.censored_from === c)
    return `${v.bias_pct > 0 ? "+" : ""}${fmt(v.bias_pct, 1)}%`
  })])))

  for (const id of ["city", "share", "hour"]) $(id).addEventListener("change", renderScenario)
  for (const id of ["case", "cost"]) $(id).addEventListener("input", renderDay)
  $("export").addEventListener("click", exportCsv)
  $("initial-status").hidden = true
  $("app").hidden = false
  renderScenario()
}

start()
