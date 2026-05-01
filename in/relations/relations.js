/**
 * Relations CRM — three pipelines on a unified schema.
 * Views: picker, kanban, table, contact detail drawer.
 * Backend: Supabase. Writes go through anon-key RLS gated by is_relations_admin().
 */

let sb = null;
let currentUser = null;

let pipelines = [];        // [{id, slug, title, custom_field_schema, ...}]
let stagesByPipeline = {}; // pipelineId -> [stage, ...] sorted by display_order
let activePipeline = null; // pipeline object or null
let activeView = 'kanban'; // 'kanban' | 'table'
let activeContactId = null;

const esc = (s) => { const d = document.createElement('div'); d.textContent = String(s ?? ''); return d.innerHTML; };
const fmtDate = (iso) => iso ? new Date(iso).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' }) : '';
const fmtDateTime = (iso) => iso ? new Date(iso).toLocaleString('en-US', { day: '2-digit', month: 'short', hour: 'numeric', minute: '2-digit' }) : '';
const fmtCurrency = (n) => (n == null || n === '') ? '' : '$' + Number(n).toLocaleString();

function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast toast--${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.classList.add('toast--visible'), 10);
  setTimeout(() => { t.classList.remove('toast--visible'); setTimeout(() => t.remove(), 300); }, 2800);
}

// ─── URL state ────────────────────────────────────────────────────────────────
function readUrl() {
  const q = new URLSearchParams(location.search);
  return { p: q.get('p') || null, v: q.get('v') || 'kanban', c: q.get('c') || null };
}
function writeUrl({ p, v, c }) {
  const q = new URLSearchParams();
  if (p) q.set('p', p);
  if (v && v !== 'kanban') q.set('v', v);
  if (c) q.set('c', c);
  const s = q.toString();
  history.pushState({}, '', s ? `?${s}` : location.pathname);
}

// ─── Boot ─────────────────────────────────────────────────────────────────────
window.initRelations = async function (user, supabase) {
  currentUser = user;
  sb = supabase;
  await loadPipelinesAndStages();
  renderHeaderNav();
  window.addEventListener('popstate', route);
  route();
};

async function loadPipelinesAndStages() {
  const [{ data: ps, error: pe }, { data: ss, error: se }] = await Promise.all([
    sb.from('relations_pipelines').select('*').order('display_order'),
    sb.from('relations_stages').select('*').order('display_order'),
  ]);
  if (pe) { toast('Failed to load pipelines: ' + pe.message, 'error'); return; }
  if (se) { toast('Failed to load stages: ' + se.message, 'error'); return; }
  pipelines = ps || [];
  stagesByPipeline = {};
  for (const s of (ss || [])) {
    (stagesByPipeline[s.pipeline_id] ||= []).push(s);
  }
}

function renderHeaderNav() {
  const nav = document.getElementById('pipeline-nav');
  nav.innerHTML = pipelines.map(p =>
    `<a href="?p=${esc(p.slug)}" data-pipeline="${esc(p.slug)}" class="nav-link">${esc(p.icon || '')} ${esc(p.title)}</a>`
  ).join('');
  nav.querySelectorAll('a').forEach(a => a.addEventListener('click', (e) => {
    e.preventDefault();
    writeUrl({ p: a.dataset.pipeline });
    route();
  }));
}

function setHeaderActive(slug) {
  document.querySelectorAll('#pipeline-nav .nav-link').forEach(a => {
    a.classList.toggle('active', a.dataset.pipeline === slug);
  });
}

// ─── Router ───────────────────────────────────────────────────────────────────
function route() {
  const { p, v, c } = readUrl();
  setHeaderActive(p);

  if (!p) {
    activePipeline = null;
    renderPicker();
    return;
  }
  const pipeline = pipelines.find(x => x.slug === p);
  if (!pipeline) {
    document.getElementById('app-main').innerHTML = `<div class="empty">Unknown pipeline: <code>${esc(p)}</code></div>`;
    return;
  }
  activePipeline = pipeline;
  activeView = (v === 'table') ? 'table' : 'kanban';
  activeContactId = c;

  if (activeView === 'kanban') renderKanban();
  else renderTable();

  if (activeContactId) openDrawer(activeContactId);
  else closeDrawer();
}

// ─── Picker ───────────────────────────────────────────────────────────────────
async function renderPicker() {
  const main = document.getElementById('app-main');
  main.innerHTML = `<section class="picker"><h2>Pick a pipeline</h2><div class="picker-grid" id="picker-grid"></div></section>`;
  const grid = document.getElementById('picker-grid');

  const counts = await Promise.all(pipelines.map(p =>
    sb.from('relations_contacts')
      .select('*', { count: 'exact', head: true })
      .eq('pipeline_id', p.id)
      .eq('status', 'active')
      .then(r => r.count ?? 0)
      .catch(() => 0)
  ));

  grid.innerHTML = pipelines.map((p, i) => `
    <a class="picker-card" href="?p=${esc(p.slug)}" data-pipeline="${esc(p.slug)}">
      <div class="picker-icon">${esc(p.icon || '📇')}</div>
      <div class="picker-title">${esc(p.title)}</div>
      <div class="picker-desc">${esc(p.description || '')}</div>
      <div class="picker-count">${counts[i]} active</div>
    </a>
  `).join('');
  grid.querySelectorAll('.picker-card').forEach(a => a.addEventListener('click', (e) => {
    e.preventDefault();
    writeUrl({ p: a.dataset.pipeline });
    route();
  }));
}

// ─── View toolbar (shared by kanban/table) ────────────────────────────────────
function viewToolbar() {
  const slug = activePipeline.slug;
  return `
    <div class="view-toolbar">
      <div class="view-tabs">
        <a href="?p=${esc(slug)}"            class="${activeView === 'kanban' ? 'active' : ''}" data-view="kanban">Kanban</a>
        <a href="?p=${esc(slug)}&v=table"    class="${activeView === 'table'  ? 'active' : ''}" data-view="table">Table</a>
      </div>
      <div class="view-actions">
        <input type="search" id="filter-input" placeholder="Filter by name, company, email…" />
        <button class="btn-primary" id="btn-new-contact">+ New contact</button>
      </div>
    </div>
  `;
}

function wireToolbar() {
  document.querySelectorAll('.view-tabs a').forEach(a => a.addEventListener('click', (e) => {
    e.preventDefault();
    writeUrl({ p: activePipeline.slug, v: a.dataset.view });
    route();
  }));
  document.getElementById('filter-input').addEventListener('input', (e) => {
    applyFilter(e.target.value.trim().toLowerCase());
  });
  document.getElementById('btn-new-contact').addEventListener('click', () => createContact());
}

function applyFilter(q) {
  document.querySelectorAll('[data-search]').forEach(el => {
    el.style.display = (!q || el.dataset.search.includes(q)) ? '' : 'none';
  });
}

// ─── Kanban ───────────────────────────────────────────────────────────────────
async function renderKanban() {
  const main = document.getElementById('app-main');
  main.innerHTML = `
    ${viewToolbar()}
    <div class="kanban" id="kanban"></div>
  `;
  wireToolbar();

  const stages = stagesByPipeline[activePipeline.id] || [];
  const { data: contacts, error } = await sb.from('relations_contacts')
    .select('*')
    .eq('pipeline_id', activePipeline.id)
    .neq('status', 'archived')
    .order('priority')
    .order('updated_at', { ascending: false });
  if (error) { toast('Failed to load contacts: ' + error.message, 'error'); return; }

  const byStage = {};
  for (const s of stages) byStage[s.id] = [];
  byStage['__none__'] = [];
  for (const c of contacts) (byStage[c.stage_id] ||= byStage['__none__']).push(c);

  const board = document.getElementById('kanban');
  board.innerHTML = stages.map(s => `
    <div class="col" data-stage-id="${s.id}">
      <div class="col-head" style="border-top-color:${esc(s.color || '#ccc')}">
        <span class="col-title">${esc(s.title)}</span>
        <span class="col-count">${(byStage[s.id] || []).length}</span>
      </div>
      <div class="col-body" data-stage-id="${s.id}">
        ${(byStage[s.id] || []).map(cardHtml).join('')}
      </div>
    </div>
  `).join('') + (
    byStage['__none__'].length ? `
      <div class="col col-unassigned">
        <div class="col-head"><span class="col-title">Unassigned</span><span class="col-count">${byStage['__none__'].length}</span></div>
        <div class="col-body" data-stage-id="">${byStage['__none__'].map(cardHtml).join('')}</div>
      </div>` : ''
  );

  board.querySelectorAll('.card').forEach(el => {
    el.addEventListener('click', () => openContact(el.dataset.id));
    el.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', el.dataset.id);
      el.classList.add('dragging');
    });
    el.addEventListener('dragend', () => el.classList.remove('dragging'));
  });
  board.querySelectorAll('.col-body').forEach(body => {
    body.addEventListener('dragover', (e) => { e.preventDefault(); body.classList.add('drop-target'); });
    body.addEventListener('dragleave', () => body.classList.remove('drop-target'));
    body.addEventListener('drop', async (e) => {
      e.preventDefault();
      body.classList.remove('drop-target');
      const id = e.dataTransfer.getData('text/plain');
      const newStageId = body.dataset.stageId || null;
      await moveContactToStage(id, newStageId);
    });
  });
}

function cardHtml(c) {
  const search = [c.name, c.company, c.email, c.title].filter(Boolean).join(' ').toLowerCase();
  const meta = [c.company, c.title].filter(Boolean).join(' · ');
  const tags = (c.tags || []).slice(0, 3).map(t => `<span class="tag">${esc(t)}</span>`).join('');
  const value = c.expected_value ? `<span class="card-value">${fmtCurrency(c.expected_value)}</span>` : '';
  return `
    <div class="card" draggable="true" data-id="${c.id}" data-search="${esc(search)}">
      <div class="card-name">${esc(c.name)}</div>
      ${meta ? `<div class="card-meta">${esc(meta)}</div>` : ''}
      <div class="card-foot">${tags}${value}</div>
    </div>
  `;
}

async function moveContactToStage(contactId, newStageId) {
  const { error } = await sb.from('relations_contacts')
    .update({ stage_id: newStageId })
    .eq('id', contactId);
  if (error) { toast('Move failed: ' + error.message, 'error'); return; }
  toast('Stage updated', 'success');
  renderKanban();
}

// ─── Table ────────────────────────────────────────────────────────────────────
async function renderTable() {
  const main = document.getElementById('app-main');
  main.innerHTML = `${viewToolbar()}<div class="table-wrap"><table class="rel-table" id="rel-table"></table></div>`;
  wireToolbar();

  const stages = stagesByPipeline[activePipeline.id] || [];
  const stageById = Object.fromEntries(stages.map(s => [s.id, s]));
  const customFields = (activePipeline.custom_field_schema?.fields) || [];

  const { data: contacts, error } = await sb.from('relations_contacts')
    .select('*')
    .eq('pipeline_id', activePipeline.id)
    .neq('status', 'archived')
    .order('updated_at', { ascending: false });
  if (error) { toast('Failed to load contacts: ' + error.message, 'error'); return; }

  const stdCols = [
    { key: 'name',     label: 'Name' },
    { key: 'stage',    label: 'Stage' },
    { key: 'company',  label: 'Company' },
    { key: 'title',    label: 'Title' },
    { key: 'email',    label: 'Email' },
    { key: 'phone',    label: 'Phone' },
    { key: 'city',     label: 'City' },
    { key: 'priority', label: 'P' },
    { key: 'expected_value', label: 'Value' },
    { key: 'next_action_at', label: 'Next action' },
  ];

  const head = `<thead><tr>
    ${stdCols.map(c => `<th>${esc(c.label)}</th>`).join('')}
    ${customFields.map(f => `<th>${esc(f.label)}</th>`).join('')}
  </tr></thead>`;

  const body = `<tbody>${
    (contacts || []).map(c => {
      const search = [c.name, c.company, c.email, c.title, c.phone].filter(Boolean).join(' ').toLowerCase();
      const stage = stageById[c.stage_id];
      return `<tr data-id="${c.id}" data-search="${esc(search)}">
        <td class="td-name">${esc(c.name)}</td>
        <td>${stage ? `<span class="stage-pill" style="background:${esc(stage.color||'#ccc')}22;color:${esc(stage.color||'#444')}">${esc(stage.title)}</span>` : ''}</td>
        <td>${esc(c.company || '')}</td>
        <td>${esc(c.title || '')}</td>
        <td>${esc(c.email || '')}</td>
        <td>${esc(c.phone || '')}</td>
        <td>${esc(c.city || '')}</td>
        <td>${esc(c.priority || '')}</td>
        <td>${fmtCurrency(c.expected_value)}</td>
        <td>${fmtDate(c.next_action_at)}</td>
        ${customFields.map(f => `<td>${esc(formatCustomValue(f, c.custom?.[f.key]))}</td>`).join('')}
      </tr>`;
    }).join('')
  }</tbody>`;

  const table = document.getElementById('rel-table');
  table.innerHTML = head + body;
  table.querySelectorAll('tbody tr').forEach(tr => {
    tr.addEventListener('click', () => openContact(tr.dataset.id));
  });
}

function formatCustomValue(field, v) {
  if (v == null || v === '') return '';
  if (field.type === 'currency') return fmtCurrency(v);
  if (field.type === 'date')     return fmtDate(v);
  if (field.type === 'boolean')  return v ? '✓' : '';
  if (field.type === 'multiselect' && Array.isArray(v)) return v.join(', ');
  return String(v);
}

// ─── Drawer (contact detail) ──────────────────────────────────────────────────
function openContact(id) {
  writeUrl({ p: activePipeline.slug, v: activeView, c: id });
  activeContactId = id;
  openDrawer(id);
}

function closeDrawer() {
  document.querySelector('.drawer-backdrop')?.remove();
  document.querySelector('.drawer')?.remove();
}

async function openDrawer(id) {
  closeDrawer();
  const { data: contact, error } = await sb.from('relations_contacts').select('*').eq('id', id).single();
  if (error) { toast('Failed to load contact: ' + error.message, 'error'); return; }
  const { data: activities } = await sb.from('relations_activities').select('*').eq('contact_id', id).order('occurred_at', { ascending: false });

  const stages = stagesByPipeline[activePipeline.id] || [];
  const customFields = (activePipeline.custom_field_schema?.fields) || [];

  const backdrop = document.createElement('div');
  backdrop.className = 'drawer-backdrop';
  backdrop.addEventListener('click', () => { writeUrl({ p: activePipeline.slug, v: activeView }); route(); });
  document.body.appendChild(backdrop);

  const drawer = document.createElement('aside');
  drawer.className = 'drawer';
  drawer.innerHTML = `
    <div class="drawer-head">
      <h3 id="d-name">${esc(contact.name)}</h3>
      <button class="drawer-close" aria-label="Close">×</button>
    </div>
    <div class="drawer-body">
      <section class="d-section">
        <h4>Stage & status</h4>
        <div class="d-row">
          <label>Stage</label>
          <select id="d-stage">
            <option value="">—</option>
            ${stages.map(s => `<option value="${s.id}" ${s.id === contact.stage_id ? 'selected' : ''}>${esc(s.title)}</option>`).join('')}
          </select>
        </div>
        <div class="d-row">
          <label>Status</label>
          <select id="d-status">
            ${['active','paused','archived'].map(v => `<option value="${v}" ${v === contact.status ? 'selected' : ''}>${v}</option>`).join('')}
          </select>
        </div>
        <div class="d-row">
          <label>Priority (1–5)</label>
          <input type="number" id="d-priority" min="1" max="5" value="${contact.priority ?? 3}">
        </div>
      </section>

      <section class="d-section">
        <h4>Standard fields</h4>
        ${stdField('name', 'Name', contact.name, 'text')}
        ${stdField('email', 'Email', contact.email, 'email')}
        ${stdField('phone', 'Phone', contact.phone, 'tel')}
        ${stdField('company', 'Company', contact.company, 'text')}
        ${stdField('title', 'Title', contact.title, 'text')}
        ${stdField('linkedin_url', 'LinkedIn', contact.linkedin_url, 'url')}
        ${stdField('website', 'Website', contact.website, 'url')}
        ${stdField('city', 'City', contact.city, 'text')}
        ${stdField('country', 'Country', contact.country, 'text')}
        ${stdField('owner_email', 'Owner', contact.owner_email, 'email')}
        ${stdField('expected_value', 'Expected value ($)', contact.expected_value, 'number')}
        ${stdField('expected_close_date', 'Expected close', contact.expected_close_date, 'date')}
        ${stdField('next_action_at', 'Next action at', toLocalDT(contact.next_action_at), 'datetime-local')}
        ${stdField('next_action_note', 'Next action', contact.next_action_note, 'text')}
        <div class="d-row d-row-full">
          <label>Tags (comma-separated)</label>
          <input type="text" id="d-tags" value="${esc((contact.tags || []).join(', '))}">
        </div>
        <div class="d-row d-row-full">
          <label>Notes</label>
          <textarea id="d-notes" rows="4">${esc(contact.notes || '')}</textarea>
        </div>
      </section>

      ${customFields.length ? `
        <section class="d-section">
          <h4>Custom fields — ${esc(activePipeline.title)}</h4>
          ${customFields.map(f => customFieldHtml(f, contact.custom?.[f.key])).join('')}
        </section>` : ''
      }

      <section class="d-section">
        <div class="d-section-head">
          <h4>Activity</h4>
        </div>
        <div class="activity-add">
          <textarea id="activity-body" rows="2" placeholder="Add a note, log a call, log a meeting…"></textarea>
          <div class="activity-add-row">
            <select id="activity-kind">
              <option value="note">Note</option>
              <option value="call">Call</option>
              <option value="meeting">Meeting</option>
              <option value="email">Email</option>
              <option value="task">Task</option>
              <option value="other">Other</option>
            </select>
            <button class="btn-primary" id="btn-add-activity">Add</button>
          </div>
        </div>
        <ul class="activity-list" id="activity-list">
          ${(activities || []).map(activityItemHtml).join('') || '<li class="empty">No activity yet.</li>'}
        </ul>
      </section>

      <section class="d-section d-danger">
        <h4>Danger</h4>
        <button class="btn-danger" id="btn-delete">Delete contact</button>
      </section>
    </div>

    <div class="drawer-foot">
      <button class="btn-primary" id="btn-save">Save</button>
      <span class="drawer-hint">Esc to close</span>
    </div>
  `;
  document.body.appendChild(drawer);

  drawer.querySelector('.drawer-close').addEventListener('click', () => { writeUrl({ p: activePipeline.slug, v: activeView }); route(); });
  drawer.querySelector('#btn-save').addEventListener('click', () => saveContact(contact));
  drawer.querySelector('#btn-add-activity').addEventListener('click', () => addActivity(contact.id));
  drawer.querySelector('#btn-delete').addEventListener('click', () => deleteContact(contact.id));

  document.addEventListener('keydown', escListener, { once: true });
}

function escListener(e) {
  if (e.key === 'Escape' && document.querySelector('.drawer')) {
    writeUrl({ p: activePipeline.slug, v: activeView });
    route();
  }
}

function stdField(key, label, value, type) {
  const v = (value == null) ? '' : value;
  return `
    <div class="d-row">
      <label>${esc(label)}</label>
      <input type="${type}" data-std="${esc(key)}" value="${esc(v)}">
    </div>
  `;
}

function customFieldHtml(f, value) {
  const v = (value == null) ? '' : value;
  const id = `cf-${f.key}`;
  if (f.type === 'textarea') {
    return `<div class="d-row d-row-full"><label>${esc(f.label)}</label><textarea id="${id}" data-cf="${esc(f.key)}" rows="3">${esc(v)}</textarea></div>`;
  }
  if (f.type === 'select') {
    return `<div class="d-row"><label>${esc(f.label)}</label><select id="${id}" data-cf="${esc(f.key)}">
      <option value="">—</option>
      ${(f.options || []).map(o => `<option value="${esc(o)}" ${o === v ? 'selected' : ''}>${esc(o)}</option>`).join('')}
    </select></div>`;
  }
  if (f.type === 'multiselect') {
    const arr = Array.isArray(v) ? v : [];
    return `<div class="d-row"><label>${esc(f.label)}</label><select id="${id}" data-cf="${esc(f.key)}" data-multi="1" multiple>
      ${(f.options || []).map(o => `<option value="${esc(o)}" ${arr.includes(o) ? 'selected' : ''}>${esc(o)}</option>`).join('')}
    </select></div>`;
  }
  if (f.type === 'boolean') {
    return `<div class="d-row d-row-checkbox"><label><input type="checkbox" id="${id}" data-cf="${esc(f.key)}" ${v ? 'checked' : ''}> ${esc(f.label)}</label></div>`;
  }
  const inputType = ({ number: 'number', currency: 'number', date: 'date', url: 'url' })[f.type] || 'text';
  return `<div class="d-row"><label>${esc(f.label)}</label><input type="${inputType}" id="${id}" data-cf="${esc(f.key)}" value="${esc(v)}"></div>`;
}

function readField(el) {
  if (!el) return null;
  if (el.dataset.multi) return Array.from(el.selectedOptions).map(o => o.value);
  if (el.type === 'checkbox') return el.checked;
  if (el.type === 'number') return el.value === '' ? null : Number(el.value);
  if (el.type === 'datetime-local') return el.value ? new Date(el.value).toISOString() : null;
  return el.value === '' ? null : el.value;
}

function toLocalDT(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function saveContact(prev) {
  const stdInputs = document.querySelectorAll('.drawer [data-std]');
  const cfInputs  = document.querySelectorAll('.drawer [data-cf]');
  const update = {};
  stdInputs.forEach(el => { update[el.dataset.std] = readField(el); });
  const tagsRaw = document.getElementById('d-tags').value;
  update.tags = tagsRaw.split(',').map(s => s.trim()).filter(Boolean);
  update.notes = document.getElementById('d-notes').value || null;
  update.stage_id = document.getElementById('d-stage').value || null;
  update.status = document.getElementById('d-status').value;
  update.priority = Number(document.getElementById('d-priority').value) || 3;

  const customFields = (activePipeline.custom_field_schema?.fields) || [];
  const custom = { ...(prev.custom || {}) };
  cfInputs.forEach(el => {
    const f = customFields.find(x => x.key === el.dataset.cf);
    if (f) custom[f.key] = readField(el);
  });
  update.custom = custom;

  const { error } = await sb.from('relations_contacts').update(update).eq('id', prev.id);
  if (error) { toast('Save failed: ' + error.message, 'error'); return; }
  toast('Saved', 'success');
  if (activeView === 'kanban') renderKanban(); else renderTable();
  openDrawer(prev.id);
}

async function addActivity(contactId) {
  const body = document.getElementById('activity-body').value.trim();
  const kind = document.getElementById('activity-kind').value;
  if (!body) { toast('Activity body is empty', 'error'); return; }
  const { error } = await sb.from('relations_activities').insert({
    contact_id: contactId, kind, body, created_by: currentUser.email,
  });
  if (error) { toast('Failed: ' + error.message, 'error'); return; }
  document.getElementById('activity-body').value = '';
  openDrawer(contactId);
}

function activityItemHtml(a) {
  const meta = a.kind === 'stage_change'
    ? `moved stages`
    : `${a.kind}${a.created_by ? ` · ${esc(a.created_by)}` : ''}`;
  return `
    <li class="activity-item activity-${esc(a.kind)}">
      <div class="activity-meta">${meta} · ${fmtDateTime(a.occurred_at)}</div>
      ${a.body ? `<div class="activity-body">${esc(a.body)}</div>` : ''}
    </li>
  `;
}

async function createContact() {
  const name = prompt(`New contact name (${activePipeline.title}):`);
  if (!name || !name.trim()) return;
  const stages = stagesByPipeline[activePipeline.id] || [];
  const firstStage = stages[0]?.id || null;
  const { data, error } = await sb.from('relations_contacts').insert({
    pipeline_id: activePipeline.id,
    stage_id: firstStage,
    name: name.trim(),
  }).select().single();
  if (error) { toast('Create failed: ' + error.message, 'error'); return; }
  toast('Contact created', 'success');
  openContact(data.id);
}

async function deleteContact(id) {
  if (!confirm('Delete this contact and all its activity? This cannot be undone.')) return;
  const { error } = await sb.from('relations_contacts').delete().eq('id', id);
  if (error) { toast('Delete failed: ' + error.message, 'error'); return; }
  toast('Deleted', 'success');
  writeUrl({ p: activePipeline.slug, v: activeView });
  route();
}
