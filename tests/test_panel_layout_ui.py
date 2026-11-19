"""Offline theme, routing and pixel-alignment checks. Requires Playwright + Chromium.
Set WOW_PANEL_BROWSER to a local Chromium executable if needed.
"""
from pathlib import Path
import os, mimetypes, unittest
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
ROOT = next((Path(__file__).resolve().parents[1] / "pages").iterdir())
BRIDGE = """
window.AstrBotPluginPage = {
 ready: () => Promise.resolve(),
 apiGet: async path => ({status:'ok',data:{
  session_ok:true,monitor_running:true,monitors:12,max_monitors:50,
  check_interval:60,dynamic_check_interval:180,groups:[],rows:[],records:[],shots:[],
  live:{rows:[]},dynamic:{rows:[]},config:{shot_enabled:true,shot_quality:85,shot_max_height:8000},
  match_types:[{value:'exact',label:'精确'}],formats:[{value:'text',label:'文本'}],
  rules:[],scopes:[{value:'global',label:'全局'}],stats:{total:12,enabled:10,hits:12345},enabled:true
 }}),
 apiPost: async (path,body) => {window.lastPost={path,body};return {status:'ok',data:{}};}
};
"""
class PanelLayoutTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start()
  cls.browser=cls.pw.chromium.launch(headless=True,**({'executable_path':os.environ['WOW_PANEL_BROWSER']} if os.environ.get('WOW_PANEL_BROWSER') else {}))
 @classmethod
 def tearDownClass(cls):
  cls.browser.close();cls.pw.stop()
 def _open(self,timezone_id='UTC',locale='en-US',connected='Panel connected'):
  self.context=self.browser.new_context(viewport={'width':1600,'height':1100},timezone_id=timezone_id,locale=locale)
  def serve(route):
   path=urlparse(route.request.url).path
   if path.endswith('bridge-sdk.js'):route.fulfill(body=BRIDGE,content_type='text/javascript; charset=utf-8');return
   file=ROOT/path.lstrip('/')
   if file.is_file() and file.parent==ROOT:route.fulfill(body=file.read_bytes(),content_type=(mimetypes.guess_type(file.name)[0] or 'text/plain')+'; charset=utf-8')
   else:route.fulfill(status=404)
  self.context.route('http://panel.test/**',serve)
  self.page=self.context.new_page();self.errors=[]
  self.page.on('pageerror',lambda e:self.errors.append(str(e)))
  self.page.goto('http://panel.test/index.html')
  expect(self.page.locator('.connection')).to_have_text(connected)
 def setUp(self):
  self._open()
 def tearDown(self):
  self.context.close();self.assertEqual(self.errors,[])
 def test_theme_and_storage(self):
  p=self.page
  expect(p.locator('html')).to_have_attribute('data-theme','light')
  p.locator('#panelTheme').click()
  expect(p.locator('html')).to_have_attribute('data-theme','dark')
  p.reload();expect(p.locator('html')).to_have_attribute('data-theme','dark')
  p.evaluate("() => {Storage.prototype.setItem=()=>{throw Error('blocked')};}")
  p.locator('#panelTheme').click();expect(p.locator('html')).to_have_attribute('data-theme','light')
 def test_dialog_and_save_wire_contract(self):
  p=self.page
  if ROOT.name=='bililive-panel':
   p.locator('.nav-item').nth(1).click();p.locator('#btnAddSub').click()
   expect(p.locator('#subMask')).to_be_visible()
   p.locator('#subCancel').click();expect(p.locator('#subMask')).to_be_hidden()
   p.locator('#btnSaveSubs').click()
   p.wait_for_function("window.lastPost && window.lastPost.path==='page/subscriptions/save'")
   self.assertEqual(p.evaluate('window.lastPost.body'),{'kind':'live','rows':[]})
  elif ROOT.name=='blueprotocol-panel':
   p.locator('#btnPickGroup').click();expect(p.locator('#pickMask')).to_be_visible()
   p.locator('#pickClose').click();expect(p.locator('#pickMask')).to_be_hidden()
   p.locator('.nav-item').nth(3).click()
   p.locator('#cfgShotQuality').fill('80');p.locator('#btnSaveConfig').click()
   p.wait_for_function("window.lastPost && window.lastPost.path==='page/config/save'")
   self.assertEqual(p.evaluate('window.lastPost.body.shot_quality'),'80')
  else:
   p.locator('#btnNew').click();expect(p.locator('#editMask')).to_be_visible()
   p.locator('#fKeyword').fill('hello');p.locator('#fReply').fill('world')
   p.locator('#editSave').click();expect(p.locator('#editMask')).to_be_hidden()
   self.assertEqual(p.evaluate('window.lastPost.path'),'page/rules')
   self.assertEqual(p.evaluate('window.lastPost.body.keyword'),'hello')
   self.assertEqual(p.evaluate('window.lastPost.body.format'),'text')

 def test_home_uses_client_icon(self):
  p=self.page
  icon=p.locator('.hero-art img.art-client-icon')
  expect(icon).to_have_count(1)
  self.assertTrue(icon.get_attribute('src').startswith('./blueprotocol-icon.png'))
  for theme in ['light','dark']:
   if p.locator('html').get_attribute('data-theme')!=theme:p.locator('#panelTheme').click()
   expect(icon).to_be_visible()
   p.wait_for_function("() => {const icon=document.querySelector('.hero-art img');return icon.complete && icon.naturalWidth===128 && icon.naturalHeight===128;}")
   self.assertEqual(p.locator('.hero-art .art-symbol').count(),0)
   self.assertEqual(icon.evaluate('img=>getComputedStyle(img).opacity'),'1')
  p.set_viewport_size({'width':390,'height':844})
  expect(p.locator('.hero-art')).to_be_hidden()
  self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))

 def test_routes_and_alignment(self):
  p=self.page
  for width in [1600,1440,768,390]:
   p.set_viewport_size({'width':width,'height':1100})
   for theme in ['light','dark']:
    if p.locator('html').get_attribute('data-theme')!=theme:p.locator('#panelTheme').click()
    for i in range(p.locator('.nav-item').count()):
     p.locator('.nav-item').nth(i).click()
     self.assertEqual(p.locator('.panel-view:visible').count(),1)
     self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),(width,theme,i))
     if os.environ.get('WOW_PANEL_SCREENSHOTS') and width in [1600,390]:
      out=Path(os.environ['WOW_PANEL_SCREENSHOTS']);out.mkdir(parents=True,exist_ok=True)
      p.screenshot(path=str(out/(ROOT.name+'-view'+str(i)+'-'+str(width)+'-'+theme+'.png')),full_page=True)

    p.locator('.nav-item').first.click()
    boxes=p.locator('.stat').evaluate_all("nodes=>nodes.map(n=>({top:n.getBoundingClientRect().top,label:n.querySelector('.l').getBoundingClientRect().top,value:n.querySelector('.n').getBoundingClientRect().top,before:getComputedStyle(n.querySelector('.l'),'::before').content}))")
    for a in boxes:
     self.assertEqual(a['before'],'none')
     for b in boxes:
      if abs(a['top']-b['top'])<1:
       self.assertAlmostEqual(a['label'],b['label'],delta=1)
       self.assertAlmostEqual(a['value'],b['value'],delta=1)
    if os.environ.get('WOW_PANEL_SCREENSHOTS') and width in [1600,390]:
     out=Path(os.environ['WOW_PANEL_SCREENSHOTS']);out.mkdir(parents=True,exist_ok=True)
     p.screenshot(path=str(out/(ROOT.name+'-'+str(width)+'-'+theme+'.png')),full_page=True)
 def test_language_toggle_switches_ui(self):
  """右上角语言按钮：中 ↔ 英 互切，并写进 localStorage。"""
  p=self.page
  expect(p.locator('html')).to_have_attribute('lang','en')
  # 按钮上显示的是"另一种语言"
  expect(p.locator('#panelLang')).to_have_text('中文')
  expect(p.locator('.nav-item').first.locator('.nav-text')).to_have_text('Overview')
  p.locator('#panelLang').click()
  expect(p.locator('html')).to_have_attribute('lang','zh-CN')
  expect(p.locator('#panelLang')).to_have_text('EN')
  expect(p.locator('.nav-item').first.locator('.nav-text')).to_have_text('总览')
  expect(p.locator('.connection')).to_have_text('面板已连接')
  self.assertEqual(p.evaluate("() => localStorage.getItem('panelLang')"),'zh')
  # 手动选择优先于自动判断：刷新后仍是中文
  p.reload()
  expect(p.locator('html')).to_have_attribute('lang','zh-CN')
  expect(p.locator('.nav-item').first.locator('.nav-text')).to_have_text('总览')
  # 再点一次切回英文
  p.locator('#panelLang').click()
  expect(p.locator('html')).to_have_attribute('lang','en')
  expect(p.locator('#panelLang')).to_have_text('中文')

 def test_language_select_in_appearance(self):
  """「界面外观」里的 Language 下拉同样能切语言。"""
  p=self.page
  p.locator('.nav-item').last.click()
  expect(p.locator('#panelLangSelect')).to_be_visible()
  p.locator('#panelLangSelect').select_option('zh')
  expect(p.locator('html')).to_have_attribute('lang','zh-CN')
  expect(p.locator('#panelLangSelect')).to_have_value('zh')

 def test_language_auto_detected_by_timezone(self):
  """中国时区自动中文，海外时区自动英文。"""
  if ROOT.name!='blueprotocol-panel':return
  self.context.close()
  self._open(timezone_id='Asia/Shanghai',locale='zh-CN',connected='面板已连接')
  expect(self.page.locator('html')).to_have_attribute('lang','zh-CN')
  expect(self.page.locator('.nav-item').first.locator('.nav-text')).to_have_text('总览')
  self.context.close()
  self._open(timezone_id='America/New_York',locale='en-US')
  expect(self.page.locator('html')).to_have_attribute('lang','en')
  expect(self.page.locator('.nav-item').first.locator('.nav-text')).to_have_text('Overview')

 def test_dynamic_content_follows_language(self):
  """动态渲染的统计卡片也要跟着切语言重画。"""
  p=self.page
  stat=p.locator('#stats .stat .l').first
  expect(stat).to_have_text('Push targets')
  p.locator('#panelLang').click()
  expect(stat).to_have_text('推送群')
 def test_page_title_follows_language(self):
  """浏览器标签页标题也跟着语言切换。"""
  p=self.page
  expect(p).to_have_title('Blue Protocol: Star Resonance — Announcements')
  p.locator('#panelLang').click()
  expect(p).to_have_title('Blue Protocol: Star Resonance — 公告面板')
  p.locator('#panelLang').click()
  expect(p).to_have_title('Blue Protocol: Star Resonance — Announcements')

 def test_push_toast_is_localized(self):
  """后端返回的英文 message，面板要按 reason 出本地化文案。"""
  p=self.page
  p.locator('.nav-item').nth(1).click()   # 「推送群」页
  p.locator('#btnPushAll').click()
  p.wait_for_function("() => document.querySelector('#toast') && document.querySelector('#toast').className.includes('show')")
  toast=p.locator('#toast').inner_text()
  self.assertNotIn('No push targets yet',toast,'面板不应直接显示后端的英文 message')
  self.assertTrue(toast.strip(),'推送后应有提示文案')
if __name__=='__main__':unittest.main()
