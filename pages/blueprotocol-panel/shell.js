/* Standalone panel shell. Local resources only; no framework or external assets. */
(function () {
  "use strict";
  /* i18n.js 没加载上时退化成"显示 key"，不至于整页白屏 */
  var I18N = window.BP_I18N || null;
  function t(key, vars) { return I18N ? I18N.t(key, vars) : key; }

  /* 文案全部走 i18n：c 里存 key，渲染时再翻 */
  var c = {
    titleKey: 'brand.title',
    brandKey: 'brand.tagline',
    heroKey: 'brand.hero',
    subKey: 'brand.sub',
    color: 'star',
    version: 'v1.0.0',
    views: [
      ['groups', 'nav.groups', 'DELIVERY', [0]],
      ['records', 'nav.records', 'HISTORY', [1]],
      ['settings', 'nav.settings', 'RENDER SETTINGS', [2]],
      ['commands', 'nav.commands', 'COMMANDS', [3]],
      ['cache', 'nav.cache', 'IMAGE ARCHIVE', [4]]
    ]
  };
  var root = document.documentElement;
  var wrap = document.querySelector('.wrap');
  var bar = wrap.querySelector('.topbar');
  var stats = document.getElementById('stats');
  var cards = Array.from(wrap.querySelectorAll(':scope > .card, :scope > .grid2 > .card'));
  var prefs = { theme: 'follow', compact: false };
  var storageKey = 'panelAppearance:' + c.color;
  var follow = 'light';
  var themeObserver;
  var pending = 0;
  var failed = false;
  /* 手动管理的文案：切语言时要单独刷一遍 */
  var manualText = [];

  function el(tag, cls, text, key) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (key) node.setAttribute('data-i18n', key);
    if (text != null) node.textContent = text;
    return node;
  }
  function button(text, fn, cls, key) {
    var node = el('button', cls, text, key);
    node.type = 'button';
    node.addEventListener('click', fn); return node;
  }
  root.dataset.palette = c.color;
  var layout = el('div', 'workspace');
  var rail = el('aside', 'rail');
  var brand = el('a', 'brand'); brand.href = '#overview';
  brand.append(el('span', 'brand-symbol', 'BP'));
  var brandText = el('span');
  brandText.append(el('strong', '', t(c.titleKey), c.titleKey), el('small', '', t(c.brandKey), c.brandKey));
  brand.append(brandText);
  rail.append(brand, el('div', 'nav-label', t('nav.workspace'), 'nav.workspace'));
  var nav = el('nav'); nav.setAttribute('aria-label', t('nav.aria')); rail.append(nav);
  var railFooter = el('div', 'rail-footer');
  var connection = el('span', 'connection', t('status.connecting'));
  railFooter.append(connection, el('small', '', c.version + ' · ASTRBOT PLUGIN')); rail.append(railFooter);
  var stage = el('main', 'stage'); stage.id = 'main-content'; stage.tabIndex = -1;
  var header = el('header', 'workspace-header');
  var crumb = el('div', 'breadcrumb', t(c.brandKey));
  var tools = el('div', 'header-tools');
  var pill = bar.querySelector('.pill'); if (pill) tools.append(pill);
  var themeButton = button(t('theme.dark'), function () { prefs.theme = root.dataset.theme === 'dark' ? 'light' : 'dark'; savePrefs(); });
  themeButton.id = 'panelTheme'; tools.append(themeButton);
  /* 语言切换按钮：显示的是"另一种语言"，点了就切过去 */
  var langButton = button(t('lang.button'), function () { if (I18N) I18N.toggle(); });
  langButton.id = 'panelLang';
  langButton.setAttribute('data-i18n', 'lang.button');
  langButton.setAttribute('data-i18n-aria-label', 'lang.aria');
  tools.append(langButton);
  // Preserve the original business action nodes and all their event handlers.
  var actionBar = el('div', 'workspace-actions');
  Array.from(bar.querySelectorAll('button')).forEach(function (node) { actionBar.append(node); });
  header.append(crumb, tools); stage.append(header);
  var content = el('div', 'workspace-content');
  var heading = el('div', 'page-heading'); var headingText = el('div');
  var eyebrow = el('span', 'eyebrow'); var title = el('h1');
  headingText.append(eyebrow, title); heading.append(headingText, actionBar); content.append(heading);
  var feedback = el('div', 'request-feedback'); feedback.hidden = true; feedback.setAttribute('role', 'alert'); content.append(feedback);
  var sync = el('div', 'sync-line', t('sync.notSynced')); sync.setAttribute('role', 'status'); content.append(sync);
  var views = {};
  function addView(key, labelKey, english, node) {
    node.classList.add('panel-view'); node.id = 'panel-' + key; node.hidden = true;
    node.setAttribute('aria-label', t(labelKey));
    content.append(node);
    var item = button('', function () { location.hash = key; }, 'nav-item');
    var index = Object.keys(views).length + 1;
    item.append(el('span', 'nav-number', String(index).padStart(2, '0')), el('span', 'nav-text', t(labelKey), labelKey), el('span', 'nav-arrow', '↗'));
    item.setAttribute('aria-label', t(labelKey)); nav.append(item);
    views[key] = { labelKey: labelKey, english: english, node: node, button: item };
  }
  var overview = el('section');
  var hero = el('div', 'hero'); var copy = el('div', 'hero-copy');
  copy.append(el('span', 'eyebrow', t(c.brandKey), c.brandKey), el('h2', '', t(c.heroKey), c.heroKey), el('p', '', t(c.subKey), c.subKey));
  var heroCta = button(t('hero.open', { view: t(c.views[0][1]) }), function () { location.hash = c.views[0][0]; }, 'primary');
  copy.append(heroCta);
  var art = el('div', 'hero-art'); art.setAttribute('aria-hidden', 'true');
  art.append(el('span', 'art-orbit'), document.getElementById('heroArtTemplate').content.cloneNode(true), el('span', 'art-caption', t('art.caption'), 'art.caption'));
  hero.append(copy, art); overview.append(hero);
  var statsTitle = el('div', 'section-heading');
  statsTitle.append(el('h2', '', t('overview.heading'), 'overview.heading'), el('span', 'hint', t('overview.hint'), 'overview.hint'));
  overview.append(statsTitle, stats);
  var shortcuts = el('div', 'shortcuts');
  c.views.forEach(function (v) {
    var b = button('', function () { location.hash = v[0]; }, 'shortcut');
    var strong = el('strong');
    strong.append(el('span', '', '', v[1]), document.createTextNode('  →'));
    b.append(el('span', 'eyebrow', v[2]), strong);
    shortcuts.append(b);
  });
  overview.append(shortcuts); addView('overview', 'nav.overview', 'OVERVIEW', overview);
  c.views.forEach(function (v) { var section = el('section'); v[3].forEach(function (i) { if (cards[i]) section.append(cards[i]); }); addView(v[0], v[1], v[2], section); });
  var appearance = el('section');
  var appearanceCard = el('div', 'card appearance-card');
  appearanceCard.innerHTML = '<span class="eyebrow" data-i18n="appearance.eyebrow">PERSONALIZE YOUR WORKSPACE</span>' +
    '<h2 data-i18n="appearance.title">Choose a comfortable workspace</h2>' +
    '<p class="hint" data-i18n="appearance.hint"></p>' +
    '<div class="field"><label for="panelThemeSelect" data-i18n="appearance.theme">Theme</label>' +
    '<select id="panelThemeSelect">' +
    '<option value="follow" data-i18n="appearance.themeFollow">Follow AstrBot</option>' +
    '<option value="light" data-i18n="appearance.themeLight">Light · day</option>' +
    '<option value="dark" data-i18n="appearance.themeDark">Dark · night</option>' +
    '</select></div>' +
    '<div class="field"><label for="panelLangSelect" data-i18n="appearance.language">Language</label>' +
    '<select id="panelLangSelect"><option value="en">English</option><option value="zh">中文</option></select></div>' +
    '<label class="compact-row"><span><span data-i18n="appearance.compact">Compact layout</span>' +
    '<small data-i18n="appearance.compactHint"></small></span>' +
    '<input id="panelCompact" type="checkbox"></label>' +
    '<p class="hint" id="panelPreferenceHint" role="status"></p>';
  appearance.append(appearanceCard); addView('appearance', 'nav.appearance', 'APPEARANCE', appearance);
  var footer = el('footer', 'workspace-footer');
  content.append(footer);
  stage.append(content); layout.append(rail, stage);
  wrap.replaceWith(layout);
  var skip = el('a', 'skip-link', t('skip'), 'skip'); skip.href = '#main-content'; document.body.prepend(skip);

  function showView() {
    var key = location.hash.slice(1); if (!Object.prototype.hasOwnProperty.call(views, key)) key = 'overview';
    Object.keys(views).forEach(function (k) {
      var v = views[k]; v.node.hidden = k !== key; v.button.classList.toggle('active', k === key);
      if (k === key) v.button.setAttribute('aria-current', 'page'); else v.button.removeAttribute('aria-current');
    });
    title.textContent = t(views[key].labelKey); eyebrow.textContent = views[key].english;
  }
  window.addEventListener('hashchange', showView); showView();
  var themeSelect = document.getElementById('panelThemeSelect');
  var langSelect = document.getElementById('panelLangSelect');
  var compact = document.getElementById('panelCompact');
  function applyPrefs() {
    if (themeObserver) themeObserver.disconnect();
    root.dataset.theme = prefs.theme === 'follow' ? follow : prefs.theme; root.dataset.compact = String(prefs.compact);
    themeSelect.value = prefs.theme; compact.checked = prefs.compact;
    if (langSelect && I18N) langSelect.value = I18N.get();
    themeButton.textContent = root.dataset.theme === 'dark' ? t('theme.light') : t('theme.dark');
    themeButton.setAttribute('aria-label', root.dataset.theme === 'dark' ? t('theme.ariaLight') : t('theme.ariaDark'));
    if (themeObserver) themeObserver.observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  }
  function savePrefs() {
    applyPrefs();
    var hint = document.getElementById('panelPreferenceHint');
    try { localStorage.setItem(storageKey, JSON.stringify(prefs)); hint.textContent = t('appearance.saved'); }
    catch (e) { hint.textContent = t('appearance.blocked'); }
  }
  themeSelect.addEventListener('change', function () { prefs.theme = this.value; savePrefs(); });
  compact.addEventListener('change', function () { prefs.compact = this.checked; savePrefs(); });
  if (langSelect && I18N) langSelect.addEventListener('change', function () { I18N.set(this.value); });
  var params = new URLSearchParams(location.search); var host = params.get('theme') || root.dataset.theme;
  if (host !== 'dark' && host !== 'light') { var d = params.get('isDark'); try { if (d === null) d = localStorage.getItem('astrbot_plugin_theme_is_dark'); } catch (e) { } host = d === 'true' ? 'dark' : 'light'; } follow = host;
  try { var saved = JSON.parse(localStorage.getItem(storageKey) || '{}'); if (['light', 'dark', 'follow'].includes(saved.theme)) prefs.theme = saved.theme; if (typeof saved.compact === 'boolean') prefs.compact = saved.compact; } catch (e) { }
  themeObserver = new MutationObserver(function () { var theme = root.dataset.theme; if (theme === 'dark' || theme === 'light') follow = theme; applyPrefs(); }); applyPrefs();
  window.addEventListener('storage', function (e) { if (e.key === 'astrbot_plugin_theme_is_dark') { follow = e.newValue === 'true' ? 'dark' : 'light'; applyPrefs(); } });
  // Make every existing table scroll inside its card instead of widening the page.
  document.querySelectorAll('.card > table').forEach(function (table) { var scroll = el('div', 'table-wrap'); table.replaceWith(scroll); scroll.append(table); });
  document.querySelectorAll('.table-wrap').forEach(function (node) { node.tabIndex = 0; node.setAttribute('aria-label', t('table.aria')); });

  /* ---------- 切语言：刷手动文案 + 重跑视图标题 ---------- */
  function refreshTexts() {
    crumb.textContent = t(c.brandKey);
    brandText.firstChild.textContent = t(c.titleKey);
    brandText.lastChild.textContent = t(c.brandKey);
    nav.setAttribute('aria-label', t('nav.aria'));
    connection.textContent = failed ? t('status.error') : t('status.connected');
    heroCta.textContent = t('hero.open', { view: t(c.views[0][1]) });
    footer.textContent = t('footer', { brand: t(c.brandKey) });
    Object.keys(views).forEach(function (k) {
      var v = views[k];
      v.node.setAttribute('aria-label', t(v.labelKey));
      v.button.setAttribute('aria-label', t(v.labelKey));
    });
    document.querySelectorAll('.table-wrap').forEach(function (node) { node.setAttribute('aria-label', t('table.aria')); });
    showView();
    applyPrefs();
    manualText.forEach(function (fn) { try { fn(); } catch (e) { /* ignore */ } });
  }
  if (I18N) {
    I18N.apply(document);
    I18N.onChange(function () { refreshTexts(); });
  }
  /* app.js 里的动态文案也要跟着刷 */
  window.PanelI18n = {
    onChange: function (fn) { manualText.push(fn); },
    refresh: refreshTexts
  };

  var toast = document.getElementById('toast'); toast.setAttribute('role', 'status'); toast.setAttribute('aria-live', 'polite');
  document.querySelectorAll('.modal-mask').forEach(function (mask, index) {
    var dialog = mask.querySelector('.modal'); dialog.setAttribute('role', 'dialog'); dialog.setAttribute('aria-modal', 'true');
    var h = dialog.querySelector('h2'); if (h) { if (!h.id) h.id = 'dialog-heading-' + index; dialog.setAttribute('aria-labelledby', h.id); }
    var previous = null; var wasHidden = mask.hidden;
    new MutationObserver(function () { if (mask.hidden === wasHidden) return; wasHidden = mask.hidden;
      if (!mask.hidden) { previous = document.activeElement; if (!mask.contains(previous)) { var focus = mask.querySelector('input:not([hidden]),select,textarea,button'); if (focus) focus.focus(); } }
      else if (previous && !mask.contains(previous) && previous.isConnected) previous.focus();
    }).observe(mask, { attributes: true, attributeFilter: ['hidden'] });
    mask.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var items = Array.from(mask.querySelectorAll('button,input,textarea,select,[tabindex="0"]')).filter(function (n) { return !n.disabled && n.getClientRects().length; });
      if (!items.length) return; var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  });
  window.PanelUI = {
    request: function (promise) {
      if (!pending) { failed = false; feedback.hidden = true; } pending++; connection.textContent = t('status.syncing');
      return promise.then(function (data) { sync.textContent = t('sync.lastRead', { time: new Date().toLocaleTimeString('en-US', { hour12: false }) }); return data; },
        function (error) {
          failed = true; feedback.hidden = false;
          feedback.textContent = t('error.action', { msg: (error && error.message) || t('error.request') });
          throw error;
        }).finally(function () {
          pending--;
          if (!pending) { connection.textContent = failed ? t('status.error') : t('status.connected'); connection.classList.toggle('error', failed); }
        });
    }
  };
})();
