const toast = document.querySelector("#toast");
const palette = document.querySelector("#commandPalette");
const paletteInput = document.querySelector("#paletteInput");
const mailList = document.querySelector("#mailList");
const loadMoreButton = document.querySelector("#loadMoreButton");
const connectButton = document.querySelector("#connectButton");
const connectionStatus = document.querySelector("#connectionStatus");
const detailDialog = document.querySelector("#emailDetail");

const apiConfig = {
  baseUrl: new URLSearchParams(window.location.search).get("api")
    || sessionStorage.getItem("mailagent.apiBaseUrl") || "",
  token: new URLSearchParams(window.location.search).get("token")
    || sessionStorage.getItem("mailagent.dashboardToken") || "",
};

const inboxState = { accountId: null, offset: 0, total: 0, loading: false };

function setConnectionStatus(message, connected = false) {
  connectionStatus.replaceChildren();
  const indicator = document.createElement("span");
  connectionStatus.append(indicator, document.createTextNode(` ${message}`));
  connectionStatus.classList.toggle("connected", connected);
}

function setMailListState(message, isError = false) {
  mailList.replaceChildren();
  const state = document.createElement("p");
  state.className = `mail-list-state${isError ? " error-state" : ""}`;
  state.textContent = message;
  mailList.appendChild(state);
  if (isError) {
    const retry = document.createElement("button");
    retry.className = "secondary-button retry-button";
    retry.type = "button";
    retry.textContent = "Retry";
    retry.addEventListener("click", () => fetchInbox());
    mailList.appendChild(retry);
  }
  loadMoreButton.hidden = true;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown time"
    : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function classificationFor(email) {
  return email.classification || {};
}

function needsReply(classification) {
  return classification.action === "reply" || classification.action === "draft_only";
}

function appendTag(parent, text, className = "") {
  const tag = document.createElement("span");
  tag.className = `tag ${className}`.trim();
  tag.textContent = text;
  parent.appendChild(tag);
}

function renderRealEmails(emails, append = false) {
  if (!append) mailList.replaceChildren();
  if (!emails.length && !append) {
    setMailListState("No messages match these filters.");
    return;
  }

  function updateInboxSummary(emails, total) {
    document.querySelector("#sortedCount").textContent = String(total);
    document.querySelector("#replyCount").textContent = String(
      emails.filter((email) => needsReply(classificationFor(email))).length,
    );
    document.querySelector("#priorityCount").textContent = String(
      emails.filter((email) => (classificationFor(email).priority_score || 0) >= 70).length,
    );
  }

  emails.forEach((email) => {
    const classification = classificationFor(email);
    const priority = Number.isFinite(classification.priority_score)
      ? classification.priority_score
      : null;
    const labels = Array.isArray(email.labels) ? email.labels : [];
    const item = document.createElement("article");
    item.className = "mail-item";
    item.tabIndex = 0;
    item.dataset.emailId = email.id;
    if (priority !== null && priority >= 70) item.classList.add("high-priority");
    if (priority !== null && priority >= 90) item.classList.add("urgent-priority");

    const check = document.createElement("div");
    check.className = "mail-check";
    check.setAttribute("aria-hidden", "true");
    const avatar = document.createElement("div");
    avatar.className = "sender-avatar purple";
    avatar.textContent = (email.sender || email.sender_email || "?").slice(0, 2).toUpperCase();

    const body = document.createElement("div");
    body.className = "mail-body";
    const meta = document.createElement("div");
    meta.className = "mail-meta";
    const sender = document.createElement("strong");
    sender.textContent = email.sender || email.sender_email || "Unknown sender";
    const received = document.createElement("span");
    received.textContent = formatDate(email.received_at);
    meta.append(sender, received);
    const subject = document.createElement("h3");
    subject.textContent = email.subject || "(No subject)";
    const preview = document.createElement("p");
    preview.textContent = (email.body || "").replace(/\s+/g, " ").slice(0, 180);
    const tags = document.createElement("div");
    tags.className = "mail-tags";

    if (priority !== null) appendTag(tags, `Priority ${priority}`, priority >= 90 ? "urgent-tag" : priority >= 70 ? "important-tag" : "");
    if (needsReply(classification)) appendTag(tags, "Needs Reply", "reply-tag");
    if (classification.category) appendTag(tags, classification.category);
    labels.slice(0, 3).forEach((label) => appendTag(tags, label, "label-tag"));
    if (!classification.category && priority === null) appendTag(tags, "Not classified", "unclassified-tag");

    body.append(meta, subject, preview, tags);
    const more = document.createElement("button");
    more.className = "more-button";
    more.type = "button";
    more.textContent = "Open";
    more.setAttribute("aria-label", `Open ${email.subject || "email"}`);
    item.append(check, avatar, body, more);
    mailList.appendChild(item);
    item.addEventListener("click", () => openEmail(email.id));
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openEmail(email.id);
      }
    });
  });
}

function queryParams() {
  const params = new URLSearchParams({
    account_id: inboxState.accountId,
    limit: "50",
    offset: String(inboxState.offset),
    sort_by: document.querySelector("#sortInbox").value,
  });
  const category = document.querySelector("#categoryFilter").value;
  const label = document.querySelector("#labelFilter").value.trim();
  const minPriority = document.querySelector("#priorityFilter").value;
  const reply = document.querySelector("#replyFilter").value;
  if (category) params.set("category", category);
  if (label) params.set("label", label);
  if (minPriority) params.set("min_priority", minPriority);
  if (reply) params.set("needs_reply", reply);
  return params;
}

async function fetchInbox(append = false) {
  if (!apiConfig.baseUrl || !apiConfig.token) {
    setConnectionStatus("Connect an inbox to begin");
    setMailListState("Connect your inbox to load real messages.");
    return false;
  }
  if (inboxState.loading) return false;
  inboxState.loading = true;
  setConnectionStatus("Loading connected inbox");
  if (!append) setMailListState("Loading messages...");
  try {
    if (!inboxState.accountId) {
      const accountsResponse = await fetch(`${apiConfig.baseUrl}/api/accounts`, {
        headers: { Authorization: `Bearer ${apiConfig.token}` },
      });
      if (!accountsResponse.ok) throw new Error(accountsResponse.status === 401 ? "Authentication failed" : "Could not load accounts");
      const accounts = (await accountsResponse.json()).accounts || [];
      if (!accounts.length) {
        setConnectionStatus("No mailbox connected");
        setMailListState("Connect a mailbox in the dashboard to see messages.");
        return true;
      }
      inboxState.accountId = accounts[0].id;
      setConnectionStatus(`Connected · ${accounts[0].email_address || accounts[0].provider}`, true);
    }
    const response = await fetch(
      `${apiConfig.baseUrl}/api/emails/with-classifications?${queryParams()}`,
      { headers: { Authorization: `Bearer ${apiConfig.token}` } },
    );
    if (!response.ok) throw new Error(response.status === 401 ? "Authentication failed" : "Could not load messages");
    const payload = await response.json();
    renderRealEmails(payload.emails || [], append);
    inboxState.total = payload.total || 0;
    updateInboxSummary(payload.emails || [], inboxState.total);
    loadMoreButton.hidden = inboxState.offset + (payload.emails || []).length >= inboxState.total;
    return true;
  } catch (error) {
    setConnectionStatus("Connection failed");
    setMailListState(error.message || "Could not load messages.", true);
    return false;
  } finally {
    inboxState.loading = false;
  }
}

async function openEmail(emailId) {
  try {
    const response = await fetch(`${apiConfig.baseUrl}/api/emails/${encodeURIComponent(emailId)}`, {
      headers: { Authorization: `Bearer ${apiConfig.token}` },
    });
    if (!response.ok) throw new Error(response.status === 404 ? "Email not found" : "Could not load email");
    const email = await response.json();
    const classification = classificationFor(email);
    document.querySelector("#detailSender").textContent = email.sender || email.sender_email || "Unknown sender";
    document.querySelector("#detailSubject").textContent = email.subject || "(No subject)";
    document.querySelector("#detailTimestamp").textContent = formatDate(email.received_at);
    document.querySelector("#detailBody").textContent = email.body || "(No message content)";
    document.querySelector("#detailClassification").textContent = classification.category
      ? `${classification.category} · Priority ${classification.priority_score ?? "unknown"}`
      : "Not classified";
    document.querySelector("#detailLabels").textContent = (email.labels || []).join(", ") || "No labels";
    detailDialog.showModal();
  } catch (error) {
    showToast(error.message || "Could not load email");
  }
}

async function connectInbox() {
  const baseUrl = apiConfig.baseUrl
    || window.prompt("Dashboard API URL", "http://127.0.0.1:8000");
  if (!baseUrl) return;
  const token = apiConfig.token
    || window.prompt("Dashboard bearer token (kept only for this browser session)");
  if (!token) return;
  apiConfig.baseUrl = baseUrl.replace(/\/+$/, "");
  apiConfig.token = token;
  inboxState.accountId = null;
  inboxState.offset = 0;
  sessionStorage.setItem("mailagent.apiBaseUrl", apiConfig.baseUrl);
  sessionStorage.setItem("mailagent.dashboardToken", apiConfig.token);
  if (await fetchInbox()) showToast("Connected inbox loaded.");
}

function showToast(message) {
  toast.replaceChildren(document.createTextNode(message));
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 3200);
}

function togglePalette(open) {
  if (!open && document.activeElement === paletteInput) paletteInput.blur();
  palette.classList.toggle("open", open);
  palette.setAttribute("aria-hidden", String(!open));
  if (open) window.setTimeout(() => paletteInput.focus(), 0);
}

document.querySelectorAll("#categoryFilter, #labelFilter, #priorityFilter, #replyFilter, #sortInbox").forEach((control) => {
  control.addEventListener(control.id === "labelFilter" ? "change" : "change", () => {
    inboxState.offset = 0;
    fetchInbox();
  });
});
loadMoreButton.addEventListener("click", () => {
  inboxState.offset += 50;
  fetchInbox(true);
});
connectButton.addEventListener("click", connectInbox);
document.querySelector("#closeDetail").addEventListener("click", () => detailDialog.close());
document.querySelector("#reviewButton").addEventListener("click", () => {
  document.querySelector(".mail-column").scrollIntoView({ behavior: "smooth", block: "center" });
});
document.querySelector("#openBrief").addEventListener("click", () => showToast("Open an email to review its classification and labels."));
document.querySelector("#modeButton").addEventListener("click", () => showToast("Approve mode is on — nothing sends without your check."));
document.querySelector(".icon-button[aria-label='Search']").addEventListener("click", () => togglePalette(true));
document.querySelector(".palette-backdrop").addEventListener("click", () => togglePalette(false));
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    togglePalette(true);
  }
  if (event.key === "Escape") togglePalette(false);
});

if (apiConfig.baseUrl && apiConfig.token) fetchInbox();
else {
  setConnectionStatus("Connect an inbox to begin");
  setMailListState("Connect your inbox to load real messages.");
}

const onboardingDialog = document.querySelector("#onboardingDialog");
const onboardingForm = document.querySelector("#onboardingForm");
if (!localStorage.getItem("mailagent.onboardingComplete")) onboardingDialog.showModal();
onboardingForm.addEventListener("submit", () => {
  localStorage.setItem("mailagent.onboardingComplete", "true");
  localStorage.setItem("mailagent.preferences", JSON.stringify({
    deployment: document.querySelector("#onboardingMode").value,
    ai: document.querySelector("#onboardingAi").value,
    autonomy: document.querySelector("#onboardingAutonomy").value,
  }));
  showToast("Preferences saved. Connect your inbox to continue.");
});
