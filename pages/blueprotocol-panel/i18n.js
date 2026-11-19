/* Blue Protocol 面板文案表 + 语言切换（English / 中文）。
 *
 * 语言判定顺序：
 *   1. 手动切换过 → 用 localStorage 里的选择（优先级最高）
 *   2. 浏览器时区在中国大陆/港澳台 → 中文
 *   3. 浏览器语言是 zh* → 中文
 *   4. 其余（海外时区）→ English
 *
 * 用法：
 *   BP_I18N.t('key')                  取文案
 *   BP_I18N.t('key', {n: 3})          取文案并替换 {n} 占位
 *   BP_I18N.apply(root)               把 [data-i18n] 标记的节点刷成当前语言
 *   BP_I18N.set('zh') / .toggle()    切语言（会触发 onChange 回调）
 *
 * 元素上可以用的标记：
 *   data-i18n="key"                   文本
 *   data-i18n-placeholder="key"       placeholder
 *   data-i18n-aria-label="key"        aria-label
 *   data-i18n-title="key"            title
 */
(function () {
  "use strict";

  var STORAGE_KEY = 'panelLang';
  /* 中国大陆 + 港澳台的时区：命中即默认中文 */
  var CN_ZONES = [
    'Asia/Shanghai', 'Asia/Chongqing', 'Asia/Chungking', 'Asia/Harbin',
    'Asia/Kashgar', 'Asia/Urumqi', 'Asia/Macau', 'Asia/Hong_Kong',
    'Asia/Taipei'
  ];

  var DICT = {
    en: {
      /* ---------- 顶部 / 品牌 ---------- */
      'top.title': 'Blue Protocol: Star Resonance',
      'top.pick': 'Select groups…',
      'top.reload': 'Refresh',
      'brand.title': 'Blue Protocol: Star Resonance',
      'brand.tagline': 'BLUE PROTOCOL / NEWSROOM',
      'brand.hero': 'Resonance news,\none page.\n',
      'brand.sub': 'From official announcements to group alerts — manage your Blue Protocol: Star Resonance news feed.',
      'art.caption': 'STAR RESONANCE · ADVENTURERS',

      /* ---------- 导航 ---------- */
      'nav.overview': 'Overview',
      'nav.groups': 'Push targets',
      'nav.records': 'Push records',
      'nav.settings': 'Image settings',
      'nav.cache': 'Image cache',
      'nav.appearance': 'Appearance',
      'nav.workspace': 'WORKSPACE',
      'nav.aria': 'Page navigation',
      'hero.open': 'Open {view}  ↗',
      'overview.heading': 'Runtime overview',
      'overview.hint': 'Figures reflect the last read',
      'footer': '{brand}  /  BUILT FOR EVERY CONNECTION',
      'skip': 'Skip to main content',

      /* ---------- 状态 ---------- */
      'status.connecting': 'Connecting',
      'status.connected': 'Panel connected',
      'status.syncing': 'Syncing',
      'status.error': 'Connection or action error',
      'sync.notSynced': 'Not synced yet',
      'sync.lastRead': 'Last read · {time}',
      'error.action': 'Action failed: {msg}. Please retry the action, or reload the page to reconnect.',
      'error.request': 'Request failed',
      'error.generic': 'Action failed',
      'confirm.defaultTitle': 'Confirm',

      /* ---------- 外观 ---------- */
      'theme.dark': '☾ Dark',
      'theme.light': '☀ Light',
      'theme.ariaDark': 'Switch to dark theme',
      'theme.ariaLight': 'Switch to light theme',
      'appearance.eyebrow': 'PERSONALIZE YOUR WORKSPACE',
      'appearance.title': 'Choose a comfortable workspace',
      'appearance.hint': 'Affects this browser only — it does not change the plugin config, message cards, or the view of other admins.',
      'appearance.theme': 'Theme',
      'appearance.themeFollow': 'Follow AstrBot',
      'appearance.themeLight': 'Light · day',
      'appearance.themeDark': 'Dark · night',
      'appearance.language': 'Language',
      'appearance.compact': 'Compact layout',
      'appearance.compactHint': 'Tighten card and table spacing to fit more content',
      'appearance.saved': 'Preferences saved to this browser.',
      'appearance.blocked': 'Storage is blocked — appearance applies to this session only.',
      'lang.button': '中文',
      'lang.aria': 'Switch the panel to Chinese',

      /* ---------- 推送群 ---------- */
      'card.targets.title': 'Push targets',
      'card.targets.hint': 'Tick the groups that should receive Blue Protocol announcements automatically (checked every 5 minutes, pushed only when something is new). Saving takes effect immediately — same as sending "bp push on" in the group.',
      'th.push': 'Push',
      'th.group': 'Group',
      'th.groupId': 'Group ID',
      'th.lastPushed': 'Last pushed announcement',
      'th.actions': 'Actions',
      'btn.saveTargets': 'Save push targets',
      'btn.pushAll': 'Check & push now (all groups)',
      'btn.saving': 'Saving…',
      'toast.saved': 'Saved {n} push target(s)',
      'toast.selected': '{n} group(s) selected — remember to click "Save push targets"',
      'checking': 'Checking for announcements…',
      'done': 'Done',

      /* ---------- 推送记录 ---------- */
      'card.records.title': 'Push records',
      'card.records.hint': 'The last announcement pushed to each group, used for deduplication. Reset it and the next check will push the newest announcement again.',
      'btn.clearRecords': 'Clear all records',
      'records.empty': 'No push records yet (they appear after the first successful push)',
      'records.emptyTitle': '(empty)',
      'records.resetOne': 'Reset',
      'records.count': '{n} record(s)',
      'toast.resetDone': 'Reset done',
      'confirm.resetOne': 'Reset the push record for this group?',
      'confirm.resetAll': 'Clear every push record? The next check will push the newest announcement again.',
      'confirm.resetTitle': 'Reset push records',

      /* ---------- 公告图设置 ---------- */
      'card.settings.title': 'Long-image settings',
      'lbl.longImage': 'Render announcements as a phone-sized long image',
      'opt.longImageOn': 'Enabled (render the announcement body)',
      'opt.longImageOff': 'Disabled (use the dark card image)',
      'lbl.maxHeight': 'Maximum height (CSS pixels, 0 = no limit)',
      'lbl.quality': 'JPEG quality (1-100)',
      'btn.saveSettings': 'Save settings',
      'toast.settingsSaved': 'Settings saved',

      /* ---------- 截图缓存 ---------- */
      'card.cache.title': 'Image cache',
      'btn.clearSummary': 'Clear summary cache',
      'btn.clearImages': 'Clear images',
      'cache.info': '{n} image(s), {size} (keeps the newest 20 / 7 days)',
      'cache.empty': 'No cached images yet (they appear after the first announcement push)',
      'cache.noPreview': '(preview unavailable, filename only)',
      'confirm.clearImages': 'Clear the image cache? The next push will render them again.',
      'confirm.clearImagesTitle': 'Clear image cache',
      'toast.cleared': 'Cleared',
      'cache.deleted': 'Deleted {n} image(s), freed {size}',
      'cache.summaryCleared': 'Cleared {n} summary cache entr(y/ies)',
      'page.title': 'Blue Protocol: Star Resonance — Announcements',
      'push.reason.no_groups': 'No push targets yet — pick groups in the panel, or send "bp push on" in a group.',
      'push.reason.no_list': 'The announcement list came back empty (the data source returned nothing).',
      'push.reason.fetch_failed': 'Failed to fetch the announcement list.',
      'push.reason.up_to_date': 'The latest announcement was already pushed — nothing new.',
      'push.reason.ok': 'Pushed to {n} group(s).',

      /* ---------- 选择群弹窗 ---------- */
      'modal.pick.title': 'Select push targets',
      'lbl.search': 'Search by group name / group ID',
      'ph.search': 'e.g. BlueProtocol or 339466990',
      'btn.refreshGroups': 'Refresh group list',
      'btn.applyPick': 'Replace list with selection',
      'btn.cancel': 'Cancel',
      'btn.close': 'Close',
      'btn.ok': 'OK',
      'pick.summary': '{n} session(s), {m} selected',
      'pick.empty': 'No sessions yet — click "Refresh group list" or talk in a group first',
      'pick.loading': 'Loading group list…',
      'pick.noMatch': 'No matching sessions. Try another term, or click "Refresh group list".',
      'pick.id': 'ID {id}',
      'pick.inList': 'in push list',
      'pick.seen': 'seen by the bot',
      'toast.refreshedGroups': 'Group list refreshed ({n} updated)',

      /* ---------- 测试推送弹窗 ---------- */
      'modal.test.title': 'Test push',
      'lbl.force': 'Force re-send (ignore the "already pushed" record)',
      'btn.startPush': 'Start push',
      'pushing': 'Pushing…',
      'pushFailed': 'Push failed',
      'test.target': 'Push to: {name} ({umo})',

      /* ---------- 运行速览 ---------- */
      'status.noTargets': 'No push targets',
      'status.running': 'Scheduler running',
      'status.notStarted': 'Scheduler not started',
      'stat.targets': 'Push targets',
      'stat.lastCheck': 'Last check',
      'stat.never': 'Never',
      'stat.nextCheck': 'Next check in',
      'stat.imageCache': 'Image cache ({size})',
      'stat.summaryCache': 'Summary cache',
      'stat.records': 'Push records',

      /* ---------- 群列表 ---------- */
      'groups.empty': 'No push targets yet — click "Select groups…", or send "bp push on" in a group',
      'group.noName': 'No name',
      'group.neverPushed': 'Never pushed',
      'group.testPush': 'Test push',
      'group.reset': 'Reset',
      'table.aria': 'Data table, scroll horizontally',
      'connecting': 'Connecting to the panel…',
      'loadFailed': 'Failed to load',
      'toast.refreshed': 'Refreshed'
    },

    zh: {
      /* ---------- 顶部 / 品牌 ---------- */
      'top.title': 'Blue Protocol: Star Resonance',
      'top.pick': '选择群…',
      'top.reload': '刷新',
      'brand.title': 'Blue Protocol: Star Resonance',
      'brand.tagline': 'BLUE PROTOCOL / NEWSROOM',
      'brand.hero': '共鸣新讯，\n一页尽知。\n',
      'brand.sub': '从官方公告到群内提醒，管理你的 Blue Protocol: Star Resonance 资讯推送。',
      'art.caption': '星痕共鸣 · 冒险者之家',

      /* ---------- 导航 ---------- */
      'nav.overview': '总览',
      'nav.groups': '推送群',
      'nav.records': '推送记录',
      'nav.settings': '公告图设置',
      'nav.cache': '截图缓存',
      'nav.appearance': '界面外观',
      'nav.workspace': '工作空间',
      'nav.aria': '页面导航',
      'hero.open': '进入{view}  ↗',
      'overview.heading': '运行速览',
      'overview.hint': '数据以最近一次读取为准',
      'footer': '{brand}  /  为每一次连接而设计',
      'skip': '跳到主要内容',

      /* ---------- 状态 ---------- */
      'status.connecting': '等待连接',
      'status.connected': '面板已连接',
      'status.syncing': '正在同步',
      'status.error': '连接或操作异常',
      'sync.notSynced': '数据尚未同步',
      'sync.lastRead': '最近读取 · {time}',
      'error.action': '操作未完成：{msg}。请重试原操作，或刷新页面重新连接。',
      'error.request': '请求失败',
      'error.generic': '操作失败',
      'confirm.defaultTitle': '确认',

      /* ---------- 外观 ---------- */
      'theme.dark': '☾ 深色',
      'theme.light': '☀ 浅色',
      'theme.ariaDark': '切换为深色主题',
      'theme.ariaLight': '切换为浅色主题',
      'appearance.eyebrow': 'PERSONALIZE YOUR WORKSPACE',
      'appearance.title': '选择舒适的工作方式',
      'appearance.hint': '仅影响本浏览器中的面板，不会改变插件配置、消息卡片或其他管理员的界面。',
      'appearance.theme': '界面主题',
      'appearance.themeFollow': '跟随 AstrBot',
      'appearance.themeLight': '浅色 · 日间',
      'appearance.themeDark': '深色 · 夜间',
      'appearance.language': '界面语言',
      'appearance.compact': '紧凑布局',
      'appearance.compactHint': '减小卡片和表格间距，显示更多内容',
      'appearance.saved': '偏好已保存到当前浏览器。',
      'appearance.blocked': '浏览器限制存储，外观仅在本次打开时生效。',
      'lang.button': 'EN',
      'lang.aria': '将面板切换为英文',

      /* ---------- 推送群 ---------- */
      'card.targets.title': '推送群',
      'card.targets.hint': '勾选要自动推送 Blue Protocol: Star Resonance 公告的群（每 5 分钟检查，有更新才推），保存后立即生效，与在群里发「bp push on」等价。',
      'th.push': '推送',
      'th.group': '群',
      'th.groupId': '群号',
      'th.lastPushed': '上次推送的公告',
      'th.actions': '操作',
      'btn.saveTargets': '保存推送群',
      'btn.pushAll': '立刻检查并推送（全部群）',
      'btn.saving': '保存中…',
      'toast.saved': '已保存 {n} 个推送群',
      'toast.selected': '已选 {n} 个群，记得点「保存推送群」',
      'checking': '正在检查公告…',
      'done': '已完成',

      /* ---------- 推送记录 ---------- */
      'card.records.title': '推送记录',
      'card.records.hint': '记录每个群上次推过的公告标题，用来去重。重置后下次检查会重推最新公告。',
      'btn.clearRecords': '清空全部记录',
      'records.empty': '还没有推送记录（第一次推送成功后会出现）',
      'records.emptyTitle': '（空）',
      'records.resetOne': '重置',
      'records.count': '共 {n} 条',
      'toast.resetDone': '已重置',
      'confirm.resetOne': '重置这个群的推送记录？',
      'confirm.resetAll': '清空全部推送记录？下次检查会重推最新公告。',
      'confirm.resetTitle': '重置推送记录',

      /* ---------- 公告图设置 ---------- */
      'card.settings.title': '公告图设置',
      'lbl.longImage': '公告图使用手机整页长图',
      'opt.longImageOn': '开启（渲染公告正文长图）',
      'opt.longImageOff': '关闭（用深色卡片图）',
      'lbl.maxHeight': '长图最大高度（CSS 像素，0 = 不截断）',
      'lbl.quality': '长图 JPEG 质量（1-100）',
      'btn.saveSettings': '保存参数',
      'toast.settingsSaved': '参数已保存',

      /* ---------- 截图缓存 ---------- */
      'card.cache.title': '截图缓存',
      'btn.clearSummary': '清空摘要缓存',
      'btn.clearImages': '清空截图',
      'cache.info': '共 {n} 张，占用 {size}（保留最近 20 张 / 7 天）',
      'cache.empty': '还没有截图缓存（推送过一次公告后会有）',
      'cache.noPreview': '（无法预览，只有文件名）',
      'confirm.clearImages': '清空截图缓存？下次推送会重新截图。',
      'confirm.clearImagesTitle': '清空截图缓存',
      'toast.cleared': '已清空',
      'cache.deleted': '已删除 {n} 张，释放 {size}',
      'cache.summaryCleared': '已清空 {n} 条摘要缓存',
      'page.title': 'Blue Protocol: Star Resonance — 公告面板',
      'push.reason.no_groups': '还没有推送群：在面板里按群名勾选，或在群里发「bp push on」。',
      'push.reason.no_list': '公告列表是空的（数据源没有返回内容）。',
      'push.reason.fetch_failed': '获取公告列表失败。',
      'push.reason.up_to_date': '最新公告已经推送过了，没有新内容。',
      'push.reason.ok': '已推送到 {n} 个群。',

      /* ---------- 选择群弹窗 ---------- */
      'modal.pick.title': '选择推送群',
      'lbl.search': '搜索群名 / 群号',
      'ph.search': '例：星痕 或 339466990',
      'btn.refreshGroups': '刷新群列表',
      'btn.applyPick': '用勾选结果替换名单',
      'btn.cancel': '取消',
      'btn.close': '关闭',
      'btn.ok': '确定',
      'pick.summary': '共 {n} 个会话，当前选中 {m} 个',
      'pick.empty': '还没有可选会话：点「刷新群列表」或先在群里说句话',
      'pick.loading': '正在加载群列表…',
      'pick.noMatch': '没有匹配的会话。换个词，或点「刷新群列表」。',
      'pick.id': '群号 {id}',
      'pick.inList': '已在推送名单',
      'pick.seen': '机器人所见',
      'toast.refreshedGroups': '群列表已刷新（{n} 个群有更新）',

      /* ---------- 测试推送弹窗 ---------- */
      'modal.test.title': '测试推送',
      'lbl.force': '强制重发（忽略「已推送过」的记录）',
      'btn.startPush': '开始推送',
      'pushing': '正在推送…',
      'pushFailed': '推送失败',
      'test.target': '推送到：{name}（{umo}）',

      /* ---------- 运行速览 ---------- */
      'status.noTargets': '还没有推送群',
      'status.running': '定时推送运行中',
      'status.notStarted': '定时任务未启动',
      'stat.targets': '推送群',
      'stat.lastCheck': '上次检查',
      'stat.never': '从未',
      'stat.nextCheck': '距下次检查',
      'stat.imageCache': '截图缓存（{size}）',
      'stat.summaryCache': '摘要缓存',
      'stat.records': '推送记录',

      /* ---------- 群列表 ---------- */
      'groups.empty': '还没有推送群：点右上角「选择群…」，或在群里发「bp push on」',
      'group.noName': '无群名',
      'group.neverPushed': '还没推过',
      'group.testPush': '测试推送',
      'group.reset': '重置记录',
      'table.aria': '数据表格，可横向滚动',
      'connecting': '正在连接面板…',
      'loadFailed': '加载失败',
      'toast.refreshed': '已刷新'
    }
  };

  var listeners = [];
  var current = 'en';

  function detect() {
    /* 1) 手动切换优先 */
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'zh' || saved === 'en') return saved;
    } catch (e) { /* 隐私模式：忽略 */ }
    /* 2) 时区判定：中国大陆 / 港澳台 → 中文 */
    var tz = '';
    try {
      if (typeof Intl !== 'undefined' && Intl.DateTimeFormat) {
        tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
      }
    } catch (e) { /* 老浏览器没有 Intl */ }
    if (tz && CN_ZONES.indexOf(tz) >= 0) return 'zh';
    /* 3) 浏览器语言兜底 */
    try {
      var lang = String((window.navigator && window.navigator.language) || '').toLowerCase();
      if (lang.indexOf('zh') === 0) return 'zh';
    } catch (e) { /* ignore */ }
    return 'en';
  }

  function get() { return current; }

  function t(key, vars) {
    var table = DICT[current] || DICT.en;
    var text;
    if (Object.prototype.hasOwnProperty.call(table, key)) text = table[key];
    else if (Object.prototype.hasOwnProperty.call(DICT.en, key)) text = DICT.en[key];
    else text = key;
    if (vars) {
      Object.keys(vars).forEach(function (name) {
        text = String(text).split('{' + name + '}').join(vars[name]);
      });
    }
    return text;
  }

  function apply(root) {
    var scope = root || document;
    if (!scope || !scope.querySelectorAll) return;
    scope.querySelectorAll('[data-i18n]').forEach(function (node) {
      var key = node.getAttribute('data-i18n');
      if (key) node.textContent = t(key);
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach(function (node) {
      var key = node.getAttribute('data-i18n-placeholder');
      if (key) node.placeholder = t(key);
    });
    scope.querySelectorAll('[data-i18n-aria-label]').forEach(function (node) {
      var key = node.getAttribute('data-i18n-aria-label');
      if (key) node.setAttribute('aria-label', t(key));
    });
    scope.querySelectorAll('[data-i18n-title]').forEach(function (node) {
      var key = node.getAttribute('data-i18n-title');
      if (key) node.setAttribute('title', t(key));
    });
  }

  function set(lang) {
    if (lang !== 'zh' && lang !== 'en') return;
    current = lang;
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) { /* ignore */ }
    apply(document);
    listeners.forEach(function (fn) {
      try { fn(lang); } catch (e) { /* 单个订阅者出错不影响其它人 */ }
    });
  }

  function toggle() { set(current === 'zh' ? 'en' : 'zh'); }

  function onChange(fn) {
    if (typeof fn === 'function') listeners.push(fn);
  }

  /* 先按规则定语言，再把 html[lang] 标好；文案由调用方随后 apply() */
  current = detect();
  document.documentElement.lang = current === 'zh' ? 'zh-CN' : 'en';

  window.BP_I18N = {
    t: t,
    apply: apply,
    get: get,
    set: set,
    toggle: toggle,
    onChange: onChange,
    detect: detect,
    dict: DICT
  };
})();
