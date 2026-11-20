/* ==========================================================================
   数据来源注明页：按来源类型分组，渲染署名式说明（名称 / 类型 / 用途 / 更新方式）。
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
    loaded: (count) => `共 ${count} 项数据来源，类型标在每张卡片上。`,
    empty: '暂无可显示的数据来源。',
    purpose: '用途',
    update: '更新方式',
  };

  const dom = {
    status: document.getElementById('sources-status'),
    list: document.getElementById('source-list'),
  };

  /* ------------------------------------------------------------------------
     渲染
     --------------------------------------------------------------------- */

  function sourceCard(source) {
    const rows = [
      `<div><dt>${escapeHtml(TEXT.purpose)}</dt><dd>${escapeHtml(formatText(source.purpose))}</dd></div>`,
      `<div><dt>${escapeHtml(TEXT.update)}</dt><dd>${escapeHtml(formatText(source.update))}</dd></div>`,
    ];

    return `
      <article class="source">
        <header class="source-head">
          <h3 class="source-title">${escapeHtml(formatText(source.name))}</h3>
          <span class="badge is-low">${escapeHtml(formatText(source.category))}</span>
        </header>
        <dl class="meta">${rows.join('')}</dl>
      </article>`;
  }

  function render(payload) {
    const sources = Array.isArray(payload.sources) ? payload.sources : [];

    if (!sources.length) {
      if (dom.status) dom.status.textContent = TEXT.empty;
      return;
    }
    if (dom.status) dom.status.textContent = TEXT.loaded(sources.length);

    if (dom.list) {
      dom.list.innerHTML = `<div class="source-list">${sources.map(sourceCard).join('')}</div>`;
    }
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
