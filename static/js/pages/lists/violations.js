import { esc, badge } from "../../core/utils.js";
import { plate, violationName } from "../../core/store.js";
import { person, detailButton } from "../../components/ui.js";

const config = {
  title: "Quản lý vi phạm",
  desc: "Xem bằng chứng, duyệt sự việc và theo dõi kết quả xử lý.",
  cols: [
    "Mã vi phạm",
    "Tài xế / xe",
    "Hành vi",
    "Thời điểm",
    "Mức độ",
    "Trạng thái",
    "",
  ],
  row: (r) => [
    `<strong>VP-${String(r.id).padStart(3, "0")}</strong>`,
    `${person(r.driver)}<small>${esc(plate(r.vehicle))}</small>`,
    esc(violationName(r.type)),
    esc(r.time),
    badge(r.severity),
    badge(r.status),
    detailButton("violations", r.id),
  ],
};

export { config };
