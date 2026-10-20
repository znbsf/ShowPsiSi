"""Optional real-engine Chromium UX capture (not a native Tauri screenshot).
Run with the same environment as test_web_ui.py. Writes artifacts/ux-standards/web.
"""
from pathlib import Path
import sys,json
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_web_ui import BrowserTests
out=ROOT / 'artifacts/ux-standards/web';out.mkdir(parents=True,exist_ok=True)
BrowserTests.setUpClass()
case=BrowserTests('test_tree_composite_focus_states_and_keyboard_contract')
try:
    case.setUp();case.analyze()
    case.page.wait_for_function('() => window.showpsisi.getDetail().name === "SDT"')
    p=case.page
    metrics=[]
    for width,height in ((1440,900),(1000,680),(520,1000)):
        p.set_viewport_size({'width':width,'height':height})
        for density in (32,28):
            p.evaluate('d=>{let el=document.querySelector("#density-check");if(!el){el=document.createElement("style");el.id="density-check";document.head.append(el)}el.textContent=`.tree-node > .tree-row,.tree-leaf { min-height:${d}px; }`}',density)
            p.locator('#tree-area .tree-node').first.focus()
            assert p.evaluate('document.documentElement.scrollWidth')<=width+1
            metrics.append(p.evaluate('([width,height,density])=>({width,height,density,tree:document.querySelector("#tree-area").getBoundingClientRect().toJSON(),footer:document.querySelector("footer").getBoundingClientRect().toJSON(),visibleRows:[...document.querySelectorAll("#tree-area [role=treeitem]")].filter(el=>el.checkVisibility() && (el.querySelector(":scope > .tree-row")||el).getBoundingClientRect().top >= document.querySelector("#tree-area").getBoundingClientRect().top && (el.querySelector(":scope > .tree-row")||el).getBoundingClientRect().bottom <=document.querySelector("#tree-area").getBoundingClientRect().bottom).length,fieldFont:getComputedStyle(document.querySelector(".node-value")).fontSize})',[width,height,density]))
            p.screenshot(path=str(out/f'web-{width}-{height}-{density}.png'))
    # Real input validation rather than injecting a fabricated backend response.
    case.open_scan_options()
    p.locator('#extra-pids').fill('invalid-pid')
    p.locator('#scan').click()
    p.wait_for_function('()=>document.querySelector("#notice").classList.contains("error")')
    assert p.locator('#notice').get_attribute('aria-live')=='assertive'
    assert p.locator('#notice').evaluate('(el)=>el.scrollHeight<=el.clientHeight')
    assert p.locator('footer').evaluate('(el)=>el.getBoundingClientRect().bottom<=innerHeight')
    p.screenshot(path=str(out/'web-520-error.png'))
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2))
    # Inspect actual Chromium accessibility ownership, not just DOM attributes.
    ax=p.context.new_cdp_session(p).send('Accessibility.getFullAXTree')['nodes']
    nodes=[n for n in ax if n.get('role',{}).get('value') in ('tree','treeitem','group')]
    (out/'accessibility-tree.json').write_text(json.dumps(nodes,indent=2))
    assert any(n['role']['value']=='treeitem' for n in nodes)
    assert not case.page_errors
    print('Visual checks passed: 6 density/viewport captures, narrow real validation error, actual accessibility tree.')
finally:
    case.doCleanups()
    BrowserTests.doClassCleanups()
