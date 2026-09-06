import { data, page } from "../core/store.js";
import { button, field } from "../components/ui.js";
import { urlFor } from "../core/router.js";

function authPage() {
  const register = page === "register";
  return `<section class="card auth"><div class="card-body"><p class="eyebrow">Chào mừng đến FleetCare</p><h1>${register ? "Đăng ký tài xế" : "Đăng nhập"}</h1><p class="subtitle">An tâm trên mọi hành trình.</p><div class="notice">Giao diện mẫu. Chưa có dịch vụ xác thực; không nhập mật khẩu thật.</div><form data-form="auth">${field("username", "Tên đăng nhập")}${register ? field("email", "Email", "", "email") : ""}${field("password", "Mật khẩu mẫu", "", "password")}${register ? field("confirm", "Nhập lại mật khẩu mẫu", "", "password") : ""}<button class="button primary">${register ? "Xem thử đăng ký" : "Vào giao diện mẫu"}</button></form><div class="auth-links"><a href="${urlFor(register ? "login" : "register")}">${register ? "Đã có tài khoản? Đăng nhập" : "Đăng ký tài xế"}</a><a href="${urlFor("dashboard")}">Xem tổng quan →</a></div></div></section>`;
}

export { authPage };
