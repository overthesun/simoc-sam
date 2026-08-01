/* SIMOC Live -- lightweight frontend logic (no frameworks) */

'use strict';

const POLL_INTERVAL = 5000;  // live dashboard refresh (ms)
const PLOT_LIMIT = 500;      // max points per sensor in plot/table mode

const CHART_COLORS = ['#e28a2b', '#4488ff', '#3fae6a', '#ff5566',
                      '#b06cd9', '#3fc4c4', '#e2d02b', '#ff9955'];

// state
const state = {
  sensors: {},              // /api/sensors response (metadata)
  selection: {},            // {sensor: Set(metrics)}
  viewMode: 'plot',
  lastResult: null,         // last /api/query response
};

let charts = [];            // Chart.js instances (destroyed on re-render)

/* ---------- preference persistence ---------- */

const PREFS_KEY = 'simoc_prefs';
let _restoringPrefs = false;  // suppress saves while replaying saved state on load

function savePrefs() {
  if (_restoringPrefs) return;
  const activeRange = document.querySelector('.quick-range [data-range].on');
  const prefs = {
    selection: Object.fromEntries(
      Object.entries(state.selection).map(([s, m]) => [s, [...m]])
    ),
    viewMode: state.viewMode,
    quickRange: activeRange ? activeRange.dataset.range : null,
  };
  localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}

function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem(PREFS_KEY)) || {};
  } catch {
    return {};
  }
}
let pollTimer = null;
let datePicker = null;
let timeStartPicker = null;
let timeEndPicker = null;
let selectionUIReady = null;
let activeSensors = new Set();   // sensors known to have data (grow-only)
let discoveryLastRun = 0;
const DISCOVERY_TTL = 5 * 60 * 1000;  // re-check for new sensors every 5 minutes

const $ = (sel) => document.querySelector(sel);

function showModal(message) {
  $('#modal-message').textContent = message;
  $('#modal').showModal();
}

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function formatLocal(tsMs) {
  const d = new Date(tsMs);
  return `${d.toLocaleDateString('en-CA')} ${d.toLocaleTimeString('en-GB')}`;
}

function formatTimeNow() {
  return new Date().toLocaleTimeString('en-GB');
}


/* ---------- navigation ---------- */

async function showSection(name) {
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.section === name);
  });
  $('#section-live').hidden = name !== 'live';
  $('#section-history').hidden = name !== 'history';
  if (name === 'live') {
    startPolling();
  } else {
    stopPolling();
    if (!state.lastResult) {
      await selectionUIReady;  // ensure UI is ready before querying
      if (Object.keys(getSelection()).length) runQuery();
    }
  }
}

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => showSection(btn.dataset.section));
});


/* ---------- live dashboard ---------- */

function startPolling() {
  if (pollTimer !== null) return;
  refreshLive();
  pollTimer = setInterval(refreshLive, POLL_INTERVAL);
}

function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}

async function refreshLive() {
  if (!Object.keys(state.sensors).length) {
    await selectionUIReady;  // ensure sensor metadata is ready before first render
  }
  // Full discovery every 5 minutes to detect newly active sensors.
  const isDiscovery = Date.now() - discoveryLastRun > DISCOVERY_TTL;
  if (isDiscovery) discoveryLastRun = Date.now();
  const url = (isDiscovery || !activeSensors.size)
    ? '/api/latest'
    : `/api/latest?sensors=${[...activeSensors].join(',')}`;
  $('#live-status').textContent = 'Loading\u2026';
  let latest;
  try {
    latest = await fetchJSON(url);
  } catch (err) {
    $('#live-status').textContent = `Error: ${err.message}`;
    return;
  }
  for (const sensor of Object.keys(latest.sensors)) activeSensors.add(sensor);
  $('#live-status').textContent = `Last update: ${formatTimeNow()}`;
  renderLiveCards(state.sensors, latest.sensors);
}

function renderLiveCards(sensors, latest) {
  const container = $('#live-cards');
  container.replaceChildren();
  for (const [sensor, info] of Object.entries(sensors)) {
    if (!activeSensors.has(sensor)) continue;  // skip sensors that never had data
    const reading = latest[sensor];
    const isActive = reading?.active ?? false;
    const card = document.createElement('div');
    card.className = isActive ? 'card active' : 'card';
    const rows = Object.entries(info.metrics).map(([metric, meta]) => {
      const value = reading?.[metric];
      const display = (value === null || value === undefined) ? '--'
        : (typeof value === 'number' ? value.toFixed(1) : value);
      const unit = meta.unit ? ` ${meta.unit}` : '';
      return `<tr><td>${meta.label}</td>
              <td class="value">${display}${unit}</td></tr>`;
    }).join('');
    const ts = reading ? formatLocal(Date.parse(reading.timestamp)) : 'no data';
    card.innerHTML = `
      <h2><span class="dot"></span>${info.name}</h2>
      <table>${rows}</table>
      <div class="ts">${ts}</div>`;
    container.appendChild(card);
  }
  if (!container.children.length) {
    container.innerHTML = '<p>No sensor data available.</p>';
  }
}


/* ---------- sensor + metric selection ---------- */

async function buildSelectionUI() {
  const [sensorsData, latestData] = await Promise.all([
    fetchJSON('/api/sensors'),
    fetchJSON('/api/latest'),   // discover which sensors have data
  ]);
  state.sensors = sensorsData.sensors;
  for (const sensor of Object.keys(latestData.sensors)) activeSensors.add(sensor);
  discoveryLastRun = Date.now();
  const fieldset = $('#sensor-selection');
  const sensorControls = {};  // sensor -> {sensorBtn, metricBtns: {metric -> btn}}
  for (const [sensor, info] of Object.entries(sensorsData.sensors)) {
    if (!activeSensors.has(sensor)) continue;  // skip sensors with no DB rows
    const reading = latestData.sensors[sensor];
    const isActive = reading?.active ?? false;
    const row = document.createElement('div');
    row.className = isActive ? 'sensor-row' : 'sensor-row stale';
    const sensorBtn = document.createElement('button');
    sensorBtn.type = 'button';
    sensorBtn.className = 'toggle sensor';
    sensorBtn.textContent = info.name;
    row.appendChild(sensorBtn);
    const metricBtns = [];
    const metricBtnMap = {};
    for (const [metric, meta] of Object.entries(info.metrics)) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'toggle';
      btn.textContent = meta.label;
      btn.disabled = true;
      btn.addEventListener('click', () => {
        btn.classList.toggle('on');
        const set = state.selection[sensor];
        if (btn.classList.contains('on')) set.add(metric); else set.delete(metric);
        savePrefs();
      });
      metricBtns.push([metric, btn]);
      metricBtnMap[metric] = btn;
      row.appendChild(btn);
    }
    sensorBtn.addEventListener('click', () => {
      const on = sensorBtn.classList.toggle('on');
      if (on) {
        state.selection[sensor] = new Set();
        metricBtns.forEach(([metric, btn]) => {
          btn.disabled = false;
          btn.classList.add('on');
          state.selection[sensor].add(metric);
        });
      } else {
        delete state.selection[sensor];
        metricBtns.forEach(([, btn]) => {
          btn.disabled = true;
          btn.classList.remove('on');
        });
      }
      savePrefs();
    });
    fieldset.appendChild(row);
    sensorControls[sensor] = {sensorBtn, metricBtns: metricBtnMap};
  }
  // restore saved selection, or auto-select all active (non-stale) sensors
  const prefs = loadPrefs();
  if (prefs.selection && Object.keys(prefs.selection).length) {
    for (const [sensor, savedMetrics] of Object.entries(prefs.selection)) {
      const ctrl = sensorControls[sensor];
      if (!ctrl) continue;  // sensor no longer available
      ctrl.sensorBtn.click();  // turn on sensor, enabling all its metrics
      const savedSet = new Set(savedMetrics);
      for (const [metric, btn] of Object.entries(ctrl.metricBtns)) {
        if (!savedSet.has(metric)) btn.click();  // turn off unsaved metrics
      }
    }
  } else {
    document.querySelectorAll('.sensor-row:not(.stale) .toggle.sensor').forEach((btn) => btn.click());
  }
}

function getSelection() {
  const selection = {};
  for (const [sensor, metrics] of Object.entries(state.selection)) {
    if (metrics.size) selection[sensor] = [...metrics];
  }
  return selection;
}


/* ---------- time range ---------- */

function clearQuickRangeHighlight() {
  document.querySelectorAll('.quick-range [data-range]').forEach((b) => b.classList.remove('on'));
  savePrefs();
}

function initTimePickers() {
  datePicker = flatpickr('#date-range', {mode: 'range', dateFormat: 'Y-m-d',
    onChange: clearQuickRangeHighlight});
  const timeOpts = {enableTime: true, noCalendar: true, time_24hr: true, dateFormat: 'H:i',
    onChange: clearQuickRangeHighlight};
  timeStartPicker = flatpickr('#time-start', timeOpts);
  timeEndPicker   = flatpickr('#time-end',   timeOpts);
}

function applyQuickRange(range) {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  timeStartPicker.clear();
  timeEndPicker.clear();
  if (range === 'all') {
    datePicker.clear();
  } else if (range === 'hour') {
    const start = new Date(now - 3600 * 1000);
    datePicker.setDate([start, now]);
    timeStartPicker.setDate(`${pad(start.getHours())}:${pad(start.getMinutes())}`);
    timeEndPicker.setDate(`${pad(now.getHours())}:${pad(now.getMinutes())}`);
  } else if (range === 'day') {
    const today = new Date(now); today.setHours(0, 0, 0, 0);
    datePicker.setDate([today, now]);
  } else if (range === 'week') {
    const weekAgo = new Date(now - 7 * 86400 * 1000);
    weekAgo.setHours(0, 0, 0, 0);
    datePicker.setDate([weekAgo, now]);
  } else if (range === 'month') {
    const monthAgo = new Date(now - 30 * 86400 * 1000);
    monthAgo.setHours(0, 0, 0, 0);
    datePicker.setDate([monthAgo, now]);
  }
  // highlight the active button
  document.querySelectorAll('.quick-range [data-range]').forEach((b) => {
    b.classList.toggle('on', b.dataset.range === range);
  });
  savePrefs();
}

function getTimeRange() {
  const startTime = $('#time-start').value;
  const endTime   = $('#time-end').value;
  let dates = datePicker ? datePicker.selectedDates : [];
  if (!dates.length) {
    if (!startTime && !endTime) return {start: null, end: null};
    // time entered without a date: default to today
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    dates = [today];
  }
  const startDate = dates[0];
  const endDate   = dates[1] || dates[0];
  const combine = (date, timeStr) => {
    const d = new Date(date);
    const [h, m] = (timeStr || '00:00').split(':').map(Number);
    d.setHours(h, m, 0, 0);
    return d.toISOString().replace(/\.\d{3}Z$/, '+00:00');
  };
  const start = combine(startDate, startTime);
  let end;
  if (endTime) {
    end = combine(endDate, endTime);
  } else {
    // no end time: advance to next-day midnight so the whole last day is included
    const next = new Date(endDate);
    next.setDate(next.getDate() + 1);
    next.setHours(0, 0, 0, 0);
    end = next.toISOString().replace(/\.\d{3}Z$/, '+00:00');
  }
  return {start, end};
}


/* ---------- query + rendering ---------- */

async function runQuery() {
  const selection = getSelection();
  if (!Object.keys(selection).length) {
    showModal('Select at least one sensor and metric first.');
    return;
  }
  const {start, end} = getTimeRange();
  const body = {selection, limit: PLOT_LIMIT};
  if (start) body.start = start;
  if (end) body.end = end;
  $('#history-status').textContent = 'Loading\u2026';
  let data;
  try {
    data = await fetchJSON('/api/query', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
  } catch (err) {
    $('#history-status').textContent = `Error: ${err.message}`;
    return;
  }
  state.lastResult = data;
  $('#history-status').textContent = `${data.count} datapoints`;
  renderResults();
}

function renderResults() {
  const container = $('#history-results');
  charts.forEach((c) => c.destroy());
  charts = [];
  container.replaceChildren();
  $('#view-mode-switch').hidden = true;
  if (!state.lastResult) return;
  const selection = getSelection();

  // shared x-axis bounds: use the selected time range when set, otherwise
  // span all data so every chart has the same x scale
  const {start, end} = getTimeRange();
  let xMin = start ? new Date(start).getTime() : undefined;
  let xMax = end   ? new Date(end).getTime()   : undefined;
  if (xMin === undefined || xMax === undefined) {
    const all = Object.values(state.lastResult).flatMap(d => d.timestamps || []);
    if (all.length) {
      if (xMin === undefined) xMin = Math.min(...all);
      if (xMax === undefined) xMax = Math.max(...all);
    }
  }

  for (const [sensor, metrics] of Object.entries(selection)) {
    const data = state.lastResult[sensor];
    if (!data) continue;
    // only render metrics that were actually fetched
    const available = metrics.filter(m => Array.isArray(data[m]));
    if (!available.length) continue;
    if (state.viewMode === 'plot') {
      for (const metric of available) {
        container.appendChild(makeChartBox(sensor, metric, data, xMin, xMax));
      }
    } else {
      container.appendChild(makeTableBox(sensor, available, data));
    }
  }
  $('#view-mode-switch').hidden = container.children.length === 0;
}

// Map timestamps/values to Chart.js {x,y} points, inserting a null sentinel
// between consecutive points whose interval exceeds `factor` × the median.
// Chart.js breaks the line on null values (spanGaps defaults to false).
function prepareData(timestamps, values, factor = 5) {
  const pts = timestamps.map((ts, i) => ({x: ts, y: values[i]}));
  if (pts.length < 2) return pts;
  const intervals = pts.slice(1).map((p, i) => p.x - pts[i].x);
  const median = [...intervals].sort((a, b) => a - b)[Math.floor(intervals.length / 2)];
  const threshold = median * factor;
  const result = [];
  for (let i = 0; i < pts.length; i++) {
    if (i > 0 && intervals[i - 1] > threshold)
      result.push({x: (pts[i - 1].x + pts[i].x) / 2, y: null});
    result.push(pts[i]);
  }
  return result;
}

function makeChartBox(sensor, metric, data, xMin, xMax) {
  const info = state.sensors[sensor];
  const meta = info.metrics[metric];
  const label = meta.unit ? `${meta.label} (${meta.unit})` : meta.label;
  const box = document.createElement('div');
  box.className = 'chart-box';
  box.innerHTML = `<h3>${info.name} — ${label}</h3><div class="chart-wrap"><canvas></canvas></div>`;
  const dataset = {
    label,
    data: prepareData(data.timestamps, data[metric]),
    borderColor: CHART_COLORS[0],
    backgroundColor: CHART_COLORS[0],
    pointRadius: 0,
    borderWidth: 1.5,
  };
  const chart = new Chart(box.querySelector('canvas'), {
    type: 'line',
    data: {datasets: [dataset]},
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'time',
          ...(xMin !== undefined && {min: xMin}),
          ...(xMax !== undefined && {max: xMax}),
          time: {
            displayFormats: {
              millisecond: 'HH:mm:ss.SSS',
              second:      'HH:mm:ss',
              minute:      'HH:mm',
              hour:        'HH:mm',
              day:         'yyyy-MM-dd',
              week:        'yyyy-MM-dd',
              month:       'yyyy-MM',
              year:        'yyyy',
            },
          },
          ticks: {
            color: '#8899aa',
            maxTicksLimit: 10,
            major: {enabled: true},
            font: (ctx) => ctx.tick?.major ? {weight: 'bold'} : {},
          },
          grid: {color: '#2e3946'},
        },
        y: {ticks: {color: '#8899aa'}, grid: {color: '#2e3946'}},
      },
      plugins: {legend: {display: false}},
    },
  });
  charts.push(chart);
  return box;
}

function makeTableBox(sensor, metrics, data) {
  const info = state.sensors[sensor];
  const box = document.createElement('div');
  box.className = 'table-box';
  const headers = metrics.map((m) => {
    const {label, unit} = info.metrics[m];
    const text = unit ? `${label} (${unit})` : label;
    return `<th>${text}</th>`;
  }).join('');
  const rows = data.timestamps.map((ts, i) => {
    const cells = metrics.map((m) => `<td>${data[m][i] ?? ''}</td>`).join('');
    return `<tr><td>${formatLocal(ts)}</td>${cells}</tr>`;
  }).join('');
  box.innerHTML = `<h3>${info.name}</h3>
    <div class="table-scroll"><table><thead><tr><th>Timestamp</th>${headers}</tr></thead>
    <tbody>${rows}</tbody></table></div>`;
  return box;
}


/* ---------- export ---------- */

function downloadBlob(content, filename, mimetype) {
  const blob = new Blob([content], {type: mimetype});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function exportVisible() {
  // export the currently displayed (decimated) data, client-side
  if (!state.lastResult) {
    showModal('Run a query first.');
    return;
  }
  const format = $('#export-format').value;
  const selection = getSelection();
  if (format === 'json') {
    const {count, ...data} = state.lastResult;
    downloadBlob(JSON.stringify(data, null, 1),
                 'sensor_data.json', 'application/json');
    return;
  }
  const allMetrics = [...new Set(Object.values(selection).flat())].sort();
  const lines = [['sensor', 'timestamp', ...allMetrics].join(',')];
  for (const [sensor, metrics] of Object.entries(selection)) {
    const data = state.lastResult[sensor];
    if (!data) continue;
    data.timestamps.forEach((ts, i) => {
      const values = allMetrics.map(
        (m) => metrics.includes(m) ? (data[m][i] ?? '') : '');
      lines.push([sensor, new Date(ts).toISOString(), ...values].join(','));
    });
  }
  downloadBlob(lines.join('\n'), 'sensor_data.csv', 'text/csv');
}

async function exportFull() {
  // export all rows in the time range, from the server (no decimation)
  const selection = getSelection();
  if (!Object.keys(selection).length) {
    showModal('Select at least one sensor and metric first.');
    return;
  }
  const format = $('#export-format').value;
  const {start, end} = getTimeRange();
  const body = {selection, format};
  if (start) body.start = start;
  if (end) body.end = end;
  const response = await fetch('/api/export', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json();
    showModal(`Export failed: ${data.error || response.statusText}`);
    return;
  }
  downloadBlob(await response.blob(), `sensor_data.${format}`,
               response.headers.get('Content-Type'));
}


/* ---------- init ---------- */

$('#view-mode-toggle').addEventListener('change', (e) => {
  state.viewMode = e.target.checked ? 'table' : 'plot';
  renderResults();
  savePrefs();
});

$('#btn-query').addEventListener('click', runQuery);
$('#btn-export-visible').addEventListener('click', exportVisible);
$('#btn-export-full').addEventListener('click', exportFull);

document.querySelectorAll('.quick-range [data-range]').forEach((btn) => {
  btn.addEventListener('click', () => applyQuickRange(btn.dataset.range));
});

initTimePickers();
// restore view mode and quick range; suppress saves until selection is also restored
_restoringPrefs = true;
const {viewMode: _savedViewMode, quickRange: _savedQuickRange} = loadPrefs();
if (_savedViewMode) {
  state.viewMode = _savedViewMode;
  $('#view-mode-toggle').checked = _savedViewMode === 'table';
}
if (_savedQuickRange) applyQuickRange(_savedQuickRange);
_restoringPrefs = false;
selectionUIReady = buildSelectionUI()
  .catch((err) => {
    $('#history-status').textContent = `Error loading sensors: ${err.message}`;
  });
startPolling();
