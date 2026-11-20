/* ==========================================================================
   生态系统呼吸预测 — 页面逻辑
   调用本站预测接口，展示预测值、置信度与匹配信息。
   ========================================================================== */

(() => {
  'use strict';

  const ENDPOINT = new URL('/api/predict/', window.location.href);
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
    confidence: '置信度',
    match: '匹配方式',
    station: '站点',
    distance: '距离',
    coords: '坐标',
    weatherSource: '气象来源',
    zoneSource: '分区依据',
    attribution: '来源',
    copy: '复制结果',
    copied: '已复制',
    copyFailed: '复制失败',
    errorTitle: '预测失败',
    errorRaw: '查看服务器原始返回',
    errors: {
      required: (name) => `请输入${name}。`,
      numeric: (name) => `${name}必须为数字，例如 39.90。`,
      range: (name, min, max) => `${name}需在 ${min} ~ ${max} 之间。`,
      timeout: (seconds) => `请求超过 ${seconds} 秒未返回，已取消。`,
      network: '无法连接后端服务，请确认服务正在运行。',
      badResponse: '服务器返回的内容无法解析，请稍后重试。',
      unknown: '预测失败，请稍后重试。',
      // 接口错误码 -> 兜底文案（正常情况下直接显示服务端返回的 message）
      codes: {
        INVALID_INPUT: '经纬度格式不正确。',
        OUT_OF_CHINA: '输入的经纬度不在中国陆地范围内，无法预测。',
        WEATHER_UNAVAILABLE: '未能获取气象数据，请稍后再试。',
        MODEL_UNAVAILABLE: '该站点的模型暂不可用，请稍后再试。',
        DATA_UNAVAILABLE: '服务端数据暂时无法加载，请稍后再试。',
        INTERNAL_ERROR: '服务器内部错误，请稍后再试。',
      },
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
    renderToken: 0,
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
    return Number.isFinite(value) ? `${value.toFixed(2)} km` : '—';
  }

  function formatText(value, fallback = '—') {
    const text = value == null ? '' : String(value).trim();
    return text || fallback;
  }

  function stationLabel(station) {
    const name = formatText(station && station.name, '');
    const code = formatText(station && station.code, '');
    if (name && code) return `${name}（${code}）`;
    return name || code || '—';
  }

  function confidenceClass(confidence) {
    const code = formatText(confidence && confidence.code, 'low');
    return ['high', 'medium', 'low'].includes(code) ? code : 'low';
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
    nextRenderToken();
    dom.body.innerHTML = `
      <p class="loading-text">${escapeHtml(TEXT.loading)}</p>
      <p class="elapsed">
        <span data-elapsed>${escapeHtml(TEXT.elapsed(0))}</span>
        · <button type="button" class="text-button" data-cancel>${escapeHtml(TEXT.cancel)}</button>
      </p>`;
    updateElapsed();
  }

  function renderSuccess(data) {
    const token = nextRenderToken();
    const result = data.result || {};
    const station = result.station || {};
    const matching = result.matching || {};
    const confidence = result.confidence || {};

    dom.body.innerHTML = `
      <p class="value">
        <span class="value-symbol">${escapeHtml(TEXT.valueSymbol)}</span>
        <span class="value-number">${formatNumber(result.prediction)}</span>
      </p>
      <p class="confidence">
        <span class="confidence-label">${escapeHtml(TEXT.confidence)}</span>
        <span class="badge is-${confidenceClass(confidence)}">${escapeHtml(formatText(confidence.label))}</span>
        <span class="confidence-note">${escapeHtml(formatText(confidence.note, ''))}</span>
      </p>
      <dl class="meta">
        <div><dt>${escapeHtml(TEXT.match)}</dt><dd>${escapeHtml(formatText(matching.label))}</dd></div>
        <div><dt>${escapeHtml(TEXT.station)}</dt><dd>${escapeHtml(stationLabel(station))}</dd></div>
        <div><dt>${escapeHtml(TEXT.distance)}</dt><dd>${escapeHtml(formatDistance(matching.distance_km))}</dd></div>
        <div><dt>${escapeHtml(TEXT.coords)}</dt><dd>${escapeHtml(`${formatCoord(data.request && data.request.lat)}, ${formatCoord(data.request && data.request.lon)}`)}</dd></div>
        <div><dt>${escapeHtml(TEXT.weatherSource)}</dt><dd data-source-weather>—</dd></div>
        <div><dt>${escapeHtml(TEXT.zoneSource)}</dt><dd data-source-zones>${escapeHtml(describeZones(matching, null))}</dd></div>
      </dl>
      <div class="actions">
        <button type="button" class="text-button" data-copy>${escapeHtml(TEXT.copy)}</button>
      </div>`;

    state.payload = data;
    annotateSources(token);
  }

  /* ------------------------------------------------------------------------
     结果区的数据来源署名
     与数据来源页共用同一份文案，避免两处不一致。
     --------------------------------------------------------------------- */

  function nextRenderToken() {
    state.renderToken += 1;
    return state.renderToken;
  }

  async function annotateSources(token) {
    const common = window.RECommon;
    if (!common) return;

    let sources = null;
    try {
      sources = await common.loadSources();
    } catch (error) {
      sources = null;  // 标注失败不影响预测结果本身
    }
    if (token !== state.renderToken || !state.payload) return;

    const result = state.payload.result || {};
    const matching = result.matching || {};
    const names = common.sourceNames(sources);

    const weatherNode = dom.body.querySelector('[data-source-weather]');
    if (weatherNode && names.weather) weatherNode.textContent = names.weather;

    const zonesNode = dom.body.querySelector('[data-source-zones]');
    if (zonesNode) zonesNode.textContent = describeZones(matching, names);
  }

  function describeZones(matching, names) {
    const parts = [];
    if (matching.same_soil) {
      parts.push(`同类土壤（土壤分区：${formatText(matching.input_soil_type, '未知')}）`);
    }
    if (matching.same_climate) {
      parts.push(`同类气候（气候分区：${formatText(matching.input_climate_type, '未知')}）`);
    }
    if (!parts.length) return '未命中分区，按空间最近站点匹配';

    const labels = [];
    if (matching.same_soil && names && names.soil) labels.push(names.soil);
    if (matching.same_climate && names && names.climate) labels.push(names.climate);

    const text = parts.join('、');
    return labels.length ? `${text}；${TEXT.attribution}：${labels.join('、')}` : text;
  }

  function renderError(message, raw) {
    nextRenderToken();
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
    nextRenderToken();
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
     解析后端返回
     --------------------------------------------------------------------- */

  function parsePayload(text) {
    try {
      return JSON.parse(text);
    } catch (error) {
      return null;
    }
  }

  function errorMessage(payload) {
    const error = (payload && payload.error) || {};
    const code = formatText(error.code, '');
    const message = formatText(error.message, '');
    return message || TEXT.errors.codes[code] || TEXT.errors.unknown;
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
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });

      const text = await response.text();
      const payload = parsePayload(text);

      if (!payload) {
        renderError(TEXT.errors.badResponse, text);
        return;
      }
      if (!response.ok || payload.ok !== true) {
        renderError(errorMessage(payload), '');
        return;
      }

      renderSuccess(payload);
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
    const result = data.result || {};
    const matching = result.matching || {};
    const confidence = result.confidence || {};
    return [
      document.title,
      `${TEXT.copyValueLabel}：${formatNumber(result.prediction)}`,
      `${TEXT.confidence}：${formatText(confidence.label)}`,
      `${TEXT.match}：${formatText(matching.label)}`,
      `${TEXT.station}：${stationLabel(result.station)}`,
      `${TEXT.distance}：${formatDistance(matching.distance_km)}`,
      `${TEXT.coords}：${formatCoord(data.request && data.request.lat)}, ${formatCoord(data.request && data.request.lon)}`,
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
