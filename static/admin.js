/**
 * 🏙️ CIVIC AI COMMAND CENTER - ADMIN LOGIC
 * Restored stable single-file version. No notifications. Correct status handling.
 */

// ===============================
// 📍 GLOBAL STATE
// ===============================
let map;
let markerLayer;
let activeCity = "Bangalore";

// ===============================
// 📦 DATA FETCHING
// ===============================
async function loadComplaints() {
  try {
    const res = await fetch("/admin/complaints", { credentials: "include" });
    const data = await res.json();

    if (data.error || !Array.isArray(data)) {
      console.warn("Dashboard error or unauthorized:", data.error || "Invalid response");
      if (data.error && data.error.includes("expired")) {
        window.location.href = "/admin-login-ui";
      }
      renderComplaints([]);
      updateStats([]);
      return;
    }

    renderComplaints(data);
    updateStats(data);
    updateMarkers(data);
  } catch (err) { console.error("Fetch error:", err); }
}

// ===============================
// 📊 STATS & SUMMARY
// ===============================
function updateStats(data) {
  document.getElementById("total-count").innerText = data.length;
  document.getElementById("open-count").innerText =
    data.filter(c => c.status && c.status.toLowerCase() === "open").length;
  document.getElementById("progress-count").innerText =
    data.filter(c => (c.status && c.status.toLowerCase() === "in progress") || (c.status && c.status.toLowerCase() === "in_progress")).length;
  document.getElementById("resolved-count").innerText =
    data.filter(c => c.status && c.status.toLowerCase() === "resolved").length;

  updateCitySummary(data);
}

function updateCitySummary(data) {
  const summaryContent = document.getElementById("summary-content");
  if (!summaryContent) return;

  if (!data || data.length === 0) {
    summaryContent.innerHTML = '<div class="summary-item">No active civic trends detected.</div>';
    return;
  }

  const highPriorityCount = data.filter(c => c.priority === "HIGH").length;
  const deptStats = {};
  data.forEach(c => { deptStats[c.department] = (deptStats[c.department] || 0) + 1; });

  const trends = [];
  if (deptStats["Sanitation"] > 2) trends.push("⚠️ Sanitation rising: Multiple hygiene risks detected.");
  if (deptStats["Drainage"] > 2) trends.push("🌊 Flood risk emerging: Drainage issues concentrated.");
  if (deptStats["Roads"] > 2) trends.push("🛣️ Infrastructure hazard: Increasing road/pothole reports.");
  if (deptStats["Electric"] > 2) trends.push("⚡ Public safety risk: Power/Lighting failures detected.");

  let summaryHtml = `
    <div class="summary-item" style="border-left-color: ${highPriorityCount > 0 ? '#dc2626' : '#3b82f6'}">
      <span style="font-size: 16px;">🔥</span> 
      <span style="color: ${highPriorityCount > 0 ? '#dc2626' : '#1e293b'}"><b>${highPriorityCount}</b> High Priority issues requiring immediate attention.</span>
    </div>
    <div class="summary-item">
      <span style="font-size: 16px;">🏢</span>
      <span>Top Departments: ${Object.entries(deptStats).sort((a, b) => b[1] - a[1]).slice(0, 2).map(d => `${d[0]} (${d[1]})`).join(", ")}</span>
    </div>
  `;

  if (trends.length > 0) {
    summaryHtml += `<div class="summary-item"><span style="font-size: 16px;">⚠️</span><span>${trends[0]}</span></div>`;
  } else {
    summaryHtml += `
      <div class="summary-item" style="border-left-color: #10b981">
        <span style="font-size: 16px;">✅</span>
        <span>Operational risk levels stable.</span>
      </div>
    `;
  }

  summaryContent.innerHTML = summaryHtml;
}

// ===============================
// 📋 TABLE RENDERING
// ===============================
function renderComplaints(data) {
  const tbody = document.getElementById("table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="13" class="empty-row">No complaints found</td></tr>';
    return;
  }

  data.forEach(c => {
    try {
      const riskClass = c.risk_score >= 70 ? "high-risk" : (c.risk_score >= 40 ? "medium-risk" : "low-risk");
      const row = document.createElement("tr");

      row.innerHTML = `
        <td>#${c.id}</td>
        <td>
          ${escapeHtml(c.complaint)}
          ${c.count > 1 ? `<span class="badge badge-dup">×${c.count}</span>` : ""}
        </td>
        <td>${escapeHtml(c.department)}</td>
        <td><span class="priority-${String(c.priority).toLowerCase()}">${c.priority}</span></td>
        <td>${renderStatusBadge(c.status)}</td>
        <td>${renderSourceBadge(c.source)}</td>
        <td>${c.image_path ? `<a href="/static/${c.image_path}" target="_blank">🖼️ View</a>` : "No proof"}</td>
        <td>
          <span class="tooltip ${riskClass}" data-tip="${escapeHtml(c.explanation || 'General risk').replace(/"/g, '&quot;')}">
            ${c.risk_score}
          </span>
        </td>
        <td>${renderConfidenceBar(c.risk_score)}</td>
        <td>${c.created_at}</td>
        <td>${renderSLABadge(c.status, c.risk_score)}</td>
        <td>${formatLocation(c)}</td>
        <td>${renderActions(c.status, c.id)}</td>
      `;
      tbody.appendChild(row);
    } catch (err) { console.error(`[RENDER ERROR] Failed #${c.id}:`, err); }
  });
}

function renderActions(status, id) {
  const s = status ? status.toLowerCase() : "";
  if (s === "open" || s === "") {
    return `
      <button class="start-btn" data-id="${id}">Start</button>
      <button class="delete-btn" data-id="${id}">Delete</button>
    `;
  }
  if (s === "in_progress" || s === "in progress") {
    return `
      <button class="resolve-btn" data-id="${id}">Resolve</button>
      <button class="undo-btn" data-id="${id}">Undo</button>
      <button class="delete-btn" data-id="${id}">Delete</button>
    `;
  }
  if (s === "resolved") {
    return `
      <button class="undo-btn" data-id="${id}">Undo</button>
      <button class="delete-btn" data-id="${id}">Delete</button>
    `;
  }
  return "-";
}

// ===============================
// 🔁 ACTION HANDLERS
// ===============================
async function handleAction(id, type, status = null) {
  let url = `/complaints/${id}/status`;
  let method = "PUT";
  let body = status ? JSON.stringify({ status }) : null;

  if (type === "undo") url = `/complaints/${id}/undo`;
  if (type === "delete") {
    if (!confirm("Delete?")) return;
    url = `/complaints/${id}`;
    method = "DELETE";
  }

  await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body
  });
  loadComplaints();
}

// ===============================
// 🏷 BADGE HELPERS
// ===============================
function renderStatusBadge(status) {
  const s = status ? status.toLowerCase() : "open";
  let cls = "open";
  let display = status || "Open";
  if (s === "in_progress" || s === "in progress") {
    cls = "progress";
    display = "In Progress";
  }
  if (s === "resolved") cls = "resolved";
  return `<span class="badge badge-${cls}">${display}</span>`;
}

function renderSourceBadge(source) {
  const map = { 'user': '👤 User', 'weather': '🌦 Weather', 'news': '📰 News', 'reddit': '📎 Reddit', 'ai': '🤖 AI' };
  return `<span class="badge badge-${source || 'user'}">${map[source] || '👤 User'}</span>`;
}

function renderSLABadge(status, riskScore) {
  const s = status ? status.toLowerCase() : "";
  if (s === "resolved") return '<span class="badge badge-safe tooltip" data-tip="Within SLA">Closed</span>';

  if (riskScore >= 90) {
    return '<span class="badge badge-breached tooltip" data-tip="SLA breached">Breached</span>';
  } else if (riskScore >= 70) {
    const hours = Math.max(1, Math.floor((95 - riskScore) / 2));
    return `<span class="badge badge-breached tooltip" data-tip="${hours} hours remaining">At Risk</span>`;
  }
  return '<span class="badge badge-safe tooltip" data-tip="Within SLA">Safe</span>';
}

function renderConfidenceBar(score) {
  const confidence = Math.min(100, Math.round(score * 1.3));
  const color = confidence > 70 ? "bg-green" : (confidence >= 40 ? "bg-orange" : "bg-red");
  return `
    <div class="confidence-container tooltip" data-tip="AI Confidence: ${confidence}%">
      <div class="confidence-bar-outer">
        <div class="confidence-bar-inner ${color}" style="width: ${confidence}%"></div>
      </div>
      <span class="confidence-text">${confidence}%</span>
    </div>
  `;
}

function formatLocation(c) {
  if (c.address && c.address !== "null") return "🏠 " + escapeHtml(c.address);
  if (c.manual_location && c.manual_location !== "null") return "📍 " + escapeHtml(c.manual_location);
  if (c.latitude && c.longitude) {
    return "📍 Bangalore (AI estimated)";
  }
  return "Unknown";
}

// ===============================
// 🌤 WEATHER & MAP
// ===============================
async function loadWeather(city) {
  try {
    const res = await fetch(city ? `/api/weather?city=${encodeURIComponent(city)}` : "/api/weather");
    const data = await res.json();
    document.getElementById("weather-temp").innerText = data.temperature + "°C";
    document.getElementById("weather-condition").innerText = data.condition;
    document.getElementById("weather-risk").innerText = data.risk_level;
    const card = document.querySelector(".weather-card");
    if (card) {
      if (data.risk_level === "HIGH") card.style.background = "linear-gradient(135deg,#4b0000,#a10000)";
      else if (data.risk_level === "MEDIUM") card.style.background = "linear-gradient(135deg,#5a3d00,#b8860b)";
      else card.style.background = "linear-gradient(135deg,#001f3f,#0074d9)";
    }
  } catch (e) { console.error("Weather error", e); }
}

async function syncLocation() {
  try {
    const res = await fetch("/admin/active-location");
    const data = await res.json();
    if (data.city) {
      activeCity = data.city;
      loadWeather(activeCity);
    } else { loadWeather(); }
  } catch (e) { loadWeather(); }
}

function updateMarkers(complaints) {
  if (!markerLayer || !map) return;
  markerLayer.clearLayers();

  const coords = [];
  complaints.forEach(c => {
    if (c.latitude && c.longitude) {
      const color = c.risk_score >= 70 ? "#ef4444" : (c.risk_score >= 40 ? "#f59e0b" : "#10b981");
      L.circleMarker([c.latitude, c.longitude], {
        radius: 9,
        fillColor: color,
        color: "#fff",
        weight: 3,
        fillOpacity: 1
      })
        .addTo(markerLayer)
        .bindPopup(`<b>${escapeHtml(c.complaint)}</b><br>Score: ${c.risk_score}`);
      coords.push([c.latitude, c.longitude]);
    }
  });

  if (coords.length > 0) {
    if (coords.length === 1) {
      map.setView(coords[0], 15);
    } else {
      map.fitBounds(coords, { padding: [50, 50] });
    }
  }
}

function addMapLegend() {
  if (!map) return;
  const legend = L.control({ position: 'topright' });
  legend.onAdd = function () {
    const div = L.DomUtil.create('div', 'info legend');
    div.style.background = "white";
    div.style.padding = "10px";
    div.style.borderRadius = "8px";
    div.style.boxShadow = "0 2px 10px rgba(0,0,0,0.2)";
    div.style.fontSize = "12px";
    div.innerHTML = `
            <h4 style="margin:0 0 5px">Severity Legend</h4>
            <i style="background:#ef4444; width:10px; height:10px; display:inline-block; border-radius:50%"></i> High Risk (70+)<br>
            <i style="background:#f59e0b; width:10px; height:10px; display:inline-block; border-radius:50%"></i> Medium (40-60)<br>
            <i style="background:#10b981; width:10px; height:10px; display:inline-block; border-radius:50%"></i> Low Risk (<40)
        `;
    return div;
  };
  legend.addTo(map);
}

// ===============================
// 🛠 UTILS
// ===============================
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function filterTable(value) {
  const rows = document.querySelectorAll("#table-body tr");
  value = value.toLowerCase();
  rows.forEach(row => { row.style.display = row.innerText.toLowerCase().includes(value) ? "" : "none"; });
}

function doLogout() { window.location.href = "/admin-login-ui"; }

// ===============================
// 🚀 INITIALIZATION
// ===============================
document.addEventListener("DOMContentLoaded", () => {
  console.log("[ADMIN] Initializing Dashboard...");
  if (document.getElementById("map") && !map) {
    map = L.map('map').setView([20, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    markerLayer = L.layerGroup().addTo(map);
  }
  addMapLegend();
  loadComplaints();
  syncLocation();

  document.addEventListener("click", (e) => {
    const id = e.target.dataset.id;
    if (!id) return;
    if (e.target.classList.contains("start-btn")) handleAction(id, "status", "In Progress");
    else if (e.target.classList.contains("resolve-btn")) handleAction(id, "status", "Resolved");
    else if (e.target.classList.contains("undo-btn")) handleAction(id, "undo");
    else if (e.target.classList.contains("delete-btn")) handleAction(id, "delete");
  });

  window.filterTable = filterTable;
  window.doLogout = doLogout;

  setInterval(loadComplaints, 10000);
  setInterval(() => loadWeather(activeCity), 60000);
});