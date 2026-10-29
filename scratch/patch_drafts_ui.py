with open('app.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_drafts_block = """  // If in special views (drafts, sent, archive)
  if (inboxState.activeNav === "drafts") {
    loadMoreButton.hidden = true;
    setConnectionStatus("Drafts · Review Queue", true);
    setMailListState("No pending drafts. Open any priority email and click '✦ Generate AI Reply Draft' to test.");
    return true;
  }"""

new_drafts_block = """  // If in special views (drafts, sent, archive)
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
  }"""

if old_drafts_block in content:
    content = content.replace(old_drafts_block, new_drafts_block)
    with open('app.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced successfully!")
else:
    print("Old block not found!")

