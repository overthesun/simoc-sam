/* SIMOC Live -- lightweight frontend logic (no frameworks) */

'use strict';

const POLL_INTERVAL = 5000;  // live dashboard refresh (ms)
const PLOT_LIMIT = 1000;     // max points per sensor in plot/table mode

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
let pollTimer = null;
let datePicker = null;

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

function showSection(name) {
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.section === name);
  });
  $('#section-live').hidden = name !== 'live';
  $('#section-history').hidden = name !== 'history';
  if (name === 'live') startPolling(); else stopPolling();
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
  let sensors, latest;
  try {
    [sensors, latest] = await Promise.all([
      fetchJSON('/api/sensors'),
      fetchJSON('/api/latest'),
    ]);
  } catch (err) {
    $('#live-status').textContent = `Error fetching data: ${err.message}`;
    return;
  }
  state.sensors = sensors.sensors;
  $('#live-status').textContent = `Last update: ${formatTimeNow()}`;
  renderLiveCards(sensors.sensors, latest.sensors);
}

function renderLiveCards(sensors, latest) {
  const container = $('#live-cards');
  container.replaceChildren();
  for (const [sensor, info] of Object.entries(sensors)) {
    const reading = latest[sensor];
    if (!reading && !info.active) continue;  // skip sensors with no data
    const card = document.createElement('div');
    card.className = info.active ? 'card active' : 'card';
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
  const data = await fetchJSON('/api/sensors');
  state.sensors = data.sensors;
  const fieldset = $('#sensor-selection');
  for (const [sensor, info] of Object.entries(data.sensors)) {
    if (!info.has_data) continue;  // skip sensors with no DB rows
    const row = document.createElement('div');
    row.className = info.active ? 'sensor-row' : 'sensor-row stale';
    const sensorBtn = document.createElement('button');
    sensorBtn.className = 'toggle sensor';
    sensorBtn.textContent = info.name;
    row.appendChild(sensorBtn);
    const metricBtns = [];
    for (const [metric, meta] of Object.entries(info.metrics)) {
      const btn = document.createElement('button');
      btn.className = 'toggle';
      btn.textContent = meta.label;
      btn.disabled = true;
      btn.addEventListener('click', () => {
        btn.classList.toggle('on');
        const set = state.selection[sensor];
        if (btn.classList.contains('on')) set.add(metric); else set.delete(metric);
      });
      metricBtns.push([metric, btn]);
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
    });
    fieldset.appendChild(row);
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

function initTimePickers() {
  datePicker = flatpickr('#date-range', {mode: 'range', dateFormat: 'Y-m-d'});
  const timeOpts = {enableTime: true, noCalendar: true, time_24hr: true, dateFormat: 'H:i'};
  flatpickr('#time-start', timeOpts);
  flatpickr('#time-end', timeOpts);
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
  if (!state.lastResult) return;
  const selection = getSelection();
  for (const [sensor, metrics] of Object.entries(selection)) {
    const data = state.lastResult[sensor];
    if (!data) continue;
    if (state.viewMode === 'plot') {
      for (const metric of metrics) {
        container.appendChild(makeChartBox(sensor, metric, data));
      }
    } else {
      container.appendChild(makeTableBox(sensor, metrics, data));
    }
  }
}

function makeChartBox(sensor, metric, data) {
  const info = state.sensors[sensor];
  const meta = info.metrics[metric];
  const label = meta.unit ? `${meta.label} (${meta.unit})` : meta.label;
  const box = document.createElement('div');
  box.className = 'chart-box';
  box.innerHTML = `<h3>${info.name} — ${label}</h3><div class="chart-wrap"><canvas></canvas></div>`;
  const dataset = {
    label,
    data: data.timestamps.map((ts, i) => ({x: ts, y: data[metric][i]})),
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
        x: {type: 'time',
            time: {
              displayFormats: {
                millisecond: 'HH:mm:ss.SSS',
                second:      'HH:mm:ss',
                minute:      'HH:mm',
                hour:        'HH:mm',
                day:         'yyyy-MM-dd',
                week:        'yyyy-MM-dd',
                month:       'yyyy-MM',
                quarter:     'yyyy-MM',
                year:        'yyyy',
              },
            },
            ticks: {color: '#8899aa'}, grid: {color: '#2e3946'}},
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
    <table><thead><tr><th>Timestamp</th>${headers}</tr></thead>
    <tbody>${rows}</tbody></table>`;
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
  URL.revokeObjectURL(url);
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

document.querySelectorAll('input[name="view-mode"]').forEach((radio) => {
  radio.addEventListener('change', () => {
    state.viewMode = radio.value;
    renderResults();
  });
});

$('#btn-query').addEventListener('click', runQuery);
$('#btn-export-visible').addEventListener('click', exportVisible);
$('#btn-export-full').addEventListener('click', exportFull);

initTimePickers();
buildSelectionUI().catch((err) => {
  $('#history-status').textContent = `Error loading sensors: ${err.message}`;
});
startPolling();
