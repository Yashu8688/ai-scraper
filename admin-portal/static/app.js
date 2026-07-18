const state = {
  token: localStorage.getItem("token") || null,
  staffName: localStorage.getItem("staffName") || null,
};

const loginScreen = document.getElementById("login-screen");
const appScreen = document.getElementById("app-screen");

function authHeaders() {
  return { "Authorization": `Bearer ${state.token}`, "Content-Type": "application/json" };
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { ...authHeaders(), ...(opts.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || "Something went wrong.");
    err.status = res.status;
    throw err;
  }
  return data;
}

function showApp() {
  loginScreen.hidden = true;
  appScreen.hidden = false;
  document.getElementById("whoami-name").textContent = state.staffName;
  loadCompanies();
  loadStats();
}

function showLogin() {
  appScreen.hidden = true;
  loginScreen.hidden = false;
}

// ---------- login ----------
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("login-error");
  errEl.hidden = true;
  const staff_name = document.getElementById("staff-name").value.trim();
  const password = document.getElementById("password").value;

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ staff_name, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed.");
    state.token = data.token;
    state.staffName = data.staff_name;
    localStorage.setItem("token", state.token);
    localStorage.setItem("staffName", state.staffName);
    showApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.hidden = false;
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  localStorage.removeItem("token");
  localStorage.removeItem("staffName");
  state.token = null;
  showLogin();
});

// ---------- add company + live dedup check ----------
const nameInput = document.getElementById("f-name");
const websiteInput = document.getElementById("f-website");
const dupWarning = document.getElementById("dup-warning");
let dupCheckTimer = null;

function currentFormPayload() {
  return {
    name: nameInput.value.trim(),
    website: websiteInput.value.trim() || null,
    careers_url: document.getElementById("f-careers").value.trim() || null,
    platform: document.getElementById("f-platform").value,
    board_identifier: document.getElementById("f-board").value.trim() || null,
    state: document.getElementById("f-state").value.trim() || null,
    company_size: document.getElementById("f-size").value,
    recruiter_name: document.getElementById("f-recruiter-name").value.trim() || null,
    recruiter_contact: document.getElementById("f-recruiter-contact").value.trim() || null,
  };
}

async function liveDupCheck() {
  const payload = currentFormPayload();
  if (payload.name.length < 3) {
    dupWarning.hidden = true;
    return;
  }
  try {
    const res = await api("/api/companies/check-duplicate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (res.duplicate) {
      dupWarning.textContent = `Possible duplicate: "${res.match}" was added by ${res.added_by} on ${res.date_added}.`;
      dupWarning.hidden = false;
    } else {
      dupWarning.hidden = true;
    }
  } catch (_) { /* ignore live-check errors */ }
}

[nameInput, websiteInput].forEach((el) => {
  el.addEventListener("input", () => {
    clearTimeout(dupCheckTimer);
    dupCheckTimer = setTimeout(liveDupCheck, 450);
  });
});

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("add-error");
  const okEl = document.getElementById("add-success");
  errEl.hidden = true;
  okEl.hidden = true;

  const payload = currentFormPayload();
  if (!payload.name) {
    errEl.textContent = "Company name is required.";
    errEl.hidden = false;
    return;
  }

  const submitBtn = document.getElementById("submit-btn");
  submitBtn.disabled = true;
  submitBtn.textContent = "Adding…";

  try {
    await api("/api/companies", { method: "POST", body: JSON.stringify(payload) });
    okEl.textContent = `Added "${payload.name}".`;
    okEl.hidden = false;
    e.target.reset();
    dupWarning.hidden = true;
    loadCompanies();
    loadStats();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.hidden = false;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Add company";
  }
});

// ---------- company list ----------
const tbody = document.getElementById("companies-tbody");

function fmtDate(d) {
  if (!d) return "—";
  return d.substring(0, 10);
}

function fmtSize(size) {
  if (size === "small_mid") return "Small/Mid";
  if (size === "staffing_agency") return "Staffing Agency";
  if (size === "top_tier") return "Top Tier";
  return size || "—";
}

function renderCompanies(rows) {
  tbody.innerHTML = "";
  if (rows.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">No companies yet — add the first one.</td></tr>`;
    return;
  }
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.name)}</td>
      <td>${escapeHtml(fmtSize(r.company_size))}</td>
      <td><span class="platform-badge">${escapeHtml(r.platform)}</span></td>
      <td>${escapeHtml(r.state || "—")}</td>
      <td>${escapeHtml(r.added_by)}</td>
      <td>${fmtDate(r.date_added)}</td>
      <td>${fmtDate(r.last_shown_date)}</td>
      <td class="actions-cell">
        <button class="details-btn" data-id="${r.id}">Details</button>
        <button class="remove-btn" data-id="${r.id}">Remove</button>
      </td>
    `;
    tbody.appendChild(tr);

    const detailsTr = document.createElement("tr");
    detailsTr.className = "details-row";
    detailsTr.id = `details-${r.id}`;
    detailsTr.hidden = true;
    detailsTr.innerHTML = `
      <td colspan="8">
        <div class="details-content">
          <div class="details-grid">
            <div class="details-item">
              <span class="details-label">Website</span>
              <span class="details-val">${r.website ? `<a href="${escapeHtml(r.website.startsWith('http') ? r.website : 'https://' + r.website)}" target="_blank">${escapeHtml(r.website)}</a>` : '—'}</span>
            </div>
            <div class="details-item">
              <span class="details-label">Careers URL</span>
              <span class="details-val">${r.careers_url ? `<a href="${escapeHtml(r.careers_url)}" target="_blank">View Board</a>` : '—'}</span>
            </div>
            <div class="details-item">
              <span class="details-label">Board Token</span>
              <span class="details-val"><code>${escapeHtml(r.board_identifier || '—')}</code></span>
            </div>
            <div class="details-item">
              <span class="details-label">Recruiter Name</span>
              <span class="details-val">${escapeHtml(r.recruiter_name || '—')}</span>
            </div>
            <div class="details-item">
              <span class="details-label">Recruiter Contact</span>
              <span class="details-val">${escapeHtml(r.recruiter_contact || '—')}</span>
            </div>
          </div>
        </div>
      </td>
    `;
    tbody.appendChild(detailsTr);
  }

  tbody.querySelectorAll(".details-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const detailsRow = document.getElementById(`details-${btn.dataset.id}`);
      if (detailsRow) {
        detailsRow.hidden = !detailsRow.hidden;
        btn.textContent = detailsRow.hidden ? "Details" : "Hide";
        btn.classList.toggle("active", !detailsRow.hidden);
      }
    });
  });

  tbody.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Remove this company from the active list?")) return;
      try {
        await api(`/api/companies/${btn.dataset.id}`, { method: "DELETE" });
        loadCompanies();
        loadStats();
      } catch (err) {
        alert("Failed to remove company: " + err.message);
      }
    });
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function loadCompanies(q = "") {
  try {
    const rows = await api(`/api/companies${q ? `?q=${encodeURIComponent(q)}` : ""}`);
    renderCompanies(rows);
  } catch (err) {
    if (err.status === 401) { showLogin(); }
  }
}

let searchTimer = null;
document.getElementById("search-box").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadCompanies(e.target.value.trim()), 300);
});

// ---------- stats ----------
async function loadStats() {
  try {
    const s = await api("/api/stats");
    document.getElementById("stat-total").textContent = s.total_companies;
    document.getElementById("stat-today").textContent = s.added_today;
    document.getElementById("stat-due").textContent = s.due_for_next_export;
    const list = document.getElementById("stat-by-staff-list");
    list.innerHTML = "";
    if (s.by_staff_today.length === 0) {
      list.innerHTML = `<span class="tag">No entries yet today</span>`;
    } else {
      for (const row of s.by_staff_today) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = `${row.added_by}: ${row.c}`;
        list.appendChild(tag);
      }
    }
  } catch (err) {
    if (err.status === 401) { showLogin(); }
  }
}

// ---------- boot ----------
if (state.token) {
  showApp();
} else {
  showLogin();
}
