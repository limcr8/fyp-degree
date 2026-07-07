chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verify-selection",
    title: "Verify with Fake News Detection",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "verify-selection" || !info.selectionText) return;
  await chrome.storage.session.set({ pendingSelection: info.selectionText });
  try { chrome.action.openPopup(); } catch (_) {}
});