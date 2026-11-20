/* ==========================================================================
   模型训练情况页：读取各站点的训练结果，渲染表格并支持检索 / R² 区间筛选。
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
    loading: '正在加载模型训练情况…',
    failed: '模型训练情况加载失败',
    retry: '重试',
    loaded: (shown, total) => `共 ${total} 个站点，当前显示 ${shown} 个。`,
    none: '暂无可展示的训练情况。',
    empty: '没有符合条件的站点，换个筛选条件试试。',
  };

  /* 测试集 R² 区间：与页面下拉项的 value 一一对应 */
  const R2_RANGES = {
    high: (value) => value >= 0.95,
    mid: (value) => value >= 0.9 && value < 0.95,
    low: (value) => value < 0.9,
  };

  const DEFAULT_DISPLAY = { mse_digits: 4, r2_digits: 4 };
  const COLUMN_COUNT = 8;

  const dom = {
    search: document.getElementById('code-search'),
    r2: document.getElementById('filter-r2'),
    reset: document.getElementById('filter-reset'),
    status: document.getElementById('training-status'),
    table: document.getElementById('training-table'),
    body: document.getElementById('training-body'),
  };

  const state = {
    rows: [],
    display: { ...DEFAULT_DISPLAY },
  };

  /* ------------------------------------------------------------------------
     格式化：精度由接口返回的 display 决定（后端集中配置）
     --------------------------------------------------------------------- */

  function toDigits(value, fallback) {
    const number = Number(value);
    return Number.isInteger(number) && number >= 0 && number <= 6 ? number : fallback;
  }

  function applyDisplay(payload) {
    const raw = (payload && payload.display) || {};
    state.display = {
      mse_digits: toDigits(raw.mse_digits, DEFAULT_DISPLAY.mse_digits),
      r2_digits: toDigits(raw.r2_digits, DEFAULT_DISPLAY.r2_digits),
    };
  }

  function formatMetric(value, digits) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(digits) : '—';
  }

  function formatCount(value) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.round(number).toLocaleString('zh-CN') : '—';
  }

  /* ------------------------------------------------------------------------
     渲染
     --------------------------------------------------------------------- */

  function rowHtml(row) {
    const cells = [
      `<th scope="row" class="cell-code">${escapeHtml(formatText(row.code))}</th>`,
      `<td>${escapeHtml(formatCount(row.train_size))}</td>`,
      `<td>${escapeHtml(formatCount(row.test_size))}</td>`,
      `<td>${escapeHtml(formatMetric(row.train_mse, state.display.mse_digits))}</td>`,
      `<td>${escapeHtml(formatMetric(row.train_r2, state.display.r2_digits))}</td>`,
      `<td>${escapeHtml(formatMetric(row.test_mse, state.display.mse_digits))}</td>`,
      `<td>${escapeHtml(formatMetric(row.test_r2, state.display.r2_digits))}</td>`,
      `<td class="cell-model">${escapeHtml(formatText(row.model_type))}</td>`,
    ];
    return `<tr>${cells.join('')}</tr>`;
  }

  function render() {
    const visible = state.rows.filter(matches);

    if (dom.status) {
      dom.status.textContent = state.rows.length
        ? TEXT.loaded(visible.length, state.rows.length)
        : TEXT.none;
    }
    if (!dom.body || !dom.table) return;

    dom.table.hidden = false;
    dom.body.innerHTML = visible.length
      ? visible.map(rowHtml).join('')
      : `<tr><td class="empty-cell" colspan="${COLUMN_COUNT}">${escapeHtml(TEXT.empty)}</td></tr>`;
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
     筛选：站点检索 + 测试集 R² 区间，全部基于已加载数据
     --------------------------------------------------------------------- */

  function matches(row) {
    const search = dom.search ? dom.search.value.trim().toLowerCase() : '';
    if (search && !formatText(row.code, '').toLowerCase().includes(search)) return false;

    const range = dom.r2 ? R2_RANGES[dom.r2.value] : null;
    if (!range) return true;

    const value = Number(row.test_r2);
    return Number.isFinite(value) && range(value);
  }

  function resetFilters() {
    [dom.search, dom.r2].forEach((node) => {
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
    if (dom.table) dom.table.hidden = true;
    if (dom.body) dom.body.innerHTML = '';

    try {
      const payload = await getJson(ENDPOINT);
      state.rows = Array.isArray(payload.stations) ? payload.stations : [];
      applyDisplay(payload);
      render();
    } catch (error) {
      renderError(error);
    }
  }

  function bind() {
    [dom.search, dom.r2].forEach((node) => {
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
