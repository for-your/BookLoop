const app = createApp(App);
app.directive("reveal", BookLoopMotion.reveal);
app.directive("spotlight", BookLoopMotion.spotlight);
app.directive("tilt", BookLoopMotion.tilt);
app.component("ui-icon", UiIcon);
app.component("book-cover", BookCover);
app.component("book-card", BookCard);
app.component("reading-card", ReadingCard);
app.component("assistant-panel", AssistantPanel);
app.config.globalProperties.fmtPrice = fmtPrice;
app.config.globalProperties.levelClass = levelClass;
app.mount("#app");

let focusedDialog = null;
let previousFocus = null;
const dialogObserver = new MutationObserver(() => {
  const dialogs = [...document.querySelectorAll(".modal-mask .modal, .market-sidebar.expanded")];
  const dialog = dialogs.at(-1) || null;
  if (dialog === focusedDialog) return;
  if (focusedDialog?.matches(".market-sidebar")) {
    focusedDialog.removeAttribute("role");
    focusedDialog.removeAttribute("aria-modal");
    focusedDialog.removeAttribute("tabindex");
  }
  if (dialog) {
    if (!focusedDialog) previousFocus = document.activeElement;
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("tabindex", "-1");
    requestAnimationFrame(() => (dialog.querySelector("[data-dialog-focus]:not(:disabled)") || dialog.querySelector("button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]") || dialog).focus());
  } else if (previousFocus?.isConnected) previousFocus.focus();
  focusedDialog = dialog;
});
dialogObserver.observe(document.getElementById("app"), { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
document.addEventListener("keydown", (event) => {
  if (!focusedDialog) return;
  if (event.key === "Escape") {
    const mask = focusedDialog.closest(".modal-mask");
    if (mask) mask.click();
    else focusedDialog.querySelector("[aria-label='关闭筛选']")?.click();
    event.preventDefault();
    event.stopImmediatePropagation();
  }
  if (event.key === "Tab") {
    const elements = [...focusedDialog.querySelectorAll("button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex='0']")].filter(element => element.getClientRects().length);
    const first = elements[0];
    const last = elements.at(-1);
    if (!first) { event.preventDefault(); focusedDialog.focus(); return; }
    if (event.shiftKey && (document.activeElement === first || !focusedDialog.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || !focusedDialog.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
  }
}, true);
