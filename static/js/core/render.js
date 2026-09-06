import { $ } from "./utils.js";
import { role, page, setPage } from "./store.js";
import { menus } from "./navigation.js";
import { pageFromLocation, urlFor, navigate } from "./router.js";
import { banner } from "../components/ui.js";
import { dashboard } from "../pages/dashboard.js";
import { listPage } from "../pages/list.js";
import { profilePage } from "../pages/profile.js";
import { authPage } from "../pages/auth.js";

function render() {
  setPage(pageFromLocation());
  if (
    !menus[role].some((m) => m[0] === page) &&
    !["login", "register"].includes(page)
  ) {
    navigate("dashboard", true);
    return;
  }
  $("#navigation").innerHTML =
    menus[role]
      .map(
        ([key, icon, name]) =>
          `<a href="${urlFor(key)}" class="${page === key ? "active" : ""}" ${page === key ? 'aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">${icon}</span>${name}</a>`,
      )
      .join("") +
    `<a href="${urlFor("login")}"><span class="nav-icon" aria-hidden="true">↪</span>Đăng nhập</a>`;
  const title = menus[role].find((m) => m[0] === page)?.[2] || "Tài khoản";
  $("#breadcrumb").textContent = `Không gian làm việc / ${title}`;
  document.title = `${title} · FleetCare`;
  $("#role").value = role;
  $("#avatar").textContent = role === "admin" ? "QT" : "VM";
  $("#main").innerHTML =
    (["login", "register"].includes(page) ? "" : banner) +
    (page === "dashboard"
      ? dashboard()
      : ["profile", "license", "face"].includes(page)
        ? profilePage()
        : ["login", "register"].includes(page)
          ? authPage()
          : listPage());
  document.body.classList.remove("menu-open");
  $("#menu").setAttribute("aria-expanded", "false");
}

export { render };
