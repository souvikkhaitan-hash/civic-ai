// ===============================
// 🔐 AUTH CHECK
// ===============================
const token = localStorage.getItem("admin_token");
if (!token) {
  alert("Admin login required");
  window.location.href = "/admin-login-ui";
}

// ===============================
// 📦 LOAD COMPLAINTS
// ===============================
async function loadComplaints() {
  try {
    const res = await fetch("/admin/complaints", {
      headers: { Authorization: "Bearer " + token }
    });

    const data = await res.json();

    if (data.error) {
      alert("Session expired. Login again.");
      localStorage.removeItem("admin_token");
      window.location.href = "/admin-login-ui";
      return;
    }

    renderTable(data);
    updateStats(data);
  } catch (err) {
    console.error(err);
  }
}

// ===============================
// 📊 UPDATE STATS
// ===============================
function updateStats(data) {
  document.getElementById("total-count").innerText = data.length;
  document.getElementById("open-count").innerText =
    data.filter(c => c.status === "OPEN").length;
  document.getElementById("progress-count").innerText =
    data.filter(c => c.status === "IN_PROGRESS").length;
  document.getElementById("resolved-count").innerText =
    data.filter(c => c.status === "RESOLVED").length;
}

// ===============================
// 📋 TABLE RENDER
// ===============================
function renderTable(data) {
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = "";

  if (data.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="8" class="empty-row">No complaints found</td></tr>';
    return;
  }

  data.forEach(c => {
    const ids = c.ids && c.ids.length ? c.ids : [c.id];
    const idsJson = JSON.stringify(ids);

    const row = document.createElement("tr");
    row.innerHTML = `
      <td>#${c.id}</td>
      <td>
        ${escapeHtml(c.complaint)}
        ${c.count > 1 ? `<span class="badge badge-dup">×${c.count}</span>` : ""}
      </td>
      <td>${escapeHtml(c.department)}</td>
      <td>${c.priority}</td>
      <td>${renderStatusBadge(c.status)}</td>
      <td>${c.risk_score}</td>
      <td>${c.created_at}</td>
      <td>${renderActions(c.status, idsJson)}</td>
    `;
    tbody.appendChild(row);
  });
}

// ===============================
// 🏷 STATUS BADGE
// ===============================
function renderStatusBadge(status) {
  if (status === "OPEN") return '<span class="badge badge-open">Open</span>';
  if (status === "IN_PROGRESS") return '<span class="badge badge-progress">In Progress</span>';
  if (status === "RESOLVED") return '<span class="badge badge-resolved">Resolved</span>';
  return status;
}

// ===============================
// 🔘 ACTION BUTTONS
// ===============================
function renderActions(status, idsJson) {
  const safeIds = idsJson.replace(/'/g, "\\'");

  if (status === "OPEN") {
    return `
      <button onclick='updateStatus(${safeIds},"IN_PROGRESS")'>Start</button>
      <button onclick='deleteComplaint(${safeIds})'>Delete</button>
    `;
  }

  if (status === "IN_PROGRESS") {
    return `
      <button onclick='updateStatus(${safeIds},"RESOLVED")'>Resolve</button>
      <button onclick='undoStatus(${safeIds})'>Undo</button>
      <button onclick='deleteComplaint(${safeIds})'>Delete</button>
    `;
  }

  if (status === "RESOLVED") {
    return `
      <button onclick='undoStatus(${safeIds})'>Undo</button>
      <button onclick='deleteComplaint(${safeIds})'>Delete</button>
    `;
  }

  return "-";
}

// ===============================
// 🔁 UPDATE STATUS
// ===============================
async function updateStatus(ids, status) {
  for (const id of ids) {
    await fetch(`/complaints/${id}/status`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token
      },
      body: JSON.stringify({ status })
    });
  }
  loadComplaints();
}

// ===============================
// 🔁 UNDO STATUS (WORKS NOW)
// ===============================
async function undoStatus(ids) {
  for (const id of ids) {
    await fetch(`/complaints/${id}/undo`, {
      method: "PUT",
      headers: { Authorization: "Bearer " + token }
    });
  }
  loadComplaints();
}

// ===============================
// 🗑 DELETE
// ===============================
async function deleteComplaint(ids) {
  if (!confirm("Delete complaint(s)?")) return;

  for (const id of ids) {
    await fetch(`/complaints/${id}`, {
      method: "DELETE",
      headers: { Authorization: "Bearer " + token }
    });
  }

  loadComplaints();
}

// ===============================
// 🔍 SEARCH
// ===============================
function filterTable(value) {
  const rows = document.querySelectorAll("#table-body tr");
  value = value.toLowerCase();

  rows.forEach(row => {
    const text = row.innerText.toLowerCase();
    row.style.display = text.includes(value) ? "" : "none";
  });
}

// ===============================
// 🔐 SAFE TEXT
// ===============================
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ===============================
// 🚪 LOGOUT
// ===============================
function doLogout() {
  localStorage.removeItem("admin_token");
  window.location.href = "/admin-login-ui";
}

// ===============================
loadComplaints();