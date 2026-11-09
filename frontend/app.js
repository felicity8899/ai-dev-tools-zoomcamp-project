// TableNow SPA: host dashboard + guest join, live via WebSocket, no build step.
import { formatEta, partyLabel } from "./lib/eta.js";

const $ = (id) => document.getElementById(id);
const state = { entries: [], tables: [] };

async function api(path, options = {}) {
  const resp = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) throw new Error(`API ${path} -> ${resp.status}`);
  return resp.json();
}

// --- rendering ---------------------------------------------------------------

function render() {
  const body = $("queue-body");
  body.innerHTML = "";
  $("queue-empty").hidden = state.entries.length > 0;

  for (const entry of state.entries) {
    const tr = document.createElement("tr");
    const seatBtn = document.createElement("button");
    seatBtn.className = "action";
    seatBtn.textContent = "Seat";
    seatBtn.onclick = () => seatEntry(entry);
    const noShowBtn = document.createElement("button");
    noShowBtn.className = "action";
    noShowBtn.textContent = "No-show";
    noShowBtn.onclick = () => post(`/waitlist/${entry.id}/no-show`);
    const leftBtn = document.createElement("button");
    leftBtn.className = "action";
    leftBtn.textContent = "Left";
    leftBtn.onclick = () => post(`/waitlist/${entry.id}/left`);

    tr.innerHTML = `<td>${entry.position}</td><td></td>
      <td>${partyLabel(entry.party_size)}</td>
      <td>${formatEta(entry.estimated_wait_minutes)}</td>`;
    tr.children[1].textContent = entry.name; // textContent: no HTML injection
    const actions = document.createElement("td");
    actions.append(seatBtn, noShowBtn, leftBtn);
    tr.append(actions);
    body.append(tr);
  }

  const tablesEl = $("tables");
  tablesEl.innerHTML = "";
  for (const table of state.tables) {
    const card = document.createElement("div");
    card.className = `table-card ${table.status}`;
    card.innerHTML = `<strong></strong><br>${table.capacity} seats<br><em>${table.status}</em>`;
    card.querySelector("strong").textContent = table.name;
    if (table.status === "occupied") {
      const btn = document.createElement("button");
      btn.textContent = "Free table";
      btn.onclick = () =>
        api(`/tables/${table.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "free" }),
        }).catch(() => refresh());
      card.append(btn);
    }
    tablesEl.append(card);
  }
}

async function post(path) {
  try {
    await api(path, { method: "POST" });
  } catch {
    refresh(); // fall back to a fresh snapshot if the action failed
  }
}

function seatEntry(entry) {
  const table = state.tables.find(
    (t) => t.status === "free" && t.capacity >= entry.party_size
  );
  if (!table) {
    alert(`No free table fits a party of ${entry.party_size} right now.`);
    return;
  }
  post2(entry, table);
}

async function post2(entry, table) {
  try {
    await api(`/waitlist/${entry.id}/seat`, {
      method: "POST",
      body: JSON.stringify({ table_id: table.id }),
    });
  } catch {
    refresh();
  }
}

async function refresh() {
  const data = await api("/waitlist").catch(() => null);
  if (!data) return;
  state.entries = data;
  state.tables = await api("/tables").catch(() => state.tables);
  render();
}

// --- live updates --------------------------------------------------------------

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => ($("conn").textContent = "● live");
  ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.type === "queue") {
      state.entries = data.entries;
      state.tables = data.tables;
      render();
    }
  };
  ws.onclose = () => {
    $("conn").textContent = "○ reconnecting…";
    setTimeout(connectWs, 2000);
  };
}

// --- views ---------------------------------------------------------------------

function show(view) {
  $("view-host").hidden = view !== "host";
  $("view-guest").hidden = view !== "guest";
  $("tab-host").classList.toggle("active", view === "host");
  $("tab-guest").classList.toggle("active", view === "guest");
}
$("tab-host").onclick = () => show("host");
$("tab-guest").onclick = () => show("guest");

// --- guest join ------------------------------------------------------------------

$("join-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("join-error").hidden = true;
  $("join-result").hidden = true;
  try {
    const entry = await api("/waitlist", {
      method: "POST",
      body: JSON.stringify({
        name: $("join-name").value.trim(),
        party_size: Number($("join-size").value),
        phone: $("join-phone").value.trim() || null,
      }),
    });
    const result = $("join-result");
    result.hidden = false;
    result.innerHTML =
      `<strong>You're on the list!</strong><br>` +
      `Position <strong>#${entry.position}</strong> · ` +
      `Estimated wait: <strong>${formatEta(entry.estimated_wait_minutes)}</strong>`;
    event.target.reset();
    $("join-size").value = 2;
  } catch {
    const err = $("join-error");
    err.hidden = false;
    err.textContent =
      "Sorry — joining the waitlist failed just now. Please try again in a moment.";
  }
});

// --- boot ------------------------------------------------------------------------

refresh();
connectWs();
