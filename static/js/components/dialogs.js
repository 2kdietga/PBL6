import { esc, badge } from "../core/utils.js";
import { data, role, find, driverName, plate, visible } from "../core/store.js";
import {
  button,
  tableMarkup,
  field,
  openDialog,
  options,
  statuses,
} from "../components/ui.js";
import { configs } from "../pages/list.js";

function editForm(key, id) {
  const r = id ? find(key, id) : {};
  let fields = "";
  if (key === "vehicles")
    fields =
      field("plate", "Biển số", r.plate) +
      field("type", "Loại phương tiện", r.type, "text", options("types")) +
      field("brand", "Hãng xe", r.brand) +
      field("model", "Mẫu xe", r.model) +
      field("year", "Năm sản xuất", r.year || 2026, "number") +
      field("load", "Khối lượng (kg)", r.load || 0, "number") +
      field("seats", "Số hành khách", r.seats || 0, "number") +
      field(
        "status",
        "Trạng thái",
        r.status || "ACTIVE",
        "text",
        statuses(["ACTIVE", "INACTIVE", "LIQUIDATED"]),
      );
  if (key === "assignments")
    fields =
      field("driver", "Tài xế", r.driver, "text", options("drivers")) +
      field("vehicle", "Phương tiện", r.vehicle, "text", options("vehicles")) +
      field("start", "Bắt đầu", r.start || "", "datetime-local") +
      field(
        "end",
        "Kết thúc (không bắt buộc)",
        r.end || "",
        "datetime-local",
        null,
        false,
      );
  if (key === "devices")
    fields =
      field("code", "Mã thiết bị", r.code) +
      field("name", "Tên thiết bị", r.name) +
      field("vehicle", "Phương tiện", r.vehicle, "text", options("vehicles")) +
      field(
        "status",
        "Trạng thái",
        r.status || "OFFLINE",
        "text",
        statuses(["ONLINE", "OFFLINE", "MAINTENANCE"]),
      );
  if (key === "types")
    fields =
      field("name", "Tên loại xe", r.name) +
      field(
        "category",
        "Nhóm",
        r.category || "TRUCK",
        "text",
        statuses(["TRUCK", "BUS"]),
      ) +
      field("description", "Mô tả", r.description, "textarea", null, false);
  if (key === "violationTypes")
    fields =
      field("code", "Mã hành vi", r.code) +
      field("name", "Tên hành vi", r.name) +
      field("description", "Mô tả", r.description, "textarea", null, false);
  openDialog(
    `${id ? "Cập nhật" : "Thêm mới"} · ${configs[key].title}`,
    `<form data-form="edit" data-key="${key}" data-id="${id || ""}"><div class="form-grid">${fields}</div><p class="notice">Thay đổi được lưu tạm trong tab xem trước.</p><div class="form-actions"><button class="button primary">Lưu thông tin mẫu</button></div></form>`,
  );
}
function details(key, id) {
  const r = find(key, id);
  if (!r) return;
  let body = "",
    actions = "";
  const item = (label, value) =>
    `<div class="detail-item"><small>${label}</small><strong>${value}</strong></div>`;
  if (key === "violations") {
    if (role === "driver" && !visible(key).some((v) => v.id === r.id)) return;
    body = `<div class="detail-grid">${item("Tài xế", esc(driverName(r.driver)))}${item("Phương tiện", esc(plate(r.vehicle)))}${item("Thời điểm phát hiện", esc(r.time))}${item("Trạng thái", badge(r.status))}</div><h3>Bằng chứng hình ảnh / video</h3><div class="empty">Chưa có bằng chứng trong dữ liệu mẫu.<small>Ảnh và video sẽ được hiển thị khi kết nối API bằng chứng.</small></div>`;
    if (role === "admin")
      body += `<form data-form="review" data-id="${r.id}"><div class="form-grid">${field("type", "Loại vi phạm", r.type, "text", options("violationTypes"))}${field("severity", "Mức độ", r.severity, "text", statuses(["LOW", "MEDIUM", "HIGH"]))}${field("note", "Ghi chú của quản trị viên", r.note, "textarea", null, false)}</div><div class="form-actions">${r.status === "PENDING" ? '<button class="button danger" name="decision" value="REJECTED">Từ chối mẫu</button><button class="button primary" name="decision" value="APPROVED">Duyệt mẫu</button>' : '<button class="button" name="decision" value="PENDING">Xem xét lại</button>'}</div></form>`;
    else
      body += `<div class="notice">Ghi chú: ${esc(r.note || "Chưa có ghi chú.")}</div>${r.status === "APPROVED" && !r.appealed ? `<form data-form="appeal" data-id="${r.id}">${field("content", "Nội dung kháng cáo", "", "textarea")}<p class="notice">Mỗi vi phạm chỉ được kháng cáo một lần. Nội dung không thể sửa sau khi gửi.</p><div class="form-actions"><button class="button primary">Gửi kháng cáo mẫu</button></div></form>` : `<p class="notice">${r.appealed ? "Bạn đã gửi kháng cáo cho vi phạm này." : "Bạn có thể kháng cáo sau khi vi phạm được duyệt."}</p>`}`;
  } else if (key === "appeals") {
    body = `<div class="detail-grid">${item("Vi phạm", `VP-${r.violation}`)}${item("Trạng thái", badge(r.status))}</div><h3>Nội dung tài xế</h3><p class="notice">${esc(r.content)}</p>`;
    body +=
      role === "admin"
        ? `<form data-form="resolve" data-id="${r.id}">${field("response", "Phản hồi", r.response, "textarea", null, false)}<div class="form-actions"><button class="button danger" name="decision" value="REJECTED">Từ chối</button><button class="button primary" name="decision" value="APPROVED">Chấp nhận</button></div></form>`
        : `<p class="notice">Phản hồi: ${esc(r.response || "Đang chờ quản trị viên xử lý.")}</p>`;
  } else if (key === "drivers") {
    const l = data.licenses.find((x) => x.driver === r.id),
      f = data.faces.find((x) => x.driver === r.id);
    body = `<div class="detail-grid">${item("Họ và tên", esc(r.name))}${item("Ngày sinh", esc(r.birth))}${item("Điện thoại", esc(r.phone))}${item("Hồ sơ", badge(r.status))}${item("GPLX", l ? `${esc(l.number)} · ${esc(l.class)}<br>${badge(l.status)}` : "Chưa bổ sung")}${item("Khuôn mặt", f ? badge(f.status) : "Chưa bổ sung")}</div><div class="notice">Ảnh GPLX, ảnh khuôn mặt và embedding chưa có trong bản mẫu. Cần kiểm tra dữ liệu thật trước khi duyệt trên hệ thống chính thức.</div>`;
    actions =
      button(
        r.active ? "Vô hiệu hóa mẫu" : "Kích hoạt mẫu",
        "toggle-driver",
        r.id,
      ) +
      (r.status === "PENDING"
        ? button("Duyệt hồ sơ mẫu", "approve-driver", r.id, "primary")
        : "") +
      (l?.status === "PENDING"
        ? button("Duyệt GPLX mẫu", "approve-license", l.id)
        : "") +
      (f?.status === "PENDING"
        ? button("Duyệt khuôn mặt mẫu", "approve-face", f.id)
        : "");
  } else {
    body = tableMarkup(configs[key].cols, [
      configs[key].row(r).slice(0, -1).concat("—"),
    ]);
    if (role === "admin" && configs[key].add)
      actions = button("Chỉnh sửa", "edit", `${key}:${r.id}`, "primary");
  }
  openDialog(
    `Chi tiết · ${key === "drivers" ? r.name : key === "violations" ? "VP-" + r.id : configs[key].title}`,
    body + (actions ? `<div class="form-actions">${actions}</div>` : ""),
  );
}

export { editForm, details };
