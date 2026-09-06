// Application entry point. Page rendering and behavior live in js/ modules.
import { $ } from "./js/core/utils.js";
import { setRole } from "./js/core/store.js";
import { bindRouter, navigate } from "./js/core/router.js";
import { bindActions } from "./js/events/actions.js";
import { bindForms } from "./js/events/forms.js";
import { render } from "./js/core/render.js";

bindActions();
bindForms();
$("#close-dialog").addEventListener("click", () => $("#dialog").close());
$("#role").addEventListener("change", (event) => {
  setRole(event.target.value);
  navigate("dashboard");
});
$("#menu").addEventListener("click", () => {
  const open = document.body.classList.toggle("menu-open");
  $("#menu").setAttribute("aria-expanded", String(open));
});
bindRouter(render);
