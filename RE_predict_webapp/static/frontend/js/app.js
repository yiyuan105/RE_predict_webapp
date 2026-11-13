/* ==========================================================================
   生态系统呼吸预测 — 页面逻辑
   对接现有 Django 接口 GET /?lat=…&lon=…（返回纯文本），不修改后端代码。
   ========================================================================== */

(() => {
  'use strict';

  const ENDPOINT = new URL('/', window.location.href);
  const TIMEOUT_MS = 150000;

  /* ------------------------------------------------------------------------
     页面文案（动态部分）
     修改这里即可调整提示、结果标签和错误信息；
     标题、说明、字段名、按钮、页脚等静态文字在 index.html 里。
     --------------------------------------------------------------------- */
  const TEXT = {
    submitting: '正在预测…',
    loading: '正在获取气象数据…',
    elapsed: (seconds) => `已用时 ${seconds} 秒`,
    cancel: '取消',
    cancelled: '已取消',
    cancelledHint: '修改坐标后可以重新预测。',
    valueSymbol: 'Re =',
    copyValueLabel: '预测值',
    station: '站点',
    distance: '距离',
    coords: '坐标',
    copy: '复制结果',
    copied: '已复制',
    copyFailed: '复制失败',
    errorTitle: '预测失败',
    errorRaw: '查看服务器原始返回',
    errors: {
      required: (name) => `请输入${name}。`,
      numeric: (name) => `${name}必须为数字，例如 39.90。`,
      range: (name, min, max) => `${name}需在 ${min} ~ ${max} 之间。`,
      http: (status) => `服务器返回错误（HTTP ${status}），请检查后端终端日志。`,
      timeout: (seconds) => `请求超过 ${seconds} 秒未返回，已取消。`,
      network: '无法连接后端服务，请确认 Django 开发服务器正在运行。',
      unknown: '未能从服务器返回中解析出预测值。',
      modelLoad: '模型加载失败，请检查后端终端。',
      invalidValue: (value) => `模型返回了无效数值（${value}）。`,
      predict: (detail) => `模型预测报错：${detail}`,
    },
  };

  const dom = {
    form: document.getElementById('predict-form'),
    lat: document.getElementById('lat'),
    lon: document.getElementById('lon'),
    message: document.getElementById('form-message'),
    submit: document.getElementById('submit-btn'),
    submitLabel: document.getElementById('submit-label'),
    body: document.getElementById('result-body'),
  };

  const state = {
    busy: false,
    controller: null,
    abortReason: '',
    timer: null,
    startedAt: 0,
    payload: null,
    copyTimer: null,
  };

  /* 默认提示与按钮文字以 index.html 为准，这里只负责恢复 */
  const defaultMessage = dom.message.textContent;
  const defaultSubmitLabel = dom.submitLabel.textContent;

  /* ------------------------------------------------------------------------
     工具函数
     --------------------------------------------------------------------- */

  const escapeHtml = (value) =>
    String(value).replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    })[ch]);

  const FULLWIDTH = {
    '−': '-', '–': '-', '—': '-', '﹣': '-', '－': '-',
    '＋': '+', '．': '.', '。': '.',
  };

  function normalizeNumberText(value) {
    return String(value == null ? '' : value)
      .replace(/[０-９]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
      .replace(/[−–—﹣－＋．。]/g, (ch) => FULLWIDTH[ch] || ch)
      .replace(/[°º\s]/g, '');
  }

  function formatNumber(value) {
    return Number(value).toLocaleString('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function formatCoord(value) {
    if (!Number.isFinite(Number(value))) return '—';
    return Number(value).toLocaleString('zh-CN', {
      maximumFractionDigits: 4,
      useGrouping: false,
    });
  }

  function formatDistance(value) {
    return Number.isFinite(value) ? `${value.toFixed(2)}°` : '—';
  }

  function stationLabel(data) {
    const name = data.siteName ? String(data.siteName).trim() : '';
    const code = data.stationCode ? String(data.stationCode).trim() : '';
    if (name && code) return `${name}（${code}）`;
    return name || code || '—';
  }

  function truncate(text, limit = 2400) {
    const value = String(text || '');
    return value.length > limit ? `${value.slice(0, limit)}\n…（已截断）` : value;
  }

  function setMessage(message, isError) {
    dom.message.textContent = message;
    dom.message.classList.toggle('is-error', Boolean(isError));
  }

  function clearInvalid() {
    [dom.lat, dom.lon].forEach((input) => input.classList.remove('is-invalid'));
  }

  /* ------------------------------------------------------------------------
     输入校验
     --------------------------------------------------------------------- */

  function parseCoordinate(input, name, min, max) {
    const value = normalizeNumberText(input.value);

    if (!value) return { error: TEXT.errors.required(name) };
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value)) {
      return { error: TEXT.errors.numeric(name) };
    }

    const number = Number(value);
    if (!Number.isFinite(number)) return { error: TEXT.errors.numeric(name) };
    if (number < min || number > max) return { error: TEXT.errors.range(name, min, max) };

    return { value: number };
  }

  /* ------------------------------------------------------------------------
     结果区渲染
     --------------------------------------------------------------------- */

  function renderLoading() {
    dom.body.innerHTML = `
      <p class="loading-text">${escapeHtml(TEXT.loading)}</p>
      <p class="elapsed">
        <span data-elapsed>${escapeHtml(TEXT.elapsed(0))}</span>
        · <button type="button" class="text-button" data-cancel>${escapeHtml(TEXT.cancel)}</button>
      </p>`;
    updateElapsed();
  }

  function renderSuccess(data) {
    const station = escapeHtml(stationLabel(data));
    const distance = escapeHtml(formatDistance(data.distance));
    const coords = escapeHtml(`${formatCoord(data.lat)}, ${formatCoord(data.lon)}`);

    dom.body.innerHTML = `
      <p class="value">
        <span class="value-symbol">${escapeHtml(TEXT.valueSymbol)}</span>
        <span class="value-number">${formatNumber(data.prediction)}</span>
      </p>
      <dl class="meta">
        <div><dt>${escapeHtml(TEXT.station)}</dt><dd>${station}</dd></div>
        <div><dt>${escapeHtml(TEXT.distance)}</dt><dd>${distance}</dd></div>
        <div><dt>${escapeHtml(TEXT.coords)}</dt><dd>${coords}</dd></div>
      </dl>
      <div class="actions">
        <button type="button" class="text-button" data-copy>${escapeHtml(TEXT.copy)}</button>
      </div>`;

    state.payload = data;
  }

  function renderError(message, raw) {
    const detail = raw && String(raw).trim() ? String(raw).trim() : '';

    dom.body.innerHTML = `
      <p class="error-title">${escapeHtml(TEXT.errorTitle)}</p>
      <p class="error-text">${escapeHtml(message)}</p>
      ${detail ? `<details><summary>${escapeHtml(TEXT.errorRaw)}</summary><pre></pre></details>` : ''}`;

    const pre = dom.body.querySelector('pre');
    if (pre) pre.textContent = truncate(detail);

    state.payload = null;
  }

  function renderCancelled() {
    dom.body.innerHTML = `
      <p class="loading-text">${escapeHtml(TEXT.cancelled)}</p>
      <p class="elapsed">${escapeHtml(TEXT.cancelledHint)}</p>`;
    state.payload = null;
  }

  /* ------------------------------------------------------------------------
     计时
     --------------------------------------------------------------------- */

  function startTimer() {
    stopTimer();
    state.startedAt = Date.now();
    updateElapsed();
    state.timer = window.setInterval(updateElapsed, 500);
  }

  function stopTimer() {
    if (state.timer !== null) {
      window.clearInterval(state.timer);
      state.timer = null;
    }
  }

  function updateElapsed() {
    const node = dom.body.querySelector('[data-elapsed]');
    if (!node) return;
    const seconds = Math.max(0, Math.round((Date.now() - state.startedAt) / 1000));
    node.textContent = TEXT.elapsed(seconds);
  }

  /* ------------------------------------------------------------------------
     忙碌状态
     --------------------------------------------------------------------- */

  function setBusy(busy) {
    state.busy = busy;

    dom.submit.disabled = busy;
    dom.submitLabel.textContent = busy ? TEXT.submitting : defaultSubmitLabel;

    dom.lat.readOnly = busy;
    dom.lon.readOnly = busy;

    if (busy) startTimer();
    else stopTimer();
  }

  /* ------------------------------------------------------------------------
     解析后端纯文本
     --------------------------------------------------------------------- */

  function parseResponse(text) {
    const raw = String(text == null ? '' : text).replace(/\r\n/g, '\n').trim();
    const result = {
      raw,
      prediction: null,
      stationCode: null,
      siteName: null,
      distance: null,
      lat: null,
      lon: null,
      invalid: null,
      error: null,
    };

    const lines = raw.split('\n').map((line) => line.trim()).filter(Boolean);

    for (const line of lines) {
      let match = line.match(/^您的位置\s*[:：]\s*\(?\s*([-+]?\d+(?:\.\d+)?)\s*[,，]\s*([-+]?\d+(?:\.\d+)?)\s*\)?/);
      if (match) {
        result.lat = Number(match[1]);
        result.lon = Number(match[2]);
        continue;
      }

      match = line.match(/^匹配到最近的站点\s*[:：]\s*([A-Za-z0-9_-]+)\s*(?:\((.*)\))?\s*$/);
      if (match) {
        result.stationCode = match[1];
        result.siteName = match[2] ? match[2].trim() : null;
        continue;
      }

      match = line.match(/^距离\s*[:：]\s*([-+]?\d+(?:\.\d+)?)/);
      if (match) {
        result.distance = Number(match[1]);
        continue;
      }

      match = line.match(/^预测值\s*[:：]\s*([^\n]+)$/);
      if (match) {
        const valueText = match[1].trim();
        if (/^[+-]?(?:nan|inf(?:inity)?)$/i.test(valueText)) {
          result.invalid = valueText;
        } else {
          const value = Number(valueText);
          if (Number.isFinite(value)) result.prediction = value;
        }
        continue;
      }
    }

    if (result.prediction === null) {
      const predictError = raw.match(/模型预测报错\s*[:：]\s*([\s\S]+)/);

      if (predictError) {
        result.error = TEXT.errors.predict(predictError[1].trim());
      } else if (raw.includes('模型加载失败')) {
        result.error = TEXT.errors.modelLoad;
      } else if (raw.includes('请在网址带上经纬度')) {
        result.error = TEXT.errors.required('经纬度');
      } else if (raw.includes('经纬度必须是数字')) {
        result.error = TEXT.errors.numeric('经纬度');
      } else if (result.invalid) {
        result.error = TEXT.errors.invalidValue(result.invalid);
      } else {
        result.error = TEXT.errors.unknown;
      }
    }

    return result;
  }

  /* ------------------------------------------------------------------------
     请求
     --------------------------------------------------------------------- */

  async function runPrediction() {
    clearInvalid();

    const lat = parseCoordinate(dom.lat, '纬度', -90, 90);
    const lon = parseCoordinate(dom.lon, '经度', -180, 180);

    if (lat.error) {
      setMessage(lat.error, true);
      dom.lat.classList.add('is-invalid');
      dom.lat.focus();
      return;
    }
    if (lon.error) {
      setMessage(lon.error, true);
      dom.lon.classList.add('is-invalid');
      dom.lon.focus();
      return;
    }

    dom.lat.value = String(lat.value);
    dom.lon.value = String(lon.value);
    setMessage(defaultMessage, false);

    state.abortReason = '';
    setBusy(true);
    renderLoading();

    const url = new URL(ENDPOINT);
    url.searchParams.set('lat', String(lat.value));
    url.searchParams.set('lon', String(lon.value));

    const controller = new AbortController();
    state.controller = controller;

    const timeout = window.setTimeout(() => {
      state.abortReason = 'timeout';
      controller.abort();
    }, TIMEOUT_MS);

    try {
      const response = await fetch(url.toString(), {
        method: 'GET',
        cache: 'no-store',
        headers: { Accept: 'text/plain, text/html, */*' },
        signal: controller.signal,
      });

      const text = await response.text();

      if (!response.ok) {
        renderError(TEXT.errors.http(response.status), text);
        return;
      }

      const parsed = parseResponse(text);
      if (parsed.error) {
        renderError(parsed.error, parsed.raw);
        return;
      }

      renderSuccess(parsed);
    } catch (error) {
      if (error && error.name === 'AbortError') {
        if (state.abortReason === 'cancel') renderCancelled();
        else renderError(TEXT.errors.timeout(Math.round(TIMEOUT_MS / 1000)), '');
        return;
      }

      renderError(TEXT.errors.network, '');
    } finally {
      window.clearTimeout(timeout);
      state.controller = null;
      state.abortReason = '';
      setBusy(false);
    }
  }

  function cancelRequest() {
    if (!state.busy || !state.controller) return;
    state.abortReason = 'cancel';
    state.controller.abort();
  }

  /* ------------------------------------------------------------------------
     复制结果
     --------------------------------------------------------------------- */

  function buildCopyText(data) {
    return [
      document.title,
      `${TEXT.copyValueLabel}：${formatNumber(data.prediction)}`,
      `${TEXT.station}：${stationLabel(data)}`,
      `${TEXT.distance}：${formatDistance(data.distance)}`,
      `${TEXT.coords}：${formatCoord(data.lat)}, ${formatCoord(data.lon)}`,
    ].join('\n');
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (error) {
        /* 尝试兼容方式 */
      }
    }

    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.top = '-1000px';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand('copy');
      textarea.remove();
      return copied;
    } catch (error) {
      return false;
    }
  }

  async function copyResult(button) {
    if (!state.payload) return;

    const copied = await copyText(buildCopyText(state.payload));
    button.textContent = copied ? TEXT.copied : TEXT.copyFailed;

    window.clearTimeout(state.copyTimer);
    state.copyTimer = window.setTimeout(() => {
      button.textContent = TEXT.copy;
    }, 1600);
  }

  /* ------------------------------------------------------------------------
     事件绑定
     --------------------------------------------------------------------- */

  function init() {
    dom.form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!state.busy) runPrediction();
    });

    [dom.lat, dom.lon].forEach((input) => {
      input.addEventListener('input', () => {
        input.classList.remove('is-invalid');
        if (dom.message.classList.contains('is-error')) setMessage(defaultMessage, false);
      });
    });

    dom.body.addEventListener('click', (event) => {
      const cancel = event.target.closest('[data-cancel]');
      if (cancel) {
        cancelRequest();
        return;
      }

      const copy = event.target.closest('[data-copy]');
      if (copy) copyResult(copy);
    });

    document.addEventListener('keydown', (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        if (!state.busy && typeof dom.form.requestSubmit === 'function') {
          dom.form.requestSubmit();
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
