const $ = (selector) => document.querySelector(selector);
const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
};
const esc = (value) => String(value ?? '--').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));

function lineClass(line) { return line.status === 'DOWN' ? 'down' : line.status === 'QUALITY_HOLD' ? 'hold' : 'running'; }
function lineLabel(status) { return status === 'QUALITY_HOLD' ? 'QUALITY HOLD' : status; }
function renderLines(data) {
  $('#line-grid').innerHTML = Object.values(data.lines).map((line) => `<article class="line-card ${lineClass(line)}"><div class="line-top"><strong>${esc(line.name.toUpperCase())}</strong><span class="status-chip ${lineClass(line) === 'down' ? 'red' : lineClass(line) === 'hold' ? 'amber' : 'green'}">● ${lineLabel(line.status)}</span></div><div class="line-status ${lineClass(line)}"><strong>${line.utilization_percent}% UTILIZATION</strong><span class="muted">${line.hourly_capacity} units / hour</span></div><div class="line-meta"><span>PRODUCTS ${esc(line.supported_products.join(' · '))}</span>${line.quality_hold ? '<span>QUALITY RESTRICTED</span>' : ''}</div></article>`).join('');
}
function renderDecision(data) {
  const decision = data.decisions?.at(-1);
  if (!decision) { $('#decision-content').innerHTML = '<p class="muted">No workflow has been run.</p>'; $('#approval-title').textContent = 'NO DECISION PENDING'; return; }
  $('#decision-content').innerHTML = `<div class="decision-title">${esc(decision.recommendation)}</div><p class="decision-copy">${esc(decision.reasoning_summary)}</p><div class="evidence">${(decision.evidence || []).slice(0, 5).map((item) => `<span>${esc(item)}</span>`).join('')}</div>`;
  $('#approval-title').textContent = decision.approval_required ? 'HUMAN APPROVAL REQUIRED' : 'NO APPROVAL REQUIRED';
  $('#approval-reason').textContent = decision.outcome || 'The backend is awaiting a human decision.';
}
function renderSnapshot(data) {
  const line2 = data.lines['line-2']; const equipment = data.equipment['equipment-2'];
  const cards = [['EQUIPMENT', `${line2.status} · ${equipment.downtime_minutes} MIN DOWNTIME`], ['PRODUCTION', `${equipment.lost_units} LOST · ${equipment.projected_lost_units} PROJECTED`], ['INVENTORY', `${data.inventory.days_of_inventory} DAYS · ${data.inventory.raw_material_units} RAW UNITS`], ['LABOR', `${data.labor.affected} AFFECTED · ${data.labor.reassigned} REASSIGNED`], ['ORDERS', Object.values(data.orders).map((order) => `P${order.product_id} ${order.priority}`).join(' / ')], ['RISK', `SEVERITY ${data.factory.severity} · ${data.factory.safety.status}`]];
  $('#snapshot-grid').innerHTML = cards.map(([title, value]) => `<div class="snapshot-card"><strong>${title}</strong><p>${esc(value)}</p></div>`).join('');
}
function renderEvents(data) { $('#event-feed').innerHTML = data.events?.length ? data.events.map((event) => `<div class="event"><time>${new Date(event.timestamp).toLocaleTimeString()}</time><div><strong>${esc(event.actor)} · ${esc(event.event_type)}</strong><p>${esc(event.summary)}</p></div></div>`).join('') : '<p class="muted">No events recorded.</p>'; }
function renderImpact(data) { const labels = ['EQUIPMENT FAILURE', 'CAPACITY REDUCTION', 'PRODUCTION LOSS', 'INVENTORY CHANGE', 'ORDER RISK', 'CUSTOMER IMPACT', 'REVENUE RISK']; $('#impact-chain').innerHTML = labels.map((label, index) => `<div class="impact-step ${index === 0 ? 'active' : index > 0 && index < 5 ? 'warning' : ''}">${label}</div>`).join(''); }
function renderSignals(data) { $('#signals').innerHTML = [['API STATUS', 'CONNECTED'], ['SHARED STATE', `VERSION ${data.version}`], ['SAFETY', data.factory.safety.status], ['EVENT JOURNAL', `${data.events?.length || 0} EVENTS`], ['SCENARIO', data.latest_result ? 'ASSESSMENT COMPLETE' : 'READY']].map(([name, value]) => `<div class="signal-row"><span>${name}</span><strong>${esc(value)}</strong></div>`).join(''); }
function render(data) {
  $('#factory-name').textContent = data.factory.name; $('#severity').textContent = data.factory.severity; $('#updated-at').textContent = new Date(data.updated_at).toLocaleTimeString(); $('#state-version').textContent = `VERSION ${data.version}`; $('#footer-version').textContent = `STATE VERSION ${data.version}`;
  renderLines(data); renderDecision(data); renderSnapshot(data); renderEvents(data); renderImpact(data); renderSignals(data);
  const active = data.latest_result ? 'COMPLETED' : 'WAITING'; $('#orchestrator-state').textContent = active; $('#equipment-state').textContent = active; $('#production-state').textContent = active;
}
async function refresh() { try { const data = await api('/api/dashboard'); render(data); $('#api-status').textContent = 'API CONNECTED'; $('#api-status').className = 'status-chip green'; } catch (error) { $('#api-status').textContent = 'API UNAVAILABLE'; $('#api-status').className = 'status-chip red'; } }
async function command(path) { try { await api(path, { method: 'POST' }); await refresh(); } catch (error) { $('#api-status').textContent = 'COMMAND FAILED'; $('#api-status').className = 'status-chip red'; } }
$('#start-btn').addEventListener('click', () => command('/api/scenario/line-2-failure')); $('#reset-btn').addEventListener('click', () => command('/api/scenario/reset')); document.querySelectorAll('[data-update]').forEach((button) => button.addEventListener('click', () => command(`/api/scenario/${button.dataset.update}`)));
refresh(); setInterval(refresh, 3000);
