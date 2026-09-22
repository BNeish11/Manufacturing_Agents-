const $ = (selector) => document.querySelector(selector);
const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
};
const esc = (value) => String(value ?? '--').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
let previousAgentStatus = {};
const AGENT_STATUS_ICON = { IDLE: '●', WORKING: '◉', COMPLETED: '✓', WAITING: '◷', ERROR: '✕', NEEDS_HUMAN_APPROVAL: '▲' };
const AGENT_STATUS_CLASS = { IDLE: 'idle', WORKING: 'working', COMPLETED: 'completed', WAITING: 'waiting', ERROR: 'error', NEEDS_HUMAN_APPROVAL: 'needs-approval' };
function renderAgentStatus(data) {
  const status = data.agent_status || {};
  for (const key of ['orchestrator', 'equipment', 'production', 'inventory']) {
    const value = status[key] || 'IDLE';
    const label = document.getElementById(`${key}-state`);
    if (!label) continue;
    label.textContent = `${AGENT_STATUS_ICON[value] || '●'} ${value.replace(/_/g, ' ')}`;
    const node = label.closest('.agent-node');
    if (node) {
      node.className = node.className.replace(/\bstatus-\S+/g, '').replace(/\bjust-updated\b/g, '').trim();
      node.classList.add(`status-${AGENT_STATUS_CLASS[value] || 'idle'}`);
      if (previousAgentStatus[key] && previousAgentStatus[key] !== value) {
        node.classList.add('just-updated');
        setTimeout(() => node.classList.remove('just-updated'), 1200);
      }
    }
    previousAgentStatus[key] = value;
  }
}

function lineClass(line) { return line.status === 'DOWN' ? 'down' : line.status === 'QUALITY_HOLD' ? 'hold' : 'running'; }
function lineLabel(status) { return status === 'QUALITY_HOLD' ? 'QUALITY HOLD' : status; }
function renderHero(data) {
  const lines = Object.values(data.lines || {});
  const down = lines.filter((line) => line.status === 'DOWN');
  const degraded = lines.filter((line) => line.status === 'DEGRADED' || line.status === 'QUALITY_HOLD');
  const safetyBlocked = data.factory.safety.status !== 'CLEAR';
  let signal = 'green'; let headline = 'NORMAL OPERATIONS'; let subtitle = `Simulation tick ${data.simulation?.tick ?? 0} · all lines nominal`;
  if (data.simulation?.status === 'WAITING_FOR_HUMAN') {
    signal = 'amber';
    headline = 'AWAITING HUMAN DECISION';
    subtitle = 'A recommendation requires your approval, rejection, or hold.';
  } else if (safetyBlocked || down.length) {
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
  const actions = $('#approval-actions');
  if (!decision) {
    $('#decision-content').innerHTML = '<p class="muted">No workflow has been run.</p>';
    $('#approval-title').textContent = 'NO DECISION PENDING';
    $('#approval-reason').textContent = 'Advance the simulation or inject a scenario to generate an approval packet.';
    $('#approval-badge').textContent = 'NO DECISION'; $('#approval-badge').className = 'status-chip neutral';
    actions.dataset.decisionId = '';
    actions.querySelectorAll('button').forEach((btn) => { btn.disabled = true; });
    return;
  }
  $('#decision-content').innerHTML = `<div class="decision-title">${esc(decision.recommendation)}</div><p class="decision-copy">${esc(decision.reasoning_summary)}</p><div class="evidence">${(decision.evidence || []).slice(0, 5).map((item) => `<span>${esc(item)}</span>`).join('')}</div>`;
  const isPending = decision.approval_status === 'PENDING';
  actions.dataset.decisionId = isPending ? decision.decision_id : '';
  actions.querySelectorAll('button').forEach((btn) => { btn.disabled = !isPending; });
  const badges = { PENDING: ['AWAITING APPROVAL', 'amber'], APPROVED: ['APPROVED', 'green'], REJECTED: ['REJECTED', 'red'], ON_HOLD: ['ON HOLD', 'amber'], NOT_REQUIRED: ['NO APPROVAL REQUIRED', 'neutral'] };
  const [badgeText, badgeClass] = badges[decision.approval_status] || [decision.approval_status, 'neutral'];
  $('#approval-badge').textContent = badgeText; $('#approval-badge').className = `status-chip ${badgeClass}`;
  if (isPending) {
    $('#approval-title').textContent = 'HUMAN APPROVAL REQUIRED';
    $('#approval-reason').textContent = decision.reasoning_summary || 'Review the recommendation and record your decision.';
  } else {
    $('#approval-title').textContent = badgeText;
    $('#approval-reason').textContent = decision.outcome || 'This decision has been resolved.';
  }
}
function renderSnapshot(data) {
  const line2 = data.lines['line-2']; const equipment = data.equipment['equipment-2'];
  const cards = [['EQUIPMENT', `${line2.status} · ${equipment.downtime_minutes} MIN DOWNTIME`], ['PRODUCTION', `${equipment.lost_units} LOST · ${equipment.projected_lost_units} PROJECTED`], ['INVENTORY', `${data.inventory.days_of_inventory} DAYS · ${data.inventory.raw_material_units} RAW UNITS`], ['LABOR', `${data.labor.affected} AFFECTED · ${data.labor.reassigned} REASSIGNED`], ['ORDERS', Object.values(data.orders).map((order) => `P${order.product_id} ${order.priority}`).join(' / ')], ['RISK', `SEVERITY ${data.factory.severity} · ${data.factory.safety.status}`]];
  $('#snapshot-grid').innerHTML = cards.map(([title, value]) => `<div class="snapshot-card"><strong>${title}</strong><p>${esc(value)}</p></div>`).join('');
}
function renderInventoryReport(data) {
  const report = data.inventory_report;
  if (!report) {
    $('#inventory-report-state').textContent = 'NOT AVAILABLE';
    $('#inventory-report-state').className = 'status-chip neutral';
    $('#inventory-report').innerHTML = '<p class="muted">Inventory Agent data is currently unavailable.</p>';
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
function statusClass(status) { return status === 'CRITICAL' ? 'red' : status === 'WARNING' ? 'amber' : status === 'NORMAL' ? 'green' : 'neutral'; }
function renderImpact(data) {
  const cards = data.consequence_cards || [];
  $('#impact-chain').innerHTML = cards.map((card, index) => `<div class="consequence-card ${statusClass(card.status).toLowerCase()}" data-index="${index}"><div class="consequence-top"><strong>${esc(card.subject)}</strong><span class="status-chip ${statusClass(card.status)}">${esc(card.status)}</span></div><p class="consequence-reason">${esc(card.reason)}</p><div class="consequence-details" hidden><span>METRIC · ${esc(card.metric)}</span>${card.cause ? `<span>CAUSE · ${esc(card.cause)}</span>` : ''}${card.affected && card.affected.length ? `<span>AFFECTED · ${card.affected.map(esc).join(', ')}</span>` : ''}<span>ACTION · ${esc(card.action)}</span>${card.updated_at ? `<span>UPDATED · ${new Date(card.updated_at).toLocaleTimeString()}</span>` : ''}</div></div>`).join('');
  document.querySelectorAll('.consequence-card').forEach((card) => card.addEventListener('click', () => {
    const details = card.querySelector('.consequence-details');
    details.hidden = !details.hidden;
    card.classList.toggle('expanded', !details.hidden);
  }));
}
function renderSignals(data) { $('#signals').innerHTML = [['API STATUS', 'CONNECTED'], ['SHARED STATE', `VERSION ${data.version}`], ['SIMULATION STATUS', data.simulation?.status ?? 'IDLE'], ['SIMULATION TICK', `${data.simulation?.tick ?? 0}`], ['SIMULATION TIME', data.simulation?.simulation_time ? new Date(data.simulation.simulation_time).toLocaleString() : '--'], ['SAFETY', data.factory.safety.status], ['EVENT JOURNAL', `${data.events?.length || 0} EVENTS`], ['SCENARIO', data.latest_result ? 'ASSESSMENT COMPLETE' : 'READY']].map(([name, value]) => `<div class="signal-row"><span>${name}</span><strong>${esc(value)}</strong></div>`).join(''); }
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
  renderHero(data); renderLines(data); renderDecision(data); renderSnapshot(data); renderInventoryReport(data); renderEvents(data); renderImpact(data); renderSignals(data); renderMetrics(data); renderAgentStatus(data);
}
async function refresh() { try { const data = await api('/api/dashboard'); render(data); $('#api-status').textContent = 'API CONNECTED'; $('#api-status').className = 'status-chip green'; } catch (error) { $('#api-status').textContent = 'API UNAVAILABLE'; $('#api-status').className = 'status-chip red'; $('#inventory-report-state').textContent = 'API UNAVAILABLE'; $('#inventory-report-state').className = 'status-chip red'; $('#inventory-report').innerHTML = '<p class="muted">The shared-state API is unavailable. Start the local server to view Inventory Agent findings.</p>'; } }
async function command(path) {
  const isReset = path.includes('/scenario/reset');
  if (isReset) { $('#api-status').textContent = 'RESETTING…'; $('#api-status').className = 'status-chip amber'; }
  try { await api(path, { method: 'POST' }); await refresh(); } catch (error) { $('#api-status').textContent = 'COMMAND FAILED'; $('#api-status').className = 'status-chip red'; }
}
async function submitDecision(decisionId, action) {
  try {
    await api(`/api/decisions/${decisionId}/decision`, { method: 'POST', body: JSON.stringify({ action }) });
    await refresh();
  } catch (error) {
    $('#api-status').textContent = 'DECISION FAILED'; $('#api-status').className = 'status-chip red';
  }
}
$('#approval-actions').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  const decisionId = $('#approval-actions').dataset.decisionId;
  if (!button || button.disabled || !decisionId) return;
  submitDecision(decisionId, button.dataset.action);
});
$('#start-btn').addEventListener('click', () => command('/api/scenario/line-2-failure')); $('#reset-btn').addEventListener('click', () => command('/api/scenario/reset')); $('#advance-btn').addEventListener('click', () => command('/api/simulation/tick')); document.querySelectorAll('[data-update]').forEach((button) => button.addEventListener('click', () => command(`/api/scenario/${button.dataset.update}`)));
refresh(); setInterval(refresh, 3000);
