import { esc, badge } from "../../core/utils.js";
import { person, detailButton } from "../../components/ui.js";

const config = {
  title: "Quản lý tài xế",
  desc: "Hồ sơ, giấy phép và trạng thái hoạt động của tài xế.",
  cols: ["Tài xế", "Liên hệ", "Hồ sơ", "Tài khoản", ""],
  row: (r) => [
    person(r.id),
    `${esc(r.phone)}<small>${esc(r.email)}</small>`,
    badge(r.status),
    badge(r.active ? "ACTIVE" : "INACTIVE"),
    detailButton("drivers", r.id),
  ],
};

export { config };
