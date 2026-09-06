import { esc, badge } from "../../core/utils.js";
import { plate } from "../../core/store.js";
import { detailButton } from "../../components/ui.js";

const config = {
  title: "Thiết bị giám sát",
  desc: "Theo dõi Raspberry Pi và camera được gắn trên phương tiện.",
  add: "Thêm thiết bị",
  cols: [
    "Mã thiết bị",
    "Tên thiết bị",
    "Phương tiện",
    "Trạng thái",
    "Kết nối gần nhất",
    "",
  ],
  row: (r) => [
    `<strong>${esc(r.code)}</strong>`,
    esc(r.name),
    esc(plate(r.vehicle)),
    badge(r.status),
    esc(r.seen || "Chưa kết nối"),
    detailButton("devices", r.id),
  ],
};

export { config };
