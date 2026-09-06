import { $ } from "../core/utils.js";
import { page, catalog, find } from "../core/store.js";
import { toast } from "../components/ui.js";
import { setQuery, setFilter, setCatalog } from "../core/store.js";
import { render } from "../core/render.js";
import { listResults } from "../pages/list.js";
import { details, editForm } from "../components/dialogs.js";

function bindActions() {
  document.addEventListener("click", (event) => {
    const el = event.target.closest("[data-action]");
    if (!el) return;
    const { action, id, collection } = el.dataset;
    if (action === "detail") details(collection, id);
    if (action === "create") editForm(id);
    if (action === "edit") {
      const [key, rid] = id.split(":");
      $("#dialog").close();
      editForm(key, Number(rid));
    }
    if (action === "catalog") {
      setCatalog(id);
      setQuery("");
      setFilter("");
      render();
    }
    if (action === "toggle-driver") {
      const d = find("drivers", id);
      d.active = !d.active;
      $("#dialog").close();
      render();
      toast("Đã cập nhật tài khoản mẫu.");
    }
    if (action.startsWith("approve-")) {
      const key = {
        "approve-driver": "drivers",
        "approve-license": "licenses",
        "approve-face": "faces",
      }[action];
      if (key) {
        find(key, id).status = key === "licenses" ? "ACTIVE" : "APPROVED";
        $("#dialog").close();
        render();
        toast("Đã duyệt dữ liệu mẫu.");
      }
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.id === "search") {
      setQuery(e.target.value);
      $("#results").innerHTML = listResults(
        page === "catalogs" ? catalog : page,
      );
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target.id === "filter") {
      setFilter(e.target.value);
      $("#results").innerHTML = listResults(
        page === "catalogs" ? catalog : page,
      );
    }
    if (e.target.type === "file") {
      const f = e.target.files[0];
      e.target.parentElement.querySelector("img")?.remove();
      if (!f) return;
      if (
        !["image/jpeg", "image/png", "image/webp"].includes(f.type) ||
        f.size > 5 * 1024 * 1024
      ) {
        e.target.value = "";
        toast("Chọn ảnh JPG, PNG hoặc WebP tối đa 5 MB.");
        return;
      }
      const img = document.createElement("img");
      img.className = "upload-preview";
      img.alt = "Ảnh vừa chọn";
      img.src = URL.createObjectURL(f);
      img.onload = () => URL.revokeObjectURL(img.src);
      e.target.parentElement.append(img);
    }
  });
}

export { bindActions };
