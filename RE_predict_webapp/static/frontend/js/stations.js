/* ==========================================================================
   站点模型查看页：读取 GET /api/stations/，渲染站点卡片、筛选与详情。
   ========================================================================== */

(() => {
  'use strict';

  const common = window.RECommon;
  const { escapeHtml, formatText, getJson } = common;
  const ENDPOINT = new URL('/api/stations/', window.location.href).toString();

  /* ------------------------------------------------------------------------
     页面文案（动态部分）
     --------------------------------------------------------------------- */
  const TEXT = {
    loading: '正在加载站点…',
    failed: '站点数据加载失败',
    retry: '重试',
    loaded: (shown, total) => `共 ${total} 个站点，当前显示 ${shown} 个。`,
    empty: '没有符合条件的站点，换个筛选条件试试。',
    available: '模型可用',
    unavailable: '模型不可用',
    coordinate: '经纬度',
    ecosystem: '生态系统',
    vegType: '植被类型',
    soil: '土壤类型',
    climate: '气候类型',
    modelFile: '模型文件',
    features: '模型输入特征',
    noFeatures: '该站点未声明模型特征。',
    sourceNote: '数据来源',
    detail: '查看模型与数据来源',
    unknownVariable: '未登记来源',
  };

  const dom = {
    search: document.getElementById('station-search'),
    ecosystem: document.getElementById('filter-ecosystem'),
    climate: document.getElementById('filter-climate'),
    soil: document.getElementById('filter-soil'),
    model: document.getElementById('filter-model'),
    reset: document.getElementById('filter-reset'),
    status: document.getElementById('stations-status'),
    list: document.getElementById('station-list'),
  };

  const state = {
    stations: [],
    features: {},
    sources: null,
  };

  /* ------------------------------------------------------------------------
     工具
     --------------------------------------------------------------------- */

  function formatCoord(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return number.toLocaleString('zh-CN', { maximumFractionDigits: 4, useGrouping: false });
  }

  function indexFeatures(features) {
    const index = {};
    (Array.isArray(features) ? features : []).forEach((feature) => {
      if (feature && feature.name) index[feature.name] = feature;
    });
    return index;
  }

  function featureVariable(feature) {
    const variable = formatText(feature.variable, '');
    if (!variable) return TEXT.unknownVariable;
    return feature.transform ? `${variable}（${feature.transform}）` : variable;
  }

  function sourceNote() {
    const shorts = (state.sources && state.sources.shorts) || {};
    const labels = [];
    if (shorts.climate) labels.push(`气候分区 ${shorts.climate}`);
    if (shorts.soil) labels.push(`土壤分区 ${shorts.soil}`);
    if (shorts.weather) labels.push(`气象 ${shorts.weather}`);
    if (!labels.length) return '';
    return `<p class="detail-note">${escapeHtml(TEXT.sourceNote)}：${escapeHtml(labels.join('；'))}</p>`;
  }

  /* ------------------------------------------------------------------------
     渲染
     --------------------------------------------------------------------- */

  function detailBody(station) {
    const model = station.model || {};
    const names = Array.isArray(station.features) ? station.features : [];
    const rows = names.map((name) => {
      const feature = state.features[name] || { name };
      return `<li>
          <span class="feature-head">
            <span class="feature-name">${escapeHtml(name)}</span>
            <span class="feature-label">${escapeHtml(formatText(feature.label, name))}</span>
            ${feature.unit ? `<span class="feature-unit">${escapeHtml(feature.unit)}</span>` : ''}
          </span>
          <span class="feature-source">${escapeHtml(featureVariable(feature))}</span>
        </li>`;
    }).join('');

    const size = model.size_kb ? `，约 ${model.size_kb} KB` : '';
    return `
      <p class="detail-note">${escapeHtml(TEXT.modelFile)}：<code>${escapeHtml(formatText(model.filename))}</code>
        （${escapeHtml(formatText(model.message))}${escapeHtml(size)}）</p>
      <p class="detail-note">${escapeHtml(TEXT.features)}</p>
      <ul class="feature-list">${rows || `<li><span class="feature-source">${escapeHtml(TEXT.noFeatures)}</span></li>`}</ul>
      ${sourceNote()}`;
  }

  function stationCard(station) {
    const model = station.model || {};
    const available = model.available === true;
    return `
      <article class="station">
        <header class="station-head">
          <h2 class="station-name"><span class="station-code">${escapeHtml(formatText(station.code))}</span>${escapeHtml(formatText(station.name))}</h2>
          <span class="badge ${available ? 'is-high' : 'is-low'}">${escapeHtml(available ? TEXT.available : TEXT.unavailable)}</span>
        </header>
        <dl class="station-meta">
          <div><dt>${escapeHtml(TEXT.coordinate)}</dt><dd>${escapeHtml(formatCoord(station.lat))}, ${escapeHtml(formatCoord(station.lon))}</dd></div>
          <div><dt>${escapeHtml(TEXT.ecosystem)}</dt><dd>${escapeHtml(formatText(station.ecosystem))}</dd></div>
          <div><dt>${escapeHtml(TEXT.vegType)}</dt><dd>${escapeHtml(formatText(station.veg_type))}</dd></div>
          <div><dt>${escapeHtml(TEXT.soil)}</dt><dd>${escapeHtml(formatText(station.soil_type))}</dd></div>
          <div><dt>${escapeHtml(TEXT.climate)}</dt><dd>${escapeHtml(formatText(station.climate_type))}</dd></div>
        </dl>
        <details class="station-details">
          <summary>${escapeHtml(TEXT.detail)}</summary>
          ${detailBody(station)}
        </details>
      </article>`;
  }

  function render() {
    const visible = state.stations.filter(matches);

    if (dom.status) dom.status.textContent = TEXT.loaded(visible.length, state.stations.length);
    if (!dom.list) return;

    dom.list.innerHTML = visible.length
      ? visible.map(stationCard).join('')
      : `<p class="placeholder">${escapeHtml(TEXT.empty)}</p>`;
  }

  function renderError(error) {
    if (!dom.status) return;
    dom.status.classList.add('is-error');
    dom.status.innerHTML = `${escapeHtml(TEXT.failed)}：${escapeHtml(formatText(error && error.message, common.TEXT.unknown))}
      <button type="button" class="text-button" data-retry>${escapeHtml(TEXT.retry)}</button>`;

    const retry = dom.status.querySelector('[data-retry]');
    if (retry) retry.addEventListener('click', () => {
      dom.status.classList.remove('is-error');
      load();
    });
  }

  /* ------------------------------------------------------------------------
     筛选
     --------------------------------------------------------------------- */

  function uniqueValues(key) {
    const values = new Set();
    state.stations.forEach((station) => {
      const value = formatText(station[key], '');
      if (value) values.add(value);
    });
    return [...values].sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'));
  }

  function populateSelect(select, values) {
    if (!select) return;
    const current = select.value;
    while (select.options.length > 1) select.remove(1);
    values.forEach((value) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    if (values.includes(current)) select.value = current;
  }

  function matches(station) {
    const search = dom.search ? dom.search.value.trim().toLowerCase() : '';
    if (search) {
      const haystack = [
        station.code, station.name, station.ecosystem, station.veg_type, station.soil_type, station.climate_type,
      ].map((value) => formatText(value, '').toLowerCase()).join(' ');
      if (!haystack.includes(search)) return false;
    }
    if (dom.ecosystem && dom.ecosystem.value && station.ecosystem !== dom.ecosystem.value) return false;
    if (dom.climate && dom.climate.value && station.climate_type !== dom.climate.value) return false;
    if (dom.soil && dom.soil.value && station.soil_type !== dom.soil.value) return false;

    const modelFilter = dom.model ? dom.model.value : '';
    const available = Boolean(station.model && station.model.available);
    if (modelFilter === 'ok' && !available) return false;
    if (modelFilter === 'missing' && available) return false;
    return true;
  }

  function resetFilters() {
    [dom.search, dom.ecosystem, dom.climate, dom.soil, dom.model].forEach((node) => {
      if (node) node.value = '';
    });
    render();
  }

  /* ------------------------------------------------------------------------
     加载
     --------------------------------------------------------------------- */

  async function load() {
    if (dom.status) {
      dom.status.classList.remove('is-error');
      dom.status.textContent = TEXT.loading;
    }
    if (dom.list) dom.list.innerHTML = '';

    try {
      const [payload, sources] = await Promise.all([
        getJson(ENDPOINT),
        common.loadSources().catch(() => null),  // 来源标注拿不到时不影响站点列表
      ]);

      state.stations = Array.isArray(payload.stations) ? payload.stations : [];
      state.features = indexFeatures(payload.features);
      state.sources = sources;

      populateSelect(dom.ecosystem, uniqueValues('ecosystem'));
      populateSelect(dom.climate, uniqueValues('climate_type'));
      populateSelect(dom.soil, uniqueValues('soil_type'));
      render();
    } catch (error) {
      renderError(error);
    }
  }

  function bind() {
    [dom.search, dom.ecosystem, dom.climate, dom.soil, dom.model].forEach((node) => {
      if (!node) return;
      node.addEventListener(node.tagName === 'SELECT' ? 'change' : 'input', render);
    });
    if (dom.reset) dom.reset.addEventListener('click', resetFilters);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      bind();
      load();
    }, { once: true });
  } else {
    bind();
    load();
  }
})();
