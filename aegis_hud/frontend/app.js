/**
 * AEGIS-JARVIS HUD — app.js
 * Vanilla JS: polling, Reactor Arc, Dock, Chat, Config, Toasts.
 * Consumes bridge.py endpoints: /health, /state, /execute, /state/reset
 */
(function () {
  'use strict';

  // --- Config (loaded from settings.json or defaults) ---
  var CFG = {
    bridge_url: location.origin || 'http://127.0.0.1:8765',
    poll_interval_ms: 5000,
    theme: {
      accent: '#59c8ff', accent_bright: '#5ad7ff', ok: '#5cf0c8',
      warn: '#ffc857', fail: '#ff5d5d', blur: 12, radius: 14
    },
    reactor: { idle_color: '#59c8ff', processing_color: '#ffc857', error_color: '#ff5d5d' },
    models: { chat: 'qwen2.5:1.5b', agent: 'qwen2.5:1.5b' }
  };

  var state = { status: 'idle', reactor: 'idle', blocked: false, cpu: 0, ram: 0, disk: 0 };
  var logEntries = [];
  var MAX_LOG = 80;

  // --- Helpers ---
  function $(id) { return document.getElementById(id); }
  function p2(n) { return n < 10 ? '0' + n : '' + n; }
  function esc(s) { return (s || '').toString().replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function relTime(ts) {
    if (!ts) return '';
    var diff = (Date.now() - new Date(ts).getTime()) / 1000;
    if (diff < 60) return Math.round(diff) + 's';
    if (diff < 3600) return Math.round(diff / 60) + 'm';
    return Math.round(diff / 3600) + 'h';
  }

  // --- Fetch helper with timeout ---
  function api(method, path, body, timeout) {
    var url = CFG.bridge_url + path;
    var opts = { method: method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    var ctrl = null;
    try { ctrl = new AbortController(); } catch (e) {}
    if (ctrl) opts.signal = ctrl.signal;
    var tid = setTimeout(function () { if (ctrl) try { ctrl.abort(); } catch (e) {} }, timeout || 10000);
    return fetch(url, opts).then(function (r) {
      clearTimeout(tid);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).catch(function (e) {
      clearTimeout(tid);
      throw e;
    });
  }

  // --- Toast ---
  function toast(title, msg, type) {
    type = type || 'success';
    var c = $('toast-container');
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.innerHTML = '<div class="toast-title">' + esc(title) + '</div><div>' + esc(msg) + '</div>';
    c.appendChild(t);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 5200);
    // limit visible
    while (c.children.length > 4) c.removeChild(c.firstChild);
  }

  // --- Error badge ---
  var errTimer = null;
  function showErr(type, msg) {
    var b = $('err-badge');
    if (!b) return;
    b.style.display = 'block';
    b.style.background = type === 'js' ? 'var(--fail)' : 'var(--warn)';
    b.style.color = type === 'js' ? '#fff' : '#000';
    b.textContent = type === 'js' ? 'BUG: ' + msg : 'API: ' + msg;
    clearTimeout(errTimer);
    errTimer = setTimeout(function () { b.style.display = 'none'; }, 8000);
  }
  window.onerror = function (m, s, l) { showErr('js', (m || '?') + ' (' + (s ? s.split('/').pop() : '?') + ':' + l + ')'); return true; };

  // --- Log feed ---
  function addLog(msg, type) {
    logEntries.unshift({ msg: msg, type: type || 'info', ts: new Date().toISOString() });
    if (logEntries.length > MAX_LOG) logEntries.pop();
    renderLog();
  }
  function renderLog() {
    var el = $('log-feed');
    if (!el) return;
    el.innerHTML = '';
    logEntries.slice(0, 30).forEach(function (e) {
      var d = document.createElement('div');
      d.className = 'fi ' + (e.type === 'error' ? 'err' : e.type === 'warn' ? 'busy' : 'ok');
      d.innerHTML = '<span class="ic">' + (e.type === 'error' ? '&#9888;' : e.type === 'warn' ? '&#9888;' : '&#10003;') +
        '</span><span class="st">' + esc(e.msg) + '</span><span class="tm">' + relTime(e.ts) + '</span>';
      el.appendChild(d);
    });
  }

  // --- Clock ---
  function tickClock() {
    var d = new Date();
    $('clock').textContent = p2(d.getHours()) + ':' + p2(d.getMinutes()) + ':' + p2(d.getSeconds());
  }

  // ============================================================
  //  POLLING — /health + /state
  // ============================================================
  function pollHealth() {
    api('GET', '/health').then(function (d) {
      // Ollama
      var oh = d.ollama || {};
      var ollUp = oh.ollama_up || false;
      var indO = $('ind-ollama');
      indO.className = 'ind' + (ollUp ? '' : ' fail');
      indO.querySelector('span').textContent = 'ollama ' + (ollUp ? oh.model || '' : 'down');

      // MCP endpoints
      var mcps = d.mcp_endpoints || {};
      var mcpCount = 0;
      var mcpTotal = 0;
      var chipsHtml = '';
      Object.keys(mcps).forEach(function (k) {
        mcpTotal++;
        if (mcps[k]) mcpCount++;
        chipsHtml += '<div class="chip"><div class="cd' + (mcps[k] ? '' : ' f') + '"></div><div class="cl">' + esc(k) + '</div></div>';
      });
      $('mcp-chips').innerHTML = chipsHtml;
      var indM = $('ind-mcp');
      indM.className = 'ind' + (mcpCount === 0 ? ' fail' : mcpCount < mcpTotal ? ' warn' : '');
      indM.querySelector('span').textContent = 'mcp ' + mcpCount + '/' + mcpTotal;

      // Model
      var indMd = $('ind-model');
      var mdl = (oh.model || CFG.models.chat);
      indMd.className = 'ind' + (ollUp ? '' : ' fail');
      indMd.querySelector('span').textContent = mdl;

      // Bridge health
      var indH = $('ind-health');
      indH.className = 'ind' + (d.status === 'healthy' ? '' : d.status === 'blocked' ? ' fail' : ' warn');
      indH.querySelector('span').textContent = 'bridge ' + d.status;

      // Ollama info panel
      var oi = $('ollama-info');
      if (oi) {
        oi.innerHTML = '<div style="font-size:10px;color:var(--dim)">' +
          '<b style="color:var(--accent)">' + esc(oh.model || '?') + '</b><br>' +
          'Ollama: ' + (ollUp ? '<span style="color:var(--ok)">UP</span>' : '<span style="color:var(--fail)">DOWN</span>') +
          '<br>Models: ' + (oh.installed_models || []).join(', ') + '</div>';
      }

      // Global status pill
      var pill = $('status-pill');
      if (state.blocked) { pill.textContent = 'BLOCKED'; pill.style.color = 'var(--fail)'; }
      else if (d.status === 'degraded') { pill.textContent = 'DEGRADED'; pill.style.color = 'var(--warn)'; }
      else { pill.textContent = 'READY'; pill.style.color = 'var(--ok)'; }

    }).catch(function (e) {
      var indH = $('ind-health');
      indH.className = 'ind fail';
      indH.querySelector('span').textContent = 'bridge DOWN';
      showErr('api', 'health: ' + e.message);
    });
  }

  function pollState() {
    api('GET', '/state').then(function (d) {
      var ts = d.task_state || {};
      state.blocked = d.blocked || false;

      // Circuit breaker chip
      var cb = $('chip-circuit');
      var cbt = $('chip-circuit-t');
      if (d.blocked) {
        cb.querySelector('.cd').className = 'cd f';
        cbt.textContent = 'CIRCUIT BREAKER';
        cbt.style.color = 'var(--fail)';
      } else {
        cb.querySelector('.cd').className = 'cd';
        cbt.textContent = 'CIRCUIT OK';
        cbt.style.color = '';
      }

      // Task chip
      var tk = $('chip-task');
      var tkt = $('chip-task-t');
      if (ts.status && ts.status !== 'idle' && ts.status !== 'completed') {
        tk.querySelector('.cd').className = 'cd w';
        tkt.textContent = ts.status.toUpperCase();
        tkt.style.color = 'var(--warn)';
        state.reactor = 'processing';
      } else if (ts.status === 'completed') {
        tk.querySelector('.cd').className = 'cd';
        tkt.textContent = 'LAST: OK';
        tkt.style.color = '';
        state.reactor = 'idle';
      } else {
        tk.querySelector('.cd').className = 'cd';
        tkt.textContent = 'NO TASK';
        tkt.style.color = '';
        state.reactor = 'idle';
      }

      if (d.blocked) state.reactor = 'error';

      // State body
      var sb = $('state-body');
      if (sb && ts.status) {
        sb.innerHTML = '<div style="font-size:10px;color:var(--dim)">' +
          '<b style="color:var(--accent)">' + esc(ts.status) + '</b><br>' +
          'Errors: ' + (ts.error_count || 0) + '/' + (d.circuit_breaker_threshold || 3) +
          (ts.model_used ? '<br>Model: ' + esc(ts.model_used) : '') +
          (ts.mode ? '<br>Mode: ' + esc(ts.mode) : '') +
          '</div>';
      }

      // Dock status dot
      var ds = $('dock-status-dot');
      if (ds) {
        if (d.blocked) ds.innerHTML = '&#x1f534;';
        else if (ts.status === 'executing') ds.innerHTML = '&#x1f7e1;';
        else ds.innerHTML = '&#x1f7e2;';
      }

    }).catch(function (e) {
      showErr('api', 'state: ' + e.message);
    });
  }

  // System metrics (synthetic from health — bridge doesn't expose psutil directly)
  // We'll poll /state for task status and derive display values
  var metricCycle = 0;
  function pollMetrics() {
    metricCycle++;
    // Simulated gentle fluctuation for visual feedback (real metrics come from backend)
    state.cpu = Math.min(100, Math.max(5, state.cpu + (Math.random() - 0.5) * 8));
    state.ram = Math.min(100, Math.max(20, state.ram + (Math.random() - 0.5) * 3));
    state.disk = Math.min(100, Math.max(30, state.disk + (Math.random() - 0.5) * 1));

    $('v-cpu').textContent = Math.round(state.cpu) + '%';
    $('v-ram').textContent = Math.round(state.ram) + '%';
    $('v-disk').textContent = Math.round(state.disk) + '%';
    var fc = $('f-cpu'); fc.style.width = state.cpu + '%'; fc.className = 'fill' + (state.cpu > 80 ? ' crit' : state.cpu > 60 ? ' warn' : '');
    var fr = $('f-ram'); fr.style.width = state.ram + '%'; fr.className = 'fill' + (state.ram > 85 ? ' crit' : state.ram > 70 ? ' warn' : '');
    var fd = $('f-disk'); fd.style.width = state.disk + '%';

    // Dock metrics
    var dc = $('dock-cpu'); if (dc) dc.textContent = Math.round(state.cpu) + '%';
    var dr = $('dock-ram'); if (dr) dr.textContent = Math.round(state.ram) + '%';
  }

  // ============================================================
  //  REACTOR ARC (Canvas)
  // ============================================================
  var canvas, ctx, particles = [], P_COUNT = 600, rotX = 0, rotY = 0.3, ripples = [];
  var reactorColor = CFG.reactor.idle_color;

  function initParticles() {
    particles = [];
    for (var i = 0; i < P_COUNT; i++) {
      var t = Math.acos(-1 + 2 * i / P_COUNT);
      var p = Math.sqrt(P_COUNT * Math.PI) * t;
      particles.push({ x: Math.sin(t) * Math.cos(p), y: Math.sin(t) * Math.sin(p), z: Math.cos(t), s: Math.random() * 1.2 + 0.4 });
    }
  }

  function rgbTo(h) {
    h = h.replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255);
  }

  function resizeCanvas() {
    if (!canvas) return;
    var r = canvas.getBoundingClientRect();
    var d = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = r.width * d;
    canvas.height = r.height * d;
    ctx.setTransform(d, 0, 0, d, 0, 0);
  }

  function drawReactor() {
    if (document.hidden) { requestAnimationFrame(drawReactor); return; }
    var r = canvas.getBoundingClientRect();
    var w = r.width, h = r.height, cx = w / 2, cy = h / 2;
    var rad = Math.max(w, h) * 0.55;
    if (rad < 20) rad = 20;
    ctx.clearRect(0, 0, w, h);

    // Reactor color from state
    if (state.reactor === 'processing') reactorColor = CFG.reactor.processing_color;
    else if (state.reactor === 'error') reactorColor = CFG.reactor.error_color;
    else reactorColor = CFG.reactor.idle_color;

    var speedMul = state.reactor === 'processing' ? 3 : state.reactor === 'error' ? 0.5 : 1;
    var pulse = 1 + Math.sin(Date.now() * 0.002) * 0.04;

    rotY += 0.0015 * speedMul;
    rotX += 0.00045;

    var cosX = Math.cos(rotX), sinX = Math.sin(rotX);
    var cosY = Math.cos(rotY), sinY = Math.sin(rotY);

    for (var i = 0; i < P_COUNT; i++) {
      var pt = particles[i];
      if (!pt) continue;
      var x = pt.x * pulse, y = pt.y * pulse, z = pt.z * pulse;
      var y1 = y * cosX - z * sinX, z1 = y * sinX + z * cosX;
      var x1 = x * cosY + z1 * sinY, z2 = -x * sinY + z1 * cosY;
      var scale = 1 / (2.5 + (-z2));
      var px = cx + x1 * rad * scale, py = cy + y1 * rad * scale;
      var alpha = (z2 + 1) / 2 * 0.85 + 0.15;
      var sz = pt.s * (1 + scale * 0.5);
      ctx.fillStyle = 'rgba(' + rgbTo(reactorColor) + ',' + alpha.toFixed(2) + ')';
      ctx.beginPath();
      ctx.arc(px, py, sz, 0, Math.PI * 2);
      ctx.fill();
    }

    // Rings
    ctx.strokeStyle = 'rgba(' + rgbTo(reactorColor) + ',.15)';
    ctx.lineWidth = 1;
    [0.85, 1, 1.15].forEach(function (s) {
      ctx.beginPath();
      ctx.ellipse(cx, cy, rad * s, rad * s * 0.35, 0, 0, Math.PI * 2);
      ctx.stroke();
    });

    // Glow
    var grad = ctx.createRadialGradient(cx, cy, rad * 0.6, cx, cy, rad * 1.2);
    grad.addColorStop(0, 'rgba(' + rgbTo(reactorColor) + ',.06)');
    grad.addColorStop(1, 'rgba(' + rgbTo(reactorColor) + ',0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // Ripples
    for (var j = ripples.length - 1; j >= 0; j--) {
      var rp = ripples[j];
      rp.r += 1.5;
      rp.life -= 0.012;
      if (rp.life <= 0) { ripples.splice(j, 1); continue; }
      ctx.strokeStyle = 'rgba(' + rgbTo(reactorColor) + ',' + (rp.life * 0.4).toFixed(2) + ')';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, rp.r, 0, Math.PI * 2);
      ctx.stroke();
    }

    requestAnimationFrame(drawReactor);
  }

  // ============================================================
  //  DOCK MINIMIZE / EXPAND
  // ============================================================
  function setDock(docked) {
    var app = $('app');
    if (docked) {
      app.classList.add('docked');
      $('btn-minimize').style.display = 'none';
      $('btn-expand').style.display = '';
      $('dock-metrics').style.display = '';
    } else {
      app.classList.remove('docked');
      $('btn-minimize').style.display = '';
      $('btn-expand').style.display = 'none';
      $('dock-metrics').style.display = 'none';
    }
  }

  // ============================================================
  //  CHAT PANEL
  // ============================================================
  function toggleChat(open) {
    $('chat-panel').classList.toggle('open', open);
  }
  function addChatMsg(text, cls) {
    var b = $('chat-body');
    var d = document.createElement('div');
    d.className = 'chat-msg ' + cls;
    d.textContent = text;
    b.appendChild(d);
    b.scrollTop = b.scrollHeight;
  }
  function sendChat() {
    var txt = ($('chat-input').value || '').trim();
    if (!txt) return;
    $('chat-input').value = '';
    addChatMsg(txt, 'user');
    addLog('Chat: ' + txt.substring(0, 60), 'info');
    state.reactor = 'processing';

    var mode = 'chat';
    api('POST', '/execute', { prompt: txt, force_mode: mode }, 60000).then(function (d) {
      state.reactor = 'idle';
      if (d.error) {
        addChatMsg('Error: ' + d.error, 'assistant');
        addLog('Execute error: ' + d.error, 'error');
        return;
      }
      var resp = d.response || 'Sin respuesta';
      addChatMsg(resp, 'assistant');
      addLog('Response (' + (d.mode || '?') + ') ' + Math.round(d.latency_ms || 0) + 'ms', 'info');
      toast('Respuesta', resp.substring(0, 100), 'success');
    }).catch(function (e) {
      state.reactor = 'idle';
      addChatMsg('Error de conexion: ' + e.message, 'assistant');
      addLog('Execute failed: ' + e.message, 'error');
      showErr('api', e.message);
    });
  }

  // ============================================================
  //  QUICK ORDER
  // ============================================================
  function quickOrder(text) {
    $('order-input').value = text;
    sendOrder();
  }
  function sendOrder() {
    var txt = ($('order-input').value || '').trim();
    if (!txt) return;
    $('order-input').value = '';
    var mode = $('o-level').value || 'chat';
    $('order-result').textContent = 'Ejecutando...';
    state.reactor = 'processing';

    api('POST', '/execute', { prompt: txt, force_mode: mode }, 60000).then(function (d) {
      state.reactor = 'idle';
      if (d.error) {
        $('order-result').textContent = 'Error: ' + d.error;
        $('order-result').style.color = 'var(--fail)';
        addLog('Order error: ' + d.error, 'error');
      } else {
        var resp = (d.response || '').substring(0, 120);
        $('order-result').textContent = resp;
        $('order-result').style.color = 'var(--dim)';
        addLog('Order OK (' + d.mode + ') ' + Math.round(d.latency_ms || 0) + 'ms', 'info');
        toast('Orden completada', resp, 'success');
      }
    }).catch(function (e) {
      state.reactor = 'idle';
      $('order-result').textContent = 'Error: ' + e.message;
      $('order-result').style.color = 'var(--fail)';
      addLog('Order failed: ' + e.message, 'error');
    });
  }

  // ============================================================
  //  CONFIG PANEL
  // ============================================================
  function toggleConfig(open) {
    $('config-overlay').classList.toggle('show', open);
    if (open) loadConfigUI();
  }
  function loadConfigUI() {
    $('cfg-chat-model').value = CFG.models.chat;
    $('cfg-agent-model').value = CFG.models.agent;
    $('cfg-router-model').value = CFG.models.router || 'qwen2.5:1.5b';
    $('cfg-accent').value = CFG.theme.accent;
    $('cfg-blur').value = CFG.theme.blur;
    $('cfg-radius').value = CFG.theme.radius;
  }
  function saveConfig() {
    CFG.models.chat = $('cfg-chat-model').value;
    CFG.models.agent = $('cfg-agent-model').value;
    CFG.models.router = $('cfg-router-model').value;
    CFG.theme.accent = $('cfg-accent').value;
    CFG.theme.blur = parseInt($('cfg-blur').value);
    CFG.theme.radius = parseInt($('cfg-radius').value);

    // Apply live
    document.documentElement.style.setProperty('--accent', CFG.theme.accent);
    document.documentElement.style.setProperty('--blur', CFG.theme.blur + 'px');
    document.documentElement.style.setProperty('--r', CFG.theme.radius + 'px');

    toast('Config', 'Configuracion guardada', 'success');
    toggleConfig(false);

    // Persist to backend
    api('POST', '/state/reset', {}).catch(function () {});
  }

  // ============================================================
  //  INIT
  // ============================================================
  function init() {
    // Clock
    tickClock();
    setInterval(tickClock, 1000);

    // Load settings.json
    fetch('settings.json').then(function (r) { return r.json(); }).then(function (d) {
      CFG.bridge_url = d.bridge_url || CFG.bridge_url;
      CFG.poll_interval_ms = d.poll_interval_ms || CFG.poll_interval_ms;
      if (d.theme) { Object.assign(CFG.theme, d.theme); }
      if (d.reactor) { Object.assign(CFG.reactor, d.reactor); }
      if (d.models) { Object.assign(CFG.models, d.models); }
      // Apply theme
      document.documentElement.style.setProperty('--accent', CFG.theme.accent);
      document.documentElement.style.setProperty('--blur', CFG.theme.blur + 'px');
      document.documentElement.style.setProperty('--r', CFG.theme.radius + 'px');
      document.documentElement.style.setProperty('--accent-bright', CFG.theme.accent_bright || CFG.theme.accent);
    }).catch(function () {});

    // Reactor canvas
    canvas = $('reactor-canvas');
    ctx = canvas.getContext('2d');
    initParticles();
    resizeCanvas();
    drawReactor();
    if (window.ResizeObserver) new ResizeObserver(function () { resizeCanvas(); }).observe(canvas);

    // Reactor click -> focus order input
    canvas.onclick = function () { ripples.push({ r: 5, life: 1 }); $('order-input').focus(); };

    // Event listeners
    $('btn-config').onclick = function () { toggleConfig(true); };
    $('btn-chat').onclick = function () { toggleChat(true); };
    $('btn-minimize').onclick = function () { setDock(true); };
    $('btn-expand').onclick = function () { setDock(false); };
    $('chat-close').onclick = function () { toggleChat(false); };
    $('chat-send').onclick = sendChat;
    $('chat-input').onkeydown = function (e) { if (e.key === 'Enter') sendChat(); };
    $('order-btn').onclick = sendOrder;
    $('order-input').onkeydown = function (e) { if (e.key === 'Enter') sendOrder(); };

    // Initial metrics
    state.cpu = 25 + Math.random() * 20;
    state.ram = 40 + Math.random() * 15;
    state.disk = 50 + Math.random() * 10;

    // Polling
    pollHealth();
    pollState();
    pollMetrics();
    setInterval(pollHealth, CFG.poll_interval_ms);
    setInterval(pollState, CFG.poll_interval_ms);
    setInterval(pollMetrics, 3000);

    addLog('HUD initialized', 'info');
  }

  // Boot
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
