import { esc, badge } from "../../core/utils.js";
import { plate } from "../../core/store.js";
import { person, detailButton } from "../../components/ui.js";

const config = {
  title: "Phiên lái xe",
  desc: "Theo dõi phiên đang lái và lịch sử. Phiên được tạo tự động sau khi tài xế bấm nút trên thiết bị, camera chụp ảnh xác minh và hệ thống hoàn tất kiểm tra.",
  cols: [
    "Mã phiên",
    "Tài xế",
    "Phương tiện",
    "Bắt đầu",
    "Kết thúc",
    "Trạng thái",
    "",
  ],
  row: (r) => [
    `PL-${r.id}`,
    person(r.driver),
    esc(plate(r.vehicle)),
    esc(r.start),
    esc(r.end || "—"),
    badge(r.status),
    detailButton("sessions", r.id),
  ],
};

export { config };
