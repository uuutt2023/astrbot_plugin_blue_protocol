/* Standalone panel shell. Local resources only; no framework or external assets. */
(function () {
  "use strict";
  var c = {"title": "Blue Protocol: Star Resonance", "brand": "BLUE PROTOCOL / NEWSROOM", "mark": "BP", "hero": "Resonance news,\none page.\n", "sub": "From official announcements to group alerts — manage your Blue Protocol: Star Resonance news feed.", "color": "star", "version": "v1.0.0", "old": "v1.0.0", "views": [["groups", "Push targets", "DELIVERY", [0]], ["records", "Push records", "HISTORY", [1]], ["settings", "Image settings", "RENDER SETTINGS", [2]], ["cache", "Image cache", "IMAGE ARCHIVE", [3]]]};
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
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function button(text, fn, cls) {
    var node = el('button', cls, text); node.type = 'button';
    node.addEventListener('click', fn); return node;
  }
  root.dataset.palette = c.color;
  var layout = el('div', 'workspace');
  var rail = el('aside', 'rail');
  var brand = el('a', 'brand'); brand.href = '#overview';
  brand.append(el('span', 'brand-symbol', c.mark));
  var brandText = el('span'); brandText.append(el('strong', '', c.title), el('small', '', c.brand)); brand.append(brandText);
  rail.append(brand, el('div', 'nav-label', 'WORKSPACE'));
  var nav = el('nav'); nav.setAttribute('aria-label','Page navigation'); rail.append(nav);
  var railFooter = el('div', 'rail-footer');
  var connection = el('span','connection','Connecting');
  railFooter.append(connection, el('small','',c.version + ' · ASTRBOT PLUGIN')); rail.append(railFooter);
  var stage = el('main','stage'); stage.id='main-content'; stage.tabIndex=-1;
  var header = el('header','workspace-header');
  var crumb=el('div','breadcrumb', c.brand);
  var tools=el('div','header-tools');
  var pill=bar.querySelector('.pill'); if(pill) tools.append(pill);
  var themeButton=button('☾ Dark',function(){prefs.theme=root.dataset.theme==='dark'?'light':'dark'; savePrefs();});
  themeButton.id='panelTheme'; tools.append(themeButton);
  // Preserve the original business action nodes and all their event handlers.
  var actionBar=el('div','workspace-actions');
  Array.from(bar.querySelectorAll('button')).forEach(function(node){actionBar.append(node);});
  header.append(crumb,tools); stage.append(header);
  var content=el('div','workspace-content');
  var heading=el('div','page-heading'); var headingText=el('div');
  var eyebrow=el('span','eyebrow'); var title=el('h1');
  headingText.append(eyebrow,title); heading.append(headingText,actionBar); content.append(heading);
  var feedback=el('div','request-feedback'); feedback.hidden=true; feedback.setAttribute('role','alert'); content.append(feedback);
  var sync=el('div','sync-line','Not synced yet'); sync.setAttribute('role','status'); content.append(sync);
  var views={};
  function addView(key,label,english,node) {
    node.classList.add('panel-view'); node.id='panel-'+key; node.hidden=true;
    var labelId='panel-heading-'+key; node.setAttribute('aria-label',label);
    content.append(node);
    var item=button('',function(){location.hash=key;},'nav-item');
    var index=Object.keys(views).length+1;
    item.append(el('span','nav-number',String(index).padStart(2,'0')),el('span','nav-text',label),el('span','nav-arrow','↗'));
    item.setAttribute('aria-label',label); nav.append(item);
    views[key]={label:label,english:english,node:node,button:item};
  }
  var overview=el('section');
  var hero=el('div','hero'); var copy=el('div','hero-copy');
  copy.append(el('span','eyebrow',c.brand),el('h2','',c.hero),el('p','',c.sub));
  copy.append(button('Open '+c.views[0][1]+'  ↗',function(){location.hash=c.views[0][0];},'primary'));
  var art=el('div','hero-art'); art.setAttribute('aria-hidden','true');
  art.append(el('span','art-orbit'),document.getElementById('heroArtTemplate').content.cloneNode(true),el('span','art-caption', c.color==='pink'?'ON AIR / STAY CONNECTED':c.color==='star'?'STAR RESONANCE · ADVENTURERS':'IF MESSAGE → REPLY'));
  hero.append(copy,art); overview.append(hero);
  var statsTitle=el('div','section-heading'); statsTitle.append(el('h2','','Runtime overview'),el('span','hint','Figures reflect the last read')); overview.append(statsTitle,stats);
  var shortcuts=el('div','shortcuts');
  c.views.forEach(function(v){var b=button('',function(){location.hash=v[0];},'shortcut'); b.append(el('span','eyebrow',v[2]),el('strong','',v[1]+'  →'));shortcuts.append(b);});
  overview.append(shortcuts); addView('overview','Overview','OVERVIEW',overview);
  c.views.forEach(function(v){var section=el('section');v[3].forEach(function(i){if(cards[i])section.append(cards[i]);});addView(v[0],v[1],v[2],section);});
  var appearance=el('section');
  var appearanceCard=el('div','card appearance-card');
  appearanceCard.innerHTML='<span class="eyebrow">PERSONALIZE YOUR WORKSPACE</span><h2>Choose a comfortable workspace</h2><p class="hint">Affects this browser only — it does not change the plugin config, message cards, or the view of other admins.</p><div class="field"><label for="panelThemeSelect">Theme</label><select id="panelThemeSelect"><option value="follow">Follow AstrBot</option><option value="light">Light · day</option><option value="dark">Dark · night</option></select></div><label class="compact-row"><span>Compact layout<small>Tighten card and table spacing to fit more content</small></span><input id="panelCompact" type="checkbox"></label><p class="hint" id="panelPreferenceHint" role="status"></p>';
  appearance.append(appearanceCard);addView('appearance','Appearance','APPEARANCE',appearance);
  content.append(el('footer','workspace-footer', c.brand+'  /  BUILT FOR EVERY CONNECTION'));
  stage.append(content);layout.append(rail,stage);
  wrap.replaceWith(layout);
  var skip=el('a','skip-link','Skip to main content');skip.href='#main-content';document.body.prepend(skip);
  function showView() {
    var key=location.hash.slice(1);if(!Object.prototype.hasOwnProperty.call(views,key)) key='overview';
    Object.keys(views).forEach(function(k){var v=views[k];v.node.hidden=k!==key;v.button.classList.toggle('active',k===key);if(k===key)v.button.setAttribute('aria-current','page');else v.button.removeAttribute('aria-current');});
    title.textContent=views[key].label;eyebrow.textContent=views[key].english;
  }
  window.addEventListener('hashchange',showView);showView();
  var themeSelect=document.getElementById('panelThemeSelect');var compact=document.getElementById('panelCompact');
  function applyPrefs(){
    if(themeObserver)themeObserver.disconnect();
    root.dataset.theme=prefs.theme==='follow'?follow:prefs.theme;root.dataset.compact=String(prefs.compact);
    themeSelect.value=prefs.theme;compact.checked=prefs.compact;
    themeButton.textContent=root.dataset.theme==='dark'?'☀ Light':'☾ Dark';themeButton.setAttribute('aria-label',root.dataset.theme==='dark'?'Switch to light theme':'Switch to dark theme');
    if(themeObserver)themeObserver.observe(root,{attributes:true,attributeFilter:['data-theme']});
  }
  function savePrefs(){applyPrefs();var hint=document.getElementById('panelPreferenceHint');try{localStorage.setItem(storageKey,JSON.stringify(prefs));hint.textContent='Preferences saved to this browser.';}catch(e){hint.textContent='Storage is blocked — appearance applies to this session only.';}}
  themeSelect.addEventListener('change',function(){prefs.theme=this.value;savePrefs();});compact.addEventListener('change',function(){prefs.compact=this.checked;savePrefs();});
  var params=new URLSearchParams(location.search);var host=params.get('theme')||root.dataset.theme;
  if(host!=='dark'&&host!=='light'){var d=params.get('isDark');try{if(d===null)d=localStorage.getItem('astrbot_plugin_theme_is_dark');}catch(e){}host=d==='true'?'dark':'light';}follow=host;
  try{var saved=JSON.parse(localStorage.getItem(storageKey)||'{}');if(['light','dark','follow'].includes(saved.theme))prefs.theme=saved.theme;if(typeof saved.compact==='boolean')prefs.compact=saved.compact;}catch(e){}
  themeObserver=new MutationObserver(function(){var theme=root.dataset.theme;if(theme==='dark'||theme==='light')follow=theme;applyPrefs();});applyPrefs();
  window.addEventListener('storage',function(e){if(e.key==='astrbot_plugin_theme_is_dark'){follow=e.newValue==='true'?'dark':'light';applyPrefs();}});
  // Make every existing table scroll inside its card instead of widening the page.
  document.querySelectorAll('.card > table').forEach(function(table){var scroll=el('div','table-wrap');table.replaceWith(scroll);scroll.append(table);});
  document.querySelectorAll('.table-wrap').forEach(function(node){node.tabIndex=0;node.setAttribute('aria-label','Data table, scroll horizontally');});
  var toast=document.getElementById('toast');toast.setAttribute('role','status');toast.setAttribute('aria-live','polite');
  document.querySelectorAll('.modal-mask').forEach(function(mask,index){
    var dialog=mask.querySelector('.modal');dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');
    var h=dialog.querySelector('h2');if(h){if(!h.id)h.id='dialog-heading-'+index;dialog.setAttribute('aria-labelledby',h.id);}
    var previous=null;var wasHidden=mask.hidden;
    new MutationObserver(function(){if(mask.hidden===wasHidden)return;wasHidden=mask.hidden;
      if(!mask.hidden){previous=document.activeElement;if(!mask.contains(previous)){var focus=mask.querySelector('input:not([hidden]),select,textarea,button');if(focus)focus.focus();}}
      else if(previous&&!mask.contains(previous)&&previous.isConnected)previous.focus();
    }).observe(mask,{attributes:true,attributeFilter:['hidden']});
    mask.addEventListener('keydown',function(e){
      if(e.key!=='Tab')return;
      var items=Array.from(mask.querySelectorAll('button,input,textarea,select,[tabindex="0"]')).filter(function(n){return !n.disabled&&n.getClientRects().length;});
      if(!items.length)return;var first=items[0],last=items[items.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
    });
  });
  window.PanelUI={
    request:function(promise){
      if(!pending){failed=false;feedback.hidden=true;}pending++;connection.textContent='Syncing';
      return promise.then(function(data){sync.textContent='Last read · '+new Date().toLocaleTimeString('en-US',{hour12:false});return data;},function(error){failed=true;feedback.hidden=false;feedback.textContent='Action failed: '+(error.message||'Request failed')+'. Please retry the action, or reload the page to reconnect.';throw error;}).finally(function(){pending--;if(!pending){connection.textContent=failed?'Connection or action error':'Panel connected';connection.classList.toggle('error',failed);}});
    }
  };
})();
