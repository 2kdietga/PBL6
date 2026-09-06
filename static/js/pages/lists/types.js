import { esc, badge } from "../../core/utils.js";
import { detailButton } from "../../components/ui.js";

const config = {
  title: "Loại phương tiện",
  desc: "Danh mục xe tải và xe khách.",
  add: "Thêm loại xe",
  cols: ["Tên loại xe", "Nhóm", "Mô tả", ""],
  row: (r) => [
    esc(r.name),
    badge(r.category),
    esc(r.description),
    detailButton("types", r.id),
  ],
};

export { config };
