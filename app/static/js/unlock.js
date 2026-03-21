const form = document.getElementById('unlock-form');
const passwordEl = document.getElementById('unlock-password');
const statusEl = document.getElementById('unlock-status');
const submitEl = document.getElementById('unlock-submit');

function setStatus(message, type = '') {
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = 'status' + (type ? ` ${type}` : '');
}

form?.addEventListener('submit', async (event) => {
  event.preventDefault();

  const password = passwordEl?.value || '';
  if (!password) {
    setStatus('请输入访问密码', 'error');
    passwordEl?.focus();
    return;
  }

  if (submitEl) {
    submitEl.disabled = true;
    submitEl.textContent = '验证中...';
  }
  setStatus('正在验证，请稍候...');

  try {
    const response = await fetch('/api/access/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    const payload = await response.json().catch(() => ({}));

    if (response.ok && payload.ok) {
      setStatus('验证成功，跳转中...', 'success');
      window.location.href = '/';
      return;
    }

    setStatus(payload.detail || '密码错误', 'error');
    passwordEl?.select();
  } catch (error) {
    setStatus('验证失败，请稍后重试', 'error');
  } finally {
    if (submitEl) {
      submitEl.disabled = false;
      submitEl.textContent = '验证进入';
    }
  }
});
