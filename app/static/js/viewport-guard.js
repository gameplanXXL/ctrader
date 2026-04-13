// Viewport guard — UX-DR29.
//
// ctrader is desktop-only. Any viewport below 1024px gets a full-screen
// overlay telling the user to resize. No mobile layout, no responsive
// tricks — this is a deliberate constraint from the UX spec.
//
// Runs on DOMContentLoaded and on every resize; the overlay is a plain
// DOM node so it respects whatever CSS tokens are in force.

(function () {
  "use strict";

  const MIN_WIDTH_PX = 1024;
  const OVERLAY_ID = "viewport-guard-overlay";

  function ensureOverlay() {
    let overlay = document.getElementById(OVERLAY_ID);
    if (overlay) {
      return overlay;
    }

    overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.setAttribute("role", "alert");
    overlay.setAttribute("aria-live", "assertive");
    overlay.style.cssText = [
      "position:fixed",
      "inset:0",
      "z-index:2147483647",
      "display:none",
      "align-items:center",
      "justify-content:center",
      "background-color:var(--bg-void,#0d1117)",
      "color:var(--text-primary,#f0f6fc)",
      "font-family:var(--font-sans,system-ui,sans-serif)",
      "padding:24px",
      "text-align:center",
    ].join(";");

    const content = document.createElement("div");
    content.style.cssText = [
      "max-width:480px",
      "line-height:1.5",
    ].join(";");
    content.innerHTML = [
      '<p style="font-size:20px;margin-bottom:12px;">ctrader benötigt mindestens <strong>1024 px</strong> Viewport-Breite.</p>',
      '<p style="font-size:14px;color:var(--text-secondary,#c9d1d9);">Bitte vergrößere das Browserfenster oder öffne ctrader auf einem größeren Display. Kein Mobile-Layout geplant.</p>',
    ].join("");

    overlay.appendChild(content);
    document.body.appendChild(overlay);
    return overlay;
  }

  function update() {
    const overlay = ensureOverlay();
    const tooNarrow = window.innerWidth < MIN_WIDTH_PX;
    overlay.style.display = tooNarrow ? "flex" : "none";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", update);
  } else {
    update();
  }
  window.addEventListener("resize", update, { passive: true });
})();
