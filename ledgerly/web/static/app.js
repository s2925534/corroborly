// Vanilla JS only, deliberately: this app has no build step and no third-party
// dependency. Every data operation below calls the same /api/v1/* JSON API the
// CLI uses (see docs/api/CONTRACT.md) rather than duplicating any engine logic
// here. Session auth rides on the httponly cookie the login page sets, so
// fetch() calls never need to read or store a token themselves.

const state = {
  workspace: null,
  uploads: [],
};

// --- theme (dark/light) ---
// Applied immediately, not inside DOMContentLoaded, so there's no
// flash-of-wrong-theme on load — `document.documentElement` (<html>)
// already exists as soon as the script tag runs.

const THEME_KEY = "ledgerly:theme";

function applyStoredTheme() {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    if (stored === "dark" || stored === "light") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (err) {
    // Private browsing / storage disabled: fall back to system preference via CSS media query.
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const effectiveCurrent = current || (prefersDark ? "dark" : "light");
  const next = effectiveCurrent === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try {
    window.localStorage.setItem(THEME_KEY, next);
  } catch (err) {
    // ignore
  }
}

applyStoredTheme();

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
  refreshDataSources();
  refreshNotes();
  refreshTranscribeJobs();
  refreshAiUsageLog();
  refreshStages();
  showSinceLastVisitDigest();
}

// A proactive "what changed since you were last here" banner, shown once
// per workspace open -- complements the on-demand research-progress log
// and stale-claims report with something surfaced automatically. Marks
// the workspace visited as a side effect of loading it (the API's default),
// so the next distinct visit starts a fresh window.
async function showSinceLastVisitDigest() {
  const panel = document.getElementById("digest-panel");
  const summaryEl = document.getElementById("digest-summary");
  const emptyEl = document.getElementById("digest-empty");
  try {
    const digest = await api("GET", "/api/v1/reports/digest");
    if (digest.is_first_visit) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    const hasActivity =
      digest.new_claim_count > 0 || digest.updated_claim_count > 0 || digest.activity_event_count > 0;
    emptyEl.hidden = hasActivity;
    summaryEl.textContent = hasActivity
      ? `Since ${digest.last_visited_at}: ${digest.new_claim_count} new claim(s), ${digest.updated_claim_count} updated claim(s), ${digest.activity_event_count} project-log event(s). ${digest.stale_open_claim_count} open claim(s) are stale.`
      : `${digest.stale_open_claim_count} open claim(s) are stale.`;
  } catch (err) {
    panel.hidden = true;
  }
}

async function loadUploadLimits() {
  const limits = await api("GET", "/api/v1/artefacts/upload/limits");
  document.getElementById("upload-limits").textContent =
    `Up to ${limits.max_files} files per batch, ${limits.max_file_size_mb} MB each. ` +
    `Allowed types: ${limits.allowed_extensions.join(", ")}.`;
}

state.uploadsView = "list";

async function refreshUploads() {
  const uploads = await api("GET", "/api/v1/artefacts/uploads");
  state.uploads = uploads;
  renderUploadsTable(uploads);
  renderUploadsGallery(uploads);
}

const GALLERY_TYPE_ICONS = {
  ".pdf": "\u{1F4C4}",
  ".doc": "\u{1F4C4}",
  ".docx": "\u{1F4C4}",
  ".txt": "\u{1F4C4}",
  ".md": "\u{1F4C4}",
  ".csv": "\u{1F4CA}",
  ".json": "\u{1F4CA}",
  ".xlsx": "\u{1F4CA}",
  ".xls": "\u{1F4CA}",
  ".ppt": "\u{1F4D1}",
  ".pptx": "\u{1F4D1}",
};
const GALLERY_DEFAULT_ICON = "\u{1F4C4}";

function setUploadsView(view) {
  state.uploadsView = view;
  document.getElementById("uploads-table").hidden = view !== "list";
  document.getElementById("uploads-gallery").hidden = view !== "gallery";
  document.getElementById("uploads-view-list-btn").disabled = view === "list";
  document.getElementById("uploads-view-gallery-btn").disabled = view === "gallery";
}

function renderUploadsGallery(uploads) {
  const galleryEl = document.getElementById("uploads-gallery");
  galleryEl.innerHTML = uploads
    .map((upload) => {
      const ext = extensionOf(upload.renamed_file_name || "");
      const label = upload.title || upload.original_file_name || upload.renamed_file_name || "";
      let thumbHtml;
      if (IMAGE_PREVIEW_EXTENSIONS.has(ext)) {
        const fileUrl = apiUrl(`/api/v1/artefacts/uploads/${encodeURIComponent(upload.upload_id)}/file`);
        thumbHtml = `<img src="${fileUrl}" alt="" loading="lazy">`;
      } else {
        thumbHtml = `<span class="gallery-icon">${GALLERY_TYPE_ICONS[ext] || GALLERY_DEFAULT_ICON}</span>`;
      }
      return `
        <div class="gallery-tile" data-upload-id="${escapeHtml(upload.upload_id)}" tabindex="0" role="button">
          <div class="gallery-thumb">${thumbHtml}</div>
          <div class="gallery-title">${escapeHtml(label)}</div>
        </div>`;
    })
    .join("");
  galleryEl.querySelectorAll(".gallery-tile").forEach((tile) => {
    const upload = uploads.find((u) => u.upload_id === tile.dataset.uploadId);
    if (!upload) return;
    tile.addEventListener("click", () => openPreview(upload));
    tile.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openPreview(upload);
      }
    });
  });
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

function statusBadgeClass(status) {
  const s = (status || "").toLowerCase();
  if (["accepted", "approved", "supported", "ok", "reviewed", "ready_for_review"].includes(s)) return "accepted";
  if (["rejected", "ignored", "archived", "failed", "not_ready"].includes(s)) return "rejected";
  if (s.includes("needs") || s.includes("pending") || s === "maybe" || s === "draft" || s === "active") return "warning";
  return "neutral";
}

function statusBadgeHtml(status) {
  const label = status || "unknown";
  return `<span class="candidate-status ${statusBadgeClass(status)}">${escapeHtml(label)}</span>`;
}

// A visual traffic-light for the deterministic grounding-check result
// (Phase 27's `grounding` field) -- green/yellow/red derived from
// `fully_grounded`/`uncited_paragraph_count`, never a new AI judgment call.
function groundingBadgeHtml(grounding) {
  if (!grounding) return "";
  let cls;
  let label;
  if (!grounding.fully_grounded) {
    cls = "rejected";
    label = `${grounding.ungrounded_citations.length} ungrounded citation(s)`;
  } else if (grounding.uncited_paragraph_count) {
    cls = "warning";
    label = `${grounding.uncited_paragraph_count} uncited paragraph(s)`;
  } else {
    cls = "accepted";
    label = "fully grounded";
  }
  return `<span class="candidate-status ${cls}" title="Deterministic grounding check (Phase 27)">${escapeHtml(label)}</span>`;
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
        <td>${statusBadgeHtml(row.status)}</td>
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
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(candidate.target_title || candidate.target_id)}</strong>
        <span class="muted small">(${escapeHtml(candidate.target_kind)}, matched: ${
          (candidate.matched_keywords || []).join(", ")
        })</span>
        <div>${statusBadgeHtml(candidate.review_status)}</div>
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

function lastActivityLabel(days) {
  if (days == null) return "no activity yet";
  return days === 0 ? "today" : `${days}d ago`;
}

async function refreshDashboard() {
  const statsEl = document.getElementById("dashboard-stats");
  try {
    const summary = await api("GET", "/api/v1/projects/dashboard");
    const sourceCounts = summary.source_counts || {};
    const claimCounts = summary.claim_counts || {};
    const tiles = [
      ["Sources", sourceCounts.total || 0],
      ["Pending review", sourceCounts.pending_review || 0],
      ["Accepted", sourceCounts.accepted || 0],
      ["Claims", claimCounts.total || 0],
      ["Artefacts", summary.artefact_count || 0],
      ["Open RQs", summary.open_research_question_count || 0],
      ["Last activity", lastActivityLabel(summary.days_since_last_activity)],
    ];
    statsEl.innerHTML = tiles
      .map(
        ([label, value]) => `
        <div class="stat-tile">
          <span class="stat-value">${escapeHtml(String(value))}</span>
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

function highlightSnippet(snippet) {
  // snippet() wraps matches in literal [ ] markers (see the `db_search`
  // SQL); escape the raw text first (it's untrusted corpus content), then
  // turn the still-intact bracket markers into <mark> tags.
  return escapeHtml(snippet).replace(/\[/g, "<mark>").replace(/\]/g, "</mark>");
}

async function searchCorpus() {
  const messageEl = document.getElementById("corpus-search-message");
  const resultsEl = document.getElementById("corpus-search-results");
  const query = document.getElementById("corpus-search-input").value.trim();
  resultsEl.innerHTML = "";
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!query) {
    messageEl.textContent = "Enter a search query.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Searching...";
  try {
    const result = await api("GET", "/api/v1/db/search", { params: { query } });
    if (result.report.status === "not_indexed") {
      messageEl.textContent = result.report.hint;
      return;
    }
    if (result.report.status === "invalid_query") {
      messageEl.textContent = `Invalid query: ${result.report.error}`;
      messageEl.classList.add("error");
      return;
    }
    const rows = result.report.results || [];
    if (!rows.length) {
      messageEl.textContent = "No matches.";
      return;
    }
    messageEl.hidden = true;
    resultsEl.innerHTML = rows
      .map(
        (row) => `
        <div class="rq-row">
          <div>
            <span class="candidate-status">${escapeHtml(row.doc_kind)}</span>
            <span class="muted small">${escapeHtml(row.path)}</span>
            <div>${highlightSnippet(row.snippet)}</div>
          </div>
        </div>`
      )
      .join("");
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function compareWorkspaces() {
  const messageEl = document.getElementById("compare-workspaces-message");
  const tableEl = document.getElementById("compare-workspaces-table");
  const tbody = document.getElementById("compare-workspaces-tbody");
  const paths = document
    .getElementById("compare-workspaces-input")
    .value.split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  messageEl.hidden = false;
  messageEl.className = "small";
  if (paths.length < 2) {
    messageEl.textContent = "Provide at least two workspace paths, one per line.";
    messageEl.classList.add("error");
    tableEl.hidden = true;
    return;
  }
  messageEl.textContent = "Comparing...";

  try {
    const url = new URL("/api/v1/projects/compare", window.location.origin);
    for (const path of paths) url.searchParams.append("workspaces", path);
    const response = await fetch(url.toString(), { credentials: "same-origin" });
    if (response.status === 401) {
      window.location.href = "/login?next=" + encodeURIComponent(window.location.href);
      return;
    }
    const body = await response.json();
    if (!response.ok || !body.ok) {
      throw new Error((body.errors && body.errors[0] && body.errors[0].message) || `Request failed (${response.status})`);
    }
    const rows = body.data.workspaces;
    tbody.innerHTML = rows
      .map(
        (row) => `
        <tr>
          <td>${escapeHtml(row.project_name || row.workspace)}</td>
          <td>${row.source_counts.total || 0}</td>
          <td>${row.claim_counts.total || 0}</td>
          <td>${row.artefact_count}</td>
          <td>${row.open_research_question_count}</td>
          <td>${escapeHtml(lastActivityLabel(row.days_since_last_activity))}</td>
        </tr>`
      )
      .join("");
    tableEl.hidden = false;
    messageEl.hidden = true;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
    tableEl.hidden = true;
  }
}

// --- AI-assisted features (explicit per-action opt-in, mirrors the CLI's --ai flag) ---

const AI_ACTION_ROUTES = {
  review: "/api/v1/ai/review",
  "corpus-summary": "/api/v1/ai/corpus-summary",
  "claim-check": "/api/v1/ai/claim-check",
  "citation-gaps": "/api/v1/ai/citation-gaps",
  "artefact-cross-reference": "/api/v1/ai/artefact-cross-reference",
  "source-relevance": "/api/v1/ai/source-relevance",
  "abstract-screening": "/api/v1/ai/abstract-screening",
  novelty: "/api/v1/ai/novelty",
  "rqs-assess": "/api/v1/ai/rqs/assess",
};

async function checkAiReadiness() {
  const messageEl = document.getElementById("ai-readiness-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const result = await api("POST", "/api/v1/ai/test", { json: { ai: false } });
    messageEl.textContent =
      `Key loaded: ${result.key_loaded}. Default model: ${result.default_model}. ` +
      "No live request was made (readiness check only, no workspace content sent).";
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function runAiAction() {
  const messageEl = document.getElementById("ai-run-message");
  const resultEl = document.getElementById("ai-run-result");
  const action = document.getElementById("ai-action-select").value;
  const optedIn = document.getElementById("ai-opt-in-checkbox").checked;
  const rqId = document.getElementById("ai-rq-id-input").value.trim();
  resultEl.innerHTML = "";
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!optedIn) {
    messageEl.textContent = "Check the consent box to run this AI action.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Running (this sends bounded excerpts to OpenAI)...";
  const body = { ai: true };
  if (action === "rqs-assess" && rqId) body.rq_id = rqId;
  try {
    const result = await api("POST", AI_ACTION_ROUTES[action], { json: body });
    if (result.insufficient_evidence) {
      messageEl.textContent = `Insufficient evidence. ${result.insufficient_evidence_reason}`;
      refreshAiUsageLog();
      return;
    }
    messageEl.hidden = true;
    const text = result.review || result.assessment || result.report || "";
    const grounding = result.grounding;
    let warningHtml = grounding ? `<p class="small">${groundingBadgeHtml(grounding)}</p>` : "";
    if (grounding && !grounding.fully_grounded) {
      warningHtml += `<p class="small error">Grounding warning: ${grounding.ungrounded_citations.length} citation(s) reference an ID not present in the supplied context -- verify manually before trusting them.</p>`;
    }
    if (grounding && grounding.uncited_paragraph_count) {
      warningHtml += `<p class="small">${grounding.uncited_paragraph_count} paragraph(s) have no citation marker at all -- treat as unsupported until verified.</p>`;
    }
    resultEl.innerHTML = `${warningHtml}<pre class="code-block"></pre>`;
    resultEl.querySelector("pre").textContent = text;
    // Re-require the consent checkbox for the next action — a deliberate
    // per-action opt-in, not a session-wide toggle, matching the CLI's
    // per-invocation --ai flag.
    document.getElementById("ai-opt-in-checkbox").checked = false;
    refreshAiUsageLog();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function refreshAiUsageLog() {
  const tbody = document.getElementById("ai-usage-log-tbody");
  const emptyEl = document.getElementById("ai-usage-log-empty");
  try {
    const entries = await api("GET", "/api/v1/ai/usage-log");
    tbody.innerHTML = "";
    emptyEl.hidden = entries.length > 0;
    for (const entry of entries) {
      const row = document.createElement("tr");
      const groundedBadge =
        entry.grounding_fully_grounded === null || entry.grounding_fully_grounded === undefined
          ? `<span class="candidate-status neutral">n/a</span>`
          : entry.grounding_fully_grounded
          ? `<span class="candidate-status accepted">yes</span>`
          : `<span class="candidate-status rejected">no</span>`;
      row.innerHTML = `
        <td>${escapeHtml(entry.timestamp || "")}</td>
        <td>${escapeHtml(entry.kind || "")}</td>
        <td>${entry.ai_used ? "yes" : "no"}</td>
        <td>${groundedBadge}</td>
        <td>${escapeHtml(entry.model || "")}</td>
      `;
      tbody.appendChild(row);
    }
  } catch (err) {
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
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
      <td>${statusBadgeHtml(source.status)}</td>
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

async function showSourceReviewReport() {
  const messageEl = document.getElementById("source-review-report-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/sources/report");
    const rows = report.sources || [];
    const notConverted = rows.filter((row) => row.conversion_status !== "converted").length;
    const untagged = rows.filter((row) => (row.tags || []).length === 0).length;
    const noNotes = rows.filter((row) => !row.has_notes).length;
    messageEl.textContent =
      `${rows.length} source(s): ${notConverted} not yet converted, ${untagged} untagged, ${noNotes} without notes.`;
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
  document.getElementById("source-review-report-btn").addEventListener("click", showSourceReviewReport);
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
      ? `<span class="candidate-status ${statusBadgeClass(item.readiness.status)}">${escapeHtml(item.readiness.status)} (score ${item.readiness.score})</span>`
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
        <td>${statusBadgeHtml(artefact.review_status)}</td>
        <td class="muted small">${linkCount} linked</td>
        <td></td>
      `;
      const statusCell = tr.children[4];
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
  const rqId = document.getElementById("artefact-create-rq-input").value.trim();
  const includeMaybe = document.getElementById("artefact-create-include-maybe").checked;
  messageEl.hidden = false;
  messageEl.className = "small";
  if (artefactType === "paper-draft" && !rqId) {
    messageEl.textContent = "Paper draft requires a research question ID.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Creating...";
  try {
    const result = await api("POST", "/api/v1/artefacts/create", {
      json: { artefact_type: artefactType, title: title || null, include_maybe: includeMaybe, rq_id: rqId || null },
    });
    messageEl.textContent = `Created: ${result.path}`;
    await refreshArtefacts();
    await refreshDashboard();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function registerArtefact() {
  const messageEl = document.getElementById("artefact-register-message");
  const title = document.getElementById("artefact-register-title-input").value.trim();
  const artefactType = document.getElementById("artefact-register-type-input").value.trim();
  const path = document.getElementById("artefact-register-path-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!title || !artefactType || !path) {
    messageEl.textContent = "Title, type, and path are all required.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Registering...";
  try {
    await api("POST", "/api/v1/artefacts", { json: { title, artefact_type: artefactType, path } });
    messageEl.textContent = "Registered.";
    await refreshArtefacts();
    await refreshDashboard();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function checkArtefactDependencies() {
  const messageEl = document.getElementById("artefact-dependencies-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/artefacts/dependencies");
    const needsReview = report.artefacts.filter((row) => row.status !== "ok").length;
    messageEl.textContent = `${report.artefacts.length} artefact(s) checked, ${needsReview} need review (missing/non-accepted linked source or unapproved linked research question).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupRqAndArtefactPanels() {
  document.getElementById("rq-check-btn").addEventListener("click", checkRqReadiness);
  document.getElementById("artefact-create-btn").addEventListener("click", createArtefact);
  document.getElementById("artefact-register-btn").addEventListener("click", registerArtefact);
  document.getElementById("artefact-dependencies-btn").addEventListener("click", checkArtefactDependencies);
}

// --- research stages ---

const STAGE_STATUSES = ["not_started", "in_progress", "blocked", "done"];

async function refreshStages() {
  const tbody = document.getElementById("stages-tbody");
  const emptyEl = document.getElementById("stages-empty");
  document.getElementById("stages-ics-link").href = apiUrl("/api/v1/stages/ics");
  try {
    const stages = await api("GET", "/api/v1/stages");
    tbody.innerHTML = "";
    emptyEl.hidden = stages.length > 0;
    for (const stage of stages) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${escapeHtml(stage.name || stage.id || "")}</td><td></td><td></td>`;

      const statusCell = tr.children[1];
      const select = document.createElement("select");
      for (const status of STAGE_STATUSES) {
        const option = document.createElement("option");
        option.value = status;
        option.textContent = status;
        if (stage.status === status) option.selected = true;
        select.appendChild(option);
      }
      select.addEventListener("change", () => setStageStatus(stage.id, select.value));
      statusCell.appendChild(select);

      const dateCell = tr.children[2];
      const dateInput = document.createElement("input");
      dateInput.type = "date";
      dateInput.value = stage.target_date || "";
      dateInput.addEventListener("change", () => setStageTargetDate(stage.id, dateInput.value || null));
      dateCell.appendChild(dateInput);

      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function setStageStatus(stageId, status) {
  try {
    await api("POST", `/api/v1/stages/${encodeURIComponent(stageId)}/status`, { json: { status } });
  } catch (err) {
    showWorkspaceError(err.message);
    refreshStages();
  }
}

async function setStageTargetDate(stageId, targetDate) {
  try {
    await api("POST", `/api/v1/stages/${encodeURIComponent(stageId)}/target-date`, {
      json: { target_date: targetDate },
    });
  } catch (err) {
    showWorkspaceError(err.message);
    refreshStages();
  }
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
        <td>${statusBadgeHtml(claim.status)}</td>
        <td class="muted small">${linkCount} linked</td>
        <td></td>
      `;
      const statusCell = tr.children[3];
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

async function showStaleClaimsReport() {
  const messageEl = document.getElementById("claim-report-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/claims/stale");
    messageEl.textContent = `${report.stale_count} open claim(s) not touched in ${report.days_threshold}+ days (${report.citation_gap_count} of those also have a citation gap).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showDuplicateClaimsReport() {
  const messageEl = document.getElementById("claim-report-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/claims/duplicates");
    messageEl.textContent = `${report.duplicate_pair_count} likely duplicate claim pair(s) found (similarity >= ${report.threshold}). Deterministic text similarity only -- review each pair before merging or dismissing.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function refreshCitationRelationships() {
  const listEl = document.getElementById("relationships-list");
  const emptyEl = document.getElementById("relationships-empty");
  try {
    const report = await api("GET", "/api/v1/reports/citation-relationships");
    const rows = report.sources || [];
    emptyEl.hidden = rows.length > 0;
    listEl.innerHTML = rows
      .map((source) => {
        const claimItems = (source.claims || [])
          .map((claim) => `<li>${escapeHtml(claim.text || claim.id)}</li>`)
          .join("");
        const artefactItems = (source.artefacts || [])
          .map((artefact) => `<li>${escapeHtml(artefact.title || artefact.id)}</li>`)
          .join("");
        return `
          <div class="rq-item">
            <strong>${escapeHtml(source.file_name || source.source_id)}</strong>
            ${statusBadgeHtml(source.status)}
            ${claimItems ? `<p class="muted small">Supports claims:</p><ul>${claimItems}</ul>` : ""}
            ${artefactItems ? `<p class="muted small">Used in artefacts:</p><ul>${artefactItems}</ul>` : ""}
          </div>`;
      })
      .join("");
  } catch (err) {
    listEl.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function refreshResearchProgress() {
  const listEl = document.getElementById("progress-list");
  const emptyEl = document.getElementById("progress-empty");
  try {
    const report = await api("GET", "/api/v1/reports/research-progress");
    const events = report.events || [];
    emptyEl.hidden = events.length > 0;
    listEl.innerHTML = events
      .map(
        (event) => `
        <div class="rq-row">
          <div>
            <span class="candidate-status">${escapeHtml(event.kind || "")}</span>
            <span class="muted small">${escapeHtml(formatTimelineTimestamp(event.at))}</span>
            <div>${escapeHtml(event.entity_id || "")}${event.detail ? ` — ${escapeHtml(event.detail)}` : ""}</div>
          </div>
        </div>`
      )
      .join("");
  } catch (err) {
    listEl.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

function setupClaimsPanel() {
  document.getElementById("claim-add-btn").addEventListener("click", addClaim);
  document.getElementById("claim-gaps-btn").addEventListener("click", showClaimGapReport);
  document.getElementById("claim-validate-btn").addEventListener("click", showClaimValidationReport);
  document.getElementById("claim-stale-btn").addEventListener("click", showStaleClaimsReport);
  document.getElementById("claim-duplicates-btn").addEventListener("click", showDuplicateClaimsReport);
}

// --- citation planning ---

let citationPlanState = null;

async function createCitationPlan() {
  const messageEl = document.getElementById("citation-plan-message");
  const target = document.getElementById("citation-target-input").value.trim();
  const citationStyle = document.getElementById("citation-style-select").value;
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!target) {
    messageEl.textContent = "Provide a document target path.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Creating plan...";
  try {
    const result = await api("POST", "/api/v1/citations/plan", { json: { target, citation_style: citationStyle } });
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
        &middot; ${statusBadgeHtml(insertion.review_status)}
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
          `<tr><td class="muted small">${escapeHtml(row.source || "")}</td><td>${escapeHtml(row.text || "")}</td><td>${statusBadgeHtml(row.status)}</td></tr>`
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

// --- document vault & version history ---

async function snapshotDocument() {
  const messageEl = document.getElementById("doc-snapshot-message");
  const target = document.getElementById("doc-snapshot-target-input").value.trim();
  const reason = document.getElementById("doc-snapshot-reason-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!target) {
    messageEl.textContent = "Provide a document target.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Snapshotting...";
  try {
    const record = await api("POST", "/api/v1/doc/version", { json: { target, reason: reason || "manual_snapshot" } });
    messageEl.textContent = `Snapshot created: ${record.version_id}.`;
    document.getElementById("doc-versions-target-input").value = target;
    await loadDocVersions();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function loadDocVersions() {
  const tbody = document.getElementById("doc-versions-tbody");
  const emptyEl = document.getElementById("doc-versions-empty");
  const target = document.getElementById("doc-versions-target-input").value.trim();
  try {
    const rows = await api("GET", "/api/v1/doc/versions", { params: target ? { target } : {} });
    tbody.innerHTML = "";
    emptyEl.hidden = rows.length > 0;
    for (const row of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(row.version_id || "")}</td>
        <td class="muted small">${escapeHtml(row.target || "")}</td>
        <td class="muted small">${escapeHtml(row.created_at || "")}</td>
        <td class="muted small">${escapeHtml(row.creation_reason || "")}</td>
        <td class="row-actions"></td>
      `;
      const restoreBtn = document.createElement("button");
      restoreBtn.type = "button";
      restoreBtn.className = "secondary";
      restoreBtn.textContent = "Restore";
      restoreBtn.addEventListener("click", () => restoreDocVersion(row.version_id));
      tr.querySelector(".row-actions").appendChild(restoreBtn);
      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function restoreDocVersion(versionId) {
  try {
    const record = await api("POST", "/api/v1/doc/restore", { json: { version_id: versionId } });
    document.getElementById("doc-diff-compare-message").hidden = false;
    document.getElementById("doc-diff-compare-message").className = "small";
    document.getElementById("doc-diff-compare-message").textContent = `Restored ${versionId} to ${record.restored_to_path || "a new copy"}.`;
  } catch (err) {
    showWorkspaceError(err.message);
  }
}

async function diffDocVersions() {
  const messageEl = document.getElementById("doc-diff-compare-message");
  const resultEl = document.getElementById("doc-diff-result");
  document.getElementById("doc-compare-result").innerHTML = "";
  const versionIdA = document.getElementById("doc-version-a-input").value.trim();
  const versionIdB = document.getElementById("doc-version-b-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!versionIdA || !versionIdB) {
    messageEl.textContent = "Provide both version IDs.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Diffing...";
  try {
    const report = await api("GET", "/api/v1/doc/diff", { params: { version_id_a: versionIdA, version_id_b: versionIdB } });
    messageEl.textContent = "";
    messageEl.hidden = true;
    if (!report.diff_supported) {
      resultEl.innerHTML = `<p class="muted small">${escapeHtml(report.reason || "Diff not supported for these file types.")}</p>`;
      return;
    }
    if (!report.lines.length) {
      resultEl.innerHTML = `<p class="muted small">No differences.</p>`;
      return;
    }
    resultEl.innerHTML = `<pre class="code-block"></pre>`;
    resultEl.querySelector("pre").textContent = report.lines.join("\n");
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function renderDiffList(title, addedRemoved) {
  const added = (addedRemoved && addedRemoved.added) || [];
  const removed = (addedRemoved && addedRemoved.removed) || [];
  if (!added.length && !removed.length) return "";
  return `
    <h4>${escapeHtml(title)}</h4>
    ${added.length ? `<p class="muted small">Added:</p><ul>${added.map((v) => `<li>${escapeHtml(v)}</li>`).join("")}</ul>` : ""}
    ${removed.length ? `<p class="muted small">Removed:</p><ul>${removed.map((v) => `<li>${escapeHtml(v)}</li>`).join("")}</ul>` : ""}
  `;
}

async function compareDocVersions() {
  const messageEl = document.getElementById("doc-diff-compare-message");
  const resultEl = document.getElementById("doc-compare-result");
  document.getElementById("doc-diff-result").innerHTML = "";
  const versionIdA = document.getElementById("doc-version-a-input").value.trim();
  const versionIdB = document.getElementById("doc-version-b-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!versionIdA || !versionIdB) {
    messageEl.textContent = "Provide both version IDs.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Comparing...";
  try {
    const report = await api("GET", "/api/v1/doc/compare", { params: { version_id_a: versionIdA, version_id_b: versionIdB } });
    messageEl.textContent = "";
    messageEl.hidden = true;
    if (!report.comparable) {
      resultEl.innerHTML = `<p class="muted small">${escapeHtml(report.reason || "Not comparable — both versions need a linked validation report.")}</p>`;
      return;
    }
    resultEl.innerHTML = `<div class="diff-summary">
      ${renderDiffList("Strengths", report.strengths)}
      ${renderDiffList("Weaknesses", report.weaknesses)}
      ${renderDiffList("Unsupported claims", report.unsupported_claims)}
      ${renderDiffList("Weakly supported claims", report.weakly_supported_claims)}
      ${renderDiffList("References", report.references)}
    </div>`;
    if (!resultEl.querySelector("h4")) {
      resultEl.innerHTML = `<p class="muted small">No differences between these two versions' validation reports.</p>`;
    }
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function buildDerivedTextAnchors() {
  const messageEl = document.getElementById("doc-derive-text-message");
  const versionId = document.getElementById("doc-derive-text-version-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!versionId) {
    messageEl.textContent = "Provide a version ID.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Building...";
  try {
    const snapshot = await api("POST", `/api/v1/doc/derive-text/${encodeURIComponent(versionId)}`, { json: {} });
    messageEl.textContent = `Built ${snapshot.paragraph_count} paragraph anchor(s) for ${snapshot.version_id}.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupDocVaultPanel() {
  document.getElementById("doc-snapshot-btn").addEventListener("click", snapshotDocument);
  document.getElementById("doc-versions-load-btn").addEventListener("click", loadDocVersions);
  document.getElementById("doc-diff-btn").addEventListener("click", diffDocVersions);
  document.getElementById("doc-compare-btn").addEventListener("click", compareDocVersions);
  document.getElementById("doc-derive-text-btn").addEventListener("click", buildDerivedTextAnchors);
}

// --- data sources, metadata quality, conversion, backup, db admin ---

async function refreshDataSources() {
  const statusLine = document.getElementById("data-status-line");
  const tbody = document.getElementById("data-sources-tbody");
  const emptyEl = document.getElementById("data-sources-empty");
  try {
    const counts = await api("GET", "/api/v1/data/status");
    statusLine.textContent = `${counts.total || 0} data source(s): ${counts.profiled || 0} profiled, ${counts.unprofiled || 0} unprofiled.`;
    const rows = await api("GET", "/api/v1/data");
    tbody.innerHTML = "";
    emptyEl.hidden = rows.length > 0;
    for (const row of rows) {
      const profiled = row.data_profile && row.data_profile.status === "profiled";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(row.file_name || "")}</td>
        <td class="muted small">${escapeHtml(row.file_ext || "")}</td>
        <td><span class="candidate-status ${profiled ? "connected" : "not-connected"}">${profiled ? "profiled" : "not profiled"}</span></td>
      `;
      tbody.appendChild(tr);
    }
  } catch (err) {
    statusLine.textContent = "";
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function profileDataSources() {
  const messageEl = document.getElementById("data-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Profiling...";
  try {
    const result = await api("POST", "/api/v1/data/profile", { json: {} });
    messageEl.textContent = `Processed ${result.processed}: ${result.profiled} profiled, ${result.skipped} skipped.`;
    await refreshDataSources();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupDataPanel() {
  document.getElementById("data-refresh-btn").addEventListener("click", refreshDataSources);
  document.getElementById("data-profile-btn").addEventListener("click", profileDataSources);
}

async function extractMetadata() {
  const messageEl = document.getElementById("metadata-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Extracting...";
  try {
    const result = await api("POST", "/api/v1/metadata/extract", { json: {} });
    messageEl.textContent = `Processed ${result.processed}, updated ${result.updated}.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function buildMetadataIndex() {
  const messageEl = document.getElementById("metadata-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Building index...";
  try {
    const result = await api("POST", "/api/v1/metadata/index", { json: {} });
    const entryCount = (result.entries || []).length;
    messageEl.textContent = `Keyword index built: ${entryCount} entr${entryCount === 1 ? "y" : "ies"}.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showMetadataValidation() {
  const messageEl = document.getElementById("metadata-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/metadata/validate");
    const needsReview = (report.sources || []).filter((s) => s.status !== "ok").length;
    messageEl.textContent = `${report.source_count} source(s) checked, ${needsReview} need review (missing citation fields or invalid DOI).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showMetadataDuplicates() {
  const messageEl = document.getElementById("metadata-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/metadata/duplicates");
    const groups = report.duplicate_groups || [];
    messageEl.textContent = `${groups.length} duplicate group(s) found.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupMetadataPanel() {
  document.getElementById("metadata-extract-btn").addEventListener("click", extractMetadata);
  document.getElementById("metadata-index-btn").addEventListener("click", buildMetadataIndex);
  document.getElementById("metadata-validate-btn").addEventListener("click", showMetadataValidation);
  document.getElementById("metadata-duplicates-btn").addEventListener("click", showMetadataDuplicates);
}

async function runConversion() {
  const messageEl = document.getElementById("conversion-message");
  const allowOcr = document.getElementById("conversion-ocr-checkbox").checked;
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Converting...";
  try {
    const result = await api("POST", "/api/v1/conversion/run", { json: { allow_ocr: allowOcr } });
    messageEl.textContent = `Processed ${result.processed}: ${result.converted} converted, ${result.skipped} skipped, ${result.failed} failed.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupConversionPanel() {
  document.getElementById("conversion-run-btn").addEventListener("click", runConversion);
}

async function createBackup() {
  const messageEl = document.getElementById("backup-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Creating backup...";
  try {
    const result = await api("POST", "/api/v1/backup", { json: {} });
    messageEl.textContent = `Backup created: ${result.backup_path}`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function inspectBackup() {
  const messageEl = document.getElementById("backup-message");
  const backupPath = document.getElementById("backup-inspect-path-input").value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!backupPath) {
    messageEl.textContent = "Provide a backup zip path.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Inspecting...";
  try {
    const report = await api("GET", "/api/v1/backup/inspect", { params: { backup_path: backupPath } });
    messageEl.textContent = `${report.file_count} file(s), ${report.total_uncompressed_bytes} bytes, ${report.contains_original_sources ? "includes" : "excludes"} original sources.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupBackupPanel() {
  document.getElementById("backup-create-btn").addEventListener("click", createBackup);
  document.getElementById("backup-inspect-btn").addEventListener("click", inspectBackup);
}

async function runDbAction(action, method, path) {
  const messageEl = document.getElementById("db-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = `Running ${action}...`;
  try {
    const result = await api(method, path, method === "POST" ? { json: {} } : {});
    messageEl.textContent = `${action} done. Database: ${result.database_path}.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupDbAdminPanel() {
  document.getElementById("db-init-btn").addEventListener("click", () => runDbAction("Init", "POST", "/api/v1/db/init"));
  document.getElementById("db-sync-btn").addEventListener("click", () => runDbAction("Sync", "POST", "/api/v1/db/sync"));
  document.getElementById("db-status-btn").addEventListener("click", () => runDbAction("Status", "GET", "/api/v1/db/status"));
  document.getElementById("db-rebuild-btn").addEventListener("click", () => runDbAction("Rebuild", "POST", "/api/v1/db/rebuild"));
  document.getElementById("db-pending-btn").addEventListener("click", () => runDbAction("Pending", "GET", "/api/v1/db/pending"));
  document.getElementById("db-apply-pending-btn").addEventListener("click", () => runDbAction("Apply pending", "POST", "/api/v1/db/apply-pending"));
  document.getElementById("db-privacy-btn").addEventListener("click", () => runDbAction("Privacy check", "GET", "/api/v1/db/privacy"));
}

async function runDbBackendAction(action, method, path, { confirmMessage } = {}) {
  const messageEl = document.getElementById("db-backend-message");
  if (confirmMessage && !window.confirm(confirmMessage)) return;
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = `Running ${action}...`;
  try {
    const result = await api(method, path, method === "POST" ? { json: {} } : {});
    messageEl.textContent = `${action}: ${JSON.stringify(result.report)}`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupDbBackendPanel() {
  document.getElementById("db-backend-status-btn").addEventListener("click", () =>
    runDbBackendAction("Status", "GET", "/api/v1/db/backend-status")
  );
  document.getElementById("db-backend-activate-btn").addEventListener("click", () =>
    runDbBackendAction("Activate", "POST", "/api/v1/db/activate-backend", {
      confirmMessage: "Activate the configured secondary backend and mirror the current SQLite cache into it?",
    })
  );
  document.getElementById("db-backend-deactivate-btn").addEventListener("click", () =>
    runDbBackendAction("Deactivate", "POST", "/api/v1/db/deactivate-backend")
  );
  document.getElementById("db-repair-sqlite-btn").addEventListener("click", () =>
    runDbBackendAction("Repair SQLite from backend", "POST", "/api/v1/db/repair-sqlite", {
      confirmMessage: "Recreate the local SQLite cache from the active secondary backend? Use this if the local SQLite file was lost.",
    })
  );
  document.getElementById("db-repair-backend-btn").addEventListener("click", () =>
    runDbBackendAction("Repair backend from SQLite", "POST", "/api/v1/db/repair-backend", {
      confirmMessage: "Re-mirror the active secondary backend from the current SQLite cache? Use this if the secondary backend was unreachable or lost data.",
    })
  );
}

// --- export & reporting ---

async function exportEvidence() {
  const messageEl = document.getElementById("export-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Exporting...";
  try {
    const result = await api("POST", "/api/v1/export/evidence", { json: {} });
    messageEl.textContent = `Evidence bundle written: ${result.bundle_path}`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function exportCorpus() {
  const messageEl = document.getElementById("export-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Exporting...";
  try {
    const result = await api("POST", "/api/v1/export/corpus", { json: {} });
    messageEl.textContent = `Corpus written: ${result.corpus_path} (${result.included_count} included, ${result.skipped_count} skipped).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function exportSupervisorBundle() {
  const messageEl = document.getElementById("export-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Exporting...";
  try {
    const result = await api("POST", "/api/v1/export/supervisor-bundle", { json: {} });
    messageEl.textContent = `Supervisor bundle written: ${result.bundle_path}`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showWorkspaceReport() {
  const resultEl = document.getElementById("report-result");
  resultEl.innerHTML = `<p class="muted small">Loading...</p>`;
  try {
    const report = await api("GET", "/api/v1/reports/workspace");
    resultEl.innerHTML = `<pre class="code-block"></pre>`;
    resultEl.querySelector("pre").textContent = report.markdown;
  } catch (err) {
    resultEl.innerHTML = `<p class="error small">${escapeHtml(err.message)}</p>`;
  }
}

function formatTimelineTimestamp(at) {
  if (!at) return "unknown time";
  const parsed = new Date(at);
  return Number.isNaN(parsed.getTime()) ? at : parsed.toLocaleString();
}

async function showTimelineReport() {
  const resultEl = document.getElementById("report-result");
  resultEl.innerHTML = `<p class="muted small">Loading...</p>`;
  try {
    const report = await api("GET", "/api/v1/reports/timeline");
    if (!report.events.length) {
      resultEl.innerHTML = `<p class="muted small">No timeline events yet.</p>`;
      return;
    }
    const rows = report.events
      .map((event) => {
        const label = event.text || event.command || event.path || event.id || "";
        return `
          <div class="rq-row">
            <div>
              <span class="candidate-status">${escapeHtml(event.kind || "")}</span>
              <span class="muted small">${escapeHtml(formatTimelineTimestamp(event.at))}</span>
              <div>${escapeHtml(label)}${event.status ? ` — ${escapeHtml(event.status)}` : ""}</div>
            </div>
          </div>`;
      })
      .join("");
    resultEl.innerHTML = `<div class="rq-list">${rows}</div>`;
  } catch (err) {
    resultEl.innerHTML = `<p class="error small">${escapeHtml(err.message)}</p>`;
  }
}

async function showReportSchemas() {
  const messageEl = document.getElementById("export-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Generating...";
  try {
    const result = await api("GET", "/api/v1/reports/schemas");
    messageEl.textContent = `${result.schema_count} report schema(s) written to ${result.markdown_path}.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showOcrReadiness() {
  const messageEl = document.getElementById("export-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/conversion/ocr-readiness");
    messageEl.textContent = `OCR supported locally: ${report.ocr_supported_locally}.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function showProcessingIssues() {
  const messageEl = document.getElementById("export-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/conversion/processing-issues");
    messageEl.textContent = `${report.issue_count} processing issue(s).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function runWatch() {
  const messageEl = document.getElementById("export-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Watching...";
  try {
    const report = await api("GET", "/api/v1/sources/watch");
    messageEl.textContent = `${report.candidate_count || 0} unregistered candidate file(s) found. Use "Scan a folder" in Sources to register them.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function runMergePdfs() {
  const messageEl = document.getElementById("merge-pdfs-message");
  const write = document.getElementById("merge-pdfs-write-checkbox").checked;
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Running...";
  try {
    const result = await api("POST", "/api/v1/export/merge-pdfs", { json: { write } });
    messageEl.textContent =
      `Included ${result.included}, skipped ${result.skipped}, failed ${result.failed}.` +
      (result.output_path ? ` PDF: ${result.output_path}.` : " (manifest only, no PDF written.)");
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupExportPanel() {
  document.getElementById("export-evidence-btn").addEventListener("click", exportEvidence);
  document.getElementById("export-corpus-btn").addEventListener("click", exportCorpus);
  document.getElementById("export-supervisor-bundle-btn").addEventListener("click", exportSupervisorBundle);
  document.getElementById("report-workspace-btn").addEventListener("click", showWorkspaceReport);
  document.getElementById("report-timeline-btn").addEventListener("click", showTimelineReport);
  document.getElementById("report-schemas-btn").addEventListener("click", showReportSchemas);
  document.getElementById("ocr-readiness-btn").addEventListener("click", showOcrReadiness);
  document.getElementById("processing-issues-btn").addEventListener("click", showProcessingIssues);
  document.getElementById("watch-btn").addEventListener("click", runWatch);
  document.getElementById("merge-pdfs-btn").addEventListener("click", runMergePdfs);
}

// --- localStorage: remember the last-used workspace path ---

const LAST_WORKSPACE_KEY = "ledgerly:lastWorkspace";

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
// routes the CLI's `ledgerly zotero` commands use. Never writes inside
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
    await refreshZoteroApiCollections();
  } catch (err) {
    if (/Missing ZOTERO_API_KEY|Missing ZOTERO_USER_ID/.test(err.message)) {
      setStatusPill("zotero-api-status", "Not linked", "not-connected");
    } else {
      setStatusPill("zotero-api-status", `Error: ${err.message}`, "error");
    }
    document.getElementById("zotero-api-collections-list").innerHTML = "";
    document.getElementById("zotero-api-collections-empty").hidden = false;
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
      <span><input type="checkbox" data-collection-key="${escapeHtml(collection.key)}"> ${escapeHtml(collection.name)}</span>
      <span class="muted small">${collection.item_count} item${collection.item_count === 1 ? "" : "s"}</span>
    `;
    listEl.appendChild(row);
  }
}

async function useSelectedZoteroCollections() {
  const messageEl = document.getElementById("zotero-collections-select-message");
  const checked = Array.from(document.querySelectorAll("#zotero-collections-list input[type=checkbox]:checked"));
  const collectionKeys = checked.map((box) => box.dataset.collectionKey);
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!collectionKeys.length) {
    messageEl.textContent = "Check at least one collection first.";
    messageEl.classList.add("error");
    return;
  }
  try {
    await api("POST", "/api/v1/zotero/local/collections/select", {
      json: { collection_keys: collectionKeys, include_subcollections: true },
    });
    messageEl.textContent = `Configured ${collectionKeys.length} selected collection(s) for future scans.`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function useEntireZoteroLibrary() {
  const messageEl = document.getElementById("zotero-collections-select-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  try {
    await api("POST", "/api/v1/zotero/local/use-entire-library", { json: {} });
    messageEl.textContent = "Configured to scan the entire local library.";
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function refreshZoteroApiCollections() {
  const listEl = document.getElementById("zotero-api-collections-list");
  const emptyEl = document.getElementById("zotero-api-collections-empty");
  try {
    const collections = await api("GET", "/api/v1/zotero/api/collections");
    listEl.innerHTML = "";
    emptyEl.hidden = collections.length > 0;
    for (const collection of collections) {
      const row = document.createElement("div");
      row.className = "zotero-collection-row";
      row.innerHTML = `<span><input type="checkbox" data-collection-key="${escapeHtml(collection.key || "")}"> ${escapeHtml(
        collection.name || collection.key || ""
      )}</span>`;
      listEl.appendChild(row);
    }
  } catch (err) {
    listEl.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function saveSelectedZoteroApiCollections() {
  const messageEl = document.getElementById("zotero-api-collections-select-message");
  const checked = Array.from(document.querySelectorAll("#zotero-api-collections-list input[type=checkbox]:checked"));
  const collectionKeys = checked.map((box) => box.dataset.collectionKey);
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!collectionKeys.length) {
    messageEl.textContent = "Check at least one Web API collection first.";
    messageEl.classList.add("error");
    return;
  }
  try {
    await api("POST", "/api/v1/zotero/api/collections/select", {
      json: { collection_keys: collectionKeys, include_subcollections: true },
    });
    messageEl.textContent = `Saved ${collectionKeys.length} selected Web API collection(s).`;
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function runZoteroReport(action, path) {
  const messageEl = document.getElementById("zotero-report-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = `Running ${action}...`;
  try {
    const report = await api("GET", path);
    if (report.snapshot_path) {
      messageEl.textContent = `Snapshot written: ${report.snapshot_path}`;
    } else if (report.bibtex_path) {
      messageEl.textContent = `${report.entries} entr${report.entries === 1 ? "y" : "ies"} written to ${report.bibtex_path}.`;
    } else if (report.duplicates) {
      messageEl.textContent = `${report.duplicates.length} duplicate group(s) found.`;
    } else if (report.total_attachments !== undefined) {
      messageEl.textContent = `${report.total_attachments} attachment(s): ${report.missing_title.length} missing title, ${report.missing_year.length} missing year, ${report.missing_doi.length} missing DOI.`;
    } else if (report.sqlite_attachments !== undefined) {
      messageEl.textContent = `${report.storage_files} storage file(s), ${report.sqlite_attachments} SQLite attachment(s), ${report.missing_attachment_files.length} missing, ${report.unlinked_storage_files.length} unlinked.`;
    } else if (report.with_fulltext_cache !== undefined) {
      messageEl.textContent = `${report.total_sources} source(s): ${report.with_fulltext_cache} with fulltext cache, ${report.without_fulltext_cache} without.`;
    } else {
      messageEl.textContent = `${action} done.`;
    }
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
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
  if (!window.confirm("Unlink this Zotero Web API account? You'll need to re-enter the API key to reconnect.")) return;
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
  document.getElementById("zotero-use-selected-btn").addEventListener("click", useSelectedZoteroCollections);
  document.getElementById("zotero-use-entire-library-btn").addEventListener("click", useEntireZoteroLibrary);
  document.getElementById("zotero-api-use-selected-btn").addEventListener("click", saveSelectedZoteroApiCollections);
  document.getElementById("zotero-metadata-report-btn").addEventListener("click", () => runZoteroReport("metadata report", "/api/v1/zotero/local/metadata-report"));
  document.getElementById("zotero-attachment-health-btn").addEventListener("click", () => runZoteroReport("attachment health", "/api/v1/zotero/local/attachment-health"));
  document.getElementById("zotero-fulltext-report-btn").addEventListener("click", () => runZoteroReport("fulltext report", "/api/v1/zotero/local/fulltext-report"));
  document.getElementById("zotero-duplicates-btn").addEventListener("click", () => runZoteroReport("duplicates", "/api/v1/zotero/local/duplicates"));
  document.getElementById("zotero-snapshot-btn").addEventListener("click", () => runZoteroReport("snapshot", "/api/v1/zotero/local/snapshot"));
  document.getElementById("zotero-export-bibtex-btn").addEventListener("click", () => runZoteroReport("BibTeX export", "/api/v1/zotero/local/export-bibtex"));
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

// --- global keyboard shortcuts ---
// Deliberately small and conservative: single unmodified keys, and only
// while the workspace is loaded and focus isn't in a text field (so typing
// a claim, note, etc. never triggers one by accident). Documented in the
// About modal — keep that list in sync with this table.
const KEYBOARD_SHORTCUTS = [
  { key: "u", description: "Jump to Upload artefacts" },
  { key: "/", description: "Jump to and focus Search corpus" },
  { key: "?", description: "Show this shortcuts list (opens About)" },
  { key: "Escape", description: "Close an open dialog" },
];

function isTypingTarget(target) {
  if (!target) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (isTypingTarget(event.target)) return;
    if (document.getElementById("app-main").hidden) return;

    if (event.key === "u") {
      const dropzone = document.getElementById("dropzone");
      dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
      dropzone.focus();
    } else if (event.key === "/") {
      event.preventDefault();
      const searchInput = document.getElementById("corpus-search-input");
      searchInput.scrollIntoView({ behavior: "smooth", block: "center" });
      searchInput.focus();
    } else if (event.key === "?") {
      openModal("about-modal");
    }
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

// --- personal notes, meeting notes, transcripts ---

function renderNotes(notes) {
  const tbody = document.getElementById("notes-tbody");
  const emptyEl = document.getElementById("notes-empty");
  tbody.innerHTML = "";
  emptyEl.hidden = notes.length > 0;
  for (const note of notes) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="muted small">${escapeHtml(note.kind || "")}</td>
      <td>${escapeHtml(note.text || "")}</td>
      <td class="muted small">${escapeHtml((note.tags || []).join(", "))}</td>
      <td class="muted small">${escapeHtml(note.source_label || "")}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshNotes() {
  const tbody = document.getElementById("notes-tbody");
  const emptyEl = document.getElementById("notes-empty");
  try {
    const notes = await api("GET", "/api/v1/notes");
    renderNotes(notes);
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function addNote() {
  const messageEl = document.getElementById("note-add-message");
  const textInput = document.getElementById("note-add-text-input");
  const kindSelect = document.getElementById("note-add-kind-select");
  const tagsInput = document.getElementById("note-add-tags-input");
  const text = textInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!text) {
    messageEl.textContent = "Note text is required.";
    messageEl.classList.add("error");
    return;
  }
  const tags = tagsInput.value.trim() ? tagsInput.value.split(",").map((t) => t.trim()).filter(Boolean) : [];
  try {
    await api("POST", "/api/v1/notes", { json: { text, kind: kindSelect.value, tags } });
    textInput.value = "";
    tagsInput.value = "";
    messageEl.textContent = "Added.";
    await refreshNotes();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function importNoteTranscript() {
  const messageEl = document.getElementById("note-import-message");
  const pathInput = document.getElementById("note-import-path-input");
  const path = pathInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!path) {
    messageEl.textContent = "Provide a file path.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Importing...";
  try {
    await api("POST", "/api/v1/notes/import-transcript", { json: { path } });
    pathInput.value = "";
    messageEl.textContent = "Imported.";
    await refreshNotes();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function searchNotesPanel() {
  const query = document.getElementById("note-search-input").value.trim();
  if (!query) {
    await refreshNotes();
    return;
  }
  try {
    const notes = await api("GET", "/api/v1/notes/search", { params: { query } });
    renderNotes(notes);
  } catch (err) {
    showWorkspaceError(err.message);
  }
}

function setupNotesPanel() {
  document.getElementById("note-add-btn").addEventListener("click", addNote);
  document.getElementById("note-import-btn").addEventListener("click", importNoteTranscript);
  document.getElementById("note-search-btn").addEventListener("click", searchNotesPanel);
  document.getElementById("note-search-clear-btn").addEventListener("click", () => {
    document.getElementById("note-search-input").value = "";
    refreshNotes();
  });
  document.getElementById("note-search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchNotesPanel();
  });
}

// --- audio/video transcription (SourceScribe, subprocess) ---

async function checkTranscribeReadiness() {
  const messageEl = document.getElementById("transcribe-readiness-message");
  messageEl.hidden = false;
  messageEl.className = "small";
  messageEl.textContent = "Checking...";
  try {
    const report = await api("GET", "/api/v1/transcription/readiness");
    if (report.available) {
      messageEl.textContent = `Available at ${report.sourcescribe_path}. Supported: ${report.supported_extensions.join(", ")}.`;
    } else {
      messageEl.textContent = report.reason;
      messageEl.classList.add("error");
    }
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function refreshTranscribeJobs() {
  const tbody = document.getElementById("transcribe-jobs-tbody");
  const emptyEl = document.getElementById("transcribe-jobs-empty");
  try {
    const jobs = await api("GET", "/api/v1/transcription/jobs");
    tbody.innerHTML = "";
    emptyEl.hidden = jobs.length > 0;
    for (const job of jobs) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(job.job_id || "")}</td>
        <td>${statusBadgeHtml(job.status)}</td>
        <td>${escapeHtml(job.original_file_name || "")}</td>
        <td class="muted small">${escapeHtml(job.note_id || (job.error || ""))}</td>
      `;
      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = "";
    emptyEl.hidden = false;
    emptyEl.textContent = err.message;
  }
}

async function uploadTranscribeFile() {
  const messageEl = document.getElementById("transcribe-upload-message");
  const fileInput = document.getElementById("transcribe-file-input");
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!fileInput.files.length) {
    messageEl.textContent = "Choose a file first.";
    messageEl.classList.add("error");
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  messageEl.textContent = "Uploading...";
  try {
    const job = await api("POST", "/api/v1/transcription/upload", { formData });
    fileInput.value = "";
    messageEl.textContent = `Uploaded ${job.job_id} (status: ${job.status}).`;
    document.getElementById("transcribe-job-id-input").value = job.job_id;
    await refreshTranscribeJobs();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

async function startTranscribeJob() {
  const messageEl = document.getElementById("transcribe-start-message");
  const jobId = document.getElementById("transcribe-job-id-input").value.trim();
  const language = document.getElementById("transcribe-language-input").value.trim();
  const prompt = document.getElementById("transcribe-prompt-input").value.trim();
  const useAi = document.getElementById("transcribe-ai-checkbox").checked;
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!jobId) {
    messageEl.textContent = "Job ID is required.";
    messageEl.classList.add("error");
    return;
  }
  const body = { ai: useAi };
  if (language) body.language = language;
  if (prompt) body.prompt = prompt;
  messageEl.textContent = "Transcribing (this runs synchronously and may take a while)...";
  try {
    const job = await api("POST", `/api/v1/transcription/jobs/${encodeURIComponent(jobId)}/start`, { json: body });
    messageEl.textContent =
      job.status === "completed" ? `Completed → note ${job.note_id}.` : `Failed: ${job.error || "unknown error"}`;
    await refreshTranscribeJobs();
    if (job.status === "completed") await refreshNotes();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupTranscribePanel() {
  document.getElementById("transcribe-readiness-btn").addEventListener("click", checkTranscribeReadiness);
  document.getElementById("transcribe-upload-btn").addEventListener("click", uploadTranscribeFile);
  document.getElementById("transcribe-start-btn").addEventListener("click", startTranscribeJob);
}

// --- create workspace (not gated behind an already-loaded workspace) ---

async function createWorkspace() {
  const messageEl = document.getElementById("create-ws-message");
  const pathInput = document.getElementById("create-ws-path-input");
  const nameInput = document.getElementById("create-ws-name-input");
  const typeSelect = document.getElementById("create-ws-type-select");
  const topicInput = document.getElementById("create-ws-topic-input");
  const sourceRootInput = document.getElementById("create-ws-source-root-input");

  const workspace = pathInput.value.trim();
  const projectName = nameInput.value.trim();
  messageEl.hidden = false;
  messageEl.className = "small";
  if (!workspace || !projectName) {
    messageEl.textContent = "Workspace path and project name are required.";
    messageEl.classList.add("error");
    return;
  }
  messageEl.textContent = "Creating...";
  try {
    const body = {
      workspace,
      project_name: projectName,
      project_type: typeSelect.value,
      topic: topicInput.value.trim(),
    };
    const sourceRoot = sourceRootInput.value.trim();
    if (sourceRoot) {
      body.source_root = sourceRoot;
      body.source_mode = "local_folder";
    }
    const response = await fetch("/api/v1/projects/init", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const responseBody = await response.json();
    if (!response.ok || !responseBody.ok) {
      throw new Error((responseBody.errors && responseBody.errors[0] && responseBody.errors[0].message) || "Could not create workspace.");
    }
    messageEl.textContent = `Workspace created at ${responseBody.data.workspace}. Loading it now...`;
    document.getElementById("workspace-input").value = responseBody.data.workspace;
    setWorkspaceInUrl(responseBody.data.workspace);
    await loadWorkspace(responseBody.data.workspace);
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.classList.add("error");
  }
}

function setupCreateWorkspacePanel() {
  document.getElementById("create-ws-btn").addEventListener("click", createWorkspace);
}

document.addEventListener("DOMContentLoaded", () => {
  setupDropzone();
  document.getElementById("uploads-view-list-btn").addEventListener("click", () => setUploadsView("list"));
  document.getElementById("uploads-view-gallery-btn").addEventListener("click", () => setUploadsView("gallery"));
  setUploadsView("list");
  setupModals();
  setupKeyboardShortcuts();
  setupZoteroPanel();
  setupSourcesPanel();
  setupCreateWorkspacePanel();
  setupNotesPanel();
  setupTranscribePanel();
  setupRqAndArtefactPanels();
  setupClaimsPanel();
  setupCitationPanel();
  document.getElementById("relationships-refresh-btn").addEventListener("click", refreshCitationRelationships);
  document.getElementById("progress-refresh-btn").addEventListener("click", refreshResearchProgress);
  setupGuidelinesPanel();
  setupProjectLogPanel();
  setupDocVaultPanel();
  setupDataPanel();
  setupMetadataPanel();
  setupConversionPanel();
  setupBackupPanel();
  setupDbAdminPanel();
  setupDbBackendPanel();
  setupExportPanel();

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

  document.getElementById("theme-toggle-btn").addEventListener("click", toggleTheme);
  document.getElementById("compare-workspaces-btn").addEventListener("click", compareWorkspaces);
  document.getElementById("ai-readiness-btn").addEventListener("click", checkAiReadiness);
  document.getElementById("ai-run-btn").addEventListener("click", runAiAction);
  document.getElementById("ai-usage-log-refresh-btn").addEventListener("click", refreshAiUsageLog);
  document.getElementById("corpus-search-btn").addEventListener("click", searchCorpus);
  document.getElementById("corpus-search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") searchCorpus();
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
