(() => {
  const root = document.querySelector('[data-iot-status]');
  if (!root) return;
  const date = value => value && value !== '—' ? new Date(value).toLocaleString('vi-VN') : '—';
  async function refresh() {
    try {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 10000);
      let response;
      try {
        response = await fetch(root.dataset.iotStatus, {headers: {'Accept': 'application/json'}, cache: 'no-store', signal: controller.signal});
      } finally { window.clearTimeout(timeout); }
      if (!response.ok) throw new Error('status');
      const data = await response.json();
      const workerState = document.getElementById('worker-state');
      workerState.textContent = data.worker_available ? 'MQTT · Đã kết nối' : 'MQTT · Mất kết nối';
      workerState.dataset.state = data.worker_available ? 'connected' : 'disconnected';
      for (const row of data.devices) {
        const element = root.querySelector(`[data-device-id="${row.id}"]`);
        if (!element) continue;
        for (const target of element.querySelectorAll('[data-field]')) {
          const key = target.dataset.field;
          if (key === 'connection') target.dataset.state = ({Online: 'online', Offline: 'offline', 'Mất tín hiệu': 'stale'})[row[key]] || 'unknown';
          if (key === 'ai') target.dataset.state = ({'Đang chạy': 'online', 'Đã dừng': 'offline'})[row[key]] || 'unknown';
          if (key === 'sync') target.dataset.state = ({'Đã áp dụng': 'online', 'Bị từ chối': 'offline', 'Chờ gửi': 'pending', 'Chờ xác nhận': 'pending'})[row[key]] || 'unknown';
          target.textContent = ['heartbeat', 'applied_at', 'updated_at'].includes(key) ? date(row[key]) : row[key];
        }
      }
      for (const count of document.querySelectorAll('[data-count]')) {
        count.textContent = count.dataset.count === 'total' ? data.devices.length : data.devices.filter(row => row.connection === count.dataset.count).length;
      }
      const formVersion = document.querySelector('[name="version"]');
      const warning = document.getElementById('iot-stale-form');
      if (warning && formVersion && data.devices.length) warning.hidden = Number(formVersion.value) === data.devices[0].desired;
      const applied = document.getElementById('iot-applied');
      if (applied && data.applied_parameters) {
        applied.replaceChildren();
        for (const [key, value] of Object.entries(data.applied_parameters)) {
          const term = document.createElement('dt'), description = document.createElement('dd');
          term.textContent = key; description.textContent = value;
          applied.append(term, description);
        }
        if (!applied.children.length) {
          const empty = document.createElement('dd'); empty.textContent = 'Chưa nhận xác nhận từ AI.'; applied.append(empty);
        }
      }
      const events = document.getElementById('iot-events');
      if (events && data.events) {
        events.replaceChildren();
        for (const event of data.events) {
          const item = document.createElement('li'); item.textContent = `${date(event.created_at)} — ${event.message}`; events.append(item);
        }
        if (!events.children.length) {
          const empty = document.createElement('li'); empty.textContent = 'Chưa có sự kiện.'; events.append(empty);
        }
      }
    } catch (_) {
      const workerState = document.getElementById('worker-state');
      workerState.textContent = 'MQTT · Chưa xác định';
      workerState.dataset.state = 'disconnected';
    } finally {
      window.setTimeout(refresh, 5000);
    }
  }
  refresh();
})();
