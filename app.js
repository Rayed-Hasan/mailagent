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

const inboxState = { 
  accountId: null, 
  offset: 0, 
  total: 0, 
  loading: false, 
  isDemoMode: false, 
  allEmails: [],
  activeNav: "inbox",
  tokensUsed: 0
};

function addTokenUsage(tokens) {
  inboxState.tokensUsed += (tokens || 0);
  const tokenEl = document.querySelector("#tokenUsageText");
  if (tokenEl) {
    if (inboxState.tokensUsed >= 1000) {
      tokenEl.textContent = `${(inboxState.tokensUsed / 1000).toFixed(1)}k tokens`;
    } else {
      tokenEl.textContent = `${inboxState.tokensUsed} tokens`;
    }
  }
}

function setConnectionStatus(message, connected = false) {
  connectionStatus.replaceChildren();
  const indicator = document.createElement("span");
  connectionStatus.append(indicator, document.createTextNode(` ${message}`));
  connectionStatus.classList.toggle("connected", connected);
}

async function checkDemoMode() {
  // Check if we're in demo mode by querying the demo status endpoint
  if (!apiConfig.baseUrl) {
    // If no base URL configured, use current origin
    apiConfig.baseUrl = window.location.origin;
  }

  try {
    const response = await fetch(`${apiConfig.baseUrl}/api/demo/status`);
    if (response.ok) {
      const data = await response.json();
      if (data.demo_mode) {
        inboxState.isDemoMode = true;
        inboxState.accountId = data.demo_account_id;

        if (data.gmail_connected) {
          const email = data.demo_account_email || "dedicated Gmail";
          setConnectionStatus(`Connected · ${email} (Real Gmail)`, true);
        } else {
          setConnectionStatus("Gmail disconnected · Owner authorization pending", false);
        }

        // Hide connect button in demo mode since judges do not log in
        if (connectButton) connectButton.style.display = "none";

        // Update profile card with demo account info
        updateProfileCard(data.demo_account_email, data.gmail_connected);

        return true;
      }
    }
  } catch (error) {
    console.log("Not in demo mode or demo endpoint not accessible");
  }

  return false;
}

function updateProfileCard(email, connected) {
  const profileDiv = document.querySelector(".profile");
  if (!profileDiv) return;
  const nameEl = profileDiv.querySelector("strong");
  const emailEl = profileDiv.querySelector("span");
  if (email && connected) {
    const name = email.split("@")[0].replace(/[._-]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    if (nameEl) nameEl.textContent = name;
    if (emailEl) emailEl.textContent = email;
    const avatar = profileDiv.querySelector(".profile-avatar");
    if (avatar) avatar.textContent = name.slice(0, 2).toUpperCase();
  } else {
    if (nameEl) nameEl.textContent = "Demo Mailbox";
    if (emailEl) emailEl.textContent = email || "not connected";
    const avatar = profileDiv.querySelector(".profile-avatar");
    if (avatar) avatar.textContent = "DM";
  }
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

function updateCurrentDateTime() {
  const dateTime = document.querySelector("#currentDateTime");
  if (!dateTime) return;

  const now = new Date();
  dateTime.dateTime = now.toISOString();
  dateTime.textContent = new Intl.DateTimeFormat([], {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(now).toUpperCase();
}

updateCurrentDateTime();
window.setInterval(updateCurrentDateTime, 60_000);

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

// =====================================================================
// updateInboxSummary — module-scope function (was incorrectly nested)
// Updates summary cards AND sidebar counts from real data
// =====================================================================
function updateInboxSummary(emails, total) {
  // Summary cards
  const sortedEl = document.querySelector("#sortedCount");
  const replyEl = document.querySelector("#replyCount");
  const priorityEl = document.querySelector("#priorityCount");

  if (sortedEl) sortedEl.textContent = String(total);

  const replyCount = emails.filter((email) => needsReply(classificationFor(email))).length;
  if (replyEl) replyEl.textContent = String(replyCount);

  const priorityCount = emails.filter((email) => (classificationFor(email).priority_score || 0) >= 70).length;
  if (priorityEl) priorityEl.textContent = String(priorityCount);

  // Update inbox count in sidebar
  const inboxNav = document.querySelector('a.nav-item[href="#inbox"] b');
  if (inboxNav) inboxNav.textContent = String(total);

  // Store emails for summary-based sidebar updates
  inboxState.allEmails = emails;
}

// =====================================================================
// Update sidebar counts from real /api/demo/summary data
// =====================================================================
async function updateSidebarFromApi() {
  if (!inboxState.isDemoMode) return;
  try {
    const response = await fetch(`${apiConfig.baseUrl}/api/demo/summary`);
    if (!response.ok) return;
    const data = await response.json();

    // Update sidebar inbox count
    const inboxNav = document.querySelector('a.nav-item[href="#inbox"] b');
    if (inboxNav) inboxNav.textContent = String(data.total || 0);

    // Update sidebar draft count
    const draftNav = document.querySelector('a.nav-item[href="#drafts"] b');
    if (draftNav) draftNav.textContent = String(data.draft_count || 0);

    // Update label counts
    const labels = data.labels || {};
    // Map label names to sidebar elements
    const labelMap = {
      "follow-up": ["Needs Reply", "Important"],
      "read-later": ["Read Later"],
      "newsletters": ["Newsletter"],
    };

    for (const [hash, labelNames] of Object.entries(labelMap)) {
      const navEl = document.querySelector(`a.nav-item[href="#${hash}"] b`);
      if (navEl) {
        let count = 0;
        for (const name of labelNames) {
          count += labels[name] || 0;
        }
        navEl.textContent = count > 0 ? String(count) : "";
      }
    }

    // Update summary cards from API data too
    const sortedEl = document.querySelector("#sortedCount");
    const replyEl = document.querySelector("#replyCount");
    const priorityEl = document.querySelector("#priorityCount");
    if (sortedEl) sortedEl.textContent = String(data.total || 0);
    if (replyEl) replyEl.textContent = String(data.needs_reply || 0);
    if (priorityEl) priorityEl.textContent = String(data.high_priority || 0);

    // Update connection status if needed
    if (data.gmail_connected && data.email_address) {
      setConnectionStatus(`Connected · ${data.email_address} (Real Gmail)`, true);
    }
  } catch (e) {
    // Sidebar update is best-effort
  }
}

function renderDraftsList(drafts) {
  mailList.replaceChildren();
  drafts.forEach((draft) => {
    const item = document.createElement("article");
    item.className = "mail-item high-priority";
    item.tabIndex = 0;
    item.dataset.emailId = draft.email_id;

    const check = document.createElement("div");
    check.className = "mail-check";
    check.setAttribute("aria-hidden", "true");

    const avatar = document.createElement("div");
    avatar.className = "sender-avatar purple";
    avatar.textContent = "AI";

    const body = document.createElement("div");
    body.className = "mail-body";

    const meta = document.createElement("div");
    meta.className = "mail-meta";
    const sender = document.createElement("strong");
    sender.textContent = draft.sender || (draft.email_id ? `Reply to: ${draft.subject || "Message"}` : "AI Reply Draft");
    const received = document.createElement("span");
    received.textContent = formatDate(draft.created_at || draft.updated_at);
    meta.append(sender, received);

    const subject = document.createElement("h3");
    subject.textContent = draft.subject ? `Draft Reply: ${draft.subject}` : "AI Draft Reply (Pending Approval)";

    const preview = document.createElement("p");
    preview.textContent = (draft.content || "").replace(/\s+/g, " ").slice(0, 180);

    const tags = document.createElement("div");
    tags.className = "mail-tags";
    appendTag(tags, "Draft", "important-tag");
    appendTag(tags, "Pending Review", "reply-tag");

    body.append(meta, subject, preview, tags);

    const more = document.createElement("button");
    more.className = "more-button";
    more.type = "button";
    more.textContent = "Review";
    item.append(check, avatar, body, more);

    item.addEventListener("click", () => {
      if (draft.email_id) openEmail(draft.email_id);
    });
    mailList.appendChild(item);
  });
}

function renderRealEmails(emails, append = false) {
  if (!append) mailList.replaceChildren();
  if (!emails.length && !append) {
    setMailListState("No messages match these filters.");
    return;
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

  // If a sidebar folder or label is active
  if (inboxState.activeNav) {
    if (inboxState.activeNav === "read-later") {
      params.set("label", "Read Later");
    } else if (inboxState.activeNav === "follow-up") {
      params.set("needs_reply", "true");
    } else if (inboxState.activeNav === "newsletters") {
      params.set("category", "newsletter");
    }
  }
  return params;
}

async function fetchInbox(append = false) {
  // If in special views (drafts, sent, archive)
  if (inboxState.activeNav === "drafts") {
    loadMoreButton.hidden = true;
    setConnectionStatus("Drafts · Review Queue", true);
    setMailListState("Loading saved drafts...");
    try {
      if (!inboxState.accountId) {
        const accRes = await fetch(`${apiConfig.baseUrl}/api/accounts`, {
          headers: inboxState.isDemoMode ? {} : { Authorization: `Bearer ${apiConfig.token}` },
        });
        if (accRes.ok) {
          const accData = await accRes.json();
          if (accData.accounts && accData.accounts.length > 0) {
            inboxState.accountId = accData.accounts[0].id;
          }
        }
      }
      const accId = inboxState.accountId || "demo-account-001";
      const draftsRes = await fetch(`${apiConfig.baseUrl}/api/drafts?account_id=${encodeURIComponent(accId)}`, {
        headers: inboxState.isDemoMode ? {} : { Authorization: `Bearer ${apiConfig.token}` },
      });
      if (!draftsRes.ok) throw new Error("Could not load drafts");
      const draftsData = await draftsRes.json();
      const draftsList = draftsData.drafts || [];
      if (!draftsList.length) {
        setMailListState("No pending drafts. Open any priority email and click '✦ Generate AI Reply Draft' to test.");
        return true;
      }
      renderDraftsList(draftsList);
      return true;
    } catch (e) {
      setMailListState(e.message || "Failed to load drafts", true);
      return false;
    }
  }
  if (inboxState.activeNav === "sent") {
    loadMoreButton.hidden = true;
    setConnectionStatus("Sent Messages · Protected", true);
    setMailListState("Outbound sending is disabled in public demo mode. Sent folder is read-only.");
    return true;
  }
  if (inboxState.activeNav === "archive") {
    loadMoreButton.hidden = true;
    setConnectionStatus("Archive", true);
    setMailListState("No archived threads in current session.");
    return true;
  }

  // In demo mode, don't require token
  if (!inboxState.isDemoMode && (!apiConfig.baseUrl || !apiConfig.token)) {
    setConnectionStatus("Connect an inbox to begin");
    setMailListState("Connect your inbox to load real messages.");
    return false;
  }
  if (inboxState.loading) return false;
  inboxState.loading = true;
  setConnectionStatus(inboxState.isDemoMode ? "Loading demo inbox" : "Loading connected inbox");
  if (!append) setMailListState("Loading messages...");
  try {
    if (!inboxState.accountId) {
      const headers = inboxState.isDemoMode ? {} : { Authorization: `Bearer ${apiConfig.token}` };
      const accountsResponse = await fetch(`${apiConfig.baseUrl}/api/accounts`, {
        headers,
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
    const headers = inboxState.isDemoMode ? {} : { Authorization: `Bearer ${apiConfig.token}` };
    const response = await fetch(
      `${apiConfig.baseUrl}/api/emails/with-classifications?${queryParams()}`,
      { headers },
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
    const headers = inboxState.isDemoMode ? {} : { Authorization: `Bearer ${apiConfig.token}` };
    const response = await fetch(`${apiConfig.baseUrl}/api/emails/${encodeURIComponent(emailId)}`, {
      headers,
    });
    if (!response.ok) throw new Error(response.status === 404 ? "Email not found" : "Could not load email");
    const email = await response.json();
    const classification = classificationFor(email);
    document.querySelector("#detailSender").textContent = email.sender || email.sender_email || "Unknown sender";
    document.querySelector("#detailSubject").textContent = email.subject || "(No subject)";
    document.querySelector("#detailTimestamp").textContent = formatDate(email.received_at);
    document.querySelector("#detailBody").textContent = email.body || "(No message content)";

    // Show classification details with reason
    const classEl = document.querySelector("#detailClassification");
    if (classification.category) {
      classEl.textContent = `${classification.category} · Priority ${classification.priority_score ?? "unknown"} · ${classification.reason || ""}`;
    } else {
      classEl.textContent = "Not classified";
    }
    document.querySelector("#detailLabels").textContent = (email.labels || []).join(", ") || "No labels";

    // Setup AI draft generator button in dialog
    const generateBtn = document.querySelector("#generateDraftButton");
    const draftArea = document.querySelector("#draftResultArea");
    const draftMeta = document.querySelector("#draftMeta");
    const draftContent = document.querySelector("#draftContent");

    if (generateBtn && draftArea) {
      draftArea.style.display = "none";
      generateBtn.textContent = "✦ Generate AI Reply Draft";
      generateBtn.disabled = false;

      generateBtn.onclick = async () => {
        generateBtn.disabled = true;
        generateBtn.textContent = "Generating draft with AI...";
        try {
          const draftRes = await fetch(`${apiConfig.baseUrl}/api/demo/drafts/generate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email_id: email.id }),
          });
          if (!draftRes.ok) {
            const err = await draftRes.json().catch(() => ({}));
            throw new Error(err.detail || "Draft generation failed");
          }
          const draftData = await draftRes.json();
          const replyBody = typeof draftData.content === "string" ? draftData.content.trim() : "";
          if (!replyBody) {
            throw new Error("The AI provider did not return a usable reply. No draft was saved.");
          }

          // Show fallback warning banner if applicable
          if (draftData.fallback) {
            const warningBanner = document.createElement("div");
            warningBanner.style.cssText = "background: #fff3cd; border: 1px solid #ffc107; color: #856404; padding: 12px; margin-bottom: 12px; border-radius: 4px; font-size: 14px; display: flex; align-items: center; gap: 8px;";
            warningBanner.innerHTML = "⚠ <strong>Draft from contextual fallback</strong> — OpenRouter quota exceeded. This is a template, not a live AI response.";
            draftArea.prepend(warningBanner);
          }

          draftMeta.textContent = `AI-generated · ${draftData.provider} (${draftData.model})`;
          draftContent.textContent = replyBody;
          draftArea.style.display = "block";
          generateBtn.textContent = "✦ Regenerate Reply Draft";
          addTokenUsage(draftData.tokens || 350);
          // Refresh sidebar draft count
          await updateSidebarFromApi();
        } catch (e) {
          showToast(e.message || "Failed to generate draft");
          generateBtn.textContent = "✦ Generate AI Reply Draft";
        } finally {
          generateBtn.disabled = false;
        }
      };
    }

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
  control.addEventListener("change", () => {
    inboxState.offset = 0;
    fetchInbox();
  });
});
loadMoreButton.addEventListener("click", () => {
  inboxState.offset += 50;
  fetchInbox(true);
});
connectButton.addEventListener("click", connectInbox);

const syncButton = document.querySelector("#syncButton");
if (syncButton) {
  syncButton.addEventListener("click", async () => {
    syncButton.disabled = true;
    syncButton.textContent = "Syncing Gmail...";
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/demo/sync`, { method: "POST" });
      const data = await response.json();
      if (data.synced) {
        showToast(`Synced ${data.stats?.new || 0} new messages from Gmail.`);
        inboxState.offset = 0;
        await fetchInbox();
        await updateSidebarFromApi();
      } else {
        showToast(data.message || "Sync completed.");
      }
    } catch (e) {
      showToast("Sync failed: " + e.message);
    } finally {
      syncButton.disabled = false;
      syncButton.textContent = "↻ Sync Mailbox";
    }
  });
}

document.querySelector("#closeDetail").addEventListener("click", () => detailDialog.close());

// Review Priority Mail — triggers real AI classification then refreshes inbox
document.querySelector("#reviewButton").addEventListener("click", async () => {
  const reviewBtn = document.querySelector("#reviewButton");
  reviewBtn.disabled = true;
  reviewBtn.textContent = "Classifying with AI...";
  try {
    const response = await fetch(`${apiConfig.baseUrl}/api/demo/classify`, { method: "POST" });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Classification failed");
    }
    const data = await response.json();
    const provider = data.provider === "openrouter" ? `AI (${data.model})` : "Deterministic Fallback";
    showToast(`Classified ${data.classified} messages via ${provider}. ${data.skipped} already classified.`);
    if (data.classified > 0) {
      addTokenUsage(data.classified * 280);
    }
    inboxState.offset = 0;
    await fetchInbox();
    await updateSidebarFromApi();
  } catch (e) {
    showToast(e.message || "Classification failed");
  } finally {
    reviewBtn.disabled = false;
    reviewBtn.textContent = "✦ Review priority mail";
  }
});

document.querySelector("#openBrief").addEventListener("click", () => showToast("Open an email to review its classification and labels."));
document.querySelector("#modeButton").addEventListener("click", () => showToast("Approve mode is on — nothing sends without your check."));
// Sidebar navigation routing
function handleNavigation(hash) {
  const cleanHash = (hash || window.location.hash || "#inbox").replace(/^#/, "");
  inboxState.activeNav = cleanHash;

  // Update active class on sidebar links
  document.querySelectorAll(".main-nav a.nav-item").forEach((el) => {
    const href = el.getAttribute("href") || "";
    el.classList.toggle("active", href === `#${cleanHash}`);
  });

  // Update breadcrumb and section heading
  const breadcrumbStrong = document.querySelector(".breadcrumb strong");
  const sectionTitle = document.querySelector(".section-heading h2");
  const sectionDesc = document.querySelector(".section-heading p");

  const titles = {
    "inbox": ["Priority inbox", "Live messages from your connected account"],
    "drafts": ["Drafts", "AI-assisted draft replies ready for review"],
    "sent": ["Sent messages", "Messages sent from your mailbox"],
    "archive": ["Archive", "Archived email threads"],
    "follow-up": ["Follow up", "Messages requiring your reply or action"],
    "read-later": ["Read later", "Articles, newsletters, and low-priority reading"],
    "newsletters": ["Newsletters", "Subscriptions and recurring digests"],
  };

  const [title, desc] = titles[cleanHash] || ["Priority inbox", "Live messages from your connected account"];
  if (breadcrumbStrong) breadcrumbStrong.textContent = title;
  if (sectionTitle) sectionTitle.textContent = title;
  if (sectionDesc) sectionDesc.textContent = desc;

  // Reset offset and fetch
  inboxState.offset = 0;
  fetchInbox();
}

// Bind settings dialog
const settingsDialog = document.querySelector("#settingsDialog");
const closeSettings = document.querySelector("#closeSettings");
if (closeSettings && settingsDialog) {
  closeSettings.addEventListener("click", () => settingsDialog.close());
}
function openSettingsModal() {
  if (settingsDialog) settingsDialog.showModal();
  loadAutoReplySetting();
}

async function loadAutoReplySetting() {
  const status = document.querySelector("#autoReplyStatus");
  const controls = document.querySelector("#autoReplyControls");
  const button = document.querySelector("#toggleAutoReply");
  if (!status || !controls || !button) return;
  if (inboxState.isDemoMode) {
    status.textContent = "Approval mode · automatic sending is disabled in the public demo";
    controls.hidden = true;
    return;
  }
  if (!apiConfig.token) {
    status.textContent = "Connect as the owner to configure automatic replies";
    controls.hidden = true;
    return;
  }
  controls.hidden = false;
  status.textContent = "Loading setting…";
  try {
    const response = await fetch(`${apiConfig.baseUrl}/api/owner/auto-reply`, {
      headers: { Authorization: `Bearer ${apiConfig.token}` },
    });
    if (!response.ok) throw new Error("Could not load setting");
    const setting = await response.json();
    button.dataset.enabled = String(setting.enabled);
    button.textContent = setting.enabled ? "Disable automatic replies" : "Enable safe auto replies";
    status.textContent = setting.enabled
      ? "Safe auto replies are on · only eligible routine messages can be sent"
      : "Approval mode · replies stay as drafts until approved";
  } catch (_error) {
    status.textContent = "Could not load automatic-reply setting";
  }
}

document.querySelector("#toggleAutoReply")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const enabled = button.dataset.enabled !== "true";
  button.disabled = true;
  try {
    const response = await fetch(`${apiConfig.baseUrl}/api/owner/auto-reply`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiConfig.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ enabled }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not save setting");
    await loadAutoReplySetting();
    showToast(enabled ? "Safe automatic replies enabled" : "Automatic replies disabled");
  } catch (error) {
    showToast(error.message || "Could not save automatic-reply setting");
  } finally {
    button.disabled = false;
  }
});

// Bind topbar and footer buttons
const searchBtn = document.querySelector("#searchButton");
if (searchBtn) searchBtn.addEventListener("click", () => togglePalette(true));

const notifBtn = document.querySelector("#notificationButton");
if (notifBtn) notifBtn.addEventListener("click", () => {
  showToast("Notifications: Mailbox is synced and operating in Approve Mode.");
});

const helpBtn = document.querySelector("#helpButton");
if (helpBtn) helpBtn.addEventListener("click", () => {
  showToast("MailAgent: Privacy-first email assistant. Press ⌘K for command palette.");
});

// Bind palette backdrop and shortcut
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    togglePalette(true);
  }
  if (e.key === "Escape" && palette.classList.contains("open")) {
    togglePalette(false);
  }
});
const paletteBackdrop = document.querySelector(".palette-backdrop");
if (paletteBackdrop) {
  paletteBackdrop.addEventListener("click", () => togglePalette(false));
}

// Command palette buttons
document.querySelectorAll(".palette-actions button").forEach((btn, idx) => {
  btn.addEventListener("click", () => {
    togglePalette(false);
    if (idx === 0) showToast("MailAgent: All high-priority items are marked in your inbox.");
    if (idx === 1) handleNavigation("#inbox");
    if (idx === 2) openSettingsModal();
  });
});

// Settings links (footer and palette)
document.querySelectorAll("a[href='#settings']").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    openSettingsModal();
  });
});

// Listen for sidebar nav clicks and hash changes
document.querySelectorAll(".main-nav a.nav-item").forEach((link) => {
  link.addEventListener("click", (e) => {
    const href = link.getAttribute("href");
    if (href && href.startsWith("#")) {
      handleNavigation(href);
    }
  });
});
window.addEventListener("hashchange", () => handleNavigation(window.location.hash));

// Initialize: check for demo mode first, then try to load inbox
(async function init() {
  // Route initial hash if user navigated directly to #drafts, #sent, etc.
  if (window.location.hash && window.location.hash !== "#inbox") {
    handleNavigation(window.location.hash);
  }

  const isDemo = await checkDemoMode();
  if (isDemo) {
    // Set sidebar counts to 0 initially (will update from API)
    document.querySelectorAll(".nav-item b, .nav-item b.muted-count").forEach(el => {
      el.textContent = "…";
    });
    await fetchInbox();
    await updateSidebarFromApi();
  } else if (apiConfig.baseUrl && apiConfig.token) {
    await fetchInbox();
  } else {
    setConnectionStatus("Connect an inbox to begin");
    setMailListState("Connect your inbox to load real messages.");
  }
})();

