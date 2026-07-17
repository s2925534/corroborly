// Shared light/dark/system theme logic. Loaded by both the login page and
// the main app (index.html), so the choice carries across every view --
// login doesn't load app.js at all, so this stays its own small file
// rather than living inside app.js.
//
// Three explicit states, matching styles.css's existing CSS already:
//   - "light" / "dark": sets <html data-theme="..."> to force that palette.
//   - "system": removes the data-theme attribute entirely, so styles.css's
//     `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {...} }`
//     fallback takes over and follows the OS setting live -- no JS needed
//     to react to OS theme changes, the CSS media query already does that.
//
// Placed early in <head> (not deferred, not inside DOMContentLoaded) so
// there is no flash-of-wrong-theme: document.documentElement already
// exists as soon as this script tag runs.

const THEME_KEY = "corroborly:theme";
const THEME_VALUES = ["light", "dark", "system"];
const THEME_LABELS = { light: "Light", dark: "Dark", system: "System" };

function getStoredTheme() {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    return THEME_VALUES.includes(stored) ? stored : "system";
  } catch (err) {
    return "system";
  }
}

function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") {
    root.setAttribute("data-theme", theme);
  } else {
    root.removeAttribute("data-theme");
  }
  try {
    window.localStorage.setItem(THEME_KEY, theme);
  } catch (err) {
    // Private browsing / storage disabled -- selection just won't persist across reloads.
  }
}

(function paintStoredThemeImmediately() {
  const stored = getStoredTheme();
  if (stored === "light" || stored === "dark") {
    document.documentElement.setAttribute("data-theme", stored);
  }
})();

// Wires up a <details class="theme-menu"> containing three
// <button class="theme-option" data-theme-value="light|dark|system"> --
// see the markup in index.html's topbar / login.html for the exact shape.
function setupThemeMenu(menuId) {
  const menu = document.getElementById(menuId);
  if (!menu) return;
  const summaryLabel = menu.querySelector(".theme-menu-label");
  const options = menu.querySelectorAll(".theme-option");

  function refresh() {
    const current = getStoredTheme();
    if (summaryLabel) summaryLabel.textContent = `Theme: ${THEME_LABELS[current]}`;
    for (const opt of options) {
      opt.classList.toggle("active", opt.dataset.themeValue === current);
    }
  }

  for (const opt of options) {
    opt.addEventListener("click", () => {
      applyTheme(opt.dataset.themeValue);
      refresh();
      menu.removeAttribute("open");
    });
  }

  document.addEventListener("click", (event) => {
    if (menu.hasAttribute("open") && !menu.contains(event.target)) {
      menu.removeAttribute("open");
    }
  });

  refresh();
}
