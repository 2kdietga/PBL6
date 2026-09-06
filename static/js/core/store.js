import { seed } from "../data/demo.js";

// Shared demo state. These live bindings are consumed by the page modules.
let data = seed();
let role = "admin";
let page = "dashboard";
let query = "";
let filter = "";
let catalog = "types";
const setRole = (value) => {
  role = value;
};
const setPage = (value) => {
  page = value;
};
const setQuery = (value) => {
  query = value;
};
const setFilter = (value) => {
  filter = value;
};
const setCatalog = (value) => {
  catalog = value;
};
const find = (collection, id) =>
  data[collection].find((x) => x.id === Number(id));
const driverName = (id) => find("drivers", id)?.name || "Chưa có tài xế";
const plate = (id) => find("vehicles", id)?.plate || "Chưa gắn xe";
const violationName = (id) =>
  find("violationTypes", id)?.name || "Chưa phân loại";
function visible(collection) {
  let rows = data[collection];
  if (role === "admin") return rows;
  if (collection === "vehicles")
    return rows.filter((v) =>
      data.assignments.some((a) => a.driver === 1 && a.vehicle === v.id),
    );
  if (collection === "violations")
    return rows.filter(
      (v) => v.driver === 1 && ["PENDING", "APPROVED"].includes(v.status),
    );
  if (collection === "appeals")
    return rows.filter((a) =>
      visible("violations").some((v) => v.id === a.violation),
    );
  return rows.filter((r) => r.driver === 1);
}

export {
  data,
  role,
  page,
  query,
  filter,
  catalog,
  setRole,
  setPage,
  setQuery,
  setFilter,
  setCatalog,
  find,
  driverName,
  plate,
  violationName,
  visible,
};
