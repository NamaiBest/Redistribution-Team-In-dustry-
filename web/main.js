import L from "leaflet"
import scrollama from "scrollama"
import "leaflet/dist/leaflet.css"
import "./style.css"
import { historicalBalances, planTransfers, typical } from "./planner.js"

const $ = id => document.getElementById(id)
const format = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })
const number = value => format.format(value)
const mass = value => value == null ? "Unavailable" : `${number(Math.abs(value) < 1e-7 ? 0 : value)} t`
const price = value => value == null ? "Unavailable" : `₹${number(value)} / q`
const percent = value => value == null ? "Unavailable" : `${number(value)}%`
const rupees = value => `₹${Math.round(value).toLocaleString("en-IN")}`
const motion = matchMedia("(prefers-reduced-motion: reduce)")

if (!motion.matches) {
  const photo = document.querySelector(".hero-photo")
  const updateHero = () => {
    if (window.scrollY < 850) photo.style.setProperty("--hero-shift", Math.min(window.scrollY / 575, 1))
  }
  window.addEventListener("scroll", updateHero, { passive: true })
  scrollama().setup({ step: ".story-step", offset: 0.62 })
    .onStepEnter(({ element }) => {
      document.querySelector(".story-step.is-current")?.classList.remove("is-current")
      element.classList.add("is-current")
    })
}

async function readAsset(path) {
  const response = await fetch(new URL(path, location.href))
  if (!response.ok) throw new Error(`Unable to load ${path}.`)
  return response.json()
}

function inputCell(label, value, max = null) {
  const td = document.createElement("td")
  const input = document.createElement("input")
  input.type = "number"
  input.setAttribute("aria-label", label)
  input.min = "0"
  input.step = "any"
  if (max != null) input.max = max
  if (value != null) input.value = value
  else input.placeholder = "Default"
  td.append(input)
  return td
}

function textCell(value, tag = "td") {
  const cell = document.createElement(tag)
  cell.textContent = value
  return cell
}

function blend(low, high, weight) {
  const fraction = Math.max(0, Math.min(1, weight))
  return `rgb(${low.map((c, index) => Math.round(c + fraction * (high[index] - c))).join(",")})`
}

function routeCurve(from, to) {
  const [lat, lon] = from
  const [dlat, dlon] = [to[0] - lat, to[1] - lon]
  return Array.from({ length: 25 }, (_, i) => {
    const t = i / 24
    const curve = 0.45 * t * (1 - t)
    return [lat + dlat * t + dlon * curve, lon + dlon * t - dlat * curve]
  })
}

function initialize(bundle, boundaries) {
  const crop = $("crop")
  const mode = $("mode")
  const layer = $("layer")
  const form = $("configuration")
  const selector = $("state-select")
  const stateByCode = Object.fromEntries(Object.entries(bundle.hubs).map(([state, hub]) => [hub.code, state]))
  const names = Object.fromEntries(boundaries.features.map(feature => [
    feature.properties.shapeISO, stateByCode[feature.properties.shapeISO] ??
      feature.properties.shapeName.normalize("NFKD").replace(/\p{Diacritic}/gu, ""),
  ]))
  Object.keys(bundle.crops).forEach(name => crop.add(new Option(name, name)))
  Object.entries(names).sort((a,b) => a[1].localeCompare(b[1]))
    .forEach(([code, name]) => selector.add(new Option(name, code)))
  selector.value = "IN-MH"

  const customRows = Object.fromEntries(Object.keys(bundle.hubs).map(state => {
    const line = $("custom-rows").insertRow()
    line.append(textCell(state, "th"), inputCell(`${state} saleable stock`, 0),
      inputCell(`${state} confirmed orders`, 0), inputCell(`${state} remaining shelf life`, null, 720))
    return [state, Array.from(line.querySelectorAll("input"))]
  }))
  const entriesByCrop = new Map()
  let currentCrop = crop.value
  const laneRows = bundle.lanes.map(lane => {
    const line = $("lane-rows").insertRow()
    line.append(textCell(`${lane.a} ↔ ${lane.b}`, "th"),
      inputCell(`Travel hours: ${lane.a} and ${lane.b}`, lane.hours),
      inputCell(`Capacity: ${lane.a} and ${lane.b}`, lane.capacity),
      inputCell(`Cost: ${lane.a} and ${lane.b}`, lane.cost))
    line.querySelectorAll("input").forEach(input => { input.required = true })
    return Array.from(line.querySelectorAll("input"))
  })

  $("initial-status").hidden = true
  $("app").hidden = false
  const map = L.map("map", { scrollWheelZoom: false, minZoom: 3, maxZoom: 9, zoomSnap: 0.25 })
  map.attributionControl.addAttribution("geoBoundaries · CC BY 2.5 IN")
  const fit = () => map.fitBounds([[7, 67], [36.5, 98]], { padding: [8, 8], animate: false })
  fit()
  $("reset-map").addEventListener("click", fit)
  const geometry = L.geoJSON(boundaries, {
    onEachFeature(feature, path) {
      const code = feature.properties.shapeISO
      path.bindTooltip(names[code], { sticky: true })
      path.on("mouseover", () => path.setStyle({ weight: 2.5, color: "#294b3b" }))
      path.on("mouseout", () => paintState(path))
      path.on("click", () => {
        selector.value = code
        updateState()
        geometry.eachLayer(paintState)
      })
    },
  }).addTo(map)
  const routeLayer = L.layerGroup().addTo(map)
  let result, balances, survey, market, ranges

  function valueFor(code, field) {
    const state = stateByCode[code]
    if (field === "arrival" || field === "price") return market[code]?.[field][0]
    if (field === "survey") return survey[state]
    if (balances[state] == null) return null
    return field === "balance" ? balances[state] : result.local[state]
  }

  function paintState(path) {
    const code = path.feature.properties.shapeISO
    const field = layer.value
    const value = valueFor(code, field)
    let fillColor = "#c7cdc9"
    if (value != null) {
      if (field === "balance") {
        fillColor = value > 0 ? "#288264" : value < 0 ? "#be632d" : "#e9e8da"
      } else {
        const colors = {
          arrival: [[230, 242, 196], [26, 102, 69]],
          price: [[251, 237, 202], [151, 63, 26]],
          waste: [[241, 230, 248], [105, 63, 140]],
          survey: [[241, 230, 248], [105, 63, 140]],
        }
        fillColor = blend(...colors[field], value / (ranges[field] || 1))
      }
    }
    const chosen = code === selector.value
    path.setStyle({ fillColor, fillOpacity: 0.94, weight: chosen ? 2.6 : 1,
      color: chosen ? "#264636" : "#f5f7ef" })
  }

  function updateState() {
    const code = selector.value
    const state = stateByCode[code]
    const row = market[code]
    const arrivals = row?.arrival[0]
    const priceNow = row?.price[0]
    const typicalArrivals = row && typical(row.arrival)
    const typicalPrice = row && typical(row.price)
    $("state-title").textContent = names[code]
    const watch = arrivals != null && priceNow != null && typicalArrivals != null
      && typicalPrice != null && arrivals < typicalArrivals && priceNow > typicalPrice
    $("state-signal").textContent = watch
      ? "Arrivals below the August reference and prices above it. Confirm buyer demand before dispatch."
      : state ? `Dispatch hub · ${bundle.hubs[state].hub}` : "Outside the seven-hub dispatch network."
    const values = [
      ["Reported August arrivals", mass(arrivals)],
      ["Prior August median", mass(typicalArrivals)],
      ["Weighted wholesale price", price(priceNow)],
      ["Prior August price median", price(typicalPrice)],
      ["Historical survey loss", percent(survey[state])],
    ]
    if (state) values.push(["Net dispatch balance", mass(balances[state])],
      ["Outstanding target", mass(balances[state] == null ? null : Math.max(0, result.unmet[state]))])
    $("state-values").replaceChildren(...values.map(([name, value]) => {
      const row = document.createElement("div")
      row.append(textCell(name, "dt"), textCell(value, "dd"))
      return row
    }))
  }

  function redrawMap() {
    geometry.eachLayer(paintState)
    routeLayer.clearLayers()
    for (const shipment of result.shipments) {
      const points = routeCurve(bundle.hubs[shipment.from].position, bundle.hubs[shipment.to].position)
      L.polyline(points, { color: "#1c436d", weight: 3 + Math.min(4, Math.sqrt(shipment.sent)), opacity: .9 })
        .bindTooltip(`${shipment.from} → ${shipment.to}<br>${mass(shipment.delivered)} delivered · ${shipment.hours} h`)
        .addTo(routeLayer)
      const last = points[21], previous = points[20]
      const end = L.CRS.EPSG3857.project(L.latLng(last))
      const start = L.CRS.EPSG3857.project(L.latLng(previous))
      const angle = Math.atan2(start.y - end.y, end.x - start.x) * 180 / Math.PI
      L.marker(last, {
        interactive: false, keyboard: false,
        icon: L.divIcon({ className: "route-arrow", iconSize: [13,13], iconAnchor: [7,7],
          html: `<span style="display:block;color:#1c436d;transform:rotate(${angle}deg)">▶</span>` }),
      }).addTo(routeLayer)
    }
    for (const [state, hub] of Object.entries(bundle.hubs)) {
      L.circleMarker(hub.position, { radius: 4.5, color: "#fffef8", weight: 1.5,
        fillColor: "#203b50", fillOpacity: 1 })
        .bindTooltip(hub.hub)
        .on("click", () => {
          selector.value = hub.code
          updateState()
          geometry.eachLayer(paintState)
        }).addTo(routeLayer)
    }
    const legends = {
      arrival: `Light to dark green · 0 to ${mass(ranges.arrival)}`,
      price: `Light to dark amber · ₹0 to ${price(ranges.price)}`,
      balance: "Green · surplus   /   orange · shortfall   /   cream · balanced",
      waste: `Light to dark purple · 0 to ${mass(ranges.waste)} at origin`,
      survey: `Light to dark purple · 0–15% · India estimate ${percent(bundle.crops[crop.value].survey)}`,
    }
    $("map-title").textContent = `${crop.value} · ${layer.selectedOptions[0].textContent}`
    $("map-legend").textContent = legends[layer.value]
    updateState()
  }

  function updatePlan() {
    if (!form.checkValidity()) {
      $("form-status").hidden = false
      $("form-status").textContent = "Enter a valid number in each highlighted field. The results below reflect the last valid scenario."
      $("export").disabled = true
      return
    }
    $("form-status").hidden = true
    market = bundle.market[crop.value]
    survey = Object.fromEntries(bundle.losses.filter(row => row.crop === crop.value)
      .map(row => [row.state, Number(row.loss_percent)]))
    const custom = mode.value === "custom"
    const entered = Object.entries(customRows)
    const originShelf = Object.fromEntries(entered.filter(([, cells]) => cells[2].value !== "")
      .map(([state, cells]) => [state, Number(cells[2].value)]))
    balances = custom
      ? Object.fromEntries(entered.map(([state, cells]) => [state, Number(cells[0].value) - Number(cells[1].value)]))
      : historicalBalances(bundle, crop.value, Number($("share").value) / 100)
    const lanes = bundle.lanes.map((lane, index) => {
      const [hours, capacity, cost] = laneRows[index].map(input => Number(input.value))
      return { ...lane, hours, capacity, cost }
    })
    result = planTransfers(balances, lanes, {
      shelf: Number($("shelf").value), transit: Number($("transit").value),
      localLoss: Number($("local-loss").value), lossPenalty: Number($("loss-penalty").value),
      shortagePenalty: Number($("shortage-penalty").value), originShelf: custom ? originShelf : undefined,
    })
    ranges = {
      arrival: Math.max(0, ...Object.values(market).map(row => row.arrival[0] ?? 0)),
      price: Math.max(0, ...Object.values(market).map(row => row.price[0] ?? 0)),
      waste: Math.max(0, ...Object.values(result.local)), survey: 15,
    }
    $("delivered").textContent = mass(result.delivered)
    $("delivered-note").textContent = `${result.shipments.length} proposed lanes`
    $("waste").textContent = mass(result.waste)
    $("waste-note").textContent = `${mass(result.baselineWaste)} with no transfers`
    $("unmet").textContent = mass(result.remainingUnmet)
    $("unmet-note").textContent = `${mass(result.baselineUnmet)} with no transfers`
    $("route-note").textContent = `${rupees(result.cost)} modeled freight · ${result.eligibleCount} feasible lanes`
    $("shipment-rows").replaceChildren(...result.shipments.map(shipment => {
      const row = document.createElement("tr")
      row.append(...[shipment.from, shipment.to, mass(shipment.sent), mass(shipment.delivered),
        `${shipment.hours} h`, `${shipment.headroom} h`, rupees(shipment.sent * shipment.cost)].map(value => textCell(value)))
      return row
    }))
    $("shipments").hidden = !result.shipments.length
    $("export").disabled = !result.shipments.length
    $("empty-routes").hidden = !!result.shipments.length
    $("empty-routes").textContent = result.eligibleCount
      ? "No feasible lane improves the objective at the current cost and loss settings."
      : "No route matches the available stock, receiving targets, and remaining shelf life."
    redrawMap()
  }

  function setPreset() {
    $("shelf").value = bundle.crops[crop.value].shelf
    $("transit").value = bundle.crops[crop.value].transit
  }

  function setMode() {
    const custom = mode.value === "custom"
    $("custom-detail").hidden = !custom
    $("custom-detail").open = custom
    Object.values(customRows).flat().forEach(input => { input.disabled = !custom })
    $("share").disabled = custom
    $("mode-note").textContent = custom
      ? "Shipment estimates use the stock and orders you enter. All market layers remain the August replay."
      : "The replay uses a small share of the observed arrival gap as a scenario proxy for stock and orders."
  }

  function refresh() {
    try {
      updatePlan()
    } catch (error) {
      $("form-status").hidden = false
      $("form-status").textContent = error.message
      $("export").disabled = true
    }
  }
  form.addEventListener("submit", event => event.preventDefault())
  form.addEventListener("input", event => {
    if (event.target instanceof HTMLInputElement) refresh()
  })
  form.addEventListener("change", event => {
    if (event.target instanceof HTMLInputElement) return
    if (event.target === crop) {
      entriesByCrop.set(currentCrop, Object.fromEntries(Object.entries(customRows)
        .map(([state, inputs]) => [state, inputs.map(input => input.value)])))
      currentCrop = crop.value
      const saved = entriesByCrop.get(currentCrop)
      for (const [state, inputs] of Object.entries(customRows)) {
        inputs.forEach((input, index) => { input.value = saved?.[state][index] ?? (index === 2 ? "" : "0") })
      }
      setPreset()
    }
    if (event.target === mode) {
      setMode()
      layer.value = mode.value === "custom" ? "balance" : "arrival"
    }
    if (event.target === layer) redrawMap()
    else refresh()
  })
  selector.addEventListener("change", () => {
    updateState()
    geometry.eachLayer(paintState)
  })

  $("export").addEventListener("click", () => {
    const rows = [["crop", "scenario", "origin", "destination", "sent_t", "delivered_t", "hours", "shelf_hours_left", "freight_inr"],
      ...result.shipments.map(s => [crop.value, mode.value, s.from, s.to, s.sent.toFixed(3),
        s.delivered.toFixed(3), s.hours, s.headroom, (s.sent * s.cost).toFixed(2)])]
    const csv = rows.map(row => row.join(",")).join("\n")
    const link = document.createElement("a")
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }))
    link.download = `produce-relay-${crop.value.toLowerCase()}-${mode.value}.csv`
    link.click()
    setTimeout(() => URL.revokeObjectURL(link.href), 1000)
  })
  setPreset()
  setMode()
  updatePlan()
}

try {
  const [bundle, boundaries] = await Promise.all([readAsset("market.json"), readAsset("boundaries.json")])
  initialize(bundle, boundaries)
} catch (error) {
  $("initial-status").hidden = false
  $("initial-status").textContent = `The planner could not load. ${error.message}`
  console.error(error)
}
