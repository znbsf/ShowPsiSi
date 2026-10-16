"""Real Chromium + real native-engine integration tests (not native Tauri tests).

SHOWPSISI_CORE=/path/to/core python -m unittest discover -s tests -p test_web_ui.py -v
Requires Playwright Python and Chromium (PLAYWRIGHT_CHROMIUM_EXECUTABLE optional).
Screenshots: artifacts/web-ui-tests/. Every response is produced by the native core.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from cloud_preview import Bridge, Server

class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.tmp=tempfile.TemporaryDirectory(prefix='showpsisi-browser-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.output=Path(cls.tmp.name)
        cls.sample=cls.output/'lab.ts'
        subprocess.run([sys.executable,str(ROOT/'scripts/make_fixture.py'),'--mib','12','--output',str(cls.sample)],check=True,stdout=subprocess.DEVNULL,cwd=ROOT)
        cls.empty=cls.output/'empty.ts'
        # A real TS containing only null packets: valid input with no SI tables.
        cls.empty.write_bytes((bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184)*100)
        cls.original_hash=hashlib.sha256(cls.sample.read_bytes()).hexdigest()
        cls.playwright=sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        executable=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('chromium-browser')
        cls.browser=cls.playwright.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))
        cls.addClassCleanup(cls.browser.close)
        cls.artifacts=ROOT/'artifacts/web-ui-tests'
        cls.artifacts.mkdir(parents=True,exist_ok=True)

    def setUp(self):
        self.bridge=Bridge(self.output,self.sample)
        self.addCleanup(self.bridge.close)
        self.server=Server(self.bridge)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.page=self.browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        self.page_errors=[]
        self.page.on('pageerror',lambda error:self.page_errors.append(str(error)))
        self.page.goto(self.server.url)
        self.page.wait_for_function('() => window.showpsisi && document.querySelector("#source").value.length > 0')

    def tearDown(self):
        self.page.screenshot(path=str(self.artifacts/(self._testMethodName+'.png')),full_page=True)
        self.page.close()
        self.assertEqual(self.page_errors,[],'Browser JavaScript raised an exception')

    def analyze(self,path=None):
        self.page.locator('#source').fill(str(path or self.sample))
        self.page.locator('#source').press('Enter')
        self.page.wait_for_function('() => window.showpsisi.getState().complete === true')
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')

    def call(self,method,params=None):
        return self.page.evaluate('([method,params])=>window.showpsisi.call(method,params)',[method,params or {}])

    def test_real_analysis_and_selection(self):
        self.analyze()
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(len(state['services']),6)
        self.assertEqual(state['crc_errors'],2)
        self.assertEqual(state['services'][0]['name'],'Sports UHD')
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.assertIn('Sports UHD',self.page.locator('#list').inner_text())
        self.assertIn('SDT',self.page.locator('#inspector').inner_text())
        self.assertGreater(len(self.page.evaluate('window.showpsisi.getDetail().raw_hex')),0)

    def test_empty_and_read_failure(self):
        self.assertIn('Open',self.page.locator('#list').inner_text())
        self.analyze(self.empty)
        state=self.page.evaluate('window.showpsisi.getState()')
        self.assertEqual(state['services'],[])
        self.assertEqual(state['tables'],[])
        self.page.locator('#source').fill(str(self.output/'missing.ts'))
        self.page.locator('#scan').click()
        self.page.wait_for_function('() => !document.querySelector("#scan").disabled')
        self.assertRegex(self.page.locator('#notice').inner_text().lower(),r'open|read|exist|file|source')
        self.assertEqual(self.page.evaluate('window.showpsisi.getDetail()'),{})

    def test_native_picker_is_explicitly_unsupported(self):
        self.page.locator('#browse').click()
        self.page.wait_for_function('() => document.querySelector("#notice").textContent.includes("Native file dialogs")')
        self.assertIn('local TS file path',self.page.locator('#notice').inner_text())

    def test_preview_export_reparse_and_no_overwrite(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.locator('#edit').click()
        self.assertTrue(self.page.locator('#export').is_disabled())
        self.page.locator('#rename').fill('Browser verified service')
        self.page.locator('#preview').click()
        self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        self.page.locator('#rename').fill('Changed after preview')
        self.assertTrue(self.page.locator('#export').is_disabled())
        self.page.locator('#rename').fill('Browser verified service')
        self.page.locator('#preview').click()
        self.page.wait_for_function('() => !document.querySelector("#export").disabled')
        self.page.locator('#export').click()
        self.page.wait_for_function('() => document.querySelector("#diff").textContent.includes("Native file dialogs")')
        self.page.locator('#close-edit').click()
        # Save dialog is honestly unsupported. Verify export using the same real
        # JSONL API, without claiming the native save dialog was exercised.
        service=self.page.evaluate('window.showpsisi.getState().services[0]')
        preview=self.call('preview_rename',{'id':service['source_id'],'service_id':service['id'],'name':'Browser verified service'})
        output=self.output/'artifacts/browser-verified.ts'
        self.call('export',{'path':str(output),'preview_token':preview['token']})
        manifest=json.loads(Path(str(output)+'.manifest.json').read_text())
        self.assertTrue(manifest)
        self.assertEqual(hashlib.sha256(self.sample.read_bytes()).hexdigest(),self.original_hash)
        parsed=self.call('analyze',{'path':str(output)})
        self.assertIn('Browser verified service',[service['name'] for service in parsed['services']])
        self.assertEqual(parsed['crc_errors'],0)
        error=self.page.evaluate('async path=>{try{await window.showpsisi.call("export",{path});return "unexpected success"}catch(error){return String(error)}}',str(output))
        self.assertIn('already exists',error)
        blocked=self.page.evaluate('async path=>{try{await window.showpsisi.call("export",{path});return "unexpected success"}catch(error){return String(error)}}',str(self.sample))
        self.assertIn('validation artifacts directory',blocked)
        self.assertEqual(hashlib.sha256(self.sample.read_bytes()).hexdigest(),self.original_hash)

    def test_record_search_keyboard_and_tree(self):
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.keyboard.press('Control+k')
        self.assertTrue(self.page.locator('#search').evaluate('(element)=>element===document.activeElement'))
        self.page.locator('#search').fill('Sports UHD')
        self.assertEqual(self.page.locator('#list [role="option"]').count(),1)
        self.page.locator('#search').fill('NO_SUCH_SERVICE_9817')
        self.assertIn('No matching records',self.page.locator('#list').inner_text())
        self.page.locator('#search').fill('')
        rows=self.page.locator('#list [role="option"]')
        rows.first.focus();rows.first.press('ArrowDown')
        self.page.keyboard.press('Enter')
        self.page.wait_for_function('() => document.querySelectorAll("#list [aria-selected=true]").length===1 && !document.querySelector("#inspector .loading")')
        self.assertEqual(self.page.locator('#list [aria-selected="true"]').get_attribute('data-key'),rows.nth(1).get_attribute('data-key'))
        self.page.locator('#tree-area details[data-path="section"] > summary').wait_for()
        root=self.page.locator('#tree-area details[data-path="section"]')
        root.locator(':scope > summary').focus()
        self.page.keyboard.press('ArrowLeft')
        self.assertFalse(root.evaluate('(element)=>element.open'))
        self.page.keyboard.press('ArrowRight')
        self.assertTrue(root.evaluate('(element)=>element.open'))
        self.page.locator('#tree-search').fill('descriptor_tag')
        self.assertIn('descriptor_tag',self.page.locator('#tree-area').inner_text())
        self.page.locator('#tree-search').fill('NO_SUCH_FIELD_9817')
        self.assertIn('No matching fields',self.page.locator('#tree-area').inner_text())
        self.page.locator('#tree-search').fill('')
        self.page.locator('[data-view="hex"]').click()
        self.assertTrue(self.page.locator('[aria-label="Section hex dump"]').inner_text().strip())
        self.page.locator('[data-view="xml"]').click()
        self.assertIn('SDT',self.page.locator('[aria-label="TSDuck XML"]').inner_text())

    def test_standards_context_and_invalid_extra_pids(self):
        for standard in ('atsc','isdb-japan'):
            self.page.locator('#standards').select_option(standard)
            self.page.locator('#extra-pids').fill('0x123, 291')
            self.analyze()
            state=self.page.evaluate('window.showpsisi.getState()')
            self.assertEqual(state['standards_context'],standard)
            self.page.wait_for_function('() => window.showpsisi.getDetail().standards_context === '+json.dumps(standard))
            self.assertIn(standard,self.page.locator('#inspector').inner_text().lower())
        before=self.page.evaluate('window.showpsisi.getState().revision')
        self.page.locator('#extra-pids').fill('8192')
        self.page.locator('#scan').click()
        self.assertIn('between 0 and 8191',self.page.locator('#notice').inner_text())
        self.assertTrue(self.page.locator('#extra-pids').evaluate('(element)=>element===document.activeElement'))
        self.assertEqual(self.page.evaluate('window.showpsisi.getState().revision'),before)
        self.page.locator('#extra-pids').fill('0xNOPE')
        self.page.locator('#scan').click()
        self.assertIn('decimal or hexadecimal',self.page.locator('#notice').inner_text())

    def test_references_and_responsive_tree(self):
        self.page.locator('#standards').select_option('dvb')
        self.analyze()
        self.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
        self.page.locator('[data-view="references"]').click()
        links=self.page.locator('[data-reference]')
        self.assertGreater(links.count(),0,'DVB SDT should have mapped standards references')
        for link in links.all():
            url=link.get_attribute('href')
            from urllib.parse import urlsplit
            parsed=urlsplit(url)
            self.assertEqual(parsed.scheme,'https')
            self.assertTrue(parsed.hostname)
            self.assertIsNone(parsed.username)
            self.assertIn('noopener',link.get_attribute('rel'))
        # Inspect URLs only. Do not click or open an external site.
        self.page.screenshot(path=str(self.artifacts/'references.png'),full_page=True)
        self.page.locator('[data-view="tree"]').click()
        for width in (1100,900,520):
            self.page.set_viewport_size({'width':width,'height':1000})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width+1,'Unexpected horizontal viewport overflow')
            self.page.locator('#tree-search').fill('descriptor')
            self.assertIn('descriptor',self.page.locator('#tree-area').inner_text().lower())
            oversized=self.page.locator('#tree-area .node-label').evaluate_all('(elements)=>elements.filter(e=>e.getBoundingClientRect().width>e.closest("#tree-area").clientWidth).map(e=>e.textContent)')
            self.assertEqual(oversized,[],'Descriptor labels exceed inspector width')
            self.page.screenshot(path=str(self.artifacts/('responsive-'+str(width)+'.png')),full_page=True)
        self.page.set_viewport_size({'width':1440,'height':1000})
        self.page.locator('#tree-search').fill('')

    def test_bridge_rejects_unauthorized_requests(self):
        request=Request(self.server.url+'/__bridge/invoke',data=b'{"command":"environment"}',headers={'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)
        request=Request(self.server.url+'/',headers={'Host':'untrusted.example'})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)
        with urlopen(self.server.url+'/app.js') as response:
            self.assertEqual(response.read(),(ROOT/'ui/tauri/web/app.js').read_bytes())

if __name__=='__main__':unittest.main(verbosity=2)
