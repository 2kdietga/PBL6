import { esc } from "../../core/utils.js";
import { plate } from "../../core/store.js";
import { person, detailButton } from "../../components/ui.js";

const config = {
  title: "Phân công xe",
  desc: "Giao quyền sử dụng phương tiện cho tài xế theo thời gian.",
  add: "Phân công xe",
  cols: ["Tài xế", "Phương tiện", "Bắt đầu", "Kết thúc", ""],
  row: (r) => [
    person(r.driver),
    esc(plate(r.vehicle)),
    esc(r.start.replace("T", " ")),
    esc(r.end.replace("T", " ") || "Không giới hạn"),
    detailButton("assignments", r.id),
  ],
};

export { config };
