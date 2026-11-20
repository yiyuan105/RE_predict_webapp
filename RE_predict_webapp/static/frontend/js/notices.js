/* ==========================================================================
   首页公告边栏：读取公告列表，按发布时间倒序渲染紧凑卡片。
   排序与字段范围由后端决定，这里只负责展示。
   ========================================================================== */

(() => {
  'use strict';

  const common = window.RECommon;
  const { escapeHtml, formatText, getJson } = common;
  const ENDPOINT = new URL('/api/announcements/', window.location.href).toString();

  /* ------------------------------------------------------------------------
     页面文案（动态部分）
     --------------------------------------------------------------------- */
  const TEXT = {
    loading: '正在加载公告…',
    failed: '公告加载失败',
    retry: '重试',
    empty: '暂无公告。',
  };

  const dom = {
    status: document.getElementById('notice-status'),
    list: document.getElementById('notice-list'),
  };

  /* ------------------------------------------------------------------------
     渲染
     --------------------------------------------------------------------- */

  /* 正文按空行分段，保留发布方自己写的换行 */
  function bodyHtml(body) {
    const paragraphs = String(body == null ? '' : body)
      .split(/\r?\n+/)
      .map((line) => line.trim())
      .filter(Boolean);
    return paragraphs.map((text) => `<p>${escapeHtml(text)}</p>`).join('');
  }

  function noticeCard(item) {
    return `
      <article class="notice">
        <header class="notice-head">
          <h3 class="notice-title">${escapeHtml(formatText(item.title))}</h3>
          <time class="notice-time" datetime="${escapeHtml(formatText(item.published_at, ''))}">${escapeHtml(formatText(item.published_at))}</time>
        </header>
        <div class="notice-body">${bodyHtml(item.body)}</div>
      </article>`;
  }

  function render(payload) {
    const items = Array.isArray(payload.announcements) ? payload.announcements : [];

    if (dom.status) {
      dom.status.classList.remove('is-error');
      dom.status.textContent = items.length ? '' : TEXT.empty;
      dom.status.hidden = items.length > 0;
    }
    if (dom.list) dom.list.innerHTML = items.map(noticeCard).join('');
  }

  function renderError(error) {
    if (!dom.status) return;
    dom.status.hidden = false;
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
    if (dom.status) {
      dom.status.hidden = false;
      dom.status.classList.remove('is-error');
      dom.status.textContent = TEXT.loading;
    }

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
