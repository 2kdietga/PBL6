const menu = document.querySelector('#menu');
const sidebar = document.querySelector('#sidebar');
const backdrop = document.querySelector('.nav-backdrop');
const mobile = window.matchMedia('(max-width: 700px)');
const backgroundRegions = [document.querySelector('main'), document.querySelector('.page-footer'), document.querySelector('.topbar-right')];
let previouslyFocused;

function setMenu(open, restoreFocus = true) {
  open = Boolean(open && mobile.matches && menu);
  document.body.classList.toggle('menu-open', open);
  menu?.setAttribute('aria-expanded', String(open));
  menu?.setAttribute('aria-label', open ? 'Đóng menu' : 'Mở menu');
  if (backdrop) backdrop.hidden = !open;
  if (sidebar) sidebar.inert = mobile.matches && !open;
  for (const region of backgroundRegions) if (region) region.inert = open;
  if (open) {
    previouslyFocused = document.activeElement;
    sidebar?.querySelector('a')?.focus();
  } else if (restoreFocus && previouslyFocused) {
    previouslyFocused.focus();
    previouslyFocused = null;
  }
}
menu?.addEventListener('click', () => setMenu(menu.getAttribute('aria-expanded') !== 'true'));
backdrop?.addEventListener('click', () => setMenu(false));
mobile.addEventListener('change', () => setMenu(false, false));
setMenu(false, false);
document.addEventListener('keydown', event => {
  if (!document.body.classList.contains('menu-open')) return;
  if (event.key === 'Escape') { event.preventDefault(); setMenu(false); }
  if (event.key === 'Tab') {
    const items = [menu, ...sidebar.querySelectorAll('a[href],button:not([disabled])')].filter(Boolean);
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
sidebar?.addEventListener('click', event => { if (event.target.closest('a')) setMenu(false, false); });

document.querySelectorAll('input[type="password"]').forEach(input => {
  const wrapper = document.createElement('div');
  wrapper.className = 'password-control';
  input.before(wrapper);
  wrapper.append(input);
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'password-toggle';
  toggle.textContent = 'Hiện';
  toggle.setAttribute('aria-label', 'Hiện mật khẩu');
  toggle.setAttribute('aria-controls', input.id);
  toggle.setAttribute('aria-pressed', 'false');
  toggle.addEventListener('click', () => {
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    toggle.textContent = show ? 'Ẩn' : 'Hiện';
    toggle.setAttribute('aria-label', show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
    toggle.setAttribute('aria-pressed', String(show));
  });
  wrapper.append(toggle);
});
document.querySelectorAll('.has-error input,.has-error select,.has-error textarea').forEach(input => input.setAttribute('aria-invalid', 'true'));
document.querySelector('.form-error-summary')?.focus();
document.querySelectorAll('.dismiss-notice').forEach(button => button.addEventListener('click', () => button.closest('.notice').remove()));

document.querySelectorAll('.bulk-form').forEach(form => {
  const selectAll = form.querySelector('[data-select-all]');
  const rows = [...form.querySelectorAll('[data-select-row]')];
  const count = form.querySelector('[data-selected-count]');
  const deleteButton = form.querySelector('[data-bulk-delete]');
  const refresh = () => {
    const selected = rows.filter(input => input.checked).length;
    count.textContent = String(selected);
    deleteButton.disabled = selected === 0;
    selectAll.checked = rows.length > 0 && selected === rows.length;
    selectAll.indeterminate = selected > 0 && selected < rows.length;
  };
  selectAll?.addEventListener('change', () => {
    rows.forEach(input => { input.checked = selectAll.checked; });
    refresh();
  });
  rows.forEach(input => input.addEventListener('change', refresh));
  refresh();
});

const vehicleType = document.querySelector('#id_vehicle_type');
const loadCapacity = document.querySelector('#id_load_capacity');
const passengerCapacity = document.querySelector('#id_passenger_capacity');
if (vehicleType && loadCapacity && passengerCapacity) {
  const loadField = loadCapacity.closest('.field');
  const passengerField = passengerCapacity.closest('.field');
  const refreshVehicleFields = () => {
    const category = vehicleType.selectedOptions[0]?.dataset.category || '';
    const isTruck = category === 'TRUCK';
    const isBus = category === 'BUS';
    loadField.hidden = !isTruck;
    passengerField.hidden = !isBus;
    loadCapacity.disabled = !isTruck;
    passengerCapacity.disabled = !isBus;
    loadCapacity.required = isTruck;
    passengerCapacity.required = isBus;
    loadCapacity.setAttribute('aria-required', String(isTruck));
    passengerCapacity.setAttribute('aria-required', String(isBus));
  };
  vehicleType.addEventListener('change', refreshVehicleFields);
  refreshVehicleFields();
}

document.addEventListener('change', event => {
  const input = event.target;
  if (input.type !== 'file') return;
  const field = input.closest('.field');
  if (!field) return;
  field.querySelectorAll('.upload-preview').forEach(image => image.remove());
  // Preview only the supported number/size; server validation remains authoritative.
  for (const file of Array.from(input.files).slice(0, input.multiple ? 4 : 1)) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) continue;
    const image = document.createElement('img');
    image.className = 'upload-preview';
    image.alt = 'Ảnh vừa chọn: ' + file.name;
    const url = URL.createObjectURL(file);
    image.src = url;
    image.onload = image.onerror = () => URL.revokeObjectURL(url);
    field.append(image);
  }
});

document.addEventListener('submit', event => {
  const form = event.target;
  if (event.defaultPrevented || form.method.toLowerCase() !== 'post') return;
  if (form.dataset.busy === 'true') { event.preventDefault(); return; }
  const button = event.submitter;
  if (button?.dataset.confirm && !window.confirm(button.dataset.confirm)) { event.preventDefault(); return; }
  form.dataset.busy = 'true';
  form.setAttribute('aria-busy', 'true');
  // Preserve the submitter's name/value (approve/reject/etc.) in the request.
  // Actual disabled controls would be excluded from the form submission.
  if (button) {
    button.dataset.originalText = button.textContent;
    button.textContent = form.querySelector('input[type="file"]') ? 'Đang lưu…' : 'Đang xử lý…';
    button.setAttribute('aria-busy', 'true');
  }
  form.querySelectorAll('button[type="submit"],button:not([type])').forEach(item => item.setAttribute('aria-disabled', 'true'));
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[data-busy]').forEach(form => {
    delete form.dataset.busy;
    form.removeAttribute('aria-busy');
    form.querySelectorAll('button').forEach(button => {
      button.removeAttribute('aria-disabled');
      button.removeAttribute('aria-busy');
      if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
        delete button.dataset.originalText;
      }
    });
  });
  setMenu(false, false);
});
