import { esc, badge } from "../core/utils.js";
import { data, role, filter, violationName, visible } from "../core/store.js";
import {
  person,
  button,
  detailButton,
  heading,
  tableMarkup,
} from "../components/ui.js";
import { urlFor } from "../core/router.js";

function dashboard() {
  const vs = visible("violations"),
    ss = visible("sessions");
  const stats =
    role === "admin"
      ? [
          ["Tổng số tài xế", data.drivers.length, "Hồ sơ được quản lý", "♙"],
          [
            "Phương tiện",
            data.vehicles.length,
            `${data.vehicles.filter((v) => v.status === "ACTIVE").length} xe đang hoạt động`,
            "▱",
          ],
          [
            "Phiên đang lái",
            ss.filter((s) => s.status === "STARTED").length,
            "Theo dõi phiên lái hiện tại",
            "◷",
          ],
          [
            "Vi phạm chờ duyệt",
            vs.filter((v) => v.status === "PENDING").length,
            "Cần kiểm tra bằng chứng",
            "△",
          ],
        ]
      : [
          [
            "Xe được giao",
            visible("vehicles").length,
            "Phương tiện của bạn",
            "▱",
          ],
          [
            "Phiên đang lái",
            ss.filter((s) => s.status === "STARTED").length,
            "An toàn trên mỗi hành trình",
            "◷",
          ],
          ["Vi phạm", vs.length, "Chờ duyệt và đã duyệt", "△"],
          ["Kháng cáo", visible("appeals").length, "Theo dõi phản hồi", "☷"],
        ];
  const pending = data.drivers.filter((d) => d.status === "PENDING").length;
  return (
    heading(
      role === "admin" ? "Tổng quan vận hành" : "Chào buổi mới, Minh",
      role === "admin"
        ? "Theo dõi đội xe, tài xế và an toàn trên mỗi hành trình."
        : "Kiểm tra hồ sơ và chuẩn bị cho một chuyến đi an toàn.",
      `<a class="button primary" href="${urlFor(role === "admin" ? "assignments" : "sessions")}">${role === "admin" ? "+ Phân công xe" : "Theo dõi phiên lái →"}</a>`,
    ) +
    `<div class="stats">${stats.map(([name, n, note, icon]) => `<div class="stat"><div class="stat-top"><span>${name}</span><span class="stat-icon">${icon}</span></div><div class="stat-number">${String(n).padStart(2, "0")}</div><small>${note}</small></div>`).join("")}</div><div class="dashboard-grid"><section class="card"><div class="card-header"><div><h2>Hoạt động trong tuần</h2><small>Số phiên lái · Biểu đồ minh họa</small></div><span class="tag">31/08 – 06/09</span></div><div class="card-body"><div class="chart" role="img" aria-label="Dữ liệu minh họa số phiên lái từ thứ hai đến chủ nhật: 8, 12, 9, 15, 11, 18, 13">${[8, 12, 9, 15, 11, 18, 13].map((n) => `<div class="chart-column"><span>${n}</span><div class="bar" style="height:${n * 7}px"></div></div>`).join("")}</div><div class="chart-labels">${["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((d) => `<span>${d}</span>`).join("")}</div></div></section><section class="card"><div class="card-header"><h2>${role === "admin" ? "Cần xử lý" : "Chuẩn bị trước khi lái"}</h2><span class="tag warn">${role === "admin" ? "Danh sách công việc" : "Hồ sơ của bạn"}</span></div><div class="card-body">${(role ===
    "admin"
      ? [
          [
            `${pending} hồ sơ chờ duyệt`,
            "Kiểm tra thông tin tài xế",
            "drivers",
          ],
          [
            `${vs.filter((v) => v.status === "PENDING").length} vi phạm mới`,
            "Xem xét sự việc và bằng chứng",
            "violations",
          ],
          [
            `${data.appeals.filter((a) => a.status === "PENDING").length} kháng cáo chờ xử lý`,
            "Phản hồi đến tài xế",
            "appeals",
          ],
        ]
      : [
          ["Thông tin cá nhân", "Kiểm tra trạng thái phê duyệt", "profile"],
          ["Giấy phép lái xe", "Theo dõi hạng và hạn sử dụng", "license"],
          ["Xác thực khuôn mặt", "Kiểm tra hồ sơ nhận diện", "face"],
        ]
    )
      .map(
        ([t, s, link]) =>
          `<a class="task" href="${urlFor(link)}"><span class="task-symbol">${role === "admin" ? "!" : "✓"}</span><div class="task-content"><strong>${t}</strong><small>${s}</small></div><span>→</span></a>`,
      )
      .join(
        "",
      )}</div></section></div><section class="card"><div class="card-header"><div><h2>Vi phạm gần đây</h2><small>Cập nhật tình hình an toàn của đội xe</small></div><a href="${urlFor("violations")}">Xem tất cả →</a></div>${tableMarkup(
      ["Mã vi phạm", "Tài xế", "Hành vi", "Mức độ", "Trạng thái", ""],
      vs
        .slice(0, 5)
        .map((v) => [
          `<strong>VP-${String(v.id).padStart(3, "0")}</strong>`,
          person(v.driver),
          esc(violationName(v.type)),
          badge(v.severity),
          badge(v.status),
          detailButton("violations", v.id),
        ]),
    )}</section>`
  );
}

export { dashboard };
