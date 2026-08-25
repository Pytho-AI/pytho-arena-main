const trainingId = decodeURIComponent(window.location.pathname.split("/").pop());
const FALLBACK_COLORS = ["#ff6b6b", "#72c9ff", "#ffc86a", "#68f0b1"];

const $ = (id) => document.getElementById(id);
const state = {
  status: null,
  colors: new Map(),
  names: new Map(),
  algorithms: new Map(),
  timer: null,
};
const agentName = (agent) => state.names.get(agent) || agent;

async function request(url) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `${response.status} ${response.statusText}`);
  return body;
}

function fmt(value) {
  const magnitude = Math.abs(value);
  const digits = magnitude >= 10 ? 1 : magnitude >= 1 ? 2 : 3;
  return value.toFixed(digits).replace("-", "−");
}

function niceTicks(low, high, count) {
  if (low === high) { low -= 1; high += 1; }
  const span = high - low;
  const base = Math.pow(10, Math.floor(Math.log10(span / count)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * base).find((s) => span / s <= count) || base * 10;
  const ticks = [];
  for (let v = Math.ceil(low / step) * step; v <= high + 1e-9; v += step) ticks.push(+v.toFixed(6));
  return ticks;
}

async function loadScenarioContext(status) {
  let colors = new Map();
  try {
    const record = await request(
      `/api/scenarios/${status.scenario_id}?version=${status.scenario_version}`,
    );
    const factions = new Map(record.scenario.factions.map((f) => [f.id, f.color]));
    colors = new Map(
      record.scenario.policy_bindings.map((b) => [b.id, factions.get(b.faction_id)]),
    );
    state.names = new Map(
      record.scenario.policy_bindings.filter((b) => b.name).map((b) => [b.id, b.name]),
    );
  } catch {
    state.names = new Map();
  }
  state.colors = new Map(
    status.binding_ids.map((agent, index) => [
      agent,
      colors.get(agent) || FALLBACK_COLORS[index % FALLBACK_COLORS.length],
    ]),
  );
}

async function loadAlgorithmContext() {
  try {
    const body = await request("/api/training-algorithms");
    state.algorithms = new Map(body.algorithms.map((algorithm) => [algorithm.id, algorithm]));
  } catch {
    state.algorithms = new Map();
  }
}

function drawChart(rootId, status, metric) {
  const root = $(rootId);
  const agents = status.binding_ids;
  const history = status.history;
  if (!history.length) {
    root.innerHTML = '<div class="muted chart-empty">No iterations recorded yet.</div>';
    return;
  }
  const total = status.config.iterations;
  const series = agents.map((agent) => history.map((entry) => entry[metric][agent] ?? 0));

  const W = 860, H = 250;
  const PAD = { t: 12, r: 16, b: 28, l: 56 };
  let low = Math.min(0, ...series.flat());
  let high = Math.max(0, ...series.flat());
  const padY = (high - low || 1) * 0.08;
  low -= padY; high += padY;

  const x = (i) => PAD.l + (total > 1 ? i / (total - 1) : 0) * (W - PAD.l - PAD.r);
  const y = (v) => PAD.t + (1 - (v - low) / (high - low)) * (H - PAD.t - PAD.b);

  let grid = "";
  for (const tick of niceTicks(low, high, 5)) {
    const stroke = tick === 0 ? "rgba(199,209,205,.45)" : "rgba(33,61,53,.9)";
    grid += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${y(tick)}" y2="${y(tick)}" stroke="${stroke}"/>`;
    grid += `<text x="${PAD.l - 8}" y="${y(tick) + 3.5}" text-anchor="end" class="tick">${fmt(tick)}</text>`;
  }
  for (const tick of niceTicks(0, Math.max(total - 1, 1), 8).filter(Number.isInteger)) {
    grid += `<text x="${x(tick)}" y="${H - 9}" text-anchor="middle" class="tick">${tick}</text>`;
  }

  let lines = "";
  agents.forEach((agent, k) => {
    const color = state.colors.get(agent);
    const path = series[k]
      .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
      .join("");
    lines += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round"/>`;
    const lastIndex = series[k].length - 1;
    lines += `<circle cx="${x(lastIndex)}" cy="${y(series[k][lastIndex])}" r="3.5"
      fill="${color}" stroke="#0d1916" stroke-width="2"/>`;
  });

  root.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${metric} per iteration">
      ${grid}${lines}
      <line class="cross" y1="${PAD.t}" y2="${H - PAD.b}" stroke="rgba(199,209,205,.5)"
        stroke-dasharray="3 3" opacity="0"/>
      ${agents.map((agent) => `<circle class="dot" r="4" fill="${state.colors.get(agent)}"
        stroke="#0d1916" stroke-width="1.5" opacity="0"/>`).join("")}
      <rect class="hit" x="${PAD.l}" y="${PAD.t}" width="${W - PAD.l - PAD.r}"
        height="${H - PAD.t - PAD.b}" fill="transparent"/>
    </svg>
    <div class="chart-tooltip"></div>`;

  const svg = root.querySelector("svg");
  const tooltip = root.querySelector(".chart-tooltip");
  const cross = root.querySelector(".cross");
  const dots = [...root.querySelectorAll(".dot")];
  const hit = root.querySelector(".hit");
  const points = history.length;

  function showAt(clientX) {
    const rect = svg.getBoundingClientRect();
    const sx = ((clientX - rect.left) / rect.width) * W;
    const fraction = (sx - PAD.l) / (W - PAD.l - PAD.r);
    const i = Math.max(0, Math.min(points - 1, Math.round(fraction * (total - 1))));
    cross.setAttribute("x1", x(i));
    cross.setAttribute("x2", x(i));
    cross.setAttribute("opacity", "1");
    dots.forEach((dot, k) => {
      dot.setAttribute("cx", x(i));
      dot.setAttribute("cy", y(series[k][i]));
      dot.setAttribute("opacity", "1");
    });
    tooltip.innerHTML =
      `<strong>iteration ${i}</strong>` +
      agents.map((agent, k) =>
        `<div><i style="background:${state.colors.get(agent)}"></i>` +
        `${agentName(agent)} ${fmt(series[k][i])}</div>`,
      ).join("");
    tooltip.style.display = "block";
    const px = (x(i) / W) * rect.width;
    const flip = px > rect.width * 0.6;
    tooltip.style.left = flip ? "auto" : `${px + 22}px`;
    tooltip.style.right = flip ? `${rect.width - px + 14}px` : "auto";
  }
  function hide() {
    tooltip.style.display = "none";
    cross.setAttribute("opacity", "0");
    dots.forEach((dot) => dot.setAttribute("opacity", "0"));
  }
  hit.addEventListener("mousemove", (event) => showAt(event.clientX));
  hit.addEventListener("mouseleave", hide);
  hit.addEventListener("touchstart", (event) => showAt(event.touches[0].clientX), { passive: true });
  hit.addEventListener("touchmove", (event) => showAt(event.touches[0].clientX), { passive: true });
  hit.addEventListener("touchend", hide);
}

function render(status) {
  const algorithmId = status.config.algorithm_id || "reinforce";
  const algorithm = state.algorithms.get(algorithmId);
  const parameters = status.config.algorithm_parameters || {
    gamma: status.config.gamma,
    entropy_coef: status.config.entropy_coef,
  };
  const parameterSummary = Object.entries(parameters)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => `${key.replaceAll("_", " ")} ${value}`)
    .join(" · ");
  $("status-badge").textContent =
    `${status.status} · ${status.iterations_done}/${status.config.iterations}`;
  $("training-id").textContent = `training ${status.training_id}`;
  $("training-meta").classList.remove("muted");
  $("training-meta").textContent = [
    `scenario ${status.scenario_id}@${status.scenario_version}`,
    `algorithm ${algorithm?.name || algorithmId} · ${algorithm?.family || "registered backend"}`,
    `bindings ${status.binding_ids.map(agentName).join(", ")}`,
    `batch ${status.config.batch_size} · lr ${status.config.learning_rate}`,
    parameterSummary ? `parameters ${parameterSummary}` : "parameters default",
    `seed ${status.config.seed} · device ${status.device || status.config.device}`,
    `physics ${status.physics_backend || "legacy"} · contract ` +
      `${status.environment_contract_hash?.slice(0, 12) || "legacy"}`,
    `started ${status.created_at.slice(0, 19).replace("T", " ")}` +
      (status.finished_at ? ` · finished ${status.finished_at.slice(0, 19).replace("T", " ")}` : ""),
  ].join("\n");
  $("loss-description").textContent = algorithm?.loss_description || "algorithm objective";

  const latest = status.history[status.history.length - 1];
  const outcomes = $("latest-returns");
  outcomes.replaceChildren();
  if (latest) {
    outcomes.classList.remove("muted");
    status.binding_ids.forEach((agent) => {
      const card = document.createElement("div");
      card.className = "faction-outcome";
      card.style.borderLeftColor = state.colors.get(agent);
      const name = document.createElement("strong");
      name.textContent = agentName(agent);
      const value = document.createElement("span");
      value.textContent =
        `return ${fmt(latest.returns[agent] ?? 0)} · loss ${fmt(latest.loss[agent] ?? 0)}`;
      card.append(name, value);
      outcomes.append(card);
    });
  } else {
    outcomes.textContent = "No iterations recorded yet.";
  }

  const errorNode = $("training-error");
  if (status.error) {
    errorNode.textContent = `Training failed: ${status.error}`;
    errorNode.classList.remove("hidden");
  } else {
    errorNode.classList.add("hidden");
  }

  const legend = $("legend");
  legend.replaceChildren();
  status.binding_ids.forEach((agent) => {
    const item = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.style.background = state.colors.get(agent);
    item.append(swatch, document.createTextNode(agentName(agent)));
    legend.append(item);
  });

  drawChart("returns-chart", status, "returns");
  drawChart("loss-chart", status, "loss");
}

async function refresh() {
  let status;
  try {
    status = await request(`/api/trainings/${encodeURIComponent(trainingId)}`);
  } catch (error) {
    if (state.timer) clearInterval(state.timer);
    $("status-badge").textContent = "not found";
    $("training-meta").textContent = error.message;
    return;
  }
  if (!state.colors.size) await loadScenarioContext(status);
  if (!state.algorithms.size) await loadAlgorithmContext();
  state.status = status;
  render(status);
  if (status.status !== "running" && state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
}

refresh();
state.timer = setInterval(() => {
  if (!state.status || state.status.status === "running") refresh();
}, 1000);
