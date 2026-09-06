const $ = (selector) => document.querySelector(selector);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const labels = {
  PENDING: "Chờ duyệt",
  APPROVED: "Đã duyệt",
  REJECTED: "Từ chối",
  REVOKED: "Đã thu hồi",
  ACTIVE: "Hoạt động",
  INACTIVE: "Ngừng hoạt động",
  LIQUIDATED: "Đã thanh lý",
  ONLINE: "Trực tuyến",
  OFFLINE: "Ngoại tuyến",
  MAINTENANCE: "Bảo trì",
  STARTED: "Đang lái",
  ENDED: "Đã kết thúc",
  HIGH: "Cao",
  MEDIUM: "Trung bình",
  LOW: "Thấp",
  EXPIRED: "Hết hạn",
  TRUCK: "Xe tải",
  BUS: "Xe khách",
};
const badge = (s) =>
  `<span class="tag ${["APPROVED", "ACTIVE", "ONLINE"].includes(s) ? "good" : ["PENDING", "MEDIUM", "MAINTENANCE"].includes(s) ? "warn" : ["HIGH", "REJECTED", "EXPIRED", "OFFLINE"].includes(s) ? "bad" : "info"}">${esc(labels[s] || s)}</span>`;
const stamp = () => new Date().toLocaleString("vi-VN");

export { $, esc, labels, badge, stamp };
