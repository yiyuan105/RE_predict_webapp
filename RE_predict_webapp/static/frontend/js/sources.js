/* ==========================================================================
   数据来源页：读取 GET /api/sources/，按类型分组渲染来源卡片与特征表。
   ========================================================================== */

(() => {
  'use strict';

  const common = window.RECommon;
  const { escapeHtml, formatText, getJson } = common;
  const ENDPOINT = new URL('/api/sources/', window.location.href).toString();

  /* ------------------------------------------------------------------------
     页面文案（动态部分）
     --------------------------------------------------------------------- */
  const TEXT = {
    loading: '正在加载数据来源…',
    failed: '数据来源加载失败',
    retry: '重试',
    loaded: (count) => `共 ${count} 项数据来源，按类型分组展示。`,
    empty: '暂无可显示的数据来源。',
    location: '位置',
    purpose: '用途',
    update: '更新方式',
    detail: '说明',
    docRef: '对应文档',
    categoryCount: (count) => `${count} 项`,
    unknownVariable: '未登记来源',
  };

  const dom = {
    status: document.getElementById('sources-status'),
    list: document.getElementById('source-list'),
    panel: document.getElementById('feature-panel'),
    features: document.getElementById('feature-list'),
    weather: document.getElementById('weather-line'),
  };

  /* ------------------------------------------------------------------------
     渲染
     --------------------------------------------------------------------- */

  function groupByCategory(sources) {
    const order = [];
    const groups = new Map();
    sources.forEach((source) => {
      const category = formatText(source.category, '其他');
      if (!groups.has(category)) {
        groups.set(category, []);
        order.push(category);
      }
      groups.get(category).push(source);
    });
    return order.map((category) => [category, groups.get(category)]);
  }

  function sourceCard(source) {
    const rows = [
      `<div><dt>${escapeHtml(TEXT.location)}</dt><dd><code>${escapeHtml(formatText(source.location))}</code></dd></div>`,
      `<div><dt>${escapeHtml(TEXT.purpose)}</dt><dd>${escapeHtml(formatText(source.purpose))}</dd></div>`,
      `<div><dt>${escapeHtml(TEXT.update)}</dt><dd>${escapeHtml(formatText(source.update))}</dd></div>`,
    ];
    if (source.detail) {
      rows.push(`<div><dt>${escapeHtml(TEXT.detail)}</dt><dd>${escapeHtml(source.detail)}</dd></div>`);
    }
    if (source.doc_ref) {
      rows.push(`<div><dt>${escapeHtml(TEXT.docRef)}</dt><dd>维修手册 ${escapeHtml(source.doc_ref)}</dd></div>`);
    }

    return `
      <article class="source">
        <header class="source-head">
          <h3 class="source-title">${escapeHtml(formatText(source.name))}</h3>
          <span class="badge is-low">${escapeHtml(formatText(source.category))}</span>
        </header>
        <dl class="meta">${rows.join('')}</dl>
      </article>`;
  }

  function featureVariable(feature) {
    const variable = formatText(feature.variable, '');
    if (!variable) return TEXT.unknownVariable;
    return feature.transform ? `${variable}（${feature.transform}）` : variable;
  }

  function renderFeatures(features, weather) {
    if (!dom.panel || !dom.features) return;

    const items = Array.isArray(features) ? features : [];
    if (!items.length) return;

    dom.features.innerHTML = items.map((feature) => `
      <li>
        <span class="feature-head">
          <span class="feature-name">${escapeHtml(formatText(feature.name))}</span>
          <span class="feature-label">${escapeHtml(formatText(feature.label))}</span>
          ${feature.unit ? `<span class="feature-unit">${escapeHtml(feature.unit)}</span>` : ''}
        </span>
        <span class="feature-source">${escapeHtml(featureVariable(feature))}</span>
      </li>`).join('');

    if (dom.weather && weather) {
      const variables = Array.isArray(weather.variables) ? weather.variables.join('、') : '';
      dom.weather.textContent = `气象接口：${formatText(weather.endpoint)}（模型 ${formatText(weather.model, 'best_match')}）`
        + (variables ? `；请求变量：${variables}` : '');
    }

    dom.panel.hidden = false;
  }

  function render(payload) {
    const sources = Array.isArray(payload.sources) ? payload.sources : [];

    if (!sources.length) {
      if (dom.status) dom.status.textContent = TEXT.empty;
      return;
    }
    if (dom.status) dom.status.textContent = TEXT.loaded(sources.length);

    if (dom.list) {
      dom.list.innerHTML = groupByCategory(sources).map(([category, items]) => `
        <section class="source-group">
          <h2 class="section-title">${escapeHtml(category)}<span class="count">${escapeHtml(TEXT.categoryCount(items.length))}</span></h2>
          <div class="source-list">${items.map(sourceCard).join('')}</div>
        </section>`).join('');
    }

    renderFeatures(payload.features, payload.weather);
  }

  function renderError(error) {
    if (!dom.status) return;
    dom.status.classList.add('is-error');
    dom.status.innerHTML = `${escapeHtml(TEXT.failed)}：${escapeHtml(formatText(error && error.message, common.TEXT.unknown))}
      <button type="button" class="text-button" data-retry>${escapeHtml(TEXT.retry)}</button>`;

    const retry = dom.status.querySelector('[data-retry]');
    if (retry) retry.addEventListener('click', load);
  }

  /* ------------------------------------------------------------------------
     加载
     --------------------------------------------------------------------- */

  async function load() {
    if (!dom.status) return;
    dom.status.classList.remove('is-error');
    dom.status.textContent = TEXT.loading;

    try {
      render(await getJson(ENDPOINT));
    } catch (error) {
      renderError(error);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load, { once: true });
  } else {
    load();
  }
})();
