document.querySelector('#menu')?.addEventListener('click', event => {
  const open = document.body.classList.toggle('menu-open');
  event.currentTarget.setAttribute('aria-expanded', String(open));
});
document.addEventListener('click', event => {
  const button = event.target.closest('[data-confirm]');
  if (button && !window.confirm(button.dataset.confirm)) event.preventDefault();
});
document.addEventListener('change', event => {
  const input = event.target;
  if (input.type !== 'file') return;
  const field = input.closest('.field');
  field.querySelectorAll('.upload-preview').forEach(image => image.remove());
  for (const file of input.files) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) continue;
    const image = document.createElement('img');
    image.className = 'upload-preview';
    image.alt = 'Ảnh vừa chọn';
    image.src = URL.createObjectURL(file);
    image.onload = image.onerror = () => URL.revokeObjectURL(image.src);
    field.append(image);
  }
});
document.addEventListener('submit', event => {
  const form = event.target;
  if (!form.querySelector('input[type="file"]') || !form.checkValidity()) return;
  const button = event.submitter;
  if (button) { button.disabled = true; button.textContent = 'Đang lưu và xử lý ảnh…'; }
});
