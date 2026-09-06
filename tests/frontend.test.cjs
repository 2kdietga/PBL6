const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// Load actual ES modules in a minimal DOM without installing browser dependencies.
async function createApp(initialPath = "/dashboard/", hash = "") {
  const nodes = new Map();
  const events = {};
  const windowEvents = {};
  const routes = Object.fromEntries(
    [
      "dashboard",
      "drivers",
      "vehicles",
      "assignments",
      "sessions",
      "violations",
      "appeals",
      "devices",
      "catalogs",
      "profile",
      "license",
      "face",
      "login",
      "register",
    ].map((name) => [name, `/${name}/`]),
  );
  routes.home = "/";
  const location = {
    pathname: initialPath,
    hash,
    origin: "http://localhost",
    href: `http://localhost${initialPath}`,
  };
  const history = { pushState: changePath, replaceState: changePath };
  function changePath(state, title, url) {
    location.pathname = url;
    location.href = `http://localhost${url}`;
    location.hash = "";
  }
  function node(selector) {
    if (!nodes.has(selector))
      nodes.set(selector, {
        innerHTML: "",
        textContent: "",
        style: {},
        value: "",
        addEventListener() {},
        setAttribute() {},
        showModal() {},
        close() {},
        focus() {},
      });
    return nodes.get(selector);
  }
  node("#frontend-routes").textContent = JSON.stringify(routes);
  const context = vm.createContext({
    URL,
    location,
    history,
    setTimeout() {},
    clearTimeout() {},
    document: {
      querySelector: node,
      addEventListener(type, listener) {
        (events[type] ??= []).push(listener);
      },
      body: {
        classList: {
          remove() {},
          toggle() {
            return false;
          },
        },
      },
    },
    window: {
      addEventListener(type, listener) {
        windowEvents[type] = listener;
      },
      scrollTo() {},
    },
    FormData: class {
      constructor(form) {
        return Object.entries(form.values);
      }
    },
  });
  const modules = new Map();
  const root = path.resolve(__dirname, "../static");
  function load(filename) {
    if (!modules.has(filename))
      modules.set(
        filename,
        new vm.SourceTextModule(fs.readFileSync(filename, "utf8"), {
          context,
          identifier: filename,
        }),
      );
    return modules.get(filename);
  }
  const main = load(path.join(root, "app.js"));
  await main.link((specifier, parent) =>
    load(path.resolve(path.dirname(parent.identifier), specifier)),
  );
  await main.evaluate();
  return {
    node,
    location,
    events,
    windowEvents,
    store: load(path.join(root, "js/core/store.js")).namespace,
    router: load(path.join(root, "js/core/router.js")).namespace,
    dialogs: load(path.join(root, "js/components/dialogs.js")).namespace,
    submit(kind, id, values, decision) {
      const form = { dataset: { form: kind, id }, values };
      for (const listener of events.submit)
        listener({
          target: { closest: () => form },
          preventDefault() {},
          submitter: { value: decision },
        });
    },
  };
}

test("module graph loads and every page renders for its role", async () => {
  const app = await createApp();
  for (const role of ["admin", "driver"]) {
    app.store.setRole(role);
    const pages =
      role === "admin"
        ? [
            "dashboard",
            "drivers",
            "vehicles",
            "assignments",
            "sessions",
            "violations",
            "appeals",
            "devices",
            "catalogs",
            "login",
            "register",
          ]
        : [
            "dashboard",
            "profile",
            "license",
            "face",
            "vehicles",
            "sessions",
            "violations",
            "appeals",
            "login",
            "register",
          ];
    for (const page of pages) {
      app.router.navigate(page);
      assert.equal(app.location.pathname, `/${page}/`);
      assert.ok(app.node("#main").innerHTML.length > 100, page);
      assert.ok(!app.node("#main").innerHTML.includes('href="#'));
    }
  }
});

test("detail dialogs and edit forms retain their module dependencies", async () => {
  const app = await createApp();
  for (const key of ["drivers", "vehicles", "assignments", "sessions", "violations", "appeals", "devices", "types", "violationTypes"]) {
    app.dialogs.details(key, 1);
    assert.ok(app.node("#dialog-body").innerHTML.length > 100, key);
  }
  for (const key of ["vehicles", "assignments", "devices", "types", "violationTypes"]) {
    app.dialogs.editForm(key);
    assert.ok(app.node("#dialog-body").innerHTML.includes('<form'), key);
  }
});

test("direct driver URL and old bookmarks resolve correctly", async () => {
  const direct = await createApp("/license/");
  assert.equal(direct.store.role, "driver");
  assert.equal(direct.store.page, "license");
  const legacy = await createApp("/", "#vehicles");
  assert.equal(legacy.location.pathname, "/vehicles/");
  assert.equal(legacy.store.page, "vehicles");
});

test("navigation retains demo state and back navigation resets filters", async () => {
  const app = await createApp();
  app.store.data.vehicles[0].plate = "TEST-123";
  app.router.navigate("vehicles");
  app.store.setQuery("no match");
  app.location.pathname = "/violations/";
  app.windowEvents.popstate();
  assert.equal(app.store.page, "violations");
  assert.equal(app.store.query, "");
  assert.equal(app.store.data.vehicles[0].plate, "TEST-123");
});

test("appeal is single use and accepted appeal hides the driver violation", async () => {
  const app = await createApp();
  app.store.setRole("driver");
  app.submit("appeal", 2, { content: "Xin kiểm tra lại." });
  app.submit("appeal", 2, { content: "Gửi lần hai." });
  assert.equal(
    app.store.data.appeals.filter((a) => a.violation === 2).length,
    1,
  );
  app.store.setRole("admin");
  app.submit("resolve", 2, { response: "Chấp nhận" }, "APPROVED");
  app.store.setRole("driver");
  assert.equal(
    app.store.visible("violations").some((v) => v.id === 2),
    false,
  );
  assert.equal(
    app.store.visible("appeals").some((a) => a.violation === 2),
    false,
  );
});

test("web only displays sessions and cannot create one", async () => {
  const app = await createApp();
  for (const role of ["admin", "driver"]) {
    app.store.setRole(role);
    app.router.navigate("sessions");
    const html = app.node("#main").innerHTML;
    assert.ok(html.includes("camera chụp ảnh xác minh"));
    assert.ok(!/data-action="(?:start|stop|confirm-stop)"/.test(html));
    app.submit("start", 0, { vehicle: "1" });
    assert.equal(app.store.data.sessions.length, 2);
  }
});

test("entered text is escaped", async () => {
  const app = await createApp();
  app.store.setRole("admin");
  app.store.data.drivers[0].name = "<img src=x onerror=alert(1)>";
  app.router.navigate("drivers");
  assert.ok(!app.node("#main").innerHTML.includes("<img src=x"));
  assert.ok(app.node("#main").innerHTML.includes("&lt;img"));
});
