// Vanilla JS only, deliberately: this app has no build step and no third-party
// dependency. Every data operation below calls the same /api/v1/* JSON API the
// CLI uses (see docs/api/CONTRACT.md) rather than duplicating any engine logic
// here. Session auth rides on the httponly cookie the login page sets, so
// fetch() calls never need to read or store a token themselves.

const state = {
  workspace: null,
  uploads: [],
};

function apiUrl(path, params = {}) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("workspace", state.workspace);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  return url.toString();
}

async function api(method, path, { params = {}, json = null, formData = null } = {}) {
  const options = { method, credentials: "same-origin" };
  if (formData) {
    options.body = formData;
  } else if (json !== null) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(json);
  }
  const response = await fetch(apiUrl(path, params), options);
  if (response.status === 401) {
    window.location.href = "/login?next=" + encodeURIComponent(window.location.href);
    throw new Error("unauthorized");
  }
  const body = await response.json();
  if (!response.ok || !body.ok) {
    const message = (body.errors && body.errors[0] && body.errors[0].message) || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return body.data;
}

// --- workspace loading ---

function showWorkspaceError(message) {
  const el = document.getElementById("workspace-error");
  el.textContent = message;
  el.hidden = !message;
}

async function loadWorkspace(workspace) {
  state.workspace = workspace;
  showWorkspaceError("");
  document.getElementById("app-main").hidden = true;
  try {
    await loadUploadLimits();
    await refreshUploads();
    document.getElementById("app-main").hidden = false;
    saveLastWorkspace(workspace);
  } catch (err) {
    showWorkspaceError(err.message);
    return;
  }
  // Zotero/dashboard/sources panel failures are shown inline in those
  // panels, not as a workspace-load error — none of them should block the
  // rest of the app from loading.
  refreshZoteroPanel();
  refreshDashboard();
  refreshSources();
  refreshResearchQuestions();
  refreshArtefacts();
  refreshClaims();
  refreshGuidelines();
  refreshProjectLog();
}

async function loadUploadLimits() {
  const limits = await api("GET", "/api/v1/artefacts/upload/limits");
  document.getElementById("upload-limits").textContent =
    `Up to ${limits.max_files} files per batch, ${limits.max_file_size_mb} MB each. ` +
    `Allowed types: ${limits.allowed_extensions.join(", ")}.`;
}

async function refreshUploads() {
  const uploads = await api("GET", "/api/v1/artefacts/uploads");
  state.uploads = uploads;
  renderUploadsTable(uploads);
}

function renderUploadsTable(uploads) {
  const tbody = document.getElementById("uploads-tbody");
  const empty = document.getElementById("uploads-empty");
  tbody.innerHTML = "";
  empty.hidden = uploads.length > 0;
  for (const upload of uploads) {
    const tr = document.createElement("tr");
    const crossRefCount = (upload.cross_references || []).length;
    tr.innerHTML = `
      <td>${escapeHtml(upload.title || "")}</td>
      <td>${escapeHtml(upload.original_file_name || "")}</td>
      <td>${escapeHtml(upload.renamed_file_name || "")}</td>
      <td>${crossRefCount}</td>
      <td class="row-actions"></td>
    `;
    const actions = tr.querySelector(".row-actions");

    const previewBtn = document.createElement("button");
    previewBtn.type = "button";
    previewBtn.textContent = "Preview";
    previewBtn.addEventListener("click", () => openPreview(upload));
    actions.appendChild(previewBtn);

    const crossRefBtn = document.createElement("button");
    crossRefBtn.type = "button";
    crossRefBtn.className = "secondary";
    crossRefBtn.textContent = "Cross-reference";
    crossRefBtn.addEventListener("click", () => openCrossReference(upload));
    actions.appendChild(crossRefBtn);

    tbody.appendChild(tr);
  }
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

// --- upload (drag-and-drop + browse) ---

function setupDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const browseLink = document.getElementById("browse-link");

  browseLink.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("click", (event) => {
    if (event.target === browseLink) return;
    fileInput.click();
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) uploadFiles(fileInput.files);
    fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    const files = event.dataTransfer && event.dataTransfer.files;
    if (files && files.length) uploadFiles(files);
  });
}

async function uploadFiles(fileList) {
  const formData = new FormData();
  for (const file of fileList) formData.append("files", file);

  const reportEl = document.getElementById("upload-report");
  reportEl.textContent = "Uploading...";
  try {
    const report = await api("POST", "/api/v1/artefacts/upload", { formData });
    renderUploadReport(report);
    await refreshUploads();
  } catch (err) {
    reportEl.textContent = "";
    showWorkspaceError(err.message);
  }
}

function renderUploadReport(report) {
  const reportEl = document.getElementById("upload-report");
  const rows = (report.rows || [])
    .map(
      (row) => `
      <tr>
        <td>${escapeHtml(row.file_name || "")}</td>
        <td>${escapeHtml(row.status || "")}</td>
        <td>${escapeHtml(row.reason || "")}</td>
      </tr>`
    )
    .join("");
  reportEl.innerHTML = `
    <p>Processed ${report.processed}: ${report.accepted} accepted, ${report.duplicate} duplicate,
       ${report.rejected} rejected, ${report.failed} failed.</p>
    <table class="data-table">
      <thead><tr><th>File</th><th>Status</th><th>Reason</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// --- preview modal ---

const TEXT_PREVIEW_EXTENSIONS = new Set([".txt", ".md", ".csv", ".json"]);
const IMAGE_PREVIEW_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"]);

function extensionOf(filename) {
  const idx = filename.lastIndexOf(".");
  return idx === -1 ? "" : filename.slice(idx).toLowerCase();
}

async function openPreview(upload) {
  const titleEl = document.getElementById("preview-title");
  const bodyEl = document.getElementById("preview-body");
  titleEl.textContent = upload.title || upload.renamed_file_name || "Preview";
  bodyEl.innerHTML = "Loading preview...";
  openModal("preview-modal");

  const ext = extensionOf(upload.renamed_file_name || "");
  const fileUrl = apiUrl(`/api/v1/artefacts/uploads/${encodeURIComponent(upload.upload_id)}/file`);

  if (ext === ".pdf") {
    bodyEl.innerHTML = `<iframe src="${fileUrl}" title="Preview"></iframe>`;
  } else if (IMAGE_PREVIEW_EXTENSIONS.has(ext)) {
    bodyEl.innerHTML = `<img src="${fileUrl}" alt="Preview">`;
  } else if (TEXT_PREVIEW_EXTENSIONS.has(ext)) {
    try {
      const response = await fetch(fileUrl, { credentials: "same-origin" });
      const text = await response.text();
      bodyEl.innerHTML = `<pre></pre>`;
      bodyEl.querySelector("pre").textContent = text;
    } catch (err) {
      bodyEl.textContent = "Could not load preview.";
    }
  } else {
    bodyEl.innerHTML = `<p>No inline preview available for ${escapeHtml(ext || "this file type")}.
      <a href="${fileUrl}" target="_blank" rel="noopener">Open in a new tab</a> instead.</p>`;
  }
}

// --- cross-reference review overlay ---

let crossRefUploadId = null;

async function openCrossReference(upload) {
  crossRefUploadId = upload.upload_id;
  const bodyEl = document.getElementById("crossref-body");
  bodyEl.innerHTML = "Loading candidates...";
  openModal("crossref-modal");
  await refreshCrossReferenceCandidates();
}

async function refreshCrossReferenceCandidates() {
  const bodyEl = document.getElementById("crossref-body");
  try {
    const report = await api("GET", "/api/v1/artefacts/cross-reference", { params: { upload_id: crossRefUploadId } });
    renderCrossReferenceCandidates(report.candidates || []);
  } catch (err) {
    bodyEl.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
  }
}

function renderCrossReferenceCandidates(candidates) {
  const bodyEl = document.getElementById("crossref-body");
  if (!candidates.length) {
    bodyEl.innerHTML = "<p class=\"muted\">No candidates found for this upload.</p>";
    return;
  }
  bodyEl.innerHTML = "";
  for (const candidate of candidates) {
    const row = document.createElement("div");
    row.className = "candidate-row";
    const statusClass = candidate.review_status === "accepted" || candidate.review_status === "approved"
      ? "accepted"
      : candidate.review_status === "rejected"
        ? "rejected"
        : "";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(candidate.target_title || candidate.target_id)}</strong>
        <span class="muted small">(${escapeHtml(candidate.target_kind)}, matched: ${
          (candidate.matched_keywords || []).join(", ")
        })</span>
        <div class="candidate-status ${statusClass}">${escapeHtml(candidate.review_status)}</div>
      </div>
      <div class="row-actions"></div>
    `;
    const actions = row.querySelector(".row-actions");
    const acceptBtn = document.createElement("button");
    acceptBtn.type = "button";
    acceptBtn.textContent = "Accept";
    acceptBtn.addEventListener("click", () => reviewCandidate(candidate, "accepted"));
    const rejectBtn = document.createElement("button");
    rejectBtn.type = "button";
    rejectBtn.className = "secondary";
    rejectBtn.textContent = "Reject";
    rejectBtn.addEventListener("click", () => reviewCandidate(candidate, "rejected"));
    actions.appendChild(acceptBtn);
    actions.appendChild(rejectBtn);
    bodyEl.appendChild(row);
  }
}

async function reviewCandidate(candidate, reviewStatus) {
  try {
    await api("POST", "/api/v1/artefacts/cross-reference/candidate-review", {
      params: { upload_id: crossRefUploadId },
      json: { target_kind: candidate.target_kind, target_id: candidate.target_id, review_status: reviewStatus },
    });
    await refreshCrossReferenceCandidates();
  } catch (err) {
    document.getElementById("crossref-body").insertAdjacentHTML(
      "afterbegin",
      `<p class="error">${escapeHtml(err.message)}</p>`
    );
  }
}

async function applyCrossReferenceLinks() {
  try {
    await api("POST", "/api/v1/artefacts/cross-reference/apply", { json: { upload_id: crossRefUploadId } });
    await refreshUploads();
    closeModal("crossref-modal");
  } catch (err) {
    document.getElementById("crossref-body").insertAdjacentHTML(
      "afterbegin",
      `<p class="error">${escapeHtml(err.message)}</p>`
    );
  }
}

// --- workspace dashboard ---

async function refreshDashboard() {
  const statsEl = document.getElementById("dashboard-stats");
  try {
    const counts = await api("GET", "/api/v1/projects/status");
    const tiles = [
      ["total", "Total"],
      ["pending_review", "Pending review"],
      ["accepted", "Accepted"],
      ["maybe", "Maybe"],
      ["ignored", "Ignored"],
    ];
    statsEl.innerHTML = tiles
      .map(
        ([key, label]) => `
        <div class="stat-tile">
          <span class="stat-value">${counts[key] || 0}</span>
          <span class="stat-label">${escapeHtml(label)}</span>
        </div>`
      )
      .join("");
  } catch (err) {
    statsEl.innerHTML = `<p class="error small">${escapeHtml(err.message)}</p>`;
  }

  try {
    const health = await api("GET", "/api/v1/projects/health");
    const ok = health.status === "ok";
    setStatusPill("dashboard-health-status", ok ? "OK" : "Needs review", ok ? "connected" : "error");
    const detailEl = document.getElementById("dashboard-health-detail");
    const problems = [];
    if ((health.missing_files || []).length) problems.push(`${health.missing_files.length} missing file(s)`);
    if ((health.missing_dirs || []).length) problems.push(`${health.missing_dirs.length} missing folder(s)`);
    if ((health.failed_conversions || []).length) problems.push(`${health.failed_conversions.length} failed conversion(s)`);
    if ((health.unsupported_files || []).length) problems.push(`${health.unsupported_files.length} unsupported file(s)`);
    detailEl.hidden = problems.length === 0;
    detailEl.textContent = problems.join(", ");
  } catch (err) {
    setStatusPill("dashboard-health-status", `Error: ${err.message}`, "error");
  }
}

// --- sources ---

state.sourceStatusFilter = "";
state.sourceEditId = null;

async function refreshSources() {
  const tbody = document.getElementById("sources-tbody");
  const emptyEl = document.getElementById("sources-empty");
  try {
    const params = state.sourceStatusFilter ? { status: state.sourceStatusFilter } : {};
    const sources = await api("GET", "/api/v1/sources", { params });
    renderSourcesTable(sources);
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

function renderSourcesTable(sources) {
  const tbody = document.getElementById("sources-tbody");
  const emptyEl = document.getElementById("sources-empty");
  tbody.innerHTML = "";
  emptyEl.hidden = sources.length > 0;
  for (const source of sources) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(source.file_name || "")}</td>
      <td class="muted small">${escapeHtml(source.provider || "")}</td>
      <td><span class="candidate-status">${escapeHtml(source.status || "")}</span></td>
      <td class="muted small">${escapeHtml((source.tags || []).join(", "))}</td>
      <td class="muted small">${escapeHtml(source.notes || "")}</td>
      <td class="row-actions"></td>
    `;
    const actions = tr.querySelector(".row-actions");
    for (const [status, label] of [["accepted", "Accept"], ["maybe", "Maybe"], ["ignored", "Ignore"]]) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.textContent = label;
      btn.disabled = source.status === status;
      btn.addEventListener("click", () => setSourceStatus(source.source_id, status));
      actions.appendChild(btn);
    }
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "secondary";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", () => openSourceEdit(source));
    actions.appendChild(editBtn);
    tbody.appendChild(tr);
  }
}

async function setSourceStatus(sourceId, newStatus) {
  try {
    await api("POST", `/api/v1/sources/${encodeURIComponent(sourceId)}/status`, { json: { new_status: newStatus } });
    await refreshSources();
    await refreshDashboard();
  } catch (err) {
    showWorkspaceError(err.message);
  }
}

function openSourceEdit(source) {
  state.sourceEditId = source.source_id;
  document.getElementById("source-edit-title").textContent = source.file_name || "Edit source";
  document.getElementById("source-edit-note-input").value = source.notes || "";
  document.getElementById("source-edit-tag-input").value = "";
  document.getElementById("source-edit-tags-list").textContent = (source.tags || []).join(", ") || "No tags yet.";
  document.getElementById("source-edit-message").hidden = true;
  openModal("source-edit-modal");
}

async function saveSourceEditNote() {
  const messageEl = document.getElementById("source-edit-message");
  const note = document.getElementById("source-edit-note-input").value;
  try {
    await api("POST", `/api/v1/sources/${encodeURIComponent(state.sourceEditId)}/note`, { json: { note } });
    messageEl.hidden = false;
    messageEl.className = "small";
    messageEl.textContent = "Note saved.";
    await refreshSources();
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "small error";
    messageEl.textContent = err.message;
  }
}

async function addSourceEditTag() {
  const messageEl = document.getElementById("source-edit-message");
  const tagInput = document.getElementById("source-edit-tag-input");
  const tag = tagInput.value.trim();
  if (!tag) return;
  try {
    await api("POST", `/api/v1/sources/${encodeURIComponent(state.sourceEditId)}/tags`, { json: { tag } });
    tagInput.value = "";
    const sources = await api("GET", "/api/v1/sources");
    const updated = sources.find((s) => s.source_id === state.sourceEditId);
    document.getElementById("source-edit-tags-list").textContent = ((updated && updated.tags) || []).join(", ") || "No tags yet.";
    await refreshSources();
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "small error";
    messageEl.textContent = err.message;
  }
}

async function scanSources() {
  const messageEl = document.getElementById("source-scan-message");
  const sourceRoot = document.getElementById("source-scan-root-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!sourceRoot) {
    messageEl.textContent = "Provide a folder path to scan.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Scanning...";
  try {
    const result = await api("POST", "/api/v1/sources/scan", { json: { source_root: sourceRoot } });
    messageEl.textContent =
      `Processed ${result.processed}: ${result.added} added, ${result.duplicates} duplicate, ${result.skipped} skipped.`;
    await refreshSources();
    await refreshDashboard();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupSourcesPanel() {
  document.querySelectorAll("#source-filter-tabs .filter-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#source-filter-tabs .filter-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.sourceStatusFilter = tab.dataset.status || "";
      refreshSources();
    });
  });
  document.getElementById("source-scan-btn").addEventListener("click", scanSources);
  document.getElementById("source-edit-save-note-btn").addEventListener("click", saveSourceEditNote);
  document.getElementById("source-edit-add-tag-btn").addEventListener("click", addSourceEditTag);
}

// --- research questions ---

async function refreshResearchQuestions() {
  try {
    const groups = await api("GET", "/api/v1/rqs");
    renderRqGroup("rq-candidates-list", "rq-candidates-empty", groups.candidates || [], "candidates");
    renderRqGroup("rq-approved-list", "rq-approved-empty", groups.approved || [], "approved");
    renderRqGroup("rq-rejected-list", "rq-rejected-empty", groups.rejected || [], "rejected");
  } catch (err) {
    showWorkspaceError(err.message);
  }
}

function renderRqGroup(listId, emptyId, items, group) {
  const listEl = document.getElementById(listId);
  const emptyEl = document.getElementById(emptyId);
  listEl.innerHTML = "";
  emptyEl.hidden = items.length > 0;
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "rq-row";
    const subquestions = (item.subquestions || [])
      .map((sq) => `<li>${escapeHtml(sq)}</li>`)
      .join("");
    const readiness = item.readiness
      ? `<span class="candidate-status">${escapeHtml(item.readiness.status)} (score ${item.readiness.score})</span>`
      : "";
    const reasonNote = group === "rejected" && item.reason ? `<p class="muted small">Reason: ${escapeHtml(item.reason)}</p>` : "";
    const statusNote = group === "rejected" ? `<p class="muted small">Status: ${escapeHtml(item.status || "")}</p>` : "";
    row.innerHTML = `
      <div class="rq-question">${escapeHtml(item.question || "")}</div>
      ${subquestions ? `<ul class="rq-subquestions">${subquestions}</ul>` : ""}
      <p>${readiness}</p>
      ${statusNote}
      ${reasonNote}
      <div class="row-actions"></div>
    `;
    const actions = row.querySelector(".row-actions");
    if (group === "candidates") {
      const approveBtn = document.createElement("button");
      approveBtn.type = "button";
      approveBtn.textContent = "Approve";
      approveBtn.addEventListener("click", () => rqAction(item.id, "approve"));
      actions.appendChild(approveBtn);
    }
    if (group === "candidates" || group === "approved") {
      const rejectBtn = document.createElement("button");
      rejectBtn.type = "button";
      rejectBtn.className = "secondary";
      rejectBtn.textContent = "Reject";
      rejectBtn.addEventListener("click", () => rqAction(item.id, "reject"));
      const archiveBtn = document.createElement("button");
      archiveBtn.type = "button";
      archiveBtn.className = "secondary";
      archiveBtn.textContent = "Archive";
      archiveBtn.addEventListener("click", () => rqAction(item.id, "archive"));
      actions.appendChild(rejectBtn);
      actions.appendChild(archiveBtn);
    }
    listEl.appendChild(row);
  }
}

async function rqAction(rqId, action) {
  try {
    await api("POST", `/api/v1/rqs/${encodeURIComponent(rqId)}/${action}`, { json: {} });
    await refreshResearchQuestions();
    await refreshDashboard();
  } catch (err) {
    showWorkspaceError(err.message);
  }
}

async function checkRqReadiness() {
  const messageEl = document.getElementById("rq-check-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("POST", "/api/v1/rqs/check", { json: {} });
    messageEl.textContent = `Checked ${report.checked_count} research question(s) — deterministic rules only, human review still required.`;
    await refreshResearchQuestions();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

// --- artefact registry ---

async function refreshArtefacts() {
  const tbody = document.getElementById("artefacts-tbody");
  const emptyEl = document.getElementById("artefacts-empty");
  try {
    const artefacts = await api("GET", "/api/v1/artefacts");
    tbody.innerHTML = "";
    emptyEl.hidden = artefacts.length > 0;
    for (const artefact of artefacts) {
      const tr = document.createElement("tr");
      const linkCount = (artefact.linked_sources || []).length + (artefact.linked_research_questions || []).length;
      tr.innerHTML = `
        <td>${escapeHtml(artefact.title || "")}</td>
        <td class="muted small">${escapeHtml(artefact.type || "")}</td>
        <td></td>
        <td class="muted small">${linkCount} linked</td>
        <td></td>
      `;
      const statusCell = tr.children[2];
      const select = document.createElement("select");
      for (const status of ["pending_review", "reviewed", "needs_revision", "accepted", "not_required"]) {
        const option = document.createElement("option");
        option.value = status;
        option.textContent = status;
        if (artefact.review_status === status) option.selected = true;
        select.appendChild(option);
      }
      select.addEventListener("change", () => setArtefactReviewStatus(artefact.id, select.value));
      statusCell.appendChild(select);
      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function setArtefactReviewStatus(artefactId, status) {
  try {
    await api("POST", `/api/v1/artefacts/${encodeURIComponent(artefactId)}/review`, { json: { status } });
    await refreshArtefacts();
  } catch (err) {
    showWorkspaceError(err.message);
  }
}

async function createArtefact() {
  const messageEl = document.getElementById("artefact-create-message");
  const artefactType = document.getElementById("artefact-create-type-select").value;
  const title = document.getElementById("artefact-create-title-input").value.trim();
  const includeMaybe = document.getElementById("artefact-create-include-maybe").checked;
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Creating...";
  try {
    const result = await api("POST", "/api/v1/artefacts/create", {
      json: { artefact_type: artefactType, title: title || null, include_maybe: includeMaybe },
    });
    messageEl.textContent = `Created: ${result.path}`;
    await refreshArtefacts();
    await refreshDashboard();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupRqAndArtefactPanels() {
  document.getElementById("rq-check-btn").addEventListener("click", checkRqReadiness);
  document.getElementById("artefact-create-btn").addEventListener("click", createArtefact);
}

// --- claims ledger ---

const CLAIM_STATUSES = ["active", "supported", "needs_evidence", "rejected", "needs_review"];

async function refreshClaims() {
  const tbody = document.getElementById("claims-tbody");
  const emptyEl = document.getElementById("claims-empty");
  try {
    const claims = await api("GET", "/api/v1/claims");
    tbody.innerHTML = "";
    emptyEl.hidden = claims.length > 0;
    for (const claim of claims) {
      const tr = document.createElement("tr");
      const linkCount = (claim.linked_sources || []).length + (claim.linked_research_questions || []).length;
      tr.innerHTML = `
        <td>${escapeHtml(claim.text || "")}</td>
        <td></td>
        <td class="muted small">${linkCount} linked</td>
      `;
      const statusCell = tr.children[1];
      const select = document.createElement("select");
      for (const status of CLAIM_STATUSES) {
        const option = document.createElement("option");
        option.value = status;
        option.textContent = status;
        if (claim.status === status) option.selected = true;
        select.appendChild(option);
      }
      select.addEventListener("change", () => setClaimStatus(claim.id, select.value));
      statusCell.appendChild(select);
      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function setClaimStatus(claimId, status) {
  try {
    await api("POST", `/api/v1/claims/${encodeURIComponent(claimId)}/status`, { json: { status } });
    await refreshClaims();
  } catch (err) {
    showWorkspaceError(err.message);
  }
}

async function addClaim() {
  const messageEl = document.getElementById("claim-add-message");
  const textInput = document.getElementById("claim-add-text-input");
  const text = textInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!text) {
    messageEl.textContent = "Claim text is required.";
    messageEl.classList.add("error");
    return;
  }
  try {
    await api("POST", "/api/v1/claims", { json: { text } });
    textInput.value = "";
    messageEl.textContent = "Claim added.";
    await refreshClaims();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showClaimGapReport() {
  const messageEl = document.getElementById("claim-report-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/claims/gaps");
    messageEl.textContent = `${report.gap_count} claim(s) with a citation gap.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showClaimValidationReport() {
  const messageEl = document.getElementById("claim-report-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/claims/validate");
    const rows = report.claims || [];
    const needsReview = rows.filter((row) => row.status !== "ok").length;
    messageEl.textContent = `${rows.length} claim(s) checked, ${needsReview} need review (missing or non-accepted linked source).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupClaimsPanel() {
  document.getElementById("claim-add-btn").addEventListener("click", addClaim);
  document.getElementById("claim-gaps-btn").addEventListener("click", showClaimGapReport);
  document.getElementById("claim-validate-btn").addEventListener("click", showClaimValidationReport);
}

// --- citation planning ---

let citationPlanState = null;

async function createCitationPlan() {
  const messageEl = document.getElementById("citation-plan-message");
  const target = document.getElementById("citation-target-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!target) {
    messageEl.textContent = "Provide a document target path.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Creating plan...";
  try {
    const result = await api("POST", "/api/v1/citations/plan", { json: { target } });
    citationPlanState = { target, insertions: result.plan.insertions || [] };
    messageEl.textContent = `Plan created: ${citationPlanState.insertions.length} proposed insertion(s).`;
    renderCitationInsertions();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function renderCitationInsertions() {
  const listEl = document.getElementById("citation-insertions-list");
  const emptyEl = document.getElementById("citation-insertions-empty");
  listEl.innerHTML = "";
  const insertions = (citationPlanState && citationPlanState.insertions) || [];
  emptyEl.hidden = insertions.length > 0;
  for (const insertion of insertions) {
    const row = document.createElement("div");
    row.className = "rq-row";
    row.innerHTML = `
      <div class="rq-question">${escapeHtml(insertion.target_sentence || "")}</div>
      <p class="muted small">
        Suggested: ${escapeHtml(insertion.suggested_inline_citation || "")}
        &middot; confidence: ${insertion.confidence_score != null ? insertion.confidence_score : "n/a"}
        &middot; <span class="candidate-status">${escapeHtml(insertion.review_status || "")}</span>
      </p>
      <div class="row-actions"></div>
    `;
    const actions = row.querySelector(".row-actions");
    const acceptBtn = document.createElement("button");
    acceptBtn.type = "button";
    acceptBtn.textContent = "Accept";
    acceptBtn.addEventListener("click", () => reviewCitationInsertion(insertion, "accepted"));
    const rejectBtn = document.createElement("button");
    rejectBtn.type = "button";
    rejectBtn.className = "secondary";
    rejectBtn.textContent = "Reject";
    rejectBtn.addEventListener("click", () => reviewCitationInsertion(insertion, "rejected"));
    actions.appendChild(acceptBtn);
    actions.appendChild(rejectBtn);
    listEl.appendChild(row);
  }
}

async function reviewCitationInsertion(insertion, reviewStatus) {
  const messageEl = document.getElementById("citation-plan-message");
  try {
    await api("POST", "/api/v1/citations/plan/insertion-review", {
      json: {
        target: citationPlanState.target,
        sentence_index: insertion.sentence_index,
        source_id: insertion.source_id,
        review_status: reviewStatus,
      },
    });
    insertion.review_status = reviewStatus;
    renderCitationInsertions();
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "small error";
    messageEl.textContent = err.message;
  }
}

async function applyCitationPlan() {
  const messageEl = document.getElementById("citation-plan-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!citationPlanState) {
    messageEl.textContent = "Create a plan first.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Applying...";
  try {
    const result = await api("POST", "/api/v1/citations/apply", { json: { target: citationPlanState.target } });
    messageEl.textContent = `Applied ${result.applied}, skipped ${result.skipped}. New version: ${result.version_id}.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupCitationPanel() {
  document.getElementById("citation-plan-btn").addEventListener("click", createCitationPlan);
  document.getElementById("citation-apply-btn").addEventListener("click", applyCitationPlan);
}

// --- guidelines ---

async function refreshGuidelines() {
  const tbody = document.getElementById("guidelines-tbody");
  const emptyEl = document.getElementById("guidelines-empty");
  try {
    const guidelines = await api("GET", "/api/v1/guidelines");
    tbody.innerHTML = "";
    emptyEl.hidden = guidelines.length > 0;
    for (const guideline of guidelines) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td></td>
        <td>${escapeHtml(guideline.title || "")}</td>
        <td class="muted small">${escapeHtml((guideline.scopes || []).join(", "))}</td>
      `;
      const checkboxCell = tr.children[0];
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.dataset.guidelineId = guideline.id;
      checkboxCell.appendChild(checkbox);
      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function registerGuideline() {
  const messageEl = document.getElementById("guideline-register-message");
  const source = document.getElementById("guideline-source-input").value.trim();
  const title = document.getElementById("guideline-title-input").value.trim();
  const scopesRaw = document.getElementById("guideline-scopes-input").value.trim();
  const scopes = scopesRaw ? scopesRaw.split(",").map((s) => s.trim()).filter(Boolean) : [];
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!source) {
    messageEl.textContent = "A source URL or local path is required.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Registering...";
  try {
    await api("POST", "/api/v1/guidelines", { json: { source, title: title || null, scopes } });
    messageEl.textContent = "Registered.";
    await refreshGuidelines();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function saveGuidelineDefaults() {
  const messageEl = document.getElementById("guideline-report-message");
  const checked = Array.from(document.querySelectorAll("#guidelines-tbody input[type=checkbox]:checked"));
  const guidelineIds = checked.map((box) => box.dataset.guidelineId);
  messageEl.hidden = false;
  messageEl.className = "small";
  try {
    await api("POST", "/api/v1/guidelines/defaults", { json: { guideline_ids: guidelineIds } });
    messageEl.textContent = `Saved ${guidelineIds.length} default guideline(s).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showGuidelineConflicts() {
  const messageEl = document.getElementById("guideline-report-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/guidelines/conflicts");
    messageEl.textContent = `${report.conflict_count} conflict(s) found across ${report.guidelines_checked.length} guideline(s).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupGuidelinesPanel() {
  document.getElementById("guideline-register-btn").addEventListener("click", registerGuideline);
  document.getElementById("guideline-save-defaults-btn").addEventListener("click", saveGuidelineDefaults);
  document.getElementById("guideline-conflicts-btn").addEventListener("click", showGuidelineConflicts);
}

// --- project log: decisions, terminology, feedback, context changelog ---

async function refreshProjectLog() {
  await Promise.all([refreshDecisions(), refreshTerminology(), refreshFeedback(), refreshContextChanges()]);
}

async function refreshDecisions() {
  const tbody = document.getElementById("decisions-tbody");
  const emptyEl = document.getElementById("decisions-empty");
  try {
    const rows = await api("GET", "/api/v1/decisions");
    tbody.innerHTML = rows
      .map((row) => `<tr><td>${escapeHtml(row.decision || "")}</td><td class="muted small">${escapeHtml(row.reason || "")}</td></tr>`)
      .join("");
    emptyEl.hidden = rows.length > 0;
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function addDecision() {
  const messageEl = document.getElementById("decision-add-message");
  const textInput = document.getElementById("decision-text-input");
  const reasonInput = document.getElementById("decision-reason-input");
  const text = textInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!text) {
    messageEl.textContent = "Decision text is required.";
    messageEl.classList.add("error");
    return;
  }
  try {
    await api("POST", "/api/v1/decisions", { json: { text, reason: reasonInput.value.trim() } });
    textInput.value = "";
    reasonInput.value = "";
    messageEl.textContent = "Added.";
    await refreshDecisions();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function refreshTerminology() {
  const tbody = document.getElementById("terminology-tbody");
  const emptyEl = document.getElementById("terminology-empty");
  try {
    const rows = await api("GET", "/api/v1/terminology");
    tbody.innerHTML = rows
      .map((row) => `<tr><td>${escapeHtml(row.term || "")}</td><td class="muted small">${escapeHtml(row.definition || "")}</td></tr>`)
      .join("");
    emptyEl.hidden = rows.length > 0;
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function addTerminology() {
  const messageEl = document.getElementById("terminology-add-message");
  const termInput = document.getElementById("terminology-term-input");
  const definitionInput = document.getElementById("terminology-definition-input");
  const term = termInput.value.trim();
  const definition = definitionInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!term || !definition) {
    messageEl.textContent = "Both a term and a definition are required.";
    messageEl.classList.add("error");
    return;
  }
  try {
    await api("POST", "/api/v1/terminology", { json: { term, definition } });
    termInput.value = "";
    definitionInput.value = "";
    messageEl.textContent = "Added.";
    await refreshTerminology();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function refreshFeedback() {
  const tbody = document.getElementById("feedback-tbody");
  const emptyEl = document.getElementById("feedback-empty");
  try {
    const rows = await api("GET", "/api/v1/feedback");
    tbody.innerHTML = rows
      .map(
        (row) =>
          `<tr><td class="muted small">${escapeHtml(row.source || "")}</td><td>${escapeHtml(row.text || "")}</td><td class="muted small">${escapeHtml(row.status || "")}</td></tr>`
      )
      .join("");
    emptyEl.hidden = rows.length > 0;
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function addFeedback() {
  const messageEl = document.getElementById("feedback-add-message");
  const textInput = document.getElementById("feedback-text-input");
  const sourceInput = document.getElementById("feedback-source-input");
  const text = textInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!text) {
    messageEl.textContent = "Feedback text is required.";
    messageEl.classList.add("error");
    return;
  }
  try {
    await api("POST", "/api/v1/feedback", { json: { text, source: sourceInput.value.trim() } });
    textInput.value = "";
    sourceInput.value = "";
    messageEl.textContent = "Added.";
    await refreshFeedback();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function refreshContextChanges() {
  const tbody = document.getElementById("context-tbody");
  const emptyEl = document.getElementById("context-empty");
  try {
    const rows = await api("GET", "/api/v1/context/changelog");
    tbody.innerHTML = rows.map((row) => `<tr><td>${escapeHtml(row.text || "")}</td></tr>`).join("");
    emptyEl.hidden = rows.length > 0;
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function addContextChange() {
  const messageEl = document.getElementById("context-add-message");
  const textInput = document.getElementById("context-text-input");
  const text = textInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!text) {
    messageEl.textContent = "Text is required.";
    messageEl.classList.add("error");
    return;
  }
  try {
    await api("POST", "/api/v1/context/changelog", { json: { text } });
    textInput.value = "";
    messageEl.textContent = "Added.";
    await refreshContextChanges();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupProjectLogPanel() {
  document.getElementById("decision-add-btn").addEventListener("click", addDecision);
  document.getElementById("terminology-add-btn").addEventListener("click", addTerminology);
  document.getElementById("feedback-add-btn").addEventListener("click", addFeedback);
  document.getElementById("context-add-btn").addEventListener("click", addContextChange);
}

// --- localStorage: remember the last-used workspace path ---

const LAST_WORKSPACE_KEY = "researchboss:lastWorkspace";

function saveLastWorkspace(workspace) {
  try {
    window.localStorage.setItem(LAST_WORKSPACE_KEY, workspace);
  } catch (err) {
    // Private browsing / storage disabled: not fatal, just skip persistence.
  }
}

function getLastWorkspace() {
  try {
    return window.localStorage.getItem(LAST_WORKSPACE_KEY) || "";
  } catch (err) {
    return "";
  }
}

// --- Zotero: link/unlink account, local status, basic browse ---
// "Basic perusal" only: read-only views over the same GET /api/v1/zotero/*
// routes the CLI's `researchboss zotero` commands use. Never writes inside
// the user's local Zotero directory (see AGENTS.md's Zotero no-write rule) —
// linking only saves API credentials into this workspace's own .env.

function setStatusPill(elId, text, cssClass) {
  const el = document.getElementById(elId);
  el.textContent = text;
  el.className = `candidate-status ${cssClass}`;
}

async function refreshZoteroPanel() {
  await Promise.all([refreshZoteroApiStatus(), refreshZoteroLocalStatus()]);
}

async function refreshZoteroApiStatus() {
  try {
    const report = await api("GET", "/api/v1/zotero/api/test");
    setStatusPill("zotero-api-status", `Connected (user ${report.user_id})`, "connected");
    if (report.key_has_write_access) {
      setStatusPill("zotero-api-status", `Connected (user ${report.user_id}) — key has write access, use read-only`, "error");
    }
  } catch (err) {
    if (/Missing ZOTERO_API_KEY|Missing ZOTERO_USER_ID/.test(err.message)) {
      setStatusPill("zotero-api-status", "Not linked", "not-connected");
    } else {
      setStatusPill("zotero-api-status", `Error: ${err.message}`, "error");
    }
  }
}

async function refreshZoteroLocalStatus() {
  const listEl = document.getElementById("zotero-collections-list");
  const emptyEl = document.getElementById("zotero-collections-empty");
  try {
    const collections = await api("GET", "/api/v1/zotero/local/collections");
    setStatusPill(
      "zotero-local-status",
      collections.length ? `Detected (${collections.length} collection${collections.length === 1 ? "" : "s"})` : "Detected (no collections)",
      "connected"
    );
    renderZoteroCollections(collections);
  } catch (err) {
    setStatusPill("zotero-local-status", "Not detected", "not-connected");
    listEl.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

function renderZoteroCollections(collections) {
  const listEl = document.getElementById("zotero-collections-list");
  const emptyEl = document.getElementById("zotero-collections-empty");
  listEl.innerHTML = "";
  emptyEl.hidden = collections.length > 0;
  for (const collection of collections) {
    const row = document.createElement("div");
    row.className = "zotero-collection-row";
    row.innerHTML = `
      <span>${escapeHtml(collection.name)}</span>
      <span class="muted small">${collection.item_count} item${collection.item_count === 1 ? "" : "s"}</span>
    `;
    listEl.appendChild(row);
  }
}

async function saveZoteroCredentials() {
  const messageEl = document.getElementById("zotero-link-message");
  const apiKeyInput = document.getElementById("zotero-api-key-input");
  const userIdInput = document.getElementById("zotero-user-id-input");
  const apiKey = apiKeyInput.value.trim();
  const userId = userIdInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!apiKey || !userId) {
    messageEl.textContent = "Both an API key and a user ID are required.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Linking...";
  try {
    await api("POST", "/api/v1/zotero/api/credentials", { json: { api_key: apiKey, user_id: userId } });
    apiKeyInput.value = "";
    userIdInput.value = "";
    messageEl.textContent = "Linked. Credentials saved to this workspace's .env — not shown again.";
    await refreshZoteroApiStatus();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function unlinkZoteroCredentials() {
  const messageEl = document.getElementById("zotero-link-message");
  try {
    await api("DELETE", "/api/v1/zotero/api/credentials");
    messageEl.hidden = false;
    messageEl.className = "small";
    messageEl.textContent = "Unlinked.";
    await refreshZoteroApiStatus();
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "small error";
    messageEl.textContent = err.message;
  }
}

async function searchZoteroLocal() {
  const query = document.getElementById("zotero-search-input").value.trim();
  const resultsEl = document.getElementById("zotero-search-results");
  if (!query) {
    resultsEl.innerHTML = "";
    return;
  }
  resultsEl.innerHTML = "<p class=\"muted small\">Searching...</p>";
  try {
    const hits = await api("GET", "/api/v1/zotero/local/search", { params: { query, limit: 20 } });
    if (!hits.length) {
      resultsEl.innerHTML = "<p class=\"muted small\">No matches.</p>";
      return;
    }
    resultsEl.innerHTML = "";
    for (const hit of hits) {
      const row = document.createElement("div");
      row.className = "zotero-search-hit";
      const fileName = (hit.file_path || "").split("/").pop();
      row.innerHTML = `
        <strong>${escapeHtml(fileName || hit.storage_key)}</strong>
        <span class="muted small">(matched: ${escapeHtml((hit.matched_terms || []).join(", "))})</span>
        ${hit.snippet ? `<p class="small muted">${escapeHtml(hit.snippet)}</p>` : ""}
      `;
      resultsEl.appendChild(row);
    }
  } catch (err) {
    resultsEl.innerHTML = `<p class="error small">${escapeHtml(err.message)}</p>`;
  }
}

function setupZoteroPanel() {
  document.getElementById("zotero-link-save-btn").addEventListener("click", saveZoteroCredentials);
  document.getElementById("zotero-link-unlink-btn").addEventListener("click", unlinkZoteroCredentials);
  document.getElementById("zotero-search-btn").addEventListener("click", searchZoteroLocal);
  document.getElementById("zotero-search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchZoteroLocal();
  });
}

// --- modal plumbing (shared by preview / cross-reference / about) ---

function openModal(id) {
  document.getElementById(id).hidden = false;
}

function closeModal(id) {
  document.getElementById(id).hidden = true;
}

function setupModals() {
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => closeModal(btn.dataset.close));
  });
  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) overlay.hidden = true;
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".modal-overlay").forEach((overlay) => {
      if (!overlay.hidden) overlay.hidden = true;
    });
  });
}

// --- wiring ---

function currentWorkspaceFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("workspace") || "";
}

function setWorkspaceInUrl(workspace) {
  const url = new URL(window.location.href);
  url.searchParams.set("workspace", workspace);
  window.history.replaceState({}, "", url.toString());
}

document.addEventListener("DOMContentLoaded", () => {
  setupDropzone();
  setupModals();
  setupZoteroPanel();
  setupSourcesPanel();
  setupRqAndArtefactPanels();
  setupClaimsPanel();
  setupCitationPanel();
  setupGuidelinesPanel();
  setupProjectLogPanel();

  const workspaceInput = document.getElementById("workspace-input");
  // Prefer an explicit ?workspace= URL param (e.g. from a bookmark or a
  // shared link); fall back to the last workspace remembered in this
  // browser so returning to / doesn't require retyping the path every time.
  const initialWorkspace = currentWorkspaceFromUrl() || getLastWorkspace();
  if (initialWorkspace) {
    workspaceInput.value = initialWorkspace;
    setWorkspaceInUrl(initialWorkspace);
    loadWorkspace(initialWorkspace);
  }

  document.getElementById("workspace-load").addEventListener("click", () => {
    const workspace = workspaceInput.value.trim();
    if (!workspace) return;
    setWorkspaceInUrl(workspace);
    loadWorkspace(workspace);
  });
  workspaceInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") document.getElementById("workspace-load").click();
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      await fetch("/api/v1/auth/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      window.location.href = "/login";
    }
  });

  document.getElementById("about-link").addEventListener("click", () => openModal("about-modal"));
  document.getElementById("crossref-apply-btn").addEventListener("click", applyCrossReferenceLinks);
});
