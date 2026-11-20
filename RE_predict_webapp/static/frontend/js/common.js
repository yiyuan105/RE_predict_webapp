/* ==========================================================================
   公共脚本：接口请求、错误文案、文本转义与来源名称，供所有页面共用。
   ========================================================================== */

window.RECommon = (() => {
  'use strict';

  const TEXT = {
    unknown: '请求失败，请稍后重试。',
    badResponse: '服务器返回的内容无法解析，请稍后重试。',
    codes: {
      DATA_UNAVAILABLE: '服务端数据暂时无法加载，请稍后再试。',
      INTERNAL_ERROR: '服务器内部错误，请稍后再试。',
    },
  };

  const SOURCES_URL = new URL('/api/sources/', window.location.href).toString();

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    })[ch]);
  }

  function formatText(value, fallback = '—') {
    const text = value == null ? '' : String(value).trim();
    return text || fallback;
  }

  function errorMessage(payload) {
    const error = (payload && payload.error) || {};
    return formatText(error.message, '') || TEXT.codes[error.code] || TEXT.unknown;
  }

  async function getJson(url) {
    const response = await fetch(url, {
      method: 'GET',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    const text = await response.text();

    let payload = null;
    try {
      payload = JSON.parse(text);
    } catch (error) {
      payload = null;
    }

    if (!payload) {
      const failure = new Error(TEXT.badResponse);
      failure.code = 'BAD_RESPONSE';
      throw failure;
    }
    if (!response.ok || payload.ok !== true) {
      const failure = new Error(errorMessage(payload));
      failure.code = (payload.error && payload.error.code) || 'HTTP_ERROR';
      throw failure;
    }
    return payload;
  }

  /* 来源署名：key -> 来源名称，结果区标注与来源页取同一份文案 */
  function sourceNames(payload) {
    const names = {};
    const sources = (payload && payload.sources) || [];
    sources.forEach((source) => {
      if (source && source.key) names[source.key] = formatText(source.name, '');
    });
    return names;
  }

  let sourcesPromise = null;

  /* 结果区标注与数据来源页共用同一次请求，避免两处文案不一致 */
  function loadSources() {
    if (!sourcesPromise) {
      sourcesPromise = getJson(SOURCES_URL).catch((error) => {
        sourcesPromise = null;  // 失败后允许下次重试
        throw error;
      });
    }
    return sourcesPromise;
  }

  return { TEXT, escapeHtml, formatText, getJson, loadSources, sourceNames };
})();
