import { esc, badge } from "../../core/utils.js";
import { find, plate } from "../../core/store.js";
import { detailButton } from "../../components/ui.js";

const config = {
  title: "Quản lý phương tiện",
  desc: "Quản lý xe tải, xe khách và tình trạng sử dụng.",
  add: "Thêm phương tiện",
  cols: ["Biển số", "Loại xe", "Hãng / mẫu xe", "Thông số", "Trạng thái", ""],
  row: (r) => [
    `<strong>${esc(r.plate)}</strong>`,
    esc(find("types", r.type)?.name),
    `${esc(r.brand)}<small>${esc(r.model)} · ${esc(r.year)}</small>`,
    r.seats ? `${r.seats} chỗ` : `${esc(r.load)} kg`,
    badge(r.status),
    detailButton("vehicles", r.id),
  ],
};

export { config };
