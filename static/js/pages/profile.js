import { esc, badge } from "../core/utils.js";
import { data, page, find } from "../core/store.js";
import { button, heading, field } from "../components/ui.js";

function profilePage() {
  const d = find("drivers", 1),
    l = data.licenses.find((r) => r.driver === 1),
    f = data.faces.find((r) => r.driver === 1);
  let fields = "",
    note = "",
    status = d.status;
  if (page === "profile") {
    fields =
      field("name", "Họ và tên", d.name) +
      field("birth", "Ngày sinh", d.birth, "date") +
      field("phone", "Số điện thoại", d.phone, "tel") +
      field("address", "Địa chỉ", d.address);
    note =
      "Thay đổi họ tên hoặc ngày sinh sẽ đưa hồ sơ về trạng thái chờ duyệt.";
  }
  if (page === "license") {
    status = l?.status || "PENDING";
    fields =
      field("number", "Số giấy phép", l?.number) +
      field("class", "Hạng giấy phép", l?.class) +
      field("issued", "Ngày cấp", l?.issued, "date") +
      field("expiry", "Ngày hết hạn", l?.expiry, "date") +
      field("front", "Ảnh mặt trước", "", "file", null, !l) +
      field("back", "Ảnh mặt sau", "", "file", null, !l);
    note =
      "Mỗi tài xế có một GPLX hiện tại. Cập nhật sẽ chuyển giấy phép về chờ duyệt. Ảnh chỉ được xem trước trong tab.";
  }
  if (page === "face") {
    status = f?.status || "PENDING";
    fields = field("image", "Ảnh khuôn mặt rõ nét", "", "file");
    note =
      "Chọn ảnh chính diện, đủ sáng và không che khuôn mặt. Bản giao diện chưa tạo embedding hoặc thực hiện xác thực nhận diện.";
  }
  return (
    heading(
      {
        profile: "Hồ sơ cá nhân",
        license: "Giấy phép lái xe",
        face: "Hồ sơ khuôn mặt",
      }[page],
      "Cập nhật thông tin để luôn sẵn sàng cho hành trình.",
    ) +
    `<div class="profile-grid"><section class="card profile-summary"><span class="avatar">VM</span><h2>${esc(d.name)}</h2><p class="subtitle">Tài xế · TX-001</p><p>${badge(status)}</p><small>${esc(d.email)}</small></section><section class="card"><div class="card-header"><h2>Thông tin ${page === "profile" ? "tài xế" : page === "license" ? "giấy phép" : "nhận diện"}</h2></div><div class="card-body"><form data-form="profile" data-kind="${page}"><div class="form-grid">${fields}</div><div class="notice">${note}</div><div class="form-actions"><button class="button primary">Lưu thông tin mẫu</button></div></form></div></section></div>`
  );
}

export { profilePage };
