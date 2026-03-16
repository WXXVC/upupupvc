const form = document.getElementById('config-form');
const statusEl = document.getElementById('status');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  statusEl.textContent = '保存中...';
  const data = Object.fromEntries(new FormData(form).entries());
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (json.ok && json.configured) {
    statusEl.textContent = '保存成功，跳转中...';
    window.location.href = '/';
    return;
  }
  statusEl.textContent = '已保存，但配置未完整，请检查必填项。';
});
