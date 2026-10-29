import sys

with open('app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Initial hash routing on page load
old_init = """// Initialize: check for demo mode first, then try to load inbox
(async function init() {
  const isDemo = await checkDemoMode();
  if (isDemo) {
    // Set sidebar counts to 0 initially (will update from API)
    document.querySelectorAll(".nav-item b, .nav-item b.muted-count").forEach(el => {
      el.textContent = "\u2026";
    });
    await fetchInbox();
    await updateSidebarFromApi();
  } else if (apiConfig.baseUrl && apiConfig.token) {
    await fetchInbox();
  } else {
    setConnectionStatus("Connect an inbox to begin");
    setMailListState("Connect your inbox to load real messages.");
  }
})();"""

new_init = """// Initialize: check for demo mode first, then try to load inbox
(async function init() {
  // Route initial hash if user navigated directly to #drafts, #sent, etc.
  if (window.location.hash && window.location.hash !== "#inbox") {
    handleNavigation(window.location.hash);
  }

  const isDemo = await checkDemoMode();
  if (isDemo) {
    // Set sidebar counts to 0 initially (will update from API)
    document.querySelectorAll(".nav-item b, .nav-item b.muted-count").forEach(el => {
      el.textContent = "\u2026";
    });
    await fetchInbox();
    await updateSidebarFromApi();
  } else if (apiConfig.baseUrl && apiConfig.token) {
    await fetchInbox();
  } else {
    setConnectionStatus("Connect an inbox to begin");
    setMailListState("Connect your inbox to load real messages.");
  }
})();"""

if old_init in content:
    content = content.replace(old_init, new_init)
    print("Fixed init hash routing!")
else:
    print("ERROR: Could not find init block!")
    sys.exit(1)

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("app.js patched successfully.")
