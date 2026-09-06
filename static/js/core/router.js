// Django's named URLs are the single source of truth for page links.
import { $ } from "./utils.js";
import { setRole, setQuery, setFilter } from "./store.js";

const routes = JSON.parse($("#frontend-routes").textContent);
let onRouteChange;

export function urlFor(page) {
  if (!Object.hasOwn(routes, page)) throw new Error(`Unknown page: ${page}`);
  return routes[page];
}

export function pageFromLocation() {
  return (
    Object.keys(routes).find(
      (key) => key !== "home" && routes[key] === location.pathname,
    ) || "dashboard"
  );
}

export function navigate(page, replace = false) {
  history[replace ? "replaceState" : "pushState"]({}, "", urlFor(page));
  setQuery("");
  setFilter("");
  onRouteChange();
}

export function bindRouter(render) {
  onRouteChange = render;
  // Preserve bookmarked links from the original hash-based prototype.
  const legacyPage = location.hash.slice(1);
  if (Object.hasOwn(routes, legacyPage)) {
    history.replaceState({}, "", urlFor(legacyPage));
  }
  // These pages belong only to the driver preview. This is not authentication.
  if (["profile", "license", "face"].includes(pageFromLocation()))
    setRole("driver");

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (
      !link ||
      event.defaultPrevented ||
      event.button !== 0 ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey ||
      event.altKey ||
      link.target ||
      link.hasAttribute("download")
    )
      return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || url.hash || url.search) return;
    const page = Object.keys(routes).find(
      (key) => routes[key] === url.pathname,
    );
    if (!page) return;
    event.preventDefault();
    navigate(page === "home" ? "dashboard" : page);
    $("#main").focus({ preventScroll: true });
    window.scrollTo(0, 0);
  });
  window.addEventListener("popstate", () => {
    setQuery("");
    setFilter("");
    render();
  });
  render();
}
