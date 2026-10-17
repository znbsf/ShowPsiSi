"""Real Chromium/native-engine captures; not native Tauri acceptance.
Optional SHOWPSISI_BASELINE_WEB points to separately exported earlier web assets.
"""
from pathlib import Path
import json, os, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_web_ui import BrowserTests
import cloud_preview
out=ROOT/'artifacts/section-workbench/web';out.mkdir(parents=True,exist_ok=True)
BrowserTests.setUpClass()
reports=[]
try:
    baseline=os.environ.get('SHOWPSISI_BASELINE_WEB')
    for mode,assets in [('baseline',Path(baseline))] if baseline else [('final',ROOT/'ui/tauri/web')]:
        cloud_preview.WEB=assets
        case=BrowserTests('test_section_evidence_crc_groups_arrival_and_scopes')
        try:
            case.setUp()
            if mode=='final':
                case.test_section_evidence_crc_groups_arrival_and_scopes()
                case.page.screenshot(path=str(out/'final-all-bad-crc.png'),full_page=True)
                case.page.locator('#show-bad-crc').uncheck()
            for name,path in [('synthetic',case.sample),('uhf22',ROOT/'samples/real/tnt-uhf22-2019.ts')]:
                if not path.is_file(): raise RuntimeError('Required capture source absent: '+str(path))
                case.analyze(path)
                p=case.page
                p.wait_for_function('()=>window.showpsisi.getDetail().name')
                p.locator('[data-tab="Tables"]').click()
                for width,height in [(1440,900),(1000,680),(520,1000)]:
                    p.set_viewport_size({'width':width,'height':height})
                    p.screenshot(path=str(out/f'{mode}-{name}-{width}.png'),full_page=True)
                    reports.append(p.evaluate('([mode,name,width,height])=>({mode,name,width,height,source:window.showpsisi.getState().source,records:window.showpsisi.getState().tables.length,tree:document.querySelector("#tree-area")?.getBoundingClientRect().toJSON(),documentWidth:document.documentElement.scrollWidth})',[mode,name,width,height]))
                if mode=='final':
                    p.set_viewport_size({'width':1440,'height':900})
                    if not p.locator('.table-branch').count(): p.locator('#table-group-toggle').click()
                    p.locator('.table-branch > summary').first.click()
                    p.screenshot(path=str(out/f'final-{name}-groups.png'),full_page=True)
                    p.locator('#table-group-toggle').click()
                    p.locator('[data-view="xml"]').click()
                    p.screenshot(path=str(out/f'final-{name}-xml.png'),full_page=True)
                    p.locator('[data-view="tree"]').click()
            assert not case.page_errors,case.page_errors
        finally:
            if hasattr(case,'page'):case.page.close()
            case.doCleanups()
    (out/('baseline-metrics.json' if baseline else 'final-metrics.json')).write_text(json.dumps(reports,indent=2))
finally:
    BrowserTests.doClassCleanups()
