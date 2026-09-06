import { $, stamp } from "../core/utils.js";
import { data, role, page, find } from "../core/store.js";
import { toast } from "../components/ui.js";
import { setRole } from "../core/store.js";
import { navigate } from "../core/router.js";
import { render } from "../core/render.js";

function bindForms() {
  document.addEventListener("submit", (e) => {
    const form = e.target.closest("form[data-form]");
    if (!form) return;
    e.preventDefault();
    const values = Object.fromEntries(new FormData(form));
    const kind = form.dataset.form,
      id = Number(form.dataset.id);
    if (!["auth", "edit", "profile", "review", "appeal", "resolve"].includes(kind)) return;
    const fail = (message) => {
      toast(message);
      return false;
    };
    if (kind === "auth") {
      if (page === "register" && values.password !== values.confirm)
        return fail("Mật khẩu nhập lại chưa khớp.");
      if (page === "register") {
        form.reset();
        toast("Đã kiểm tra biểu mẫu. Chưa tạo tài khoản vì chưa kết nối API.");
        return;
      }
      setRole("driver");
      $("#role").value = role;
      navigate("dashboard");
      return;
    }
    if (kind === "edit") {
      const key = form.dataset.key;
      for (const k of ["driver", "vehicle", "type", "year", "load", "seats"])
        if (k in values) values[k] = Number(values[k]);
      for (const k of Object.keys(values))
        if (typeof values[k] === "string") values[k] = values[k].trim();
      if (key === "violationTypes")
        values.code = values.code.toUpperCase().replace(/\s+/g, "_");
      const unique = {
        vehicles: "plate",
        devices: "code",
        violationTypes: "code",
      }[key];
      if (
        unique &&
        data[key].some(
          (r) =>
            r.id !== id &&
            r[unique].toLowerCase() === values[unique].toLowerCase(),
        )
      )
        return fail("Mã hoặc biển số này đã tồn tại.");
      if (
        key === "devices" &&
        data.devices.some((r) => r.id !== id && r.vehicle === values.vehicle)
      )
        return fail("Xe đã được gắn một thiết bị.");
      if (key === "vehicles") {
        const type = find("types", values.type);
        if (type.category === "TRUCK" && values.load <= 0)
          return fail("Xe tải cần khối lượng lớn hơn 0.");
        if (type.category === "BUS" && values.seats <= 0)
          return fail("Xe khách cần số hành khách lớn hơn 0.");
        if (type.category === "TRUCK") values.seats = 0;
        else values.load = 0;
      }
      if (key === "assignments") {
        if (values.end && values.end <= values.start)
          return fail("Thời gian kết thúc phải sau thời gian bắt đầu.");
        if (find("vehicles", values.vehicle).status !== "ACTIVE")
          return fail("Chỉ phân công phương tiện đang hoạt động.");
      }
      if (id) Object.assign(find(key, id), values);
      else
        data[key].push({
          ...values,
          id: Math.max(0, ...data[key].map((r) => r.id)) + 1,
        });
    }
    if (kind === "profile") {
      const p = form.dataset.kind;
      if (p === "profile") {
        const d = find("drivers", 1);
        if (d.name !== values.name || d.birth !== values.birth)
          d.status = "PENDING";
        Object.assign(d, values);
      } else if (p === "license") {
        if (values.expiry <= values.issued)
          return fail("Ngày hết hạn phải sau ngày cấp.");
        let l = data.licenses.find((r) => r.driver === 1);
        if (!l) {
          l = {
            id: Math.max(0, ...data.licenses.map((r) => r.id)) + 1,
            driver: 1,
          };
          data.licenses.push(l);
        }
        Object.assign(l, {
          number: values.number,
          class: values.class,
          issued: values.issued,
          expiry: values.expiry,
          status: "PENDING",
        });
      } else {
        let f = data.faces.find((r) => r.driver === 1);
        if (!f) {
          f = {
            id: Math.max(0, ...data.faces.map((r) => r.id)) + 1,
            driver: 1,
          };
          data.faces.push(f);
        }
        f.status = "PENDING";
      }
    }
    if (kind === "review") {
      Object.assign(find("violations", id), {
        type: Number(values.type),
        severity: values.severity,
        note: values.note,
        status: e.submitter.value,
      });
    }
    if (kind === "appeal") {
      const v = find("violations", id);
      if (v.driver !== 1 || v.status !== "APPROVED" || v.appealed)
        return fail("Vi phạm không đủ điều kiện kháng cáo.");
      if (!values.content.trim())
        return fail("Vui lòng nhập nội dung kháng cáo.");
      v.appealed = true;
      data.appeals.push({
        id: Math.max(0, ...data.appeals.map((r) => r.id)) + 1,
        violation: id,
        content: values.content.trim(),
        status: "PENDING",
        response: "",
      });
    }
    if (kind === "resolve") {
      const a = find("appeals", id);
      a.status = e.submitter.value;
      a.response = values.response;
      a.resolved = stamp();
      find("violations", a.violation).status =
        a.status === "APPROVED" ? "REVOKED" : "APPROVED";
    }
    $("#dialog").close();
    render();
    toast("Đã cập nhật dữ liệu mẫu trong tab này.");
  });
}

export { bindForms };
