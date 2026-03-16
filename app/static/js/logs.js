const listEl = document.getElementById('log-list');
const searchEl = document.getElementById('log-search');
const levelEl = document.getElementById('log-level');
const refreshBtn = document.getElementById('log-refresh');

async function loadLogs() {
  const params = new URLSearchParams();
  if (levelEl.value) params.set('level', levelEl.value);
  if (searchEl.value) params.set('q', searchEl.value);
  const res = await fetch(`/api/logs?${params.toString()}`);
  const json = await res.json();
  const items = json.items || [];
  if (!items.length) {
    listEl.className = 'empty';
    listEl.textContent = '暂无日志';
    return;
  }
  listEl.className = '';
  listEl.innerHTML = items.map(item => `
    <div class="task">
      <div>
        <div class="task-title">${item.level.toUpperCase()} | ${item.created_at}</div>
        <div class="task-meta">${item.message}</div>
      </div>
    </div>
  `).join('');
}

refreshBtn.addEventListener('click', loadLogs);
searchEl.addEventListener('input', loadLogs);
levelEl.addEventListener('change', loadLogs);

loadLogs();
