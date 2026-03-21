const statusEl = document.getElementById('sse-status');
const codeModal = document.getElementById('auth-code-modal');
const passwordModal = document.getElementById('auth-password-modal');
const codeDetailEl = document.getElementById('auth-code-detail');
const passwordDetailEl = document.getElementById('auth-password-detail');
const codeForm = document.getElementById('auth-code-form');
const passwordForm = document.getElementById('auth-password-form');
const codeInput = document.getElementById('auth-code');
const passwordInput = document.getElementById('auth-password');

const downloadForm = document.getElementById('download-form');
const downloadUrlInput = document.getElementById('download-url');
const downloadBatch = document.getElementById('download-batch');
const downloadBatchSubmit = document.getElementById('download-batch-submit');
const downloadBatchModal = document.getElementById('download-batch-modal');
const downloadBatchForm = document.getElementById('download-batch-form');
const downloadBatchDescription = document.getElementById('download-batch-description');
const downloadBatchCancel = document.getElementById('download-batch-cancel');
const downloadList = document.getElementById('download-list');
const downloadSearch = document.getElementById('download-search');
const downloadStatus = document.getElementById('download-status');
const downloadFileType = document.getElementById('download-file-type');
const downloadDateFrom = document.getElementById('download-date-from');
const downloadDateTo = document.getElementById('download-date-to');

const uploadForm = document.getElementById('upload-form');
const uploadPathInput = document.getElementById('upload-path');
const uploadPickBtn = document.getElementById('upload-pick');
const uploadFileInput = document.getElementById('upload-file');
const uploadQuickStatus = document.getElementById('upload-quick-status');
const uploadList = document.getElementById('upload-list');
const uploadSearch = document.getElementById('upload-search');
const uploadStatus = document.getElementById('upload-status');

const downloadPrev = document.getElementById('download-prev');
const downloadNext = document.getElementById('download-next');
const downloadPageEl = document.getElementById('download-page');
const uploadPrev = document.getElementById('upload-prev');
const uploadNext = document.getElementById('upload-next');
const uploadPageEl = document.getElementById('upload-page');
const downloadPageSizeEl = document.getElementById('download-page-size');
const uploadPageSizeEl = document.getElementById('upload-page-size');
const downloadColumnsEl = document.getElementById('download-columns');
const uploadColumnsEl = document.getElementById('upload-columns');

const downloadSelectAll = document.getElementById('download-select-all');
const uploadSelectAll = document.getElementById('upload-select-all');
const downloadSelectedCount = document.getElementById('download-selected-count');
const uploadSelectedCount = document.getElementById('upload-selected-count');
const bulkButtons = Array.from(document.querySelectorAll('[data-bulk-target][data-bulk-action]'));

const diskUsageEl = document.getElementById('disk-usage');
const authStatusEl = document.getElementById('auth-status');
const authOpenBtn = document.getElementById('auth-open-btn');
const authInlinePanel = document.getElementById('auth-inline-panel');
const authInlineSummary = document.getElementById('auth-inline-summary');
const authInlineState = document.getElementById('auth-inline-state');
const authInlineCodeBox = document.getElementById('auth-inline-code-box');
const authInlinePasswordBox = document.getElementById('auth-inline-password-box');
const authInlineCodeDetailEl = document.getElementById('auth-inline-code-detail');
const authInlinePasswordDetailEl = document.getElementById('auth-inline-password-detail');
const authInlineCodeForm = document.getElementById('auth-inline-code-form');
const authInlinePasswordForm = document.getElementById('auth-inline-password-form');
const authInlineCodeInput = document.getElementById('auth-inline-code');
const authInlinePasswordInput = document.getElementById('auth-inline-password');
const themeToggle = document.getElementById('theme-toggle');
const detailPanel = document.getElementById('detail-panel');
const detailBody = document.getElementById('detail-body');
const detailTitle = document.getElementById('detail-title');
const detailClose = document.getElementById('detail-close');
const logListInline = document.getElementById('log-list-inline');
const logRefreshInline = document.getElementById('log-refresh-inline');
const prepareModal = document.getElementById('prepare-modal');
const prepareInfo = document.getElementById('prepare-info');
const prepareForm = document.getElementById('prepare-form');
const prepareFilename = document.getElementById('prepare-filename');
const prepareCancel = document.getElementById('prepare-cancel');
const prepareQuality = document.getElementById('prepare-quality');
const prepareVideoFormat = document.getElementById('prepare-video-format');
const prepareAudioFormat = document.getElementById('prepare-audio-format');
const batchUploadModal = document.getElementById('batch-upload-modal');
const batchUploadForm = document.getElementById('batch-upload-form');
const batchUploadDescription = document.getElementById('batch-upload-description');
const batchUploadCancel = document.getElementById('batch-upload-cancel');
const previewModal = document.getElementById('preview-modal');
const previewTitle = document.getElementById('preview-title');
const previewBody = document.getElementById('preview-body');
const previewClose = document.getElementById('preview-close');
const settingsForm = document.getElementById('settings-form');
const settingsStatus = document.getElementById('settings-status');
const tabButtons = Array.from(document.querySelectorAll('[data-tab-button]'));
const tabPanels = Array.from(document.querySelectorAll('[data-tab-panel]'));

let downloadItems = [];
let uploadItems = [];
let downloadPage = 1;
let uploadPage = 1;
const PAGE_SIZE_OPTIONS = [10, 20, 50];
let downloadPageSize = PAGE_SIZE_OPTIONS.includes(Number(localStorage.getItem('download_page_size')))
  ? Number(localStorage.getItem('download_page_size'))
  : 20;
let uploadPageSize = PAGE_SIZE_OPTIONS.includes(Number(localStorage.getItem('upload_page_size')))
  ? Number(localStorage.getItem('upload_page_size'))
  : 20;
let downloadColumns = [1, 2, 3, 4, 5].includes(Number(localStorage.getItem('download_columns')))
  ? Number(localStorage.getItem('download_columns'))
  : 2;
let uploadColumns = [1, 2, 3, 4, 5].includes(Number(localStorage.getItem('upload_columns')))
  ? Number(localStorage.getItem('upload_columns'))
  : 2;
let pendingPrepareUrl = '';
let pendingPrepareFormat = '';
let pendingBatchUploadIds = [];
let pendingBatchUploadDescription = '';
let pendingBatchDownloadUrls = [];
const expandedDownloadBatchIds = new Set();
const expandedUploadBatchIds = new Set();
const downloadBatchChildrenCache = new Map();
const uploadBatchChildrenCache = new Map();
let autoUpload = true;
const selectedDownloadIds = new Set();
const selectedUploadIds = new Set();
const selectedDownloadOrder = new Map();
let logsTimer = null;
let detailRefreshTimer = null;
let activeDetail = null;
let selectedDownloadSequence = 0;

function applyTheme(theme) {
  const mode = theme === 'light' ? 'light' : 'dark';
  document.body.classList.toggle('light', mode === 'light');
  document.documentElement.style.colorScheme = mode;
  if (themeToggle) {
    themeToggle.textContent = mode === 'light' ? '深夜主题' : '白天主题';
  }
  localStorage.setItem('theme', mode);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

function applyTaskColumns() {
  if (downloadList) downloadList.style.setProperty('--task-columns', String(downloadColumns));
  if (uploadList) uploadList.style.setProperty('--task-columns', String(uploadColumns));
}

function showAuthCodeModal(detail) {
  if (codeDetailEl) codeDetailEl.textContent = detail || '';
  if (passwordModal) passwordModal.classList.add('hidden');
  if (codeModal) codeModal.classList.remove('hidden');
}

function showAuthPasswordModal(detail) {
  if (passwordDetailEl) passwordDetailEl.textContent = detail || '';
  if (codeModal) codeModal.classList.add('hidden');
  if (passwordModal) passwordModal.classList.remove('hidden');
}

function showInlineAuthPanel(mode, detail) {
  if (authInlinePanel) authInlinePanel.classList.remove('hidden');
  if (authInlineState) authInlineState.textContent = mode === 'wait_password' ? '等待二次验证' : '等待验证码';
  if (authInlineSummary) {
    authInlineSummary.textContent = mode === 'wait_password'
      ? 'Telegram 当前需要两步验证密码。即使弹窗被浏览器拦住，也可以直接在这里输入。'
      : 'Telegram 当前需要短信验证码。即使弹窗被浏览器拦住，也可以直接在这里输入。';
  }
  if (mode === 'wait_password') {
    if (authInlineCodeBox) authInlineCodeBox.classList.add('hidden');
    if (authInlinePasswordBox) authInlinePasswordBox.classList.remove('hidden');
    if (authInlinePasswordDetailEl) authInlinePasswordDetailEl.textContent = detail || '请输入两步验证密码';
  } else {
    if (authInlinePasswordBox) authInlinePasswordBox.classList.add('hidden');
    if (authInlineCodeBox) authInlineCodeBox.classList.remove('hidden');
    if (authInlineCodeDetailEl) authInlineCodeDetailEl.textContent = detail || '请输入短信验证码';
  }
}

function hideInlineAuthPanel() {
  if (authInlinePanel) authInlinePanel.classList.add('hidden');
  if (authInlineCodeBox) authInlineCodeBox.classList.add('hidden');
  if (authInlinePasswordBox) authInlinePasswordBox.classList.add('hidden');
  if (authInlineState) authInlineState.textContent = '待命';
  if (authInlineSummary) authInlineSummary.textContent = '当 Telegram 要求验证码或两步验证密码时，可在这里手动输入。';
  if (authInlineCodeInput) authInlineCodeInput.value = '';
  if (authInlinePasswordInput) authInlinePasswordInput.value = '';
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
  if (codeModal) codeModal.classList.add('hidden');
  if (passwordModal) passwordModal.classList.add('hidden');
  if (codeInput) codeInput.value = '';
  if (passwordInput) passwordInput.value = '';
}

function applyAuthState(json, options = {}) {
  if (authStatusEl) authStatusEl.textContent = json.state || '未知';
  if (!json.configured) {
    hideModal();
    hideInlineAuthPanel();
    setActiveTab('settings');
    return;
  }
  if (json.state === 'wait_code') {
    showAuthCodeModal(json.detail || '请输入短信验证码');
    showInlineAuthPanel('wait_code', json.detail);
    if (options.scrollInline && authInlinePanel) {
      authInlinePanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    return;
  }
  if (json.state === 'wait_password') {
    showAuthPasswordModal(json.detail || '请输入两步验证密码');
    showInlineAuthPanel('wait_password', json.detail);
    if (options.scrollInline && authInlinePanel) {
      authInlinePanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    return;
  }
  hideModal();
  hideInlineAuthPanel();
}

async function submitAuthValue(type, value, inputEl) {
  const trimmed = String(value || '').trim();
  if (!trimmed) {
    inputEl?.focus();
    return;
  }
  const res = await fetch('/api/auth/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type,
      value: trimmed,
    }),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || !json.ok) {
    const detail = json.detail || '认证提交失败，请稍后重试';
    window.alert(detail);
    inputEl?.focus();
    inputEl?.select?.();
    return;
  }
  if (inputEl) inputEl.value = '';
}

function showPrepareModal(info, filename) {
  prepareInfo.textContent = info || '';
  prepareFilename.value = filename || '';
  prepareModal.classList.remove('hidden');
}

function hidePrepareModal() {
  prepareModal.classList.add('hidden');
  pendingPrepareUrl = '';
  pendingPrepareFormat = '';
  if (prepareQuality) prepareQuality.classList.add('hidden');
  if (prepareVideoFormat) prepareVideoFormat.innerHTML = '';
  if (prepareAudioFormat) prepareAudioFormat.innerHTML = '';
}

function showBatchUploadModal(ids) {
  pendingBatchUploadIds = ids.slice();
  pendingBatchUploadDescription = '';
  if (batchUploadDescription) batchUploadDescription.value = '';
  batchUploadModal?.classList.remove('hidden');
}

function hideBatchUploadModal() {
  pendingBatchUploadIds = [];
  pendingBatchUploadDescription = '';
  batchUploadModal?.classList.add('hidden');
}

function showDownloadBatchModal(urls) {
  pendingBatchDownloadUrls = urls.slice();
  if (downloadBatchDescription) downloadBatchDescription.value = '';
  downloadBatchModal?.classList.remove('hidden');
}

function hideDownloadBatchModal() {
  pendingBatchDownloadUrls = [];
  downloadBatchModal?.classList.add('hidden');
}

function showPreview(item) {
  if (!previewModal || !previewBody || !previewTitle) return;
  previewTitle.textContent = item.filename || item.url || `任务 #${item.id}`;
  if (item.file_type === 'image' && item.preview_url) {
    previewBody.innerHTML = `<img src="${escapeHtml(item.preview_url)}" alt="${escapeHtml(item.filename || '预览图')}" class="preview-media" />`;
  } else if (item.file_type === 'video' && item.preview_url) {
    previewBody.innerHTML = `<video src="${escapeHtml(item.preview_url)}" class="preview-media" controls playsinline preload="metadata"></video>`;
  } else if (item.file_type === 'audio' && item.preview_url) {
    previewBody.innerHTML = `<div class="preview-audio"><i data-lucide="music-4"></i><audio src="${escapeHtml(item.preview_url)}" controls preload="metadata"></audio></div>`;
  } else {
    previewBody.innerHTML = `
      <div class="preview-empty">
        <i data-lucide="file"></i>
        <div>${escapeHtml(item.filename || '该文件类型不支持预览')}</div>
      </div>
    `;
  }
  previewModal.classList.remove('hidden');
  refreshIcons();
}

function hidePreviewModal() {
  if (!previewModal || !previewBody) return;
  previewModal.classList.add('hidden');
  previewBody.innerHTML = '';
}

function basename(input) {
  return String(input || '').split(/[\\/]/).pop() || '';
}

function renderDetailValue(value, fallback = '-') {
  return escapeHtml(value == null || value === '' ? fallback : value);
}

function childDisplayName(child, kind) {
  if (kind === 'upload') {
    return child.title || basename(child.source_path) || `任务 #${child.id}`;
  }
  return child.filename || child.title || child.url || `任务 #${child.id}`;
}

function buildPreviewPayload(item, fallbackKind = 'download') {
  return {
    id: item.id,
    kind: item.kind || fallbackKind,
    filename: item.filename || item.title || basename(item.source_path) || item.url || `任务 #${item.id}`,
    file_type: item.file_type || 'file',
    preview_url: item.preview_url || null,
    thumb_url: item.thumb_url || null,
  };
}

function renderBatchChildPreview(child, kind) {
  const preview = buildPreviewPayload(child, kind);
  const label = childDisplayName(child, kind);
  if (!preview.preview_url && !preview.thumb_url) {
    return `<button type="button" class="detail-subtask-preview is-empty" disabled><i data-lucide="file-search"></i><span>暂无预览</span></button>`;
  }
  if (preview.file_type === 'image' && preview.preview_url) {
    return `<button type="button" class="detail-subtask-preview" data-action="detail-preview" data-kind="${escapeHtml(kind)}" data-preview='${escapeHtml(JSON.stringify(preview))}'><img src="${escapeHtml(preview.thumb_url || preview.preview_url)}" alt="${escapeHtml(label)}" /></button>`;
  }
  if (preview.file_type === 'video') {
    const poster = preview.thumb_url
      ? `<img src="${escapeHtml(preview.thumb_url)}" alt="${escapeHtml(label)}" />`
      : `<div class="detail-subtask-preview-fallback"><i data-lucide="film"></i></div>`;
    return `<button type="button" class="detail-subtask-preview" data-action="detail-preview" data-kind="${escapeHtml(kind)}" data-preview='${escapeHtml(JSON.stringify(preview))}'>${poster}<span class="detail-subtask-preview-play"><i data-lucide="play"></i></span></button>`;
  }
  if (preview.file_type === 'audio' && preview.preview_url) {
    return `<button type="button" class="detail-subtask-preview is-audio" data-action="detail-preview" data-kind="${escapeHtml(kind)}" data-preview='${escapeHtml(JSON.stringify(preview))}'><i data-lucide="music-4"></i><span>音频</span></button>`;
  }
  return `<button type="button" class="detail-subtask-preview is-file" data-action="detail-preview" data-kind="${escapeHtml(kind)}" data-preview='${escapeHtml(JSON.stringify(preview))}'><i data-lucide="file"></i><span>文件</span></button>`;
}

function fileTypeLabel(type) {
  const map = {
    video: '视频',
    image: '图片',
    audio: '音频',
    file: '文件',
    unknown: '未知',
  };
  return map[type] || type || '文件';
}

function renderBatchChildCard(child, kind) {
  if (kind === 'upload') {
    const name = childDisplayName(child, kind);
    const descLine = child.description ? `<div class="detail-subtask-meta">\u63cf\u8ff0: ${escapeHtml(child.description)}</div>` : '';
    const partLine = child.part_total > 1 ? `<div class="detail-subtask-meta">\u5206\u7247: ${child.part_index || 1} / ${child.part_total}</div>` : '';
    const errorLine = child.error ? `<div class="detail-subtask-error">${escapeHtml(child.error)}</div>` : '';
    return `
      <div class="detail-subtask">
        <div class="detail-subtask-layout">
          ${renderBatchChildPreview(child, kind)}
          <div class="detail-subtask-main">
            <div class="detail-subtask-head">
              <strong>${escapeHtml(name)}</strong>
              <span class="badge ${child.status === 'completed' ? 'success' : (child.status === 'failed' ? 'fail' : 'running')}">${escapeHtml(statusLabel(child.status))}</span>
            </div>
            <div class="detail-subtask-meta">\u7c7b\u578b: ${renderDetailValue(fileTypeLabel(child.file_type || 'file'))}</div>
            <div class="detail-subtask-meta">\u6e90\u6587\u4ef6: ${renderDetailValue(child.source_path)}</div>
            <div class="detail-subtask-meta">\u76ee\u6807: ${renderDetailValue(child.target_channel)}</div>
            <div class="detail-subtask-meta">\u8fdb\u5ea6 ${Number(child.progress || 0).toFixed(0)}% | \u5df2\u4f20 ${formatBytes(child.uploaded || 0)} / ${formatBytes(child.total_size || 0)}</div>
            ${descLine}
            ${partLine}
            ${errorLine}
          </div>
        </div>
      </div>
    `;
  }

  const name = childDisplayName(child, kind);
  const pathLine = child.save_path ? `<div class="detail-subtask-meta">\u6587\u4ef6: ${escapeHtml(child.save_path)}</div>` : '';
  const errorLine = child.error ? `<div class="detail-subtask-error">${escapeHtml(child.error)}</div>` : '';
  return `
    <div class="detail-subtask">
      <div class="detail-subtask-layout">
        ${renderBatchChildPreview(child, kind)}
        <div class="detail-subtask-main">
          <div class="detail-subtask-head">
            <strong>${escapeHtml(name)}</strong>
            <span class="badge ${child.status === 'completed' ? 'success' : (child.status === 'failed' ? 'fail' : 'running')}">${escapeHtml(statusLabel(child.status))}</span>
          </div>
          <div class="detail-subtask-meta">\u94fe\u63a5: ${renderDetailValue(child.url)}</div>
          <div class="detail-subtask-meta">\u7c7b\u578b: ${renderDetailValue(fileTypeLabel(child.file_type || 'file'))}</div>
          <div class="detail-subtask-meta">\u8fdb\u5ea6 ${Number(child.progress || 0).toFixed(0)}% | \u5df2\u4e0b ${formatBytes(child.downloaded || 0)} / ${formatBytes(child.total_size || 0)}</div>
          ${pathLine}
          ${errorLine}
        </div>
      </div>
    </div>
  `;
}

function renderBatchDetailPanel(item, children, kind) {
  const noun = kind === 'upload' ? '上传' : '下载';
  return `
    <div class="row"><div class="label">标题</div><div>${escapeHtml(item.title)}</div></div>
    <div class="row"><div class="label">状态</div><div>${escapeHtml(statusLabel(item.status))}</div></div>
    <div class="row"><div class="label">描述</div><div>${renderDetailValue(item.description)}</div></div>
    <div class="row"><div class="label">统计</div><div>共 ${item.child_count} 项，成功 ${item.completed_count}，失败 ${item.failed_count}</div></div>
    <div class="row"><div class="label">总进度</div><div>${Number(item.progress || 0).toFixed(0)}%</div></div>
    <div class="detail-subtasks">
      ${children.length ? children.map(child => renderBatchChildCard(child, kind)).join('') : `<div class="empty">暂无${noun}子任务</div>`}
    </div>
  `;
}

function renderFormatOptions(selectEl, items, kind) {
  if (!selectEl) return;
  const defaultLabel = kind === 'video' ? '最高视频' : '最高音频';
  if (!items || !items.length) {
    selectEl.innerHTML = `<option value="">${defaultLabel}</option>`;
    return;
  }
  selectEl.innerHTML = items.map((item, idx) => {
    const label = item.label || item.id;
    const suffix = item.filesize ? ` | ${formatBytes(item.filesize)}` : '';
    const defaultTag = idx === 0 ? ' (默认最高)' : '';
    return `<option value="${escapeHtml(item.id)}">${escapeHtml(label + suffix + defaultTag)}</option>`;
  }).join('');
}

function buildSelectedFormat() {
  const videoId = (prepareVideoFormat?.value || '').trim();
  const audioId = (prepareAudioFormat?.value || '').trim();
  if (videoId && audioId) return `${videoId}+${audioId}/b`;
  if (videoId) return `${videoId}/b`;
  if (audioId) return audioId;
  return '';
}

async function fetchAuthStatus() {
  const res = await fetch('/api/auth/status');
  const json = await res.json();
  applyAuthState(json);
}

async function openAuthModalFromStatus() {
  const res = await fetch('/api/auth/status');
  const json = await res.json();
  applyAuthState(json, { scrollInline: true });
  if (json.state === 'wait_code' || json.state === 'wait_password') return;
  const detail = json.detail || '当前没有待输入的验证码或两步验证密码';
  window.alert(detail);
}

codeForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  await submitAuthValue('code', codeInput?.value, codeInput);
});

passwordForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  await submitAuthValue('password', passwordInput?.value, passwordInput);
});

authInlineCodeForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  await submitAuthValue('code', authInlineCodeInput?.value, authInlineCodeInput);
});

authInlinePasswordForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  await submitAuthValue('password', authInlinePasswordInput?.value, authInlinePasswordInput);
});

function keepSelectionCurrent(kind, items) {
  const currentIds = new Set(items.map(item => item.id));
  const targetSet = kind === 'download' ? selectedDownloadIds : selectedUploadIds;
  Array.from(targetSet).forEach(id => {
    if (!currentIds.has(id)) {
      targetSet.delete(id);
      if (kind === 'download') {
        selectedDownloadOrder.delete(id);
      }
    }
  });
}

function setDownloadSelection(id, checked) {
  if (checked) {
    selectedDownloadIds.add(id);
    if (!selectedDownloadOrder.has(id)) {
      selectedDownloadSequence += 1;
      selectedDownloadOrder.set(id, selectedDownloadSequence);
    }
    return;
  }
  selectedDownloadIds.delete(id);
  selectedDownloadOrder.delete(id);
}

function isDownloadStartable(item) {
  return ['failed', 'canceled', 'auth_required'].includes(item.status);
}

function isUploadStartable(item) {
  return ['failed', 'canceled', 'auth_required'].includes(item.status);
}

function isDownloadPauseable(item) {
  return ['pending', 'queued', 'downloading'].includes(item.status);
}

function isDownloadResumable(item) {
  return item.status === 'paused';
}

function isCancelable(status) {
  return !['completed', 'failed', 'canceled'].includes(status);
}

function isDeletable(status) {
  return ['completed', 'failed', 'canceled'].includes(status);
}

function updateSelectionUI(kind) {
  if (kind === 'download') {
    const pageIds = downloadItems.map(item => item.id);
    const selectedOnPage = pageIds.filter(id => selectedDownloadIds.has(id)).length;
    const selectedItems = downloadItems.filter(item => selectedDownloadIds.has(item.id));
    if (downloadSelectAll) {
      downloadSelectAll.checked = pageIds.length > 0 && selectedOnPage === pageIds.length;
      downloadSelectAll.indeterminate = selectedOnPage > 0 && selectedOnPage < pageIds.length;
      downloadSelectAll.disabled = false;
    }
    if (downloadSelectedCount) {
      const batchCount = selectedItems.filter(item => item.kind === 'batch').length;
      const fileCount = selectedItems.length - batchCount;
      const breakdown = selectedItems.length
        ? ` | 包含 ${batchCount} 个批次，${fileCount} 个单文件`
        : '';
      downloadSelectedCount.textContent = `已选 ${selectedDownloadIds.size} 项${breakdown}`;
      downloadSelectedCount.classList.toggle('strong', selectedDownloadIds.size > 0);
    }
    setBulkButtonStates('download', selectedItems);
  } else {
    const pageIds = uploadItems.map(item => item.id);
    const selectedOnPage = pageIds.filter(id => selectedUploadIds.has(id)).length;
    const selectedItems = uploadItems.filter(item => selectedUploadIds.has(item.id));
    if (uploadSelectAll) {
      uploadSelectAll.checked = pageIds.length > 0 && selectedOnPage === pageIds.length;
      uploadSelectAll.indeterminate = selectedOnPage > 0 && selectedOnPage < pageIds.length;
    }
    if (uploadSelectedCount) {
      uploadSelectedCount.textContent = `已选 ${selectedUploadIds.size} 项`;
      uploadSelectedCount.classList.toggle('strong', selectedUploadIds.size > 0);
    }
    setBulkButtonStates('upload', selectedItems);
  }
}

function setBulkButtonStates(target, selectedItems) {
  const has = fn => selectedItems.some(fn);
  bulkButtons
    .filter(btn => btn.dataset.bulkTarget === target)
    .forEach(btn => {
      const action = btn.dataset.bulkAction;
      let enabled = selectedItems.length > 0;
      if (target === 'download') {
        if (action === 'start') enabled = has(isDownloadStartable);
        if (action === 'pause') enabled = has(isDownloadPauseable);
        if (action === 'resume') enabled = has(isDownloadResumable);
        if (action === 'cancel') enabled = has(item => isCancelable(item.status));
        if (action === 'batch-upload') enabled = has(item => (item.kind === 'batch' && item.completed_count > 0) || (item.status === 'completed' && item.save_path));
        if (action === 'delete') enabled = has(item => isDeletable(item.status));
      } else {
        if (action === 'start') enabled = has(isUploadStartable);
        if (action === 'cancel') enabled = has(item => isCancelable(item.status));
        if (action === 'delete') enabled = has(item => isDeletable(item.status));
      }
      btn.disabled = !enabled;
    });
}

function renderTaskControl(icon, action, label, extra = '') {
  return `<button type="button" class="icon-btn ${extra}" data-action="${action}" title="${label}" aria-label="${label}"><i data-lucide="${icon}"></i></button>`;
}

function renderPreviewCard(item) {
  if (!item.save_path || item.status !== 'completed') {
    return `<button type="button" class="task-preview task-preview-empty" disabled><i data-lucide="file-search"></i><span>暂无预览</span></button>`;
  }
  if (item.file_type === 'image' && item.preview_url) {
    return `<button type="button" class="task-preview" data-action="preview"><img src="${escapeHtml(item.preview_url)}" alt="${escapeHtml(item.filename || '图片预览')}" /></button>`;
  }
  if (item.file_type === 'video') {
    const poster = item.thumb_url
      ? `<img src="${escapeHtml(item.thumb_url)}" alt="${escapeHtml(item.filename || '视频预览')}" />`
      : `<div class="task-preview-fallback"><i data-lucide="film"></i></div>`;
    return `<button type="button" class="task-preview" data-action="preview">${poster}<span class="task-preview-play"><i data-lucide="play"></i></span></button>`;
  }
  if (item.file_type === 'audio') {
    return `<button type="button" class="task-preview task-preview-audio" data-action="preview"><i data-lucide="music-4"></i><span>音频预览</span></button>`;
  }
  return `<button type="button" class="task-preview task-preview-file" data-action="preview"><i data-lucide="file"></i><span>文件信息</span></button>`;
}

function renderBatchStats(item, noun = '项') {
  return `
    <div class="task-batch-stats">
      <span class="task-mini-pill">总计 ${item.child_count} ${noun}</span>
      <span class="task-mini-pill is-success">成功 ${item.completed_count}</span>
      <span class="task-mini-pill is-fail">失败 ${item.failed_count}</span>
      ${item.description ? `<span class="task-mini-pill is-note">${escapeHtml(item.description)}</span>` : ''}
    </div>
  `;
}

function renderBatchHeader(item, expanded) {
  const badgeClass = item.status === 'completed' ? 'success' : (item.status === 'failed' ? 'fail' : 'running');
  const icon = expanded ? 'chevron-up' : 'chevron-down';
  return `
    <div class="task-batch-header">
      <div class="task-batch-headline">
        <span class="badge ${badgeClass}">批次 ${escapeHtml(statusLabel(item.status))}</span>
        <span class="task-batch-progress">${Math.round(item.progress || 0)}%</span>
      </div>
      <button type="button" class="icon-btn" data-action="toggle-batch" title="展开批次摘要" aria-label="展开批次摘要">
        <i data-lucide="${icon}"></i>
      </button>
    </div>
  `;
}

function renderBatchChildrenSummary(children, kind) {
  if (!children || !children.length) {
    return `<div class="task-batch-children"><div class="task-batch-empty">\u6682\u65e0\u5b50\u4efb\u52a1\u6458\u8981</div></div>`;
  }
  const rows = children.slice(0, 3).map(child => {
    const name = childDisplayName(child, kind);
    const amount = kind === 'download'
      ? `${formatBytes(child.downloaded || 0)} / ${formatBytes(child.total_size || 0)}`
      : `${formatBytes(child.uploaded || 0)} / ${formatBytes(child.total_size || 0)}`;
    const badgeClass = child.status === 'completed' ? 'success' : (child.status === 'failed' ? 'fail' : 'running');
    return `
      <div class="task-batch-child">
        ${renderBatchChildPreview(child, kind)}
        <div class="task-batch-child-main">
          <strong>${escapeHtml(name)}</strong>
          <span class="task-batch-child-type">${escapeHtml(fileTypeLabel(child.file_type || 'file'))}</span>
          <span class="task-batch-child-meta">${amount}</span>
        </div>
        <span class="badge ${badgeClass}">${escapeHtml(statusLabel(child.status))}</span>
      </div>
    `;
  }).join('');
  const more = children.length > 3
    ? `<div class="task-batch-more">\u8fd8\u6709 ${children.length - 3} \u9879\uff0c\u70b9\u51fb\u5361\u7247\u67e5\u770b\u5b8c\u6574\u8be6\u60c5</div>`
    : '';
  return `<div class="task-batch-children">${rows}${more}</div>`;
}

async function ensureBatchChildren(kind, id, options = {}) {
  const cache = kind === 'download' ? downloadBatchChildrenCache : uploadBatchChildrenCache;
  if (!options.force && cache.has(id)) return cache.get(id);
  const url = kind === 'download' ? `/api/tasks/download/batch/${id}` : `/api/tasks/upload/batch/${id}`;
  const res = await fetch(url);
  const json = await res.json();
  if (!res.ok) {
    throw new Error(json.error || 'batch_children_failed');
  }
  const items = json.items || [];
  cache.set(id, items);
  return items;
}

async function refreshExpandedBatchChildren(kind) {
  const expandedIds = kind === 'download' ? Array.from(expandedDownloadBatchIds) : Array.from(expandedUploadBatchIds);
  const sourceItems = kind === 'download' ? downloadItems : uploadItems;
  const validIds = expandedIds.filter(id => sourceItems.some(item => item.id === id && item.kind === 'batch'));
  await Promise.all(validIds.map(id => ensureBatchChildren(kind, id, { force: true })));
}

async function resolveDownloadUploadIds(selectedItems) {
  const ids = new Set();
  for (const item of selectedItems) {
    if (item.kind === 'batch') {
      const children = await ensureBatchChildren('download', item.id, { force: true });
      children
        .filter(child => child.status === 'completed' && child.save_path)
        .forEach(child => ids.add(child.id));
      continue;
    }
    if (item.status === 'completed' && item.save_path) {
      ids.add(item.id);
    }
  }
  return Array.from(ids);
}

async function executeOrderedDownloadBatchUpload(selectedItems) {
  const ordered = selectedItems
    .slice()
    .sort((a, b) => (selectedDownloadOrder.get(a.id) || 0) - (selectedDownloadOrder.get(b.id) || 0));
  const batchItems = ordered.filter(item => item.kind === 'batch');
  const fileIds = [];

  for (const batch of batchItems) {
    const ids = await resolveDownloadUploadIds([batch]);
    if (!ids.length) continue;
    await submitBatchUpload(ids, batch.description || '');
  }

  for (const item of ordered) {
    if (item.kind === 'batch') continue;
    if (item.status === 'completed' && item.save_path) {
      fileIds.push(item.id);
    }
  }

  return { hasBatch: batchItems.length > 0, fileIds };
}

function stopDetailRefresh() {
  if (detailRefreshTimer) {
    clearInterval(detailRefreshTimer);
    detailRefreshTimer = null;
  }
}

async function withButtonFeedback(button, fn) {
  if (!button) {
    return fn();
  }
  const prevDisabled = !!button.disabled;
  button.disabled = true;
  button.classList.remove('is-done', 'is-error');
  button.classList.add('is-busy');
  try {
    const result = await fn();
    button.classList.add('is-done');
    setTimeout(() => button.classList.remove('is-done'), 500);
    return result;
  } catch (err) {
    button.classList.add('is-error');
    setTimeout(() => button.classList.remove('is-error'), 800);
    throw err;
  } finally {
    button.classList.remove('is-busy');
    button.disabled = prevDisabled;
  }
}

function renderDownloads() {
  applyTaskColumns();
  if (!downloadItems.length) {
    downloadList.className = 'task-list';
    downloadList.innerHTML = '<div class="empty">暂无下载任务</div>';
    updateSelectionUI('download');
    return;
  }

  downloadList.className = 'task-list';
  downloadList.innerHTML = downloadItems.map(item => {
    const percent = item.total_size ? Math.round(item.progress) : 0;
    const badgeClass = item.status === 'completed' ? 'success' : (item.status === 'failed' ? 'fail' : 'running');
    const statusText = statusLabel(item.status);
    const checked = selectedDownloadIds.has(item.id) ? 'checked' : '';
    const selectedClass = checked ? 'is-selected' : '';
    const isExpanded = item.kind === 'batch' && expandedDownloadBatchIds.has(item.id);
    const batchChildren = isExpanded ? (downloadBatchChildrenCache.get(item.id) || []) : [];
    const title = escapeHtml(item.kind === 'batch' ? item.title : (item.filename || item.url || `任务 #${item.id}`));
    const meta = item.kind === 'batch'
      ? `${item.child_count} 项 | 成功 ${item.completed_count} | 失败 ${item.failed_count} | ${percent}%`
      : `${typeLabel(item.file_type)} | ${percent}% | ${formatBytes(item.speed || 0)}/s`;
    const subline = item.kind === 'batch'
      ? `<div class="task-subline">批量下载任务</div>`
      : (item.filename && item.url ? `<div class="task-subline">${escapeHtml(item.url)}</div>` : '');
    const completionMeta = item.status === 'completed' && item.updated_at
      ? `<div class="task-subline">完成时间: ${escapeHtml(item.updated_at)}</div>`
      : '';

    let toggleBtn = '';
    if (isDownloadPauseable(item)) {
      toggleBtn = renderTaskControl('pause', 'pause', '暂停');
    } else if (isDownloadResumable(item)) {
      toggleBtn = renderTaskControl('play', 'resume', '继续');
    }

    const endBtn = isDeletable(item.status)
      ? renderTaskControl('trash-2', 'delete', '删除', 'danger')
      : renderTaskControl('x-circle', 'cancel', '取消', 'warn');

    const startBtn = isDownloadStartable(item)
      ? renderTaskControl('rotate-ccw', 'retry', '开始')
      : '';

    const manualUploadBtn = (!autoUpload && item.kind !== 'batch' && item.status === 'completed' && item.save_path)
      ? `<button type="button" class="icon-btn" data-action="manual-upload" data-path="${escapeHtml(item.save_path)}" title="手动上传" aria-label="手动上传"><i data-lucide="upload"></i></button>`
      : '';

    return `
      <div class="task task-modern ${selectedClass}" data-type="download" data-id="${item.id}">
        <label class="task-select" title="选择任务">
          <input type="checkbox" class="task-check" data-kind="download" data-id="${item.id}" ${checked} />
        </label>
        ${item.kind === 'batch'
          ? `<div class="task-preview task-preview-file task-preview-batch"><i data-lucide="layers-3"></i><span>批次 ${item.child_count}</span></div>`
          : renderPreviewCard(item)}
        <div class="task-main">
          ${item.kind === 'batch' ? renderBatchHeader(item, isExpanded) : ''}
          <div class="task-title">${title}</div>
          ${subline}
          ${item.kind === 'batch' ? renderBatchStats(item, '项') : ''}
          ${item.kind === 'batch' && isExpanded ? renderBatchChildrenSummary(batchChildren, 'download') : ''}
          ${completionMeta}
          <div class="task-meta">
            <span class="badge ${badgeClass}">${statusText}</span>
            ${meta}
          </div>
          <div class="progress-wrap">
            <div class="progress"><span style="width:${percent}%"></span></div>
          </div>
        </div>
        <div class="task-ops">
          ${startBtn}
          ${toggleBtn}
          ${endBtn}
          ${manualUploadBtn}
        </div>
      </div>
    `;
  }).join('');

  updateSelectionUI('download');
  refreshIcons();
}

function renderUploads() {
  applyTaskColumns();
  if (!uploadItems.length) {
    uploadList.className = 'task-list';
    uploadList.innerHTML = '<div class="empty">暂无上传任务</div>';
    updateSelectionUI('upload');
    return;
  }

  uploadList.className = 'task-list';
  uploadList.innerHTML = uploadItems.map(item => {
    const percent = item.total_size ? Math.round(item.progress) : 0;
    const name = item.kind === 'batch'
      ? item.title
      : (item.source_path || '').split('\\').pop().split('/').pop();
    const badgeClass = item.status === 'completed' ? 'success' : (item.status === 'failed' ? 'fail' : 'running');
    const statusText = statusLabel(item.status);
    const checked = selectedUploadIds.has(item.id) ? 'checked' : '';
    const selectedClass = checked ? 'is-selected' : '';
    const isExpanded = item.kind === 'batch' && expandedUploadBatchIds.has(item.id);
    const batchChildren = isExpanded ? (uploadBatchChildrenCache.get(item.id) || []) : [];

    const title = escapeHtml(name || item.source_path || `任务 #${item.id}`);
    const meta = item.kind === 'batch'
      ? `${item.child_count} 项 | 成功 ${item.completed_count} | 失败 ${item.failed_count} | ${percent}%`
      : `${percent}% | ${formatBytes(item.speed || 0)}/s`;
    const subline = item.kind === 'batch'
      ? `<div class="task-subline">批量上传任务</div>`
      : (item.source_path ? `<div class="task-subline">${escapeHtml(item.source_path)}</div>` : '');
    const startBtn = isUploadStartable(item)
      ? renderTaskControl('rotate-ccw', 'retry', '开始')
      : '';
    const endBtn = isDeletable(item.status)
      ? renderTaskControl('trash-2', 'delete', '删除', 'danger')
      : renderTaskControl('x-circle', 'cancel', '取消', 'warn');

    return `
      <div class="task task-modern ${selectedClass}" data-type="upload" data-id="${item.id}">
        <label class="task-select" title="选择任务">
          <input type="checkbox" class="task-check" data-kind="upload" data-id="${item.id}" ${checked} />
        </label>
        <div class="task-preview task-preview-file ${item.kind === 'batch' ? 'task-preview-batch' : ''}">
          <i data-lucide="${item.kind === 'batch' ? 'layers-3' : 'file-up'}"></i>
          <span>${item.kind === 'batch' ? `批次 ${item.child_count}` : '上传任务'}</span>
        </div>
        <div class="task-main">
          ${item.kind === 'batch' ? renderBatchHeader(item, isExpanded) : ''}
          <div class="task-title">${title}</div>
          ${subline}
          ${item.kind === 'batch' ? renderBatchStats(item, '项') : ''}
          ${item.kind === 'batch' && isExpanded ? renderBatchChildrenSummary(batchChildren, 'upload') : ''}
          <div class="task-meta">
            <span class="badge ${badgeClass}">${statusText}</span>
            ${meta}
          </div>
          <div class="progress-wrap">
            <div class="progress"><span style="width:${percent}%"></span></div>
          </div>
        </div>
        <div class="task-ops">
          ${startBtn}
          ${endBtn}
        </div>
      </div>
    `;
  }).join('');

  updateSelectionUI('upload');
  refreshIcons();
}

async function loadDownloads() {
  const params = new URLSearchParams();
  if (downloadStatus.value) params.set('status', downloadStatus.value);
  if (downloadSearch.value) params.set('q', downloadSearch.value);
  if (downloadFileType?.value) params.set('file_type', downloadFileType.value);
  if (downloadDateFrom?.value) params.set('completed_from', downloadDateFrom.value);
  if (downloadDateTo?.value) params.set('completed_to', downloadDateTo.value);
  params.set('page', String(downloadPage));
  params.set('limit', String(downloadPageSize));
  const res = await fetch(`/api/tasks/list?${params.toString()}`);
  const json = await res.json();
  downloadItems = json.items || [];
  keepSelectionCurrent('download', downloadItems);
  await refreshExpandedBatchChildren('download');
  renderDownloads();
  if (downloadPageEl) downloadPageEl.textContent = String(downloadPage);
  if (activeDetail?.kind === 'download') {
    await showDetail('download', activeDetail.id, { preserveRefresh: true });
  }
}

async function loadUploads() {
  const params = new URLSearchParams();
  if (uploadStatus.value) params.set('status', uploadStatus.value);
  if (uploadSearch.value) params.set('q', uploadSearch.value);
  params.set('page', String(uploadPage));
  params.set('limit', String(uploadPageSize));
  const res = await fetch(`/api/tasks/upload/list?${params.toString()}`);
  const json = await res.json();
  uploadItems = json.items || [];
  keepSelectionCurrent('upload', uploadItems);
  await refreshExpandedBatchChildren('upload');
  renderUploads();
  if (uploadPageEl) uploadPageEl.textContent = String(uploadPage);
  if (activeDetail?.kind === 'upload') {
    await showDetail('upload', activeDetail.id, { preserveRefresh: true });
  }
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

async function loadInlineLogs() {
  if (!logListInline) return;
  const res = await fetch('/api/logs?limit=50');
  const json = await res.json();
  const items = (json.items || []).slice().reverse();
  if (!items.length) {
    logListInline.textContent = '暂无日志';
    return;
  }
  logListInline.textContent = items.map(item => {
    return `[${item.created_at}] ${item.level.toUpperCase()} ${item.message}`;
  }).join('\n');
  logListInline.scrollTop = logListInline.scrollHeight;
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

async function createDownload(urls, description = '') {
  await fetch('/api/tasks/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urls, description }),
  });
  await loadDownloads();
}

async function uploadBrowserFile(file, triggerBtn = null) {
  if (!file) return;
  const formData = new FormData();
  const dot = (file.name || '').lastIndexOf('.');
  const baseName = dot > 0 ? file.name.slice(0, dot) : (file.name || '');
  formData.append('file', file);
  formData.append('description', baseName);
  await withButtonFeedback(triggerBtn, async () => {
    const res = await fetch('/api/tasks/upload/file', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      throw new Error('upload_file_failed');
    }
    await loadUploads();
  });
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
  const warnText = json.warning ? `\n提示: ${json.warning}` : '';
  prepareInfo.textContent = `类型: ${typeText} | 大小: ${sizeText}${resText}${durText}${warnText}`;
  prepareFilename.value = json.filename || prepareFilename.value;
  const videos = json.video_formats || [];
  const audios = json.audio_formats || [];
  renderFormatOptions(prepareVideoFormat, videos, 'video');
  renderFormatOptions(prepareAudioFormat, audios, 'audio');
  if (prepareQuality) {
    prepareQuality.classList.toggle('hidden', !(videos.length || audios.length));
  }
  pendingPrepareFormat = buildSelectedFormat();
}

async function actOnDownloadTask(id, action) {
  const item = downloadItems.find(entry => entry.id === id);
  const kind = item?.kind || 'task';
  if (action === 'delete') {
    await fetch('/api/tasks/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, kind }),
    });
    return;
  }
  await fetch('/api/tasks/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, action, kind }),
  });
}

async function submitBatchUpload(ids, description) {
  const res = await fetch('/api/tasks/download/batch-upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, description }),
  });
  if (!res.ok) {
    throw new Error('batch_upload_failed');
  }
}

async function actOnUploadTask(id, action) {
  const item = uploadItems.find(entry => entry.id === id);
  const kind = item?.kind || 'task';
  if (action === 'delete') {
    await fetch('/api/tasks/upload/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, kind }),
    });
    return;
  }
  await fetch('/api/tasks/upload/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, action, kind }),
  });
}

async function applyDownloadBulk(action) {
  const selected = getOrderedSelectedDownloadItems();
  let targets = [];
  if (action === 'batch-upload') {
    const { hasBatch, fileIds } = await executeOrderedDownloadBatchUpload(selected);
    if (hasBatch) {
      if (fileIds.length) {
        await submitBatchUpload(fileIds, '');
      }
      await loadUploads();
      return;
    }
    if (fileIds.length) {
      showBatchUploadModal(fileIds);
    }
    return;
  }
  if (action === 'start') targets = selected.filter(isDownloadStartable).map(item => [item.id, 'retry']);
  if (action === 'pause') targets = selected.filter(isDownloadPauseable).map(item => [item.id, 'pause']);
  if (action === 'resume') targets = selected.filter(isDownloadResumable).map(item => [item.id, 'resume']);
  if (action === 'cancel') targets = selected.filter(item => isCancelable(item.status)).map(item => [item.id, 'cancel']);
  if (action === 'delete') targets = selected.filter(item => isDeletable(item.status)).map(item => [item.id, 'delete']);
  await Promise.all(targets.map(([id, mapped]) => actOnDownloadTask(id, mapped)));
  await loadDownloads();
}

async function applyUploadBulk(action) {
  const selected = uploadItems.filter(item => selectedUploadIds.has(item.id));
  let targets = [];
  if (action === 'start') targets = selected.filter(isUploadStartable).map(item => [item.id, 'retry']);
  if (action === 'cancel') targets = selected.filter(item => isCancelable(item.status)).map(item => [item.id, 'cancel']);
  if (action === 'delete') targets = selected.filter(item => isDeletable(item.status)).map(item => [item.id, 'delete']);
  await Promise.all(targets.map(([id, mapped]) => actOnUploadTask(id, mapped)));
  await loadUploads();
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
    showDownloadBatchModal(lines);
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
    pendingPrepareFormat = buildSelectedFormat();
    const item = { url: pendingPrepareUrl, filename };
    if (pendingPrepareFormat) item.format = pendingPrepareFormat;
    await fetch('/api/tasks/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: [item] }),
    });
    hidePrepareModal();
    await loadDownloads();
  });
}

prepareVideoFormat?.addEventListener('change', () => {
  pendingPrepareFormat = buildSelectedFormat();
});
prepareAudioFormat?.addEventListener('change', () => {
  pendingPrepareFormat = buildSelectedFormat();
});

if (uploadForm) {
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const path = uploadPathInput.value.trim();
    if (!path) return;
    if (uploadQuickStatus) uploadQuickStatus.textContent = '提交中...';
    const res = await fetch('/api/tasks/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    const json = await res.json().catch(() => ({}));
    if (res.ok && json.ok) {
      if (uploadQuickStatus) uploadQuickStatus.textContent = '已创建上传任务';
      uploadPathInput.value = '';
      await loadUploads();
      return;
    }
    const detail = json.detail ? ` (${json.detail})` : '';
    if (uploadQuickStatus) uploadQuickStatus.textContent = `路径上传失败: ${json.error || 'unknown'}${detail}`;
  });
}

if (uploadPickBtn && uploadFileInput) {
  uploadPickBtn.addEventListener('click', () => {
    uploadFileInput.click();
  });
  uploadFileInput.addEventListener('change', async () => {
    const file = uploadFileInput.files && uploadFileInput.files[0];
    if (!file) return;
    if (uploadPathInput) uploadPathInput.value = file.name;
    try {
      if (uploadQuickStatus) uploadQuickStatus.textContent = '文件上传中...';
      await uploadBrowserFile(file, uploadPickBtn);
      if (uploadQuickStatus) uploadQuickStatus.textContent = '已创建上传任务';
    } catch (err) {
      console.error('browser file upload failed', err);
      if (uploadQuickStatus) uploadQuickStatus.textContent = '文件上传失败';
    } finally {
      uploadFileInput.value = '';
    }
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
if (uploadPageSizeEl) {
  uploadPageSizeEl.value = String(uploadPageSize);
  uploadPageSizeEl.addEventListener('change', () => {
    const size = Number(uploadPageSizeEl.value);
    if (!PAGE_SIZE_OPTIONS.includes(size)) return;
    uploadPageSize = size;
    uploadPage = 1;
    localStorage.setItem('upload_page_size', String(size));
    loadUploads();
  });
}
if (uploadColumnsEl) {
  uploadColumnsEl.value = String(uploadColumns);
  uploadColumnsEl.addEventListener('change', () => {
    const value = Number(uploadColumnsEl.value);
    if (![1, 2, 3, 4, 5].includes(value)) return;
    uploadColumns = value;
    localStorage.setItem('upload_columns', String(value));
    applyTaskColumns();
  });
}

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
if (downloadFileType) {
  downloadFileType.addEventListener('change', () => {
    downloadPage = 1;
    loadDownloads();
  });
}
if (downloadDateFrom) {
  downloadDateFrom.addEventListener('change', () => {
    downloadPage = 1;
    loadDownloads();
  });
}
if (downloadDateTo) {
  downloadDateTo.addEventListener('change', () => {
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
if (downloadPageSizeEl) {
  downloadPageSizeEl.value = String(downloadPageSize);
  downloadPageSizeEl.addEventListener('change', () => {
    const size = Number(downloadPageSizeEl.value);
    if (!PAGE_SIZE_OPTIONS.includes(size)) return;
    downloadPageSize = size;
    downloadPage = 1;
    localStorage.setItem('download_page_size', String(size));
    loadDownloads();
  });
}
if (downloadColumnsEl) {
  downloadColumnsEl.value = String(downloadColumns);
  downloadColumnsEl.addEventListener('change', () => {
    const value = Number(downloadColumnsEl.value);
    if (![1, 2, 3, 4, 5].includes(value)) return;
    downloadColumns = value;
    localStorage.setItem('download_columns', String(value));
    applyTaskColumns();
  });
}

if (downloadSelectAll) {
  downloadSelectAll.addEventListener('change', () => {
    downloadItems.forEach(item => {
      setDownloadSelection(item.id, downloadSelectAll.checked);
    });
    renderDownloads();
  });
}

if (uploadSelectAll) {
  uploadSelectAll.addEventListener('change', () => {
    uploadItems.forEach(item => {
      if (uploadSelectAll.checked) selectedUploadIds.add(item.id);
      else selectedUploadIds.delete(item.id);
    });
    renderUploads();
  });
}

bulkButtons.forEach(btn => {
  btn.addEventListener('click', async () => {
    const target = btn.dataset.bulkTarget;
    const action = btn.dataset.bulkAction;
    if (btn.disabled) return;
    try {
      await withButtonFeedback(btn, async () => {
        if (target === 'download') {
          await applyDownloadBulk(action);
        } else {
          await applyUploadBulk(action);
        }
      });
    } catch (err) {
      console.error('bulk action failed', err);
    }
  });
});

downloadList?.addEventListener('click', async (e) => {
  const check = e.target.closest('.task-check');
  if (check) {
    const id = Number(check.dataset.id);
    setDownloadSelection(id, check.checked);
    updateSelectionUI('download');
    return;
  }

  const btn = e.target.closest('button[data-action]');
  const taskEl = e.target.closest('.task');

  if (btn && taskEl) {
    e.stopPropagation();
    const id = Number(taskEl.dataset.id);
    const action = btn.dataset.action;
    if (action === 'detail-preview') {
      try {
        const payload = JSON.parse(btn.dataset.preview || '{}');
        showPreview(payload);
      } catch (err) {
        console.error('download batch preview failed', err);
      }
      return;
    }
    if (action === 'toggle-batch') {
      if (expandedDownloadBatchIds.has(id)) {
        expandedDownloadBatchIds.delete(id);
        renderDownloads();
      } else {
        try {
          await withButtonFeedback(btn, async () => {
            await ensureBatchChildren('download', id);
            expandedDownloadBatchIds.add(id);
            renderDownloads();
          });
        } catch (err) {
          console.error('download batch expand failed', err);
        }
      }
      return;
    }
    if (action === 'preview') {
      const item = downloadItems.find(task => task.id === id);
      if (item) showPreview(item);
      return;
    }
    try {
      await withButtonFeedback(btn, async () => {
        if (action === 'manual-upload') {
          const path = btn.dataset.path;
          await fetch('/api/tasks/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
          });
          await loadUploads();
          return;
        }
        await actOnDownloadTask(id, action);
        await loadDownloads();
      });
    } catch (err) {
      console.error('download task action failed', err);
    }
    return;
  }

  if (taskEl) {
    showDetail('download', Number(taskEl.dataset.id));
  }
});

uploadList?.addEventListener('click', async (e) => {
  const check = e.target.closest('.task-check');
  if (check) {
    const id = Number(check.dataset.id);
    if (check.checked) selectedUploadIds.add(id);
    else selectedUploadIds.delete(id);
    updateSelectionUI('upload');
    return;
  }

  const btn = e.target.closest('button[data-action]');
  const taskEl = e.target.closest('.task');

  if (btn && taskEl) {
    e.stopPropagation();
    const id = Number(taskEl.dataset.id);
    const action = btn.dataset.action;
    if (action === 'detail-preview') {
      try {
        const payload = JSON.parse(btn.dataset.preview || '{}');
        showPreview(payload);
      } catch (err) {
        console.error('upload batch preview failed', err);
      }
      return;
    }
    if (action === 'toggle-batch') {
      if (expandedUploadBatchIds.has(id)) {
        expandedUploadBatchIds.delete(id);
        renderUploads();
      } else {
        try {
          await withButtonFeedback(btn, async () => {
            await ensureBatchChildren('upload', id);
            expandedUploadBatchIds.add(id);
            renderUploads();
          });
        } catch (err) {
          console.error('upload batch expand failed', err);
        }
      }
      return;
    }
    try {
      await withButtonFeedback(btn, async () => {
        await actOnUploadTask(id, action);
        await loadUploads();
      });
    } catch (err) {
      console.error('upload task action failed', err);
    }
    return;
  }

  if (taskEl) {
    await showDetail('upload', Number(taskEl.dataset.id));
  }
});

function connectSSE() {
  const evtSource = new EventSource('/sse');
  evtSource.onopen = () => {
    statusEl.textContent = '已连接';
  };
  evtSource.addEventListener('auth', (event) => {
    const payload = JSON.parse(event.data || '{}');
    applyAuthState(payload);
  });
  evtSource.addEventListener('download', () => {
    loadDownloads();
    loadInlineLogs();
  });
  evtSource.addEventListener('upload', () => {
    loadUploads();
    loadInlineLogs();
  });
  evtSource.onerror = () => {
    statusEl.textContent = '连接中断，重试中...';
    evtSource.close();
    setTimeout(connectSSE, 3000);
  };
}

const savedTheme = localStorage.getItem('theme') || 'dark';
applyTheme(savedTheme);

fetchAuthStatus();
loadConfig().then(() => loadDownloads());
loadUploads();
loadSystem();
loadInlineLogs();
if (!logsTimer) {
  logsTimer = setInterval(() => {
    loadInlineLogs();
  }, 3000);
}
connectSSE();

const urlTab = new URL(window.location.href).searchParams.get('tab');
setActiveTab(urlTab || 'download');
tabButtons.forEach(btn => {
  btn.addEventListener('click', () => setActiveTab(btn.dataset.tabButton));
});

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    applyTheme(document.body.classList.contains('light') ? 'dark' : 'light');
  });
}

if (authOpenBtn) {
  authOpenBtn.addEventListener('click', () => {
    openAuthModalFromStatus().catch(err => {
      console.error('open auth modal failed', err);
      window.alert('认证状态读取失败，请稍后重试');
    });
  });
}

if (detailClose) {
  detailClose.addEventListener('click', () => {
    stopDetailRefresh();
    activeDetail = null;
    detailPanel.classList.add('hidden');
  });
}

function getOrderedSelectedDownloadItems() {
  return downloadItems
    .filter(item => selectedDownloadIds.has(item.id))
    .sort((a, b) => (selectedDownloadOrder.get(a.id) || 0) - (selectedDownloadOrder.get(b.id) || 0));
}

if (logRefreshInline) {
  logRefreshInline.addEventListener('click', () => loadInlineLogs());
}

if (batchUploadCancel) {
  batchUploadCancel.addEventListener('click', () => hideBatchUploadModal());
}

if (batchUploadForm) {
  batchUploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!pendingBatchUploadIds.length) return;
    await submitBatchUpload(pendingBatchUploadIds, batchUploadDescription?.value?.trim() || '');
    hideBatchUploadModal();
  });
}

if (downloadBatchCancel) {
  downloadBatchCancel.addEventListener('click', () => hideDownloadBatchModal());
}

if (downloadBatchForm) {
  downloadBatchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!pendingBatchDownloadUrls.length) return;
    await createDownload(pendingBatchDownloadUrls, downloadBatchDescription?.value?.trim() || '');
    downloadBatch.value = '';
    hideDownloadBatchModal();
  });
}

if (previewClose) {
  previewClose.addEventListener('click', () => hidePreviewModal());
}

detailBody?.addEventListener('click', (event) => {
  const btn = event.target.closest('button[data-action="detail-preview"]');
  if (!btn) return;
  try {
    const payload = JSON.parse(btn.dataset.preview || '{}');
    showPreview(payload);
  } catch (err) {
    console.error('detail preview failed', err);
  }
});

function beginDetailRefresh(kind, id) {
  stopDetailRefresh();
  activeDetail = { kind, id };
  detailRefreshTimer = setInterval(() => {
    showDetail(kind, id, { preserveRefresh: true }).catch(err => {
      console.error('detail refresh failed', err);
    });
  }, 3000);
}

async function showDetail(kind, id, options = {}) {
  let item = null;
  if (kind === 'download') {
    item = downloadItems.find(t => t.id === id);
  } else {
    item = uploadItems.find(t => t.id === id);
  }
  if (!item) return;
  if (!options.preserveRefresh) {
    beginDetailRefresh(kind, id);
  }
  detailTitle.textContent = kind === 'download' ? '下载任务详情' : '上传任务详情';
  if (kind === 'upload' && item.kind === 'batch') {
    try {
      const children = await ensureBatchChildren('upload', id, { force: true });
      detailTitle.textContent = '批量上传详情';
      detailBody.innerHTML = renderBatchDetailPanel(item, children, 'upload');
      detailPanel.classList.remove('hidden');
      refreshIcons();
      return;
    } catch (err) {
      detailTitle.textContent = '批量上传详情';
      detailBody.innerHTML = `<div class="empty">批次详情加载失败: ${escapeHtml(err?.message || String(err))}</div>`;
      detailPanel.classList.remove('hidden');
      return;
    }
  }
  if (kind === 'download' && item.kind === 'batch') {
    try {
      const children = await ensureBatchChildren('download', id, { force: true });
      detailTitle.textContent = '批量下载详情';
      detailBody.innerHTML = renderBatchDetailPanel(item, children, 'download');
      detailPanel.classList.remove('hidden');
      refreshIcons();
      return;
    } catch (err) {
      detailTitle.textContent = '批量下载详情';
      detailBody.innerHTML = `<div class="empty">批次详情加载失败: ${escapeHtml(err?.message || String(err))}</div>`;
      detailPanel.classList.remove('hidden');
      return;
    }
  }
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
    created_at: '创建时间',
    updated_at: '更新时间',
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
    return `<div class="row"><div class="label">${label}</div><div>${escapeHtml(value ?? '-')}</div></div>`;
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

function typeLabel(type) {
  const map = {
    video: '视频',
    image: '图片',
    audio: '音频',
    file: '文件',
  };
  return map[type] || '文件';
}
