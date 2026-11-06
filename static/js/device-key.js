(() => {
  const token = document.getElementById('device-token');
  const status = document.getElementById('copy-token-status');
  document.getElementById('copy-device-token').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(token.value);
      status.textContent = 'Đã sao chép token.';
    } catch {
      token.focus();
      token.select();
      status.textContent = 'Hãy nhấn Ctrl+C (hoặc Command+C) để sao chép phần đã chọn.';
    }
  });
  // Clear the secret before this document enters browser history/back-forward cache.
  window.addEventListener('pagehide', () => {
    token.value = '';
    token.textContent = '';
  });
})();
