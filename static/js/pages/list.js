import { esc, labels } from "../core/utils.js";
import {
  role,
  page,
  query,
  filter,
  catalog,
  driverName,
  plate,
  violationName,
  visible,
} from "../core/store.js";
import { button, heading, tableMarkup } from "../components/ui.js";
import { config as drivers } from "./lists/drivers.js";
import { config as vehicles } from "./lists/vehicles.js";
import { config as assignments } from "./lists/assignments.js";
import { config as sessions } from "./lists/sessions.js";
import { config as violations } from "./lists/violations.js";
import { config as appeals } from "./lists/appeals.js";
import { config as devices } from "./lists/devices.js";
import { config as types } from "./lists/types.js";
import { config as violationTypes } from "./lists/violationTypes.js";

const configs = {
  drivers,
  vehicles,
  assignments,
  sessions,
  violations,
  appeals,
  devices,
  types,
  violationTypes,
};
function listPage() {
  const key = page === "catalogs" ? catalog : page,
    c = configs[key];
  const action =
    role === "admin" && c.add
      ? button("+ " + c.add, "create", key, "primary")
      : "";
  return (
    heading(
      role === "driver" && page === "vehicles" ? "Xe được giao" : c.title,
      c.desc,
      action,
    ) +
    (page === "catalogs"
      ? `<div class="tabs">${["types", "violationTypes"].map((k) => button(configs[k].title, "catalog", k, k === catalog ? "primary" : "")).join("")}</div>`
      : "") +
    `<section class="card"><div class="toolbar"><input class="search" id="search" type="search" placeholder="Tìm kiếm trong danh sách…" aria-label="Tìm kiếm" value="${esc(query)}"><select id="filter" aria-label="Lọc trạng thái"><option value="">Tất cả trạng thái</option>${[
      ...new Set(
        visible(key)
          .map((r) => r.status)
          .filter(Boolean),
      ),
    ]
      .map(
        (s) =>
          `<option value="${s}" ${filter === s ? "selected" : ""}>${labels[s]}</option>`,
      )
      .join(
        "",
      )}</select></div><div id="results">${listResults(key)}</div></section>`
  );
}
function listResults(key) {
  const rows = visible(key).filter(
    (r) =>
      (!filter || r.status === filter) &&
      [
        ...Object.values(r),
        r.driver ? driverName(r.driver) : "",
        r.vehicle ? plate(r.vehicle) : "",
        r.type ? violationName(r.type) : "",
      ]
        .join(" ")
        .toLocaleLowerCase("vi")
        .includes(query.toLocaleLowerCase("vi")),
  );
  return (
    tableMarkup(configs[key].cols, rows.map(configs[key].row)) +
    `<div class="table-footer"><span>Hiển thị ${rows.length} / ${visible(key).length} bản ghi</span><span>Dữ liệu minh họa</span></div>`
  );
}

export { configs, listPage, listResults };
