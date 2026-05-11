const API = '';
const TOKEN_KEY = 'msdns_token';

function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

function api(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };
  return fetch((API || '') + path, { ...options, headers });
}

const SCREEN_HIDDEN_CLASS = 'screen-hidden';

function show(el, visible) {
  if (el) {
    el.hidden = !visible;
    if (visible) {
      el.removeAttribute('hidden');
      el.classList.remove(SCREEN_HIDDEN_CLASS);
      el.style.display = '';
      el.style.visibility = '';
    } else {
      el.setAttribute('hidden', '');
      el.classList.add(SCREEN_HIDDEN_CLASS);
      el.style.display = 'none';
      el.style.visibility = 'hidden';
    }
  }
}

function showLoggedIn(loggedIn) {
  const loginEl = document.getElementById('login-screen');
  const mainEl = document.getElementById('main-screen');
  if (loginEl) {
    loginEl.hidden = loggedIn;
    loginEl.classList.toggle(SCREEN_HIDDEN_CLASS, loggedIn);
    loginEl.style.setProperty('display', loggedIn ? 'none' : 'flex');
    loginEl.style.setProperty('visibility', loggedIn ? 'hidden' : 'visible');
  }
  if (mainEl) {
    mainEl.hidden = !loggedIn;
    mainEl.classList.toggle(SCREEN_HIDDEN_CLASS, !loggedIn);
    mainEl.style.setProperty('display', loggedIn ? 'block' : 'none');
    mainEl.style.setProperty('visibility', loggedIn ? 'visible' : 'hidden');
  }
}

function showError(el, msg) {
  el.textContent = msg || '';
  el.hidden = !msg;
}

function recordDataDisplay(record) {
  const d = record.data || {};
  switch ((record.type || '').toUpperCase()) {
    case 'A':
    case 'AAAA':
      return d.ip || '';
    case 'CNAME':
    case 'NS':
    case 'PTR':
      return d.target || '';
    case 'MX':
      return (d.exchange || '') + (d.preference != null ? ' (pref ' + d.preference + ')' : '');
    case 'TXT':
      return d.text || '';
    case 'SRV':
      return (d.target || '') + (d.port != null ? ':' + d.port : '') + (d.priority != null ? ' prio=' + d.priority : '') + (d.weight != null ? ' w=' + d.weight : '');
    default:
      return d.raw || JSON.stringify(d);
  }
}

function dataFieldsForType(type, container, prefix, values) {
  values = values || {};
  type = (type || 'A').toUpperCase();
  container.innerHTML = '';
  const add = (label, key, placeholder, typeAttr = 'text') => {
    const wrap = document.createElement('span');
    wrap.className = 'data-field';
    const id = prefix + key;
    wrap.innerHTML = `<label for="${id}">${label}</label><input id="${id}" type="${typeAttr}" placeholder="${placeholder || ''}" value="${escapeAttr(values[key] ?? '')}" />`;
    container.appendChild(wrap);
    return container.querySelector('#' + id);
  };
  switch (type) {
    case 'A':
    case 'AAAA':
      add('IP', 'ip', type === 'A' ? '192.168.1.10' : '::1');
      break;
    case 'CNAME':
    case 'NS':
    case 'PTR':
      add('Target', 'target', 'host.example.com');
      break;
    case 'MX':
      add('Mail exchange', 'exchange', 'mail.example.com');
      add('Preference', 'preference', '10', 'number');
      break;
    case 'TXT':
      add('Text', 'text', 'v=spf1 ...');
      break;
    case 'SRV':
      add('Target', 'target', 'host.example.com');
      add('Port', 'port', '443', 'number');
      add('Priority', 'priority', '0', 'number');
      add('Weight', 'weight', '0', 'number');
      break;
    default:
      add('Value', 'raw', '');
  }
}

function getDataFromFields(container, prefix, type) {
  type = (type || 'A').toUpperCase();
  const d = {};
  const get = (key) => {
    const el = document.getElementById(prefix + key);
    return el ? el.value.trim() : '';
  };
  const getNum = (key) => {
    const v = get(key);
    return v === '' ? undefined : parseInt(v, 10);
  };
  switch (type) {
    case 'A':
    case 'AAAA':
      d.ip = get('ip');
      break;
    case 'CNAME':
    case 'NS':
    case 'PTR':
      d.target = get('target');
      break;
    case 'MX':
      d.exchange = get('exchange');
      const pref = getNum('preference');
      if (pref !== undefined) d.preference = pref;
      break;
    case 'TXT':
      d.text = get('text');
      break;
    case 'SRV':
      d.target = get('target');
      const port = getNum('port');
      const priority = getNum('priority');
      const weight = getNum('weight');
      if (port !== undefined) d.port = port;
      if (priority !== undefined) d.priority = priority;
      if (weight !== undefined) d.weight = weight;
      break;
    default:
      d.raw = get('raw');
  }
  return d;
}

function escapeAttr(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML.replace(/"/g, '&quot;');
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// --- Login ---
const loginScreen = document.getElementById('login-screen');
const mainScreen = document.getElementById('main-screen');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const loginBtn = document.getElementById('login-btn');
const loginUsername = document.getElementById('username');
const loginPassword = document.getElementById('password');

function setLoginLoading(loading) {
  if (loginBtn) {
    loginBtn.disabled = loading;
    loginBtn.textContent = loading ? 'Signing in…' : 'Sign in';
    loginBtn.classList.toggle('loading', loading);
  }
  if (loginUsername) loginUsername.disabled = loading;
  if (loginPassword) loginPassword.disabled = loading;
}

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  showError(loginError);
  setLoginLoading(true);
  try {
    const form = new FormData(loginForm);
    const body = new URLSearchParams({
      username: form.get('username') || document.getElementById('username').value,
      password: form.get('password') || document.getElementById('password').value
    });
    const res = await fetch(API + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      showError(loginError, d.detail || 'Login failed');
      return;
    }
    const data = await res.json().catch(() => ({}));
    const token = data && data.access_token;
    if (!token) {
      showError(loginError, 'Invalid response from server');
      return;
    }
    setToken(token);
    showLoggedIn(true);
    loadZones().catch(() => {});
  } finally {
    setLoginLoading(false);
  }
});

document.getElementById('logout-btn').addEventListener('click', async () => {
  const token = getToken();
  try {
    if (token) {
      await fetch(API + '/api/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  } catch (_) {
    /* still clear client state */
  } finally {
    clearToken();
    showLoggedIn(false);
  }
});

// --- Zones & records ---
const zoneSelect = document.getElementById('zone-select');
const refreshZonesBtn = document.getElementById('refresh-zones');
const zoneLabel = document.getElementById('zone-label');
const recordsSection = document.getElementById('records-section');
const recordsError = document.getElementById('records-error');
const recordsTbody = document.querySelector('#records-table tbody');
const newName = document.getElementById('new-name');
const newType = document.getElementById('new-type');
const newDataFields = document.getElementById('new-data-fields');

function setZonesLoading(loading) {
  zoneSelect.disabled = loading;
  if (refreshZonesBtn) {
    refreshZonesBtn.disabled = loading;
    refreshZonesBtn.classList.toggle('loading', loading);
    refreshZonesBtn.title = loading ? 'Loading…' : 'Refresh zones';
  }
  if (loading && zoneSelect.options.length > 0) {
    zoneSelect.options[0].text = 'Loading zones…';
  }
}

function setRecordsLoading(loading) {
  zoneSelect.disabled = loading;
  if (refreshZonesBtn) refreshZonesBtn.disabled = loading;
  if (loading) {
    recordsTbody.innerHTML = '<tr class="loading-row"><td colspan="4">Loading records…</td></tr>';
  }
}

function renderAddDataFields() {
  dataFieldsForType(newType.value, newDataFields, 'new-');
}

newType.addEventListener('change', renderAddDataFields);
renderAddDataFields();

async function loadZones() {
  setZonesLoading(true);
  try {
    const res = await api('/api/zones');
    if (!res.ok) {
      if (res.status === 401) {
        clearToken();
        showLoggedIn(false);
        return;
      }
      zoneSelect.innerHTML = '<option value="">Error loading zones</option>';
      return;
    }
    const data = await res.json();
    const current = zoneSelect.value;
    zoneSelect.innerHTML = '<option value="">-- Select a zone --</option>' +
      (data.zones || []).map(z => `<option value="${escapeHtml(z)}">${escapeHtml(z)}</option>`).join('');
    if (current && data.zones && data.zones.includes(current)) zoneSelect.value = current;
    if (zoneSelect.value) await loadRecords(zoneSelect.value);
  } finally {
    if (zoneSelect.options.length > 0 && zoneSelect.options[0].text === 'Loading zones…') {
      zoneSelect.options[0].text = '-- Select a zone --';
    }
    setZonesLoading(false);
  }
}

async function loadRecords(zone) {
  zoneLabel.textContent = zone ? ` in ${zone}` : '';
  recordsTbody.innerHTML = '';
  showError(recordsError);
  if (!zone) return;
  setRecordsLoading(true);
  try {
    const res = await api(`/api/zones/${encodeURIComponent(zone)}/records`);
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      showError(recordsError, d.detail || 'Failed to load records');
      return;
    }
    const data = await res.json();
    const rows = (data.records || []).map(r => {
      const tr = document.createElement('tr');
      const dataStr = recordDataDisplay(r);
      tr.innerHTML = `<td>${escapeHtml(r.type)}</td><td>${escapeHtml(r.name)}</td><td>${escapeHtml(dataStr)}</td><td class="actions"><button type="button" class="btn-ghost btn-sm" data-action="edit">Edit</button> <button type="button" class="btn-danger btn-sm" data-action="delete">Delete</button></td>`;
      tr.querySelector('[data-action="edit"]').addEventListener('click', () => openEditModal(zone, r));
      tr.querySelector('[data-action="delete"]').addEventListener('click', (e) => removeRecord(zone, r, e.currentTarget));
      return tr;
    });
    recordsTbody.innerHTML = '';
    rows.forEach(tr => recordsTbody.appendChild(tr));
  } finally {
    setRecordsLoading(false);
  }
}

zoneSelect.addEventListener('change', () => {
  loadRecords(zoneSelect.value || '');
});

document.getElementById('refresh-zones').addEventListener('click', () => loadZones());

const addRecordBtn = document.getElementById('add-record');
addRecordBtn.addEventListener('click', async () => {
  const zone = zoneSelect.value;
  const name = newName.value.trim();
  const type = newType.value.trim();
  if (!zone || !name || !type) {
    showError(recordsError, 'Select a zone and enter name and type.');
    return;
  }
  const recordData = getDataFromFields(newDataFields, 'new-', type);
  showError(recordsError);
  addRecordBtn.disabled = true;
  addRecordBtn.textContent = 'Adding…';
  addRecordBtn.classList.add('loading');
  try {
    const res = await api(`/api/zones/${encodeURIComponent(zone)}/records`, {
      method: 'POST',
      body: JSON.stringify({ type, name, data: recordData }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showError(recordsError, data.detail || 'Failed to add record');
      return;
    }
    newName.value = '';
    renderAddDataFields();
    loadRecords(zone);
  } finally {
    addRecordBtn.disabled = false;
    addRecordBtn.textContent = 'Add record';
    addRecordBtn.classList.remove('loading');
  }
});

async function removeRecord(zone, record, deleteBtn) {
  const dataStr = recordDataDisplay(record);
  if (!confirm(`Delete ${record.type} record "${record.name}" (${dataStr})?`)) return;
  if (deleteBtn) {
    deleteBtn.disabled = true;
    deleteBtn.textContent = 'Deleting…';
    deleteBtn.classList.add('loading');
  }
  try {
    const res = await api(`/api/zones/${encodeURIComponent(zone)}/records?name=${encodeURIComponent(record.name)}`, {
      method: 'DELETE',
      body: JSON.stringify({ type: record.type, data: record.data || {} }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showError(recordsError, data.detail || 'Failed to delete record');
      return;
    }
    loadRecords(zone);
  } finally {
    if (deleteBtn) {
      deleteBtn.disabled = false;
      deleteBtn.textContent = 'Delete';
      deleteBtn.classList.remove('loading');
    }
  }
}

// --- Edit modal ---
const editModal = document.getElementById('edit-modal');
const editNameInput = document.getElementById('edit-name');
const editTypeInput = document.getElementById('edit-type');
const editNameDisplay = document.getElementById('edit-name-display');
const editTypeDisplay = document.getElementById('edit-type-display');
const editDataFields = document.getElementById('edit-data-fields');
const editSaveBtn = document.getElementById('edit-save');
const editCancelBtn = document.getElementById('edit-cancel');
let editZone = '';
let editOldData = {};

function setEditModalBusy(loading) {
  editSaveBtn.disabled = loading;
  editCancelBtn.disabled = loading;
  editSaveBtn.textContent = loading ? 'Saving…' : 'Save';
  editSaveBtn.classList.toggle('loading', loading);
  editModal.querySelector('.modal-backdrop').style.pointerEvents = loading ? 'none' : '';
}

function openEditModal(zone, record) {
  editZone = zone;
  editNameInput.value = record.name;
  editTypeInput.value = record.type;
  editNameDisplay.textContent = record.name;
  editTypeDisplay.textContent = record.type;
  editOldData = record.data || {};
  dataFieldsForType(record.type, editDataFields, 'edit-', record.data || {});
  setEditModalBusy(false);
  show(editModal, true);
}

function closeEditModal() {
  setEditModalBusy(false);
  show(editModal, false);
}

editModal.querySelector('.modal-backdrop').addEventListener('click', () => {
  if (!editSaveBtn.disabled) closeEditModal();
});
editCancelBtn.addEventListener('click', closeEditModal);

editSaveBtn.addEventListener('click', async () => {
  const name = editNameInput.value.trim();
  const type = editTypeInput.value.trim();
  const newData = getDataFromFields(editDataFields, 'edit-', type);
  setEditModalBusy(true);
  try {
    const res = await api(`/api/zones/${encodeURIComponent(editZone)}/records?name=${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify({ type, old_data: editOldData, new_data: newData }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showError(recordsError, data.detail || 'Failed to update record');
      return;
    }
    closeEditModal();
    showError(recordsError);
    loadRecords(editZone);
  } finally {
    setEditModalBusy(false);
  }
});

// Initial state: show main only when we have a token (login hidden after successful login)
function initApp() {
  showLoggedIn(!!getToken());
  if (getToken()) loadZones();
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
