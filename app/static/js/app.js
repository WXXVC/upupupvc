const statusEl = document.getElementById('sse-status');
const modal = document.getElementById('auth-modal');
const detailEl = document.getElementById('auth-detail');
const form = document.getElementById('auth-form');
const codeLabel = document.getElementById('code-label');
const passwordLabel = document.getElementById('password-label');
const codeInput = document.getElementById('auth-code');
const passwordInput = document.getElementById('auth-password');

const downloadForm = document.getElementById('download-form');
const downloadUrlInput = document.getElementById('download-url');
const downloadBatch = document.getElementById('download-batch');
const downloadBatchSubmit = document.getElementById('download-batch-submit');
const downloadList = document.getElementById('download-list');
const downloadSearch = document.getElementById('download-search');
const downloadStatus = document.getElementById('download-status');

const uploadForm = document.getElementById('upload-form');
const uploadPathInput = document.getElementById('upload-path');
const uploadList = document.getElementById('upload-list');
const uploadSearch = document.getElementById('upload-search');
const uploadStatus = document.getElementById('upload-status');
const downloadPrev = document.getElementById('download-prev');
const downloadNext = document.getElementById('download-next');
const downloadPageEl = document.getElementById('download-page');
const uploadPrev = document.getElementById('upload-prev');
const uploadNext = document.getElementById('upload-next');
const uploadPageEl = document.getElementById('upload-page');
const diskUsageEl = document.getElementById('disk-usage');
const authStatusEl = document.getElementById('auth-status');
const themeToggle = document.getElementById('theme-toggle');
const detailPanel = document.getElementById('detail-panel');
const detailBody = document.getElementById('detail-body');
const detailTitle = document.getElementById('detail-title');
const detailClose = document.getElementById('detail-close');
const prepareModal = document.getElementById('prepare-modal');
const prepareInfo = document.getElementById('prepare-info');
const prepareForm = document.getElementById('prepare-form');
const prepareFilename = document.getElementById('prepare-filename');
const prepareCancel = document.getElementById('prepare-cancel');
const settingsForm = document.getElementById('settings-form');
const settingsStatus = document.getElementById('settings-status');
const tabButtons = Array.from(document.querySelectorAll('[data-tab-button]'));
const tabPanels = Array.from(document.querySelectorAll('[data-tab-panel]'));

let downloadItems = [];
let uploadItems = [];
let downloadPage = 1;
let uploadPage = 1;
const PAGE_SIZE = 20;
let pendingPrepareUrl = '';
let autoUpload = true;

function showModal(state, detail) {
  detailEl.textContent = detail || '';
  if (state === 'wait_password') {
    codeLabel.classList.add('hidden');
    passwordLabel.classList.remove('hidden');
  } else {
    codeLabel.classList.remove('hidden');
    passwordLabel.classList.add('hidden');
  }
  modal.classList.remove('hidden');
}

function setActiveTab(name) {
  tabButtons.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tabButton === name);
  });
  tabPanels.forEach(panel => {
    panel.classList.toggle('active', panel.dataset.tabPanel === name);
  });
  const url = new URL(window.location.href);
  url.searchParams.set('tab', name);
  history.replaceState({}, '', url.toString());
}

function hideModal() {
  modal.classList.add('hidden');
  codeInput.value = '';
  passwordInput.value = '';
}

function showPrepareModal(info, filename) {
  prepareInfo.textContent = info || '';
  prepareFilename.value = filename || '';
  prepareModal.classList.remove('hidden');
}

function hidePrepareModal() {
  prepareModal.classList.add('hidden');
  pendingPrepareUrl = '';
}

async function fetchAuthStatus() {
  const res = await fetch('/api/auth/status');
  const json = await res.json();
  if (!json.configured) {
    setActiveTab('settings');
    return;
  }
  if (authStatusEl) authStatusEl.textContent = json.state || '未知';
}

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const isPassword = !passwordLabel.classList.contains('hidden');
  const payload = {
    type: isPassword ? 'password' : 'code',
    value: isPassword ? passwordInput.value : codeInput.value,
  };
  await fetch('/api/auth/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
});

function renderDownloads() {
  if (!downloadItems.length) {
    downloadList.className = 'empty';
    downloadList.textContent = '暂无下载任务';
    return;
  }
  downloadList.className = '';
  downloadList.innerHTML = downloadItems.map(item => {
    const percent = item.total_size ? Math.round(item.progress) : 0;
    const badgeClass = item.status === 'completed' ? 'success' : (item.status === 'failed' ? 'fail' : 'running');
    const statusText = statusLabel(item.status);
    const manualUploadBtn = (!autoUpload && item.status === 'completed' && item.save_path)
      ? `<button data-action="manual-upload" data-path="${item.save_path}">手动上传</button>`
      : '';
    return `
      <div class="task" data-type="download" data-id="${item.id}">
        <div>
          <div class="task-title">${item.filename || item.url}</div>
          <div class="task-meta">
            <span class="badge ${badgeClass}">${statusText}</span>
            ${percent}% | ${formatBytes(item.speed || 0)}/s
          </div>
          <div class="progress"><span style="width:${percent}%"></span></div>
        </div>
        <div class="task-actions">
          <button data-action="pause" data-id="${item.id}">暂停</button>
          <button data-action="resume" data-id="${item.id}">继续</button>
          <button data-action="cancel" data-id="${item.id}">取消</button>
          <button data-action="retry" data-id="${item.id}">重试</button>
          ${manualUploadBtn}
        </div>
      </div>
    `;
  }).join('');
}

async function loadDownloads() {
  const params = new URLSearchParams();
  if (downloadStatus.value) params.set('status', downloadStatus.value);
  if (downloadSearch.value) params.set('q', downloadSearch.value);
  params.set('page', String(downloadPage));
  params.set('limit', String(PAGE_SIZE));
  const res = await fetch(`/api/tasks/list?${params.toString()}`);
  const json = await res.json();
  downloadItems = json.items || [];
  renderDownloads();
  if (downloadPageEl) downloadPageEl.textContent = String(downloadPage);
}

function renderUploads() {
  if (!uploadItems.length) {
    uploadList.className = 'empty';
    uploadList.textContent = '暂无上传任务';
    return;
  }
  uploadList.className = '';
  uploadList.innerHTML = uploadItems.map(item => {
    const percent = item.total_size ? Math.round(item.progress) : 0;
    const name = item.source_path.split('\\').pop().split('/').pop();
    const badgeClass = item.status === 'completed' ? 'success' : (item.status === 'failed' ? 'fail' : 'running');
    const statusText = statusLabel(item.status);
    return `
      <div class="task" data-type="upload" data-id="${item.id}">
        <div>
          <div class="task-title">${name}</div>
          <div class="task-meta">
            <span class="badge ${badgeClass}">${statusText}</span>
            ${percent}% | ${formatBytes(item.speed || 0)}/s
          </div>
          <div class="progress"><span style="width:${percent}%"></span></div>
        </div>
        <div class="task-actions">
          <button data-action="cancel" data-id="${item.id}">取消</button>
          <button data-action="retry" data-id="${item.id}">重试</button>
        </div>
      </div>
    `;
  }).join('');
}

async function loadUploads() {
  const params = new URLSearchParams();
  if (uploadStatus.value) params.set('status', uploadStatus.value);
  if (uploadSearch.value) params.set('q', uploadSearch.value);
  params.set('page', String(uploadPage));
  params.set('limit', String(PAGE_SIZE));
  const res = await fetch(`/api/tasks/upload/list?${params.toString()}`);
  const json = await res.json();
  uploadItems = json.items || [];
  renderUploads();
  if (uploadPageEl) uploadPageEl.textContent = String(uploadPage);
}

async function loadSystem() {
  try {
    const res = await fetch('/api/system');
    const json = await res.json();
    if (diskUsageEl) {
      const total = json.disk_total || 0;
      const free = json.disk_free || 0;
      diskUsageEl.textContent = `${formatBytes(free)} / ${formatBytes(total)}`;
    }
  } catch {}
}

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const json = await res.json();
    autoUpload = !!json.auto_upload;
  } catch {}
}

function formatBytes(bytes) {
  if (!bytes) return '--';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let value = bytes;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

async function createDownload(urls) {
  await fetch('/api/tasks/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urls }),
  });
  await loadDownloads();
}

async function prepareDownload(url) {
  pendingPrepareUrl = url;
  showPrepareModal('解析中...', url.split('/').pop() || 'download.bin');
  const res = await fetch('/api/download/prepare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  const json = await res.json();
  if (!json.ok) {
    prepareInfo.textContent = `解析失败: ${json.error || '未知错误'}`;
    return;
  }
  const sizeText = json.size ? formatBytes(json.size) : '未知大小';
  const typeText = json.content_type || '未知类型';
  const resText = json.resolution ? ` | 分辨率: ${json.resolution}` : '';
  const durText = json.duration_text ? ` | 时长: ${json.duration_text}` : '';
  prepareInfo.textContent = `类型: ${typeText} | 大小: ${sizeText}${resText}${durText}`;
  prepareFilename.value = json.filename || prepareFilename.value;
}

async function actOnTask(id, action) {
  await fetch('/api/tasks/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, action }),
  });
  await loadDownloads();
}

if (downloadForm) {
  downloadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = downloadUrlInput.value.trim();
    if (!url) return;
    await prepareDownload(url);
    downloadUrlInput.value = '';
  });
}

if (downloadBatchSubmit) {
  downloadBatchSubmit.addEventListener('click', async () => {
    const lines = (downloadBatch.value || '').split('\n').map(v => v.trim()).filter(Boolean);
    if (!lines.length) return;
    await createDownload(lines);
    downloadBatch.value = '';
  });
}

if (prepareCancel) {
  prepareCancel.addEventListener('click', () => {
    hidePrepareModal();
  });
}

if (prepareForm) {
  prepareForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!pendingPrepareUrl) return;
    const filename = prepareFilename.value.trim();
    await fetch('/api/tasks/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: pendingPrepareUrl, filename }),
    });
    hidePrepareModal();
    await loadDownloads();
  });
}

if (uploadForm) {
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const path = uploadPathInput.value.trim();
    if (!path) return;
    await fetch('/api/tasks/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    uploadPathInput.value = '';
    await loadUploads();
  });
}

if (settingsForm) {
  settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    settingsStatus.textContent = '保存中...';
    const data = Object.fromEntries(new FormData(settingsForm).entries());
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const json = await res.json();
    if (json.ok) {
      settingsStatus.textContent = '已保存';
    } else {
      settingsStatus.textContent = '保存失败，请检查配置';
    }
  });
}

if (uploadSearch) {
  uploadSearch.addEventListener('input', () => {
    uploadPage = 1;
    loadUploads();
  });
}
if (uploadStatus) {
  uploadStatus.addEventListener('change', () => {
    uploadPage = 1;
    loadUploads();
  });
}
if (uploadPrev) {
  uploadPrev.addEventListener('click', () => {
    uploadPage = Math.max(1, uploadPage - 1);
    loadUploads();
  });
}
if (uploadNext) {
  uploadNext.addEventListener('click', () => {
    uploadPage += 1;
    loadUploads();
  });
}

uploadList?.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const id = Number(btn.dataset.id);
  const action = btn.dataset.action;
  fetch('/api/tasks/upload/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, action }),
  }).then(() => loadUploads());
});

if (downloadSearch) {
  downloadSearch.addEventListener('input', () => {
    downloadPage = 1;
    loadDownloads();
  });
}
if (downloadStatus) {
  downloadStatus.addEventListener('change', () => {
    downloadPage = 1;
    loadDownloads();
  });
}
if (downloadPrev) {
  downloadPrev.addEventListener('click', () => {
    downloadPage = Math.max(1, downloadPage - 1);
    loadDownloads();
  });
}
if (downloadNext) {
  downloadNext.addEventListener('click', () => {
    downloadPage += 1;
    loadDownloads();
  });
}

downloadList?.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  const taskEl = e.target.closest('.task');
  if (btn) {
    const id = Number(btn.dataset.id);
    const action = btn.dataset.action;
    if (action === 'manual-upload') {
      const path = btn.dataset.path;
      fetch('/api/tasks/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      }).then(() => loadUploads());
      return;
    }
    actOnTask(id, action);
    return;
  }
  if (taskEl) {
    showDetail('download', Number(taskEl.dataset.id));
  }
});

uploadList?.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  const taskEl = e.target.closest('.task');
  if (btn) {
    const id = Number(btn.dataset.id);
    const action = btn.dataset.action;
    fetch('/api/tasks/upload/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, action }),
    }).then(() => loadUploads());
    return;
  }
  if (taskEl) {
    showDetail('upload', Number(taskEl.dataset.id));
  }
});

function connectSSE() {
  const evtSource = new EventSource('/sse');
  evtSource.onopen = () => {
    statusEl.textContent = '已连接';
  };
  evtSource.addEventListener('auth', (event) => {
    const payload = JSON.parse(event.data || '{}');
    if (payload.state === 'wait_code' || payload.state === 'wait_password') {
      showModal(payload.state, payload.detail);
    }
    if (payload.state === 'ready') {
      hideModal();
    }
    if (authStatusEl) authStatusEl.textContent = payload.state || '未知';
  });
  evtSource.addEventListener('download', () => {
    loadDownloads();
  });
  evtSource.addEventListener('upload', () => {
    loadUploads();
  });
  evtSource.onerror = () => {
    statusEl.textContent = '连接中断，重试中...';
    evtSource.close();
    setTimeout(connectSSE, 3000);
  };
}

const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'light') {
  document.body.classList.add('light');
}

fetchAuthStatus();
loadConfig().then(() => loadDownloads());
loadUploads();
loadSystem();
connectSSE();

const urlTab = new URL(window.location.href).searchParams.get('tab');
setActiveTab(urlTab || 'download');
tabButtons.forEach(btn => {
  btn.addEventListener('click', () => setActiveTab(btn.dataset.tabButton));
});

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('light');
    localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
  });
}

if (detailClose) {
  detailClose.addEventListener('click', () => {
    detailPanel.classList.add('hidden');
  });
}

function showDetail(kind, id) {
  let item = null;
  if (kind === 'download') {
    item = downloadItems.find(t => t.id === id);
  } else {
    item = uploadItems.find(t => t.id === id);
  }
  if (!item) return;
  detailTitle.textContent = kind === 'download' ? '下载任务详情' : '上传任务详情';
  const map = kind === 'download' ? {
    id: 'ID',
    url: 'URL',
    filename: '文件名',
    file_type: '类型',
    status: '状态',
    progress: '进度',
    speed: '速度',
    downloaded: '已下载',
    total_size: '总大小',
    error: '错误',
    save_path: '保存路径',
    retries: '重试次数',
  } : {
    id: 'ID',
    source_path: '源文件',
    target_channel: '目标频道',
    file_id: '文件ID',
    status: '状态',
    progress: '进度',
    speed: '速度',
    uploaded: '已上传',
    total_size: '总大小',
    error: '错误',
    description: '描述',
    part_index: '分片序号',
    part_total: '分片总数',
  };
  detailBody.innerHTML = Object.entries(map).map(([key, label]) => {
    let value = item[key];
    if (key === 'speed') value = formatBytes(value || 0) + '/s';
    if (key === 'downloaded' || key === 'uploaded' || key === 'total_size') {
      value = formatBytes(value || 0);
    }
    if (key === 'progress' && value != null) value = `${Number(value).toFixed(1)}%`;
    return `<div class="row"><div class="label">${label}</div><div>${value ?? '-'}</div></div>`;
  }).join('');
  detailPanel.classList.remove('hidden');
}

function statusLabel(status) {
  const map = {
    pending: '等待中',
    queued: '排队中',
    downloading: '下载中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    canceled: '已取消',
    uploading: '上传中',
    auth_required: '需要认证',
  };
  return map[status] || status;
}
