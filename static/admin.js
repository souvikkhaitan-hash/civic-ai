let trafficLayer, markerLayer, map;
let activeLayers = { traffic: false, power: false, density: false };

/**
 * 🚀 INITIALIZATION & PERIODIC SYNC
 */
document.addEventListener("DOMContentLoaded", () => {
  console.log("[SYSTEM] Command Center Initializing...");

  // HARDENED POSITIONING ENGINE
  const config = window.ADMIN_CONFIG || {};
  const centerCoords = config.center || [12.9716, 77.5946];

  console.log(`[MAP] Centering on jurisdiction: ${centerCoords}`);

  map = L.map('map', { zoomControl: false }).setView(centerCoords, 14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
  markerLayer = L.layerGroup().addTo(map);
  trafficLayer = L.layerGroup().addTo(map);
  activeLayers.traffic = true;
  loadTrafficData();

  map.on('moveend', () => { if (activeLayers.traffic) loadTrafficData(); });

  loadComplaints();
  loadWeather(config.region.city);
  syncNotifications();

  // 2. Global Tooltip Engine
  const tooltip = document.createElement("div");
  tooltip.className = "custom-tooltip";
  tooltip.style.display = "none";
  document.body.appendChild(tooltip);

  document.addEventListener("mouseover", e => {
    const target = e.target.closest('[data-tooltip]');
    if (target) {
      tooltip.innerText = target.dataset.tooltip;
      tooltip.style.display = "block";
      const rect = target.getBoundingClientRect();
      tooltip.style.left = (rect.left + (rect.width / 2)) + "px";
      tooltip.style.top = (rect.top - 10) + "px";
      tooltip.style.transform = "translate(-50%, -100%)";
    }
  });

  document.addEventListener("mouseout", e => {
    if (e.target.closest('[data-tooltip]')) tooltip.style.display = "none";
  });

  // 3. Periodic Background Sync
  setInterval(loadComplaints, 20000);
  setInterval(syncNotifications, 5000);
});

/**
 * 📋 COMPLAINT DATA ENGINE
 */
async function loadComplaints() {
  try {
    const res = await fetch("/admin/complaints", { credentials: "include" });
    const data = await res.json();
    if (data.error || !Array.isArray(data)) return;
    renderComplaints(data);
    updateStats(data);
    updateMarkers(data);

    // AUTO ZOOM ENGINE
    if (data.length > 0 && markerLayer) {
      const validCoords = data.filter(c => c.latitude != null && c.longitude != null);
      if (validCoords.length > 0) {
        const bounds = L.latLngBounds(validCoords.map(c => [c.latitude, c.longitude]));
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
      }
    }
  } catch (err) { console.error("Fetch error:", err); }
}

function updateStats(data) {
  // CRITICAL ALERT: Count high-priority active cases
  const highPriorityCount = data.filter(c =>
    (c.priority && c.priority.toUpperCase() === "HIGH") &&
    (c.status && c.status.toLowerCase() !== "resolved")
  ).length;

  const criticalVal = document.getElementById("open-count");
  if (criticalVal) criticalVal.innerText = highPriorityCount;

  const deptStats = {};
  data.forEach(c => { deptStats[c.department] = (deptStats[c.department] || 0) + 1; });
  const sortedDepts = Object.entries(deptStats).sort((a, b) => b[1] - a[1]);
  const deptVal = document.getElementById("dept-focus-val");
  if (deptVal && sortedDepts.length > 0) {
    deptVal.innerHTML = `${sortedDepts[0][0]}<div style="font-size: 11px; color: #64748b;">${sortedDepts[0][1]} active cases</div>`;
  }
}

function renderComplaints(data) {
  const tbody = document.getElementById("table-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="12" style="padding: 40px; text-align: center; color: #94a3b8;">No active complaints in command cycle.</td></tr>';
    return;
  }

  data.forEach(c => {
    try {
      const row = document.createElement("tr");
      row.className = "complaint-row";
      const exp = parseExplanation(c.explanation);

      row.innerHTML = `
        <td class="id-badge">#C-${c.id}</td>
        <td>
          <div class="complaint-text">${escapeHtml(c.complaint)}</div>
          <div class="complaint-meta">${escapeHtml(c.translated_text || "--")}</div>
        </td>
        <td><span class="badge-pill" style="background:#f1f5f9; color:#475569;">${escapeHtml(c.department)}</span></td>
        <td><span class="badge-pill priority-${String(c.priority).toLowerCase()}">${c.priority}</span></td>
        <td>${renderSourceBadgeFinal(c.location_source)}</td>
        <td>
          <div data-tooltip="AI Risk Analysis:\n${escapeHtml(exp)}">
            ${renderRiskProgress(c.risk_score)}
          </div>
        </td>
        <td style="font-size: 11px; color: #64748b; white-space: nowrap;">${formatLocalDate(c.created_at)}</td>
        <td>${renderSLABadge(c.status, c.risk_score)}</td>
        <td>
          <div style="font-weight:700; color:#3b82f6; margin-bottom:6px; font-size:12px;">👤 ${escapeHtml(c.assigned_officer || c.department || 'Panchayat Officer')}</div>
          <select onchange="assignOfficer(this, ${c.id})" style="padding: 6px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 11px; width: 100%; outline: none; background: #fafafa;">
            <option value="">Align Officer...</option>
            <option value="Panchayat Officer">Panchayat Officer</option>
            <option value="Sanitation Worker">Sanitation Worker</option>
            <option value="Road Inspector">Road Inspector</option>
            <option value="Water Officer">Water Officer</option>
            <option value="Electricity Board">Electricity Board</option>
          </select>
        </td>
        <td style="font-size: 11px; color: #64748b; max-width: 250px; line-height: 1.4;">
          ${renderLocationLabel(c)}
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-top: 4px;">
            ${renderSourceBadgeFinal(c.location_source)}
          </div>
        </td>
        <td>
          ${c.proof_url
          ? `<img src="${c.proof_url}" 
                    style="width:40px;height:40px;border-radius:6px;cursor:pointer;object-fit:cover;border:1px solid #e2e8f0;"
                    onclick="window.open('${c.proof_url}', '_blank')">`
          : `<span style="color:#94a3b8; font-size:11px;">No proof</span>`
        }
        </td>
        <td class="action-cell">${renderActionsUI(c.status, c.id)}</td>
      `;
      tbody.appendChild(row);
    } catch (err) { console.error(`[RENDER ERROR] Failed #${c.id}:`, err); }
  });
}

function renderRiskProgress(score) {
  const s = Math.min(100, (score || 0));
  const color = s >= 70 ? "#ef4444" : (s >= 40 ? "#f59e0b" : "#10b981");
  return `<div class="risk-progress-container"><div class="risk-progress-bg"><div class="risk-progress-fill" style="width: ${s}%; background: ${color}"></div></div><span class="risk-label" style="color: ${color}">SCORE: ${s}</span></div>`;
}

function renderActionsUI(status, id) {
  const s = status ? status.toUpperCase() : "OPEN";
  if (s === "OPEN") {
    return `<button class="btn-ctrl send" title="Send" onclick="window.sendToOfficer(${id})">➤</button><button class="btn-ctrl delete" title="Purge" onclick="window.deleteComplaint(${id})">🗑</button>`;
  } else if (s === "ASSIGNED") {
    return `<span class="waiting-badge">Waiting...</span><button class="btn-ctrl delete" title="Purge" onclick="window.deleteComplaint(${id})">🗑</button>`;
  } else if (s === "IN_PROGRESS") {
    return `<span class="badge-pill" style="background:#dbeafe; color:#1e40af;">Running</span>`;
  }
  return `<span class="badge-pill" style="background:#dcfce7; color:#166534;">Closed</span>`;
}

function renderSourceBadge(source) {
  const map = { 'user': '👤 User', 'weather': '🌡 AI (Env)', 'news': '🗞 News', 'reddit': '💬 Social', 'ai': '🤖 System' };
  return `<span style="font-size: 13px; font-weight: 500; color: #64748b;">${map[source] || '👤 User'}</span>`;
}

function renderSLABadge(status, riskScore) {
  const s = status ? status.toLowerCase() : "";
  if (s === "resolved") return '<span class="status-pill" style="color: #10b981;">SAFE</span>';
  if (riskScore >= 90) return '<span class="status-pill" style="color: #ef4444; background: #fef2f2;">BREACHED</span>';
  if (riskScore >= 70) return '<span class="status-pill" style="color: #f59e0b; background: #fffbeb;">AT RISK</span>';
  return '<span class="status-pill" style="color: #3b82f6; background: #eff6ff;">SAFE</span>';
}

function formatLocalDate(utcStr) {
  if (!utcStr) return "--";
  const d = new Date(utcStr + " UTC");
  return d.toLocaleString('en-IN', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

async function loadWeather(city) {
  try {
    const res = await fetch(`/api/weather?city=${encodeURIComponent(city || 'Bengaluru')}`);
    const data = await res.json();
    document.getElementById("weather-temp") && (document.getElementById("weather-temp").innerText = data.temperature + "°C");
    document.getElementById("weather-condition") && (document.getElementById("weather-condition").innerText = data.condition);
    document.getElementById("weather-risk") && (document.getElementById("weather-risk").innerText = data.risk_level);
  } catch (e) { }
}

function updateMarkers(complaints) {
  if (!markerLayer || !map) return;
  markerLayer.clearLayers();
  complaints.forEach(c => {
    console.log("MARKER:", c.latitude, c.longitude);
    if (c.latitude != null && c.longitude != null) {
      const color = c.risk_score >= 70 ? "#ef4444" : (c.risk_score >= 40 ? "#f59e0b" : "#10b981");
      L.circleMarker([c.latitude, c.longitude], { radius: 9, fillColor: color, color: "#fff", weight: 3, fillOpacity: 1 }).addTo(markerLayer);
    }
  });
}

/**
 * 🗺 MAP OVERLAYS
 */
window.toggleLayer = function (layerName) {
  activeLayers[layerName] = !activeLayers[layerName];
  const btn = document.getElementById(`${layerName}-btn`);
  if (activeLayers[layerName]) {
    btn && btn.classList.add('active');
    if (layerName === 'traffic') loadTrafficData();
  } else {
    btn && btn.classList.remove('active');
    if (layerName === 'traffic') trafficLayer && trafficLayer.clearLayers();
  }
};

function loadTrafficData() {
  if (!map || !trafficLayer || !activeLayers.traffic) return;

  const config = window.ADMIN_CONFIG || {};
  const centerLat = config.center ? config.center[0] : map.getCenter().lat;
  const centerLng = config.center ? config.center[1] : map.getCenter().lng;

  trafficLayer.clearLayers();

  const step = 0.01;
  let delay = 0; // 🔥 IMPORTANT

  for (let i = -1; i <= 1; i++) {
    for (let j = -1; j <= 1; j++) {

      const lat = centerLat + (i * step);
      const lng = centerLng + (j * step);

      setTimeout(() => {
        fetch(`/api/traffic?lat=${lat}&lon=${lng}`)
          .then(res => res.json())
          .then(data => {
            if (!data || !data.congestion) return;

            const color =
              data.congestion === "HIGH" ? "#ef4444" :
                data.congestion === "MEDIUM" ? "#f59e0b" : "#10b981";

            if (data.coordinates && data.coordinates.length > 0) {
              const info = `${data.speed} km/h (${data.congestion})`;

              L.polyline(data.coordinates, {
                color: color,
                weight: 12,
                opacity: 1,
                lineJoin: 'round'
              })
                .addTo(trafficLayer)
                .bindTooltip(info, { sticky: true });
            }
          })
          .catch(err => console.log("Traffic fetch error:", err));

      }, delay); // ✅ THIS WAS MISSING

      delay += 200; // ✅ THIS WAS MISSING
    }
  }
}

/**
 * 🛠 HELPERS
 */
function parseExplanation(exp) {
  if (!exp) return "Baseline Intelligence Established.";
  try {
    let clean = exp.replace(/[\[\]']/g, "");
    return clean.split(',').map(s => `• ${s.trim()}`).join('\n');
  } catch (e) { return exp; }
}

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderLocationLabel(c) {
  const source = (c.location_source || "").toUpperCase();
  const addressStr = c.address || (c.latitude && c.longitude ? `${c.latitude.toFixed(5)}, ${c.longitude.toFixed(5)}` : (c.area || c.city || 'Rajanukunte'));

  return `<div style="font-weight:700; color:#1e293b;">📍 ${escapeHtml(addressStr)}</div>`;
}

function renderSourceBadgeFinal(source) {
  const s = (source || "").toLowerCase();

  if (s === "user") return '<span style="color: #10b981;">👤 User Reported</span>';
  if (s === "gps") return '<span style="color: #3b82f6;">🛰️ GPS Exact</span>';
  if (s === "user_selected") return '<span style="color: #6366f1;">✍️ Manual Area</span>';

  return '<span style="color: #f59e0b;">🤖 AI GENERATED</span>';
}

/**
 * ⚡ WINDOW-LEVEL EXPORTS
 */
window.assignOfficer = function (select, complaintId) {
  const officer = select.value;
  if (!officer) return;
  fetch("/assign-officer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ complaint_id: complaintId, officer }) }).then(() => loadComplaints());
};
window.sendToOfficer = function (complaintId) {
  fetch("/send-to-officer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ complaint_id: complaintId }) }).then(() => loadComplaints());
};
window.deleteComplaint = function (id) {
  if (confirm("Purge Record?")) fetch("/delete-complaint", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ complaint_id: id }) }).then(() => loadComplaints());
};
window.filterTable = function (val) {
  const rows = document.querySelectorAll("#table-body tr");
  rows.forEach(r => r.style.display = r.innerText.toLowerCase().includes(val.toLowerCase()) ? "" : "none");
};

/**
 * 🔔 NOTIFICATION ENGINE
 */
async function syncNotifications() {
  try {
    const res = await fetch("/notifications");
    const data = await res.json();
    const dropdown = document.getElementById("notif-dropdown");
    const badge = document.querySelector(".nav-badge");
    if (!dropdown) return;
    const unread = data.some(n => n.is_read === 0);
    if (badge) badge.style.display = unread ? "block" : "none";
    const header = '<div class="dropdown-header">Notifications</div>';
    dropdown.innerHTML = header + data.map(n => `
      <div class="dropdown-item" style="border-bottom: 1px solid #f1f5f9; cursor: default; padding: 12px; font-weight: ${n.is_read ? 'normal' : '700'};">
        <div style="font-size: 12px; color: #1e293b; margin-bottom: 4px;">${escapeHtml(n.message)}</div>
        <div style="font-size: 10px; color: #94a3b8;">${formatLocalDate(n.created_at)}</div>
      </div>
    `).join('');
  } catch (e) { }
}

window.toggleDropdown = async function (id) {
  const dropdown = document.getElementById(id);
  if (!dropdown) return;
  const isShowing = dropdown.classList.contains('show');
  document.querySelectorAll('.dropdown-menu').forEach(d => d.classList.remove('show'));
  if (!isShowing) {
    dropdown.classList.add('show');
    if (id === 'notif-dropdown') fetch("/notifications/read", { method: "POST" });
  }
  if (window.event) window.event.stopPropagation();
};

window.doLogout = function () {
  window.location.href = "/admin-logout";
};