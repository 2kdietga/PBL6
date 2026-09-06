import { esc, badge } from "../../core/utils.js";
import { detailButton } from "../../components/ui.js";

const config = {
  title: "Kháng cáo",
  desc: "Tiếp nhận ý kiến của tài xế và theo dõi kết quả xem xét.",
  cols: ["Mã kháng cáo", "Vi phạm", "Nội dung", "Trạng thái", ""],
  row: (r) => [
    `KC-${r.id}`,
    `VP-${r.violation}`,
    esc(r.content.length > 65 ? r.content.slice(0, 65) + "…" : r.content),
    badge(r.status),
    detailButton("appeals", r.id),
  ],
};

export { config };
