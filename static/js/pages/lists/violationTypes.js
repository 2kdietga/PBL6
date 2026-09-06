import { esc } from "../../core/utils.js";
import { detailButton } from "../../components/ui.js";

const config = {
  title: "Loại vi phạm",
  desc: "Danh mục hành vi được sử dụng khi xem xét vi phạm.",
  add: "Thêm loại vi phạm",
  cols: ["Mã", "Tên hành vi", "Mô tả", ""],
  row: (r) => [
    esc(r.code),
    esc(r.name),
    esc(r.description),
    detailButton("violationTypes", r.id),
  ],
};

export { config };
