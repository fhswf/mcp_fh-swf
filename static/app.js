// ── DATA ───────────────────────────────────────────────
const API = window.location.origin + '/api/v1';

let pos = [];
let filteredPOs = [];
let selectedId = null;
let sortAsc = true;
let activeFilter = null;
let uploadedFile = null;

// ── API HELPERS ───────────────────────────────────────
async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(API + endpoint, options);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unbekannter Fehler' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error('Server nicht erreichbar');
    }
    throw error;
  }
}

// ── INIT ──────────────────────────────────────────────
window.onload = async () => {
  await loadPOs();
};

async function loadPOs() {
  try {
    const data = await apiCall('/po');
    pos = data.map(p => ({
      id: p.id,
      name: p.studiengang,
      version: p.version,
      date: p.gueltig_ab,
      status: p.status,
      moduleCount: p.module_count || 0,
      modules: []
    }));
    filteredPOs = [...pos];
    renderList();
    renderSearchResults(getAllModules());
    renderFilterChips();
    renderUploadHistory();
    updateMetrics();
  } catch (error) {
    showToast(error.message, 'error', true);
  }
}

// ── METRICS ──────────────────────────────────────────
function updateMetrics() {
  document.getElementById('m-total').textContent = pos.length;
  document.getElementById('m-modules').textContent = pos.reduce((a, p) => a + p.moduleCount, 0);
}

// ── THEME ─────────────────────────────────────────────
function toggleDark() {
  const html = document.documentElement;
  const isDark = html.classList.toggle('dark');
  document.getElementById('theme-icon').textContent = isDark ? 'light_mode' : 'dark_mode';
}

// ── NAVIGATION ───────────────────────────────────────
function showView(v) {
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.getElementById('view-' + v).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('nav-active'));
  const idx = { dashboard: 0, upload: 1, search: 2 }[v];
  document.querySelectorAll('.nav-btn')[idx].classList.add('nav-active');
  const titles = { dashboard: 'Übersicht', upload: 'Dokument hochladen', search: 'Modulsuche' };
  document.getElementById('page-title').textContent = titles[v];
  document.getElementById('search-container').style.display = v === 'dashboard' ? '' : 'none';
  if (v !== 'dashboard') closeDetail();
}

// ── PO LIST ───────────────────────────────────────────
function filterPOs(q) {
  filteredPOs = pos.filter(p => p.name.toLowerCase().includes(q.toLowerCase()) || p.version.toLowerCase().includes(q.toLowerCase()));
  renderList();
  updateMetrics();
}

function renderList() {
  const el = document.getElementById('po-list');
  if (!filteredPOs.length) {
    el.innerHTML = `<div class="text-center py-10 text-slate-400"><span class="material-symbols-outlined text-4xl block mb-2">search_off</span><p class="text-sm">Keine Prüfungsordnungen gefunden</p></div>`;
    return;
  }
  el.innerHTML = filteredPOs.map(p => `
    <div class="po-row bg-white dark:bg-gray-800 hairline rounded-xl p-4 flex items-center justify-between cursor-pointer transition-all ${selectedId === p.id ? 'selected' : ''}" onclick="selectPO('${p.id}')">
      <div>
        <h4 class="font-bold text-sm text-slate-900 dark:text-slate-100 mb-1">${p.name}</h4>
        <p class="text-xs text-slate-500 dark:text-slate-400">${p.version} · ${p.moduleCount} Module · ab ${formatDate(p.date)}</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="px-2.5 py-1 text-[10px] font-bold rounded-full uppercase tracking-wide status-${p.status}">${p.status === 'ready' ? 'Bereit' : p.status === 'veraltet' ? 'Veraltet' : p.status === 'processing' ? 'Wird verarbeitet' : 'Fehler'}</span>
        <span class="material-symbols-outlined text-slate-300 dark:text-gray-600 text-[20px]">chevron_right</span>
      </div>
    </div>
  `).join('');
}

// ── DETAIL ───────────────────────────────────────────
async function selectPO(id) {
  try {
    selectedId = id;
    const poData = await apiCall(`/po/${id}`);

    // Update local cache
    const mappedModules = poData.module.map(m => ({
      name: m.name,
      sem: m.semester,
      ects: m.ects,
      pf: m.pruefungsform,
      dozent: m.dozent
    }));
    const po = {
      id: poData.id,
      name: poData.studiengang,
      version: poData.version,
      date: poData.gueltig_ab,
      status: poData.status,
      moduleCount: mappedModules.length,
      modules: mappedModules
    };

    // Update pos array
    const idx = pos.findIndex(p => p.id === id);
    if (idx !== -1) pos[idx] = po;

    document.getElementById('detail-title').textContent = po.name;
    document.getElementById('detail-sub').textContent = `${po.version} · Gültig ab ${formatDate(po.date)}`;

    // Modules
    document.getElementById('detail-modules').innerHTML = po.modules.map(m => `
      <div class="p-3.5 rounded-xl hairline bg-slate-50 dark:bg-gray-700">
        <div class="flex justify-between items-start mb-2">
          <h6 class="text-sm font-bold text-slate-900 dark:text-slate-100 leading-tight">${m.name}</h6>
          <span class="text-[10px] font-bold text-slate-400 ml-2 flex-shrink-0">${m.sem}. Sem.</span>
        </div>
        <div class="flex items-center gap-4 text-slate-600 dark:text-slate-300 mt-2.5">
          <span class="flex items-center gap-1 text-xs font-medium"><span class="material-symbols-outlined text-[16px]" style="font-variation-settings:'FILL' 1">stars</span> ${m.ects} ECTS</span>
          <span class="flex items-center gap-1 text-xs font-medium"><span class="material-symbols-outlined text-[16px]">assignment</span> ${m.pf}</span>
          ${m.dozent ? `<span class="flex items-center gap-1 text-xs font-medium bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-md ml-auto"><span class="material-symbols-outlined text-[16px]">person</span> ${m.dozent}</span>` : ''}
        </div>
      </div>
    `).join('');

    // ECTS bars per semester
    const bySem = {};
    po.modules.forEach(m => { bySem[m.sem] = (bySem[m.sem] || 0) + m.ects; });
    const maxEcts = Math.max(...Object.values(bySem));
    document.getElementById('ects-overview').innerHTML = Object.entries(bySem).sort((a, b) => parseInt(a[0]) - parseInt(b[0])).map(([sem, ects]) => `
      <div class="flex items-center gap-3">
        <span class="text-[10px] font-bold text-slate-400 w-14 flex-shrink-0">Sem. ${sem}</span>
        <div class="flex-1 ects-bar"><div class="ects-fill" style="width:${Math.round(ects / maxEcts * 100)}%"></div></div>
        <span class="text-[11px] font-bold text-slate-600 dark:text-slate-300 w-12 text-right">${ects} ECTS</span>
      </div>
    `).join('');

    document.getElementById('detail-panel').classList.remove('hidden');
    document.getElementById('detail-panel').classList.add('flex');
    renderList();
  } catch (error) {
    showToast(error.message, 'error', true);
  }
}

function closeDetail() {
  selectedId = null;
  document.getElementById('detail-panel').classList.add('hidden');
  document.getElementById('detail-panel').classList.remove('flex');
  renderList();
}

// ── ECTS MODAL ────────────────────────────────────────
function showECTS() {
  if (!selectedId) return;
  const po = pos.find(p => p.id === selectedId);
  document.getElementById('ects-modal-title').textContent = `ECTS · ${po.name}`;
  const total = po.modules.reduce((a, m) => a + m.ects, 0);
  document.getElementById('ects-modal-content').innerHTML = `
    <div class="space-y-3 mb-5">
      ${po.modules.map(m => `
        <div class="flex items-center gap-3">
          <div class="flex-1">
            <div class="flex justify-between mb-1">
              <span class="text-xs font-medium text-slate-700 dark:text-slate-300">${m.name}</span>
              <span class="text-xs font-bold">${m.ects} ECTS</span>
            </div>
            <div class="ects-bar"><div class="ects-fill" style="width:${Math.round(m.ects / 10 * 100)}%"></div></div>
          </div>
        </div>
      `).join('')}
    </div>
    <div class="pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-between items-center">
      <span class="text-sm text-slate-500">Gesamt</span>
      <span class="text-lg font-extrabold">${total} ECTS</span>
    </div>
  `;
  document.getElementById('ects-modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('ects-modal').classList.add('hidden');
}

// ── DELETE ────────────────────────────────────────────
function confirmDelete() {
  document.getElementById('delete-modal').classList.remove('hidden');
}
function closeDeleteModal() {
  document.getElementById('delete-modal').classList.add('hidden');
}
async function executDelete() {
  if (!selectedId) return;

  try {
    await apiCall(`/po/${selectedId}`, { method: 'DELETE' });

    pos = pos.filter(p => p.id !== selectedId);
    filteredPOs = filteredPOs.filter(p => p.id !== selectedId);
    closeDeleteModal();
    closeDetail();
    renderList();
    updateMetrics();
    searchModules(document.getElementById('module-search').value);
    renderFilterChips();
    showToast('Prüfungsordnung gelöscht', 'delete', false);
  } catch (error) {
    closeDeleteModal();
    showToast(error.message, 'error', true);
  }
}

// ── UPLOAD ────────────────────────────────────────────
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f && f.type === 'application/pdf') setFile(f);
  else showToast('Nur PDF-Dateien erlaubt', 'error', true);
}
function handleFileSelect(input) {
  if (input.files[0]) setFile(input.files[0]);
}
function setFile(f) {
  uploadedFile = f;
  document.getElementById('drop-title').textContent = f.name;
  document.getElementById('drop-sub').textContent = `${(f.size / 1024 / 1024).toFixed(2)} MB · PDF`;
  document.getElementById('drop-icon').innerHTML = `<span class="material-symbols-outlined text-green-500 text-3xl" style="font-variation-settings:'FILL' 1">check_circle</span>`;
}

async function handleUpload() {
  const sg = document.getElementById('f-studiengang').value.trim();
  const ver = document.getElementById('f-version').value.trim();
  const dt = document.getElementById('f-date').value;

  if (!uploadedFile) {
    showToast('Bitte PDF-Datei auswählen', 'warning', true);
    return;
  }

  if (!sg || !ver || !dt) {
    showToast('Bitte alle Felder ausfüllen', 'warning', true);
    return;
  }

  const btn = document.getElementById('upload-btn');
  btn.innerHTML = `<span class="material-symbols-outlined text-[18px] spinner">refresh</span>Wird hochgeladen...`;
  btn.disabled = true;

  try {
    const formData = new FormData();
    formData.append('file', uploadedFile);
    formData.append('studiengang', sg);
    formData.append('version', ver);
    formData.append('gueltig_ab', dt);

    // Job starten – kommt sofort zurück
    const { job_id } = await apiCall('/job', { method: 'POST', body: formData });

    // Formular zurücksetzen
    document.getElementById('f-studiengang').value = '';
    document.getElementById('f-version').value = '';
    document.getElementById('f-date').value = '';
    document.getElementById('file-input').value = '';
    uploadedFile = null;
    document.getElementById('drop-title').textContent = 'PDF hierher ziehen';
    document.getElementById('drop-sub').textContent = 'oder klicken zum Auswählen';
    document.getElementById('drop-icon').innerHTML = `<span class="material-symbols-outlined text-primary dark:text-blue-400 text-3xl" style="font-variation-settings:'FILL' 1">upload_file</span>`;
    btn.innerHTML = `<span class="material-symbols-outlined text-[18px]">cloud_done</span>Hochladen & verarbeiten`;
    btn.disabled = false;

    // Zur Fortschrittsanzeige wechseln und Status pollen
    showJobProgress(job_id);
  } catch (error) {
    btn.innerHTML = `<span class="material-symbols-outlined text-[18px]">cloud_done</span>Hochladen & verarbeiten`;
    btn.disabled = false;
    showToast(error.message, 'error', true);
  }
}

async function showJobProgress(jobId) {
  const STEP_LABELS = ['PDF validieren', 'PDF konvertieren', 'Module extrahieren', 'S3 Upload', 'Neo4j speichern'];

  // Banner sofort mit allen Schritten als "pending" anzeigen
  const initialSteps = STEP_LABELS.map(label => `
    <div class="flex items-center gap-2 text-sm">
      <span class="material-symbols-outlined text-base text-gray-400">radio_button_unchecked</span>
      <span>${label}</span>
    </div>`).join('');

  const banner = document.createElement('div');
  banner.id = `job-${jobId}`;
  banner.className = 'p-4 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-2xl';
  banner.innerHTML = `<p class="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-3">Verarbeitung läuft...</p>
    <div id="job-steps-${jobId}" class="space-y-2">${initialSteps}</div>`;

  const bannersContainer = document.getElementById('job-banners');
  bannersContainer.appendChild(banner);

  const poll = async () => {
    try {
      const job = await apiCall(`/job/${jobId}/status`);
      const stepsEl = document.getElementById(`job-steps-${jobId}`);

      stepsEl.innerHTML = job.steps.map((s, i) => {
        const icon = s.status === 'done' ? 'check_circle' : s.status === 'error' ? 'cancel' : s.status === 'processing' ? 'refresh' : 'radio_button_unchecked';
        const color = s.status === 'done' ? 'text-green-500' : s.status === 'error' ? 'text-red-500' : s.status === 'processing' ? 'text-blue-500 spinner' : 'text-gray-400';
        return `<div class="flex items-center gap-2 text-sm">
          <span class="material-symbols-outlined text-base ${color}" style="${s.status==='done'?'font-variation-settings:\'FILL\' 1':''}">${icon}</span>
          <span class="${s.status === 'processing' ? 'font-semibold' : ''}">${STEP_LABELS[i]}</span>
        </div>`;
      }).join('');

      if (job.status === 'ready') {
        banner.className = 'p-4 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-2xl mb-4';
        banner.querySelector('p').textContent = 'Erfolgreich verarbeitet!';
        banner.querySelector('p').className = 'text-sm font-semibold text-green-700 dark:text-green-300 mb-3';
        showToast('Modulhandbuch erfolgreich verarbeitet', 'check_circle', false);
        await loadPOs();
        setTimeout(() => {
          banner.remove();
          showView('dashboard');
        }, 3000);
      } else if (job.status === 'error') {
        banner.className = 'p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded-2xl mb-4';
        banner.querySelector('p').textContent = `Fehler: ${job.error || 'Unbekannter Fehler'}`;
        banner.querySelector('p').className = 'text-sm font-semibold text-red-700 dark:text-red-300 mb-3';
        // Retry-Button
        const retryBtn = document.createElement('button');
        retryBtn.className = 'mt-2 text-xs text-red-600 underline';
        retryBtn.textContent = 'Erneut versuchen';
        retryBtn.onclick = async () => {
          retryBtn.remove();
          await apiCall(`/job/${jobId}`, { method: 'PUT' });
          banner.className = 'p-4 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-2xl mb-4';
          banner.querySelector('p').textContent = 'Verarbeitung läuft...';
          banner.querySelector('p').className = 'text-sm font-semibold text-blue-700 dark:text-blue-300 mb-3';
          setTimeout(poll, 3000);
        };
        banner.appendChild(retryBtn);
        showToast(job.error || 'Verarbeitung fehlgeschlagen', 'error', true);
      } else {
        setTimeout(poll, 3000);
      }
    } catch (e) {
      setTimeout(poll, 5000);
    }
  };

  setTimeout(poll, 2000);
}

function renderUploadHistory() {
  const el = document.getElementById('upload-history');
  const recent = pos.slice(0, 3);
  el.innerHTML = recent.map(p => `
    <div class="p-3 bg-slate-50 dark:bg-gray-700 hairline rounded-xl flex items-center justify-between">
      <div>
        <p class="text-xs font-bold text-slate-800 dark:text-slate-200">${p.name}</p>
        <p class="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
          <span class="w-1.5 h-1.5 rounded-full bg-green-500 inline-block"></span>Hochgeladen
        </p>
      </div>
      <span class="text-[10px] text-slate-400">${formatDate(p.date)}</span>
    </div>
  `).join('');
}

// ── SEARCH ────────────────────────────────────────────
function getAllModules() {
  const all = [];
  pos.forEach(p => p.modules.forEach(m => all.push({ ...m, studiengang: p.name })));
  return all;
}

function searchModules(q) {
  let results = getAllModules();
  if (activeFilter) results = results.filter(m => m.studiengang.includes(activeFilter));
  if (q) results = results.filter(m =>
    m.name.toLowerCase().includes(q.toLowerCase()) ||
    m.studiengang.toLowerCase().includes(q.toLowerCase()) ||
    String(m.ects).includes(q)
  );
  if (sortAsc) results.sort((a, b) => a.name.localeCompare(b.name));
  else results.sort((a, b) => b.name.localeCompare(a.name));
  renderSearchResults(results);
}

function renderSearchResults(results) {
  const el = document.getElementById('search-results');
  const noEl = document.getElementById('no-results');
  document.getElementById('results-count').textContent = `${results.length} Module`;
  if (!results.length) { el.innerHTML = ''; noEl.classList.remove('hidden'); return; }
  noEl.classList.add('hidden');
  el.innerHTML = results.map(m => `
    <div class="grid grid-cols-12 px-5 py-4 bg-white dark:bg-gray-800 hairline rounded-xl items-center hover:border-primary dark:hover:border-blue-500 cursor-pointer transition-all group">
      <div class="col-span-4 flex items-center gap-2.5">
        <div class="w-2 h-2 rounded-full bg-primary dark:bg-blue-400 flex-shrink-0"></div>
        <span class="text-sm font-semibold text-primary dark:text-blue-400 group-hover:text-primary-hover">${m.name}</span>
      </div>
      <div class="col-span-3 text-xs text-slate-500 dark:text-slate-400 font-medium">${m.studiengang}</div>
      <div class="col-span-2 text-xs text-slate-500 dark:text-slate-400">${m.sem}. Semester</div>
      <div class="col-span-1 text-xs font-bold text-slate-700 dark:text-slate-300">${m.ects}</div>
      <div class="col-span-2 flex flex-col justify-center items-end text-right">
        <span class="px-2.5 py-1 bg-slate-100 dark:bg-gray-700 text-slate-700 dark:text-slate-200 text-xs font-bold rounded uppercase tracking-tighter mb-1">${m.pf}</span>
        ${m.dozent ? `<span class="text-xs font-medium text-blue-600 dark:text-blue-400 block truncate max-w-full"><span class="material-symbols-outlined text-[14px] align-middle mr-0.5">person</span>${m.dozent}</span>` : ''}
      </div>
    </div>
  `).join('');
}

function renderFilterChips() {
  const el = document.getElementById('filter-chips');
  const studiengaenge = [...new Set(pos.map(p => p.name))];
  el.innerHTML = `
    <button class="chip px-3 py-1 text-xs font-bold rounded-full hairline text-slate-500 dark:text-slate-400 flex items-center gap-1 hover:bg-slate-100 dark:hover:bg-gray-700 ${!activeFilter ? 'active' : ''}" onclick="setFilter(null)">
      <span class="material-symbols-outlined text-[13px]">filter_list</span>Alle
    </button>
    ${studiengaenge.map(s => `
      <button class="chip px-3 py-1 text-xs font-semibold rounded-full hairline text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-gray-700 ${activeFilter === s ? 'active' : ''}" onclick="setFilter('${s}')">${s.split(' ')[0]}</button>
    `).join('')}
  `;
}

function setFilter(f) {
  activeFilter = f;
  renderFilterChips();
  searchModules(document.getElementById('module-search').value);
}

function toggleSort() {
  sortAsc = !sortAsc;
  document.getElementById('sort-label').textContent = sortAsc ? 'Modulname ↑' : 'Modulname ↓';
  searchModules(document.getElementById('module-search').value);
}

// ── TOAST ─────────────────────────────────────────────
function showToast(msg, icon = 'check_circle', isError = false) {
  const t = document.getElementById('toast');
  document.getElementById('toast-msg').textContent = msg;
  const i = document.getElementById('toast-icon');
  i.textContent = icon;
  i.className = `material-symbols-outlined text-[18px] ${isError ? 'text-red-500' : 'text-green-500'}`;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

// ── UTILS ─────────────────────────────────────────────
function formatDate(d) {
  if (!d) return '';
  const parts = d.split('-');
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
}
