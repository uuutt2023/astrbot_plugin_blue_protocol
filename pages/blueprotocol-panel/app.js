(function () {
  "use strict";
  var I18N = window.BP_I18N || null;
  function t(key, vars) { return I18N ? I18N.t(key, vars) : key; }

  var state = {
    meta: {},
    status: {},
    groups: [],        // 主表格：{umo,label,group_id,group_name,enabled,last_pushed}
    pickGroups: [],    // 「选择群」弹窗：{value,label,group_id,group_name,enabled,source}
    picked: {},        // 弹窗里的勾选状态：umo -> bool
    pickLoaded: false,
    records: [],
    shots: [],
    testTarget: null,
    loaded: false
  };

  // ---------- 小工具 ----------

  function byId(id) { return document.getElementById(id); }

  var toastTimer = null;
  function toast(msg, isErr) {
    var el = byId("toast");
    el.textContent = String(msg || "");
    el.className = "toast show" + (isErr ? " err" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.className = "toast"; }, 3200);
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // 面板跑在 AstrBot 仪表盘的 iframe 里，浏览器会屏蔽 window.prompt/confirm，
  // 所以用页内弹窗替代（否则确认框点了没反应）。
  function _modal(opts) {
    return new Promise(function (resolve) {
      var mask = byId("modalMask");
      var input = byId("modalInput");
      byId("modalTitle").textContent = opts.title || "";
      byId("modalMsg").textContent = opts.message || "";
      input.hidden = !opts.prompt;
      if (opts.prompt) { input.value = opts.value || ""; }
      mask.hidden = false;
      var previousFocus = document.activeElement;
      byId("modalOk").focus();
      function cancelOnEscape(e) {
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); done(opts.prompt ? null : false); }
      }
      mask.addEventListener("keydown", cancelOnEscape);
      if (opts.prompt) { input.focus(); input.select(); }
      function done(val) {
        mask.hidden = true;
        mask.removeEventListener("keydown", cancelOnEscape);
        if (previousFocus && previousFocus.focus) previousFocus.focus();
        byId("modalOk").onclick = null;
        byId("modalCancel").onclick = null;
        input.onkeydown = null;
        resolve(val);
      }
      byId("modalOk").onclick = function () { done(opts.prompt ? input.value : true); };
      byId("modalCancel").onclick = function () { done(opts.prompt ? null : false); };
      input.onkeydown = function (e) {
        if (e.key === "Enter") { e.preventDefault(); done(input.value); }
        else if (e.key === "Escape") { e.preventDefault(); done(null); }
      };
    });
  }
  function promptModal(title, message, value) {
    return _modal({ prompt: true, title: title, message: message, value: value || "" });
  }
  function confirmModal(message, title) {
    return _modal({ prompt: false, title: title || t('confirm.defaultTitle'), message: message });
  }

  function fmtBytes(n) {
    n = Number(n) || 0;
    if (n >= 1048576) return (n / 1048576).toFixed(1) + " MB";
    if (n >= 1024) return (n / 1024).toFixed(0) + " KB";
    return n + " B";
  }

  // 后端统一返回 {status, message, data}；status 不是 ok 就抛出 message。
  function unwrap(resp) {
    if (resp && typeof resp === "object" && "status" in resp) {
      if (String(resp.status).toLowerCase() !== "ok") {
        throw new Error(resp.message || t('error.request'));
      }
      return resp.data || {};
    }
    return resp || {};
  }

  var _bridgeReady = null;
  function waitForBridge(timeoutMs) {
    if (_bridgeReady) return _bridgeReady;
    _bridgeReady = new Promise(function (resolve, reject) {
      var pollTimer;
      var expired = false;
      var timeout = setTimeout(function () {
        expired = true;
        clearTimeout(pollTimer);
        reject(new Error("Panel bridge unavailable — open this page from the AstrBot WebUI"));
      }, timeoutMs || 8000);
      function finish(error, bridge) {
        if (expired) return;
        clearTimeout(timeout);
        if (error) reject(error);
        else resolve(bridge);
      }
      (function poll() {
        var bridge = window.AstrBotPluginPage;
        if (!bridge) { pollTimer = setTimeout(poll, 32); return; }
        Promise.resolve().then(function () {
          if (typeof bridge.ready === "function") return bridge.ready();
        }).then(function () { finish(null, bridge); }, function (err) { finish(err); });
      })();
    }).catch(function (err) {
      _bridgeReady = null;
      throw err;
    });
    return _bridgeReady;
  }

  function apiGet(path, params) {
    return window.PanelUI.request(waitForBridge().then(function (bridge) {
      return bridge.apiGet(path, params || {}).then(unwrap);
    }));
  }

  function apiPost(path, body) {
    return window.PanelUI.request(waitForBridge().then(function (bridge) {
      return bridge.apiPost(path, body || {}).then(unwrap);
    }));
  }

  function fail(err) { toast((err && err.message) || t('error.generic'), true); }

  // ---------- 渲染 ----------

  /* 后端返回的 message 是英文的，面板按 reason / 计数自己出文案。 */
  var PUSH_REASONS = ['no_groups', 'no_list', 'fetch_failed', 'up_to_date', 'ok'];
  function pushMessage(d) {
    d = d || {};
    var reason = d.reason || '';
    if (PUSH_REASONS.indexOf(reason) < 0) return d.message || t('done');
    if (reason === 'ok') return t('push.reason.ok', { n: (d.pushed || []).length });
    return t('push.reason.' + reason);
  }
  function cacheMessage(d, kind) {
    d = d || {};
    if (kind === 'summary') return t('cache.summaryCleared', { n: d.removed || 0 });
    if (typeof d.removed === 'number') {
      return t('cache.deleted', { n: d.removed, size: fmtBytes(d.freed) });
    }
    return d.message || t('toast.cleared');
  }

  function renderStatus() {
    var st = state.status || {};
    var pill = byId("runPill");
    var hasGroups = (st.groups || []).length > 0;
    if (!hasGroups) {
      pill.textContent = t('status.noTargets');
      pill.className = "pill warn";
    } else if (st.running) {
      pill.textContent = t('status.running');
      pill.className = "pill";
    } else {
      pill.textContent = t('status.notStarted');
      pill.className = "pill off";
    }
    byId("stats").innerHTML = [
      '<div class="stat"><div class="n">' + esc((st.groups || []).length) + '</div><div class="l">' + t('stat.targets') + '</div></div>',
      '<div class="stat"><div class="n">' + esc(st.last_check_text || t('stat.never')) + '</div><div class="l">' + t('stat.lastCheck') + '</div></div>',
      '<div class="stat"><div class="n">' + (hasGroups ? (st.next_check_in || 0) + " s" : "—") + '</div><div class="l">' + t('stat.nextCheck') + '</div></div>',
      '<div class="stat"><div class="n">' + esc(st.shot_count || 0) + '</div><div class="l">' + t('stat.imageCache', { size: fmtBytes(st.shot_bytes) }) + '</div></div>',
      '<div class="stat"><div class="n">' + esc(st.summary_cache_count || 0) + '</div><div class="l">' + t('stat.summaryCache') + '</div></div>',
      '<div class="stat"><div class="n">' + esc(st.record_count || 0) + '</div><div class="l">' + t('stat.records') + '</div></div>'
    ].join("");
  }

  function renderGroups() {
    var tb = byId("groupBody");
    if (!state.groups.length) {
      tb.innerHTML = '<tr><td colspan="5" class="empty">' + esc(t('groups.empty')) + "</td></tr>";
      return;
    }
    tb.innerHTML = state.groups.map(function (g) {
      return "<tr>" +
        '<td><input type="checkbox" data-act="check" data-umo="' + esc(g.umo) + '"' +
          (g.enabled ? " checked" : "") + "></td>" +
        "<td>" + esc(g.group_name || g.label) +
          (g.group_name ? "" : ' <span class="tag warn">' + esc(t('group.noName')) + "</span>") + "</td>" +
        '<td class="nm">' + esc(g.group_id || "—") + "</td>" +
        "<td>" + (g.last_pushed ? esc(g.last_pushed) : '<span class="hint">' + esc(t('group.neverPushed')) + "</span>") + "</td>" +
        '<td class="acts">' +
          '<button class="link" data-act="test" data-umo="' + esc(g.umo) + '">' + esc(t('group.testPush')) + "</button>" +
          '<button class="link danger" data-act="reset" data-umo="' + esc(g.umo) + '">' + esc(t('group.reset')) + "</button>" +
        "</td></tr>";
    }).join("");
  }

  function renderRecords() {
    var box = byId("recordList");
    if (!state.records.length) {
      box.innerHTML = '<div class="empty">' + esc(t('records.empty')) + "</div>";
      byId("recordHint").textContent = "";
      return;
    }
    box.innerHTML = state.records.map(function (r) {
      return '<div class="list-item"><span class="nm" title="' + esc(r.title) + '">' +
        esc(r.label) + " · " + esc(r.title || t('records.emptyTitle')) + "</span>" +
        (r.umo ? '<button class="link" data-act="reset-one" data-umo="' + esc(r.umo) + '">' + esc(t('records.resetOne')) + "</button>" : "") +
        "</div>";
    }).join("");
    byId("recordHint").textContent = t('records.count', { n: state.records.length });
  }

  function renderShots() {
    var box = byId("gallery");
    var total = 0;
    state.shots.forEach(function (s) { total += Number(s.size) || 0; });
    byId("shotHint").textContent = state.shots.length
      ? t('cache.info', { n: state.shots.length, size: fmtBytes(total) })
      : t('cache.empty');
    if (!state.shots.length) { box.innerHTML = ""; return; }
    box.innerHTML = state.shots.map(function (s) {
      var inner = s.url
        ? '<img src="' + esc(s.url) + '" alt="' + esc(s.name) + '" loading="lazy">'
        : '<div class="cap">' + esc(t('cache.noPreview')) + "</div>";
      return '<div class="thumb">' + inner +
        '<div class="cap">' + esc(s.modified_text) + "<br>" + fmtBytes(s.size) + "<br>" +
        esc(s.name) + "</div></div>";
    }).join("");
  }

  function renderConfig() {
    var cfg = (state.meta || {}).config || {};
    byId("cfgShotEnabled").value = cfg.shot_enabled === false ? "0" : "1";
    byId("cfgShotHeight").value = cfg.shot_max_height == null ? "5000" : cfg.shot_max_height;
    byId("cfgShotQuality").value = cfg.shot_quality == null ? "88" : cfg.shot_quality;
    byId("cfgTypstEnabled").value = cfg.typst_enabled === false ? "0" : "1";
    byId("cfgTypstTheme").value = cfg.typst_long_theme || "dark";
    byId("cfgTypstWidth").value = cfg.typst_long_width == null ? "1280" : cfg.typst_long_width;
    byId("cfgTypstBodyWidth").value =
      cfg.typst_long_body_width == null ? "1258" : cfg.typst_long_body_width;
    byId("cfgTypstBorder").value = cfg.typst_long_border == null ? "11" : cfg.typst_long_border;
    byId("cfgTypstParaSpacing").value =
      cfg.typst_para_spacing == null ? "14" : cfg.typst_para_spacing;
    byId("cfgTypstLineHeight").value =
      cfg.typst_line_height == null ? "1.8" : cfg.typst_line_height;
    byId("cfgTypstModuleSpacing").value =
      cfg.typst_module_spacing == null ? "34" : cfg.typst_module_spacing;
    renderPrefixes();
    renderTypstStatus();
  }

  /* 指令前缀：输入框 + 当前生效的前缀 + 指令速查表 */
  function currentPrefixes() {
    var cfg = (state.meta || {}).config || {};
    var list = cfg.command_prefixes;
    if (typeof list === "string") list = list.split(/[,，;；\s]+/);
    if (!Array.isArray(list)) list = ["bp", "blue protocol"];
    list = list.map(function (x) { return String(x || "").trim(); })
               .filter(function (x) { return !!x; });
    return list.length ? list : ["bp", "blue protocol"];
  }

  function renderPrefixes() {
    var input = byId("cfgPrefixes");
    if (!input) return;
    var prefixes = currentPrefixes();
    if (document.activeElement !== input) input.value = prefixes.join(", ");
    byId("cfgPrefixHint").textContent = t('lbl.prefixesHint', { count: prefixes.length });
    renderCommandList(prefixes);
  }

  function renderCommandList(prefixes) {
    var box = byId("cmdList");
    if (!box) return;
    var head = prefixes[0] || "bp";
    var rows = [
      ['cmd.list', 'cmd.listDesc'],
      ['cmd.latest', 'cmd.latestDesc'],
      ['cmd.latestDedup', 'cmd.latestDedupDesc'],
      ['cmd.push', 'cmd.pushDesc'],
      ['cmd.reset', 'cmd.resetDesc'],
      ['cmd.help', 'cmd.helpDesc']
    ];
    var html = '';
    rows.forEach(function (row) {
      html += '<div class="cmd-item"><code>' + esc(head + ' ' + t(row[0])) +
              '</code><span>' + esc(t(row[1])) + '</span></div>';
    });
    box.innerHTML = html;
  }

  function renderTypstStatus() {
    var st = (state.meta || {}).typst || {};
    var node = byId("cfgTypstStatus");
    if (!node) return;
    if (!st.available) {
      node.textContent = t('typst.unavailable');
      return;
    }
    var fontKey = 'typst.font.' + (st.font_source || 'none');
    node.textContent = t('typst.status', { font: t(fontKey) });
  }

  /* ---------- 数据加载 ---------- */

  function loadMeta() {
    return apiGet("page/meta").then(function (d) {
      state.meta = d || {};
      renderConfig();
    });
  }

  function loadStatus() {
    return apiGet("page/status").then(function (d) {
      state.status = d || {};
      state.groups = (d.groups || []).map(function (g) {
        return {
          umo: g.umo, label: g.label, group_id: g.group_id,
          group_name: g.group_name || "", enabled: true,
          last_pushed: g.last_pushed || ""
        };
      });
      renderStatus();
      renderGroups();
    });
  }

  function loadRecords() {
    return apiGet("page/records").then(function (d) {
      state.records = d.records || [];
      renderRecords();
    });
  }

  function loadShots() {
    return apiGet("page/shots").then(function (d) {
      state.shots = d.shots || [];
      renderShots();
    });
  }

  function loadAll() {
    return Promise.all([loadMeta(), loadStatus(), loadRecords(), loadShots()]).then(function () {
      state.loaded = true;
    });
  }

  // ---------- 保存推送群 ----------

  function checkedUmOs() {
    var boxes = byId("groupBody").querySelectorAll('input[type="checkbox"][data-act="check"]');
    var out = [];
    Array.prototype.forEach.call(boxes, function (box) {
      if (box.checked) out.push(box.getAttribute("data-umo"));
    });
    return out;
  }

  function saveGroups() {
    var umos = checkedUmOs();
    var btn = byId("btnSaveGroups");
    btn.disabled = true;
    byId("saveHint").textContent = t('btn.saving');
    apiPost("page/groups/save", { groups: umos }).then(function () {
      byId("saveHint").textContent = "";
      return loadAll().then(function () { toast(t('toast.saved', { n: umos.length })); });
    }).catch(fail).then(function () {
      btn.disabled = false;
      byId("saveHint").textContent = "";
    });
  }

  // ---------- 手动推送 ----------

  function pushAll() {
    var btn = byId("btnPushAll");
    btn.disabled = true;
    byId("saveHint").textContent = t('checking');
    apiPost("page/push-now", {}).then(function (d) {
      byId("saveHint").textContent = "";
      toast(pushMessage(d), d.reason !== "ok" && d.reason !== "up_to_date");
      return loadAll();
    }).catch(fail).then(function () {
      btn.disabled = false;
      byId("saveHint").textContent = "";
    });
  }

  function openTest(umo) {
    var row = null;
    for (var i = 0; i < state.groups.length; i++) {
      if (state.groups[i].umo === umo) { row = state.groups[i]; }
    }
    state.testTarget = umo;
    byId("testTarget").textContent = t('test.target', {
      name: row ? (row.group_name || row.label) : umo,
      umo: umo
    });
    byId("testResult").textContent = "";
    byId("testForce").checked = true;
    byId("testMask").hidden = false;
  }

  function runTest() {
    if (!state.testTarget) return;
    var btn = byId("btnTestRun");
    btn.disabled = true;
    byId("testResult").textContent = t('pushing');
    apiPost("page/push-now", {
      umo: state.testTarget,
      force: byId("testForce").checked
    }).then(function (d) {
      byId("testResult").textContent = pushMessage(d);
      toast(pushMessage(d), !(d.pushed || []).length);
      return loadAll();
    }).catch(function (err) {
      byId("testResult").textContent = (err && err.message) || t('pushFailed');
      fail(err);
    }).then(function () { btn.disabled = false; });
  }

  // ---------- 推送记录 ----------

  function resetRecords(umo) {
    var tip = umo ? t('confirm.resetOne') : t('confirm.resetAll');
    confirmModal(tip, t('confirm.resetTitle')).then(function (ok) {
      if (!ok) return;
      apiPost("page/records/reset", umo ? { umo: umo } : {}).then(function () {
        return loadAll().then(function () { toast(t('toast.resetDone')); });
      }).catch(fail);
    });
  }

  // ---------- 缓存 / 参数 ----------

  function clearShots() {
    confirmModal(t('confirm.clearImages'), t('confirm.clearImagesTitle')).then(function (ok) {
      if (!ok) return;
      apiPost("page/shots/clear", {}).then(function (d) {
        return loadAll().then(function () { toast(cacheMessage(d)); });
      }).catch(fail);
    });
  }

  function clearCache() {
    apiPost("page/cache/clear", {}).then(function (d) {
      return loadAll().then(function () { toast(cacheMessage(d, 'summary')); });
    }).catch(fail);
  }

  function saveConfig() {
    var btn = byId("btnSaveConfig");
    btn.disabled = true;
    byId("cfgHint").textContent = t('btn.saving');
    apiPost("page/config/save", {
      shot_enabled: byId("cfgShotEnabled").value === "1",
      shot_max_height: byId("cfgShotHeight").value.trim(),
      shot_quality: byId("cfgShotQuality").value.trim(),
      typst_enabled: byId("cfgTypstEnabled").value === "1",
      typst_long_theme: byId("cfgTypstTheme").value,
      typst_long_width: byId("cfgTypstWidth").value.trim(),
      typst_long_body_width: byId("cfgTypstBodyWidth").value.trim(),
      typst_long_border: byId("cfgTypstBorder").value.trim(),
      typst_para_spacing: byId("cfgTypstParaSpacing").value.trim(),
      typst_line_height: byId("cfgTypstLineHeight").value.trim(),
      typst_module_spacing: byId("cfgTypstModuleSpacing").value.trim()
    }).then(function () {
      byId("cfgHint").textContent = "";
      return loadMeta().then(function () { toast(t('toast.settingsSaved')); });
    }).catch(fail).then(function () {
      btn.disabled = false;
      byId("cfgHint").textContent = "";
    });
  }

  function savePrefixes() {
    var btn = byId("btnSavePrefixes");
    var raw = byId("cfgPrefixes").value;
    btn.disabled = true;
    byId("cmdHint").textContent = t('btn.saving');
    apiPost("page/config/save", { command_prefixes: raw }).then(function (res) {
      if (res && res.status !== "ok") {
        byId("cmdHint").textContent = (res && res.message) || t("loadFailed");
        return;
      }
      byId("cmdHint").textContent = "";
      return loadMeta().then(function () { toast(t('toast.prefixesSaved')); });
    }).catch(fail).then(function () {
      btn.disabled = false;
      byId("cmdHint").textContent = "";
    });
  }

  // ---------- 选择群弹窗 ----------

  function loadPickGroups(refresh) {
    return apiGet("page/groups", refresh ? { refresh: "1" } : {}).then(function (d) {
      state.pickGroups = d.groups || [];
      state.pickLoaded = true;
      // 用当前表格的勾选状态初始化弹窗勾选（表格里没有的按后端 enabled）
      var current = {};
      checkedUmOs().forEach(function (u) { current[u] = true; });
      var next = {};
      state.pickGroups.forEach(function (g) {
        next[g.value] = current[g.value] === undefined ? !!g.enabled : !!current[g.value];
      });
      state.picked = next;
      renderPickList();
      byId("pickHint").textContent = d.total
        ? t('pick.summary', { n: d.total, m: countPicked() })
        : t('pick.empty');
      if (refresh) toast(t('toast.refreshedGroups', { n: d.refreshed || 0 }));
      return state.pickGroups;
    });
  }

  function countPicked() {
    var n = 0;
    Object.keys(state.picked).forEach(function (k) { if (state.picked[k]) n++; });
    return n;
  }

  function openPick() {
    byId("pickSearch").value = "";
    byId("pickMask").hidden = false;
    renderPickList();
    byId("pickSearch").focus();
    if (!state.pickLoaded) loadPickGroups(false).catch(fail);
  }

  function renderPickList() {
    var box = byId("pickList");
    if (!state.pickLoaded) {
      box.innerHTML = '<div class="empty">' + esc(t('pick.loading')) + "</div>";
      return;
    }
    var kw = (byId("pickSearch").value || "").trim().toLowerCase();
    var rows = state.pickGroups.filter(function (g) {
      if (!kw) return true;
      return (String(g.label) + " " + (g.group_name || "") + " " + (g.group_id || ""))
        .toLowerCase().indexOf(kw) >= 0;
    });
    if (!rows.length) {
      box.innerHTML = '<div class="empty">' + esc(t('pick.noMatch')) + "</div>";
      return;
    }
    box.innerHTML = rows.map(function (g) {
      var sub = [];
      if (g.group_id) sub.push(t('pick.id', { id: g.group_id }));
      sub.push(g.source === "pushed" ? t('pick.inList') : t('pick.seen'));
      return '<label class="pick-item">' +
        '<input type="checkbox" data-pick="' + esc(g.value) + '"' +
          (state.picked[g.value] ? " checked" : "") + ">" +
        '<span class="nm">' + esc(g.group_name || g.label) + "</span>" +
        '<span class="sub">' + esc(sub.join(" · ")) + "</span></label>";
    }).join("");
  }

  function applyPick() {
    // 把弹窗勾选结果灌回主表格：勾上的补进列表，去掉的如果是「机器人所见」就直接移除
    var tips = {};
    var verified = {};
    Object.keys(state.picked).forEach(function (umo) {
      if (state.picked[umo]) tips[umo] = true;
    });
    state.pickGroups.forEach(function (g) {
      if (state.picked[g.value]) verified[g.value] = g;
    });

    var rows = [];
    state.groups.forEach(function (g) {
      if (verified[g.umo]) { rows.push(g); tips[g.umo] = true; }
    });
    Object.keys(tips).forEach(function (umo) {
      var exists = rows.some(function (r) { return r.umo === umo; });
      if (exists) return;
      var meta = verified[umo] || {};
      rows.push({
        umo: umo,
        label: meta.label || umo,
        group_id: meta.group_id || "",
        group_name: meta.group_name || "",
        enabled: true,
        last_pushed: ""
      });
    });
    state.groups = rows;
    renderGroups();
    byId("pickMask").hidden = true;
    toast(t('toast.selected', { n: rows.length }));
  }

  // ---------- 绑定 & 启动 ----------

  function bind() {
    byId("btnReload").addEventListener("click", function () {
      loadAll().then(function () { toast(t('toast.refreshed')); }).catch(fail);
    });
    byId("btnSaveGroups").addEventListener("click", saveGroups);
    byId("btnPushAll").addEventListener("click", pushAll);
    byId("btnResetAll").addEventListener("click", function () { resetRecords(""); });
    byId("btnClearShots").addEventListener("click", clearShots);
    byId("btnClearCache").addEventListener("click", clearCache);
    byId("btnSaveConfig").addEventListener("click", saveConfig);
    byId("btnSavePrefixes").addEventListener("click", savePrefixes);
    byId("btnPickGroup").addEventListener("click", openPick);
    byId("pickClose").addEventListener("click", function () { byId("pickMask").hidden = true; });
    byId("btnPickApply").addEventListener("click", applyPick);
    byId("pickSearch").addEventListener("input", renderPickList);
    byId("btnPickRefresh").addEventListener("click", function () {
      loadPickGroups(true).catch(fail);
    });
    byId("pickList").addEventListener("change", function (e) {
      var box = e.target;
      if (!box || box.type !== "checkbox") return;
      var umo = box.getAttribute("data-pick");
      if (!umo) return;
      state.picked[umo] = box.checked;
      byId("pickHint").textContent = t('pick.summary', {
        n: state.pickGroups.length, m: countPicked()
      });
    });

    byId("groupBody").addEventListener("click", function (e) {
      var el = e.target;
      if (!el || el.tagName !== "BUTTON") return;
      var act = el.getAttribute("data-act");
      var umo = el.getAttribute("data-umo");
      if (act === "test") openTest(umo);
      else if (act === "reset") resetRecords(umo);
    });

    byId("recordList").addEventListener("click", function (e) {
      var el = e.target;
      if (!el || el.tagName !== "BUTTON" || el.getAttribute("data-act") !== "reset-one") return;
      resetRecords(el.getAttribute("data-umo"));
    });

    byId("testClose").addEventListener("click", function () { byId("testMask").hidden = true; });
    byId("btnTestRun").addEventListener("click", runTest);

    ["pickMask", "testMask"].forEach(function (id) {
      byId(id).addEventListener("click", function (e) {
        if (e.target === this) this.hidden = true;
      });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      ["pickMask", "testMask"].forEach(function (id) { byId(id).hidden = true; });
    });
  }

  /* 切语言：把动态渲染的内容重画一遍 */
  function rerender() {
    if (!state.loaded) return;
    renderStatus();
    renderGroups();
    renderRecords();
    renderShots();
    renderTypstStatus();   // 只刷新文案，不动用户还没保存的输入框
    renderCommandList(currentPrefixes());
    if (state.pickLoaded) renderPickList();
  }
  if (window.PanelI18n && window.PanelI18n.onChange) window.PanelI18n.onChange(rerender);

  bind();
  byId("groupBody").innerHTML = '<tr><td colspan="5" class="empty">' + esc(t('connecting')) + "</td></tr>";
  waitForBridge()
    .then(loadAll)
    .catch(function (err) {
      byId("groupBody").innerHTML = '<tr><td colspan="5" class="empty">' +
        esc((err && err.message) || t('loadFailed')) + "</td></tr>";
      fail(err);
    });
})();
