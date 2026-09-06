import { $, esc, labels } from "../core/utils.js";
import { data, role, driverName } from "../core/store.js";

let toastTimer;
const person = (id) =>
  `<div class="person"><span class="avatar">${esc(
    driverName(id)
      .split(" ")
      .slice(-2)
      .map((s) => s[0])
      .join(""),
  )}</span><div><strong>${esc(driverName(id))}</strong><small>TX-${String(id).padStart(3, "0")}</small></div></div>`;
const button = (text, action, id = "", style = "") =>
  `<button class="button ${style}" data-action="${action}" data-id="${id}">${text}</button>`;
const detailButton = (collection, id) =>
  `<button class="text-button" data-action="detail" data-collection="${collection}" data-id="${id}">Chi tiết ↗</button>`;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").style.display = "block";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("#toast").style.display = "none"), 4000);
}
function heading(title, description, action = "") {
  return `<div class="page-heading"><div><p class="eyebrow">${role === "admin" ? "Trung tâm điều hành" : "Không gian tài xế"}</p><h1>${title}</h1><p class="subtitle">${description}</p></div>${action}</div>`;
}
const banner =
  '<div class="demo-banner">BẢN XEM TRƯỚC · Dữ liệu minh họa, thao tác chỉ có hiệu lực trong tab này và được đặt lại khi tải lại trang. Chưa kết nối API.</div>';
function tableMarkup(cols, rows) {
  return `<div class="table-scroll"><table><thead><tr>${cols.map((c) => `<th scope="col">${c}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((row) => `<tr>${row.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${cols.length}"><div class="empty">Chưa có dữ liệu phù hợp.<br><small>Thử đổi bộ lọc hoặc thêm thông tin mới.</small></div></td></tr>`}</tbody></table></div>`;
}
function field(
  name,
  label,
  value = "",
  type = "text",
  options = null,
  required = true,
) {
  return `<label class="field ${type === "textarea" ? "full" : ""}">${label}${options ? `<select name="${name}">${options.map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(value) ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>` : type === "textarea" ? `<textarea name="${name}" ${required ? "required" : ""}>${esc(value)}</textarea>` : `<input name="${name}" type="${type}" value="${type === "file" ? "" : esc(value)}" ${required ? "required" : ""} ${type === "file" ? 'accept="image/jpeg,image/png,image/webp"' : type === "number" ? 'min="0" step="1"' : ""}>`}</label>`;
}
function openDialog(title, html) {
  $("#dialog-title").textContent = title;
  $("#dialog-body").innerHTML = html;
  $("#dialog").showModal();
}
const options = (key) => data[key].map((r) => [r.id, r.name || r.plate]);
const statuses = (values) => values.map((s) => [s, labels[s]]);

export {
  person,
  button,
  detailButton,
  toast,
  heading,
  banner,
  tableMarkup,
  field,
  openDialog,
  options,
  statuses,
};
