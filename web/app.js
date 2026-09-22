const $ = (selector) => document.querySelector(selector);
const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
};
const esc = (value) => String(value ?? '--').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));

function lineClass(line) { return line.status === 'DOWN' ? 'down' : line.status === 'QUALITY_HOLD' ? 'hold' : 'running'; }
function lineLabel(status) { return status === 'QUALITY_HOLD' ? 'QUALITY HOLD' : status; }
function renderHero(data) {
  const lines = Object.values(data.lines || {});
  const down = lines.filter((line) => line.status === 'DOWN');
  const degraded = lines.filter((line) => line.status === 'DEGRADED' || line.status === 'QUALITY_HOLD');
  const safetyBlocked = data.factory.safety.status !== 'CLEAR';
  let signal = 'green'; let headline = 'NORMAL OPERATIONS'; let subtitle = `Simulation tick ${data.simulation?.tick ?? 0} · all lines nominal`;
  if (safetyBlocked || down.length) {
    signal = 'red';
    headline = 'ATTENTION REQUIRED';
    subtitle = down.length ? `${down.map((line) => line.name).join(', ')} down` : `Safety status: ${data.factory.safety.status}`;
  } else if (degraded.length) {
    signal = 'amber';
    headline = 'DEGRADED CONDITIONS';
    subtitle = `${degraded.map((line) => line.name).join(', ')} affected`;
  }
  $('#hero-signal').className = `signal ${signal}`;
  $('#factory-status').textContent = headline;
  $('#hero-subtitle').textContent = subtitle;
}
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
function renderInventoryReport(data) {
  const report = data.latest_result?.inventory_report;
  if (!report) {
    $('#inventory-report-state').textContent = 'NOT RUN';
    $('#inventory-report-state').className = 'status-chip neutral';
    $('#inventory-report').innerHTML = '<p class="muted">Run a scenario or advance the simulation to view material constraints, available goods, and quality findings.</p>';
    return;
  }
  const productC = report.finished_goods?.C || {};
  const productCLimit = report.supported_production?.C || {};
  const productCQuality = report.quality?.C || {};
  const limitingMaterial = productCLimit.limiting_material || 'UNKNOWN';
  $('#inventory-report-state').textContent = 'ANALYSIS COMPLETE';
  $('#inventory-report-state').className = 'status-chip green';
  $('#inventory-report').innerHTML = `<div class="inventory-metrics"><div class="inventory-metric"><span>PRODUCT C AVAILABLE</span><strong>${esc(productC.available)} units</strong><small>${esc(productC.reserved)} reserved · ${esc(productC.quality_hold)} quality hold</small></div><div class="inventory-metric"><span>MATERIAL-SUPPORTED C</span><strong>${esc(productCLimit.maximum_supported_quantity)} units</strong><small>Limiting material: ${esc(limitingMaterial)}</small></div><div class="inventory-metric"><span>PRODUCT C QUALITY</span><strong>${esc(productCQuality.defect_rate_percent)}% defects</strong><small class="${productCQuality.status === 'WARNING' ? 'warning-text' : ''}">${esc(productCQuality.status)}</small></div></div><div class="inventory-materials">${Object.values(report.materials || {}).map((material) => `<div class="material-row"><span>${esc(material.name)}</span><strong>${esc(material.available_quantity)} ${esc(material.unit)}</strong><em class="${String(material.status).toLowerCase()}">${esc(material.status)}</em></div>`).join('')}</div>`;
}
function renderEvents(data) { $('#event-feed').innerHTML = data.events?.length ? data.events.map((event) => `<div class="event"><time>${new Date(event.timestamp).toLocaleTimeString()}</time><div><strong>${esc(event.actor)} · ${esc(event.event_type)}</strong><p>${esc(event.summary)}</p></div></div>`).join('') : '<p class="muted">No events recorded.</p>'; }
function renderImpact(data) { const labels = ['EQUIPMENT FAILURE', 'CAPACITY REDUCTION', 'PRODUCTION LOSS', 'INVENTORY CHANGE', 'ORDER RISK', 'CUSTOMER IMPACT', 'REVENUE RISK']; $('#impact-chain').innerHTML = labels.map((label, index) => `<div class="impact-step ${index === 0 ? 'active' : index > 0 && index < 5 ? 'warning' : ''}">${label}</div>`).join(''); }
function renderSignals(data) { $('#signals').innerHTML = [['API STATUS', 'CONNECTED'], ['SHARED STATE', `VERSION ${data.version}`], ['SIMULATION TICK', `${data.simulation?.tick ?? 0}`], ['SIMULATION TIME', data.simulation?.simulation_time ? new Date(data.simulation.simulation_time).toLocaleString() : '--'], ['SAFETY', data.factory.safety.status], ['EVENT JOURNAL', `${data.events?.length || 0} EVENTS`], ['SCENARIO', data.latest_result ? 'ASSESSMENT COMPLETE' : 'READY']].map(([name, value]) => `<div class="signal-row"><span>${name}</span><strong>${esc(value)}</strong></div>`).join(''); }
function renderMetrics(data) {
  const metrics = data.metrics || {};
  const cards = [
    ['DOWNTIME', `${metrics.downtime_minutes ?? 0} MIN`],
    ['PRODUCTION LOSS', `${metrics.production_loss_units ?? 0} UNITS`],
    ['DEFECTS LOGGED', `${metrics.defect_count_total ?? 0}`],
    ['MATERIAL SHORTAGES', `${(metrics.material_shortages || []).length}`],
    ['WEIGHT ANOMALIES', `${(metrics.weight_anomaly_products || []).length}`],
    ['PENDING APPROVALS', `${metrics.pending_human_approvals ?? 0}`],
  ];
  $('#metrics-grid').innerHTML = cards.map(([title, value]) => `<div class="snapshot-card"><strong>${title}</strong><p>${esc(value)}</p></div>`).join('');
}
function render(data) {
  $('#factory-name').textContent = data.factory.name; $('#severity').textContent = data.factory.severity; $('#updated-at').textContent = new Date(data.updated_at).toLocaleTimeString(); $('#state-version').textContent = `VERSION ${data.version}`; $('#footer-version').textContent = `STATE VERSION ${data.version}`;
  renderHero(data); renderLines(data); renderDecision(data); renderSnapshot(data); renderInventoryReport(data); renderEvents(data); renderImpact(data); renderSignals(data); renderMetrics(data);
  const agentStates = { orchestrator: 'WAITING', equipment: 'IDLE', production: 'IDLE', inventory: 'IDLE' };
  for (const event of data.events || []) {
    const actor = String(event.actor || '').toLowerCase();
    const state = event.metadata?.status || (event.event_type === 'workflow_completed' ? 'COMPLETED' : null);
    if (state && actor.includes('orchestrator')) agentStates.orchestrator = state;
    if (state && actor.includes('equipment')) agentStates.equipment = state;
    if (state && actor.includes('production')) agentStates.production = state;
    if (state && actor.includes('inventory')) agentStates.inventory = state;
  }
  $('#orchestrator-state').textContent = agentStates.orchestrator; $('#equipment-state').textContent = agentStates.equipment; $('#production-state').textContent = agentStates.production; $('#inventory-state').textContent = agentStates.inventory;
}
async function refresh() { try { const data = await api('/api/dashboard'); render(data); $('#api-status').textContent = 'API CONNECTED'; $('#api-status').className = 'status-chip green'; } catch (error) { $('#api-status').textContent = 'API UNAVAILABLE'; $('#api-status').className = 'status-chip red'; $('#inventory-report-state').textContent = 'API UNAVAILABLE'; $('#inventory-report-state').className = 'status-chip red'; $('#inventory-report').innerHTML = '<p class="muted">The shared-state API is unavailable. Start the local server to view Inventory Agent findings.</p>'; } }
async function command(path) { try { await api(path, { method: 'POST' }); await refresh(); } catch (error) { $('#api-status').textContent = 'COMMAND FAILED'; $('#api-status').className = 'status-chip red'; } }
$('#start-btn').addEventListener('click', () => command('/api/scenario/line-2-failure')); $('#reset-btn').addEventListener('click', () => command('/api/scenario/reset')); $('#advance-btn').addEventListener('click', () => command('/api/simulation/tick')); document.querySelectorAll('[data-update]').forEach((button) => button.addEventListener('click', () => command(`/api/scenario/${button.dataset.update}`)));
refresh(); setInterval(refresh, 3000);
