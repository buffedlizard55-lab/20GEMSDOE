#!/usr/bin/env python3
"""Real Chromium desktop/mobile smoke tests; local static assets only, no contest access.

Install Playwright + its official Chromium binary, then run this script. Binaries,
exports and screenshots stay in ignored .cache. A Python/Node pass is not this test.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass


def main():
    from playwright.sync_api import sync_playwright
    from gems.submission import check_variants
    from gems.footprint import write_template
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',help='Optional legitimately installed Chromium executable')
    parser.add_argument('--output',type=Path,default=ROOT/'.cache/browser_review.json')
    args=parser.parse_args()
    folder=ROOT/'.cache/browser-review';folder.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('0.0.0.0',0),partial(QuietHandler,directory=str(ROOT/'docs')))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'  # automation browser/server share sandbox, NOT application API code
    errors=[];checks=[]
    try:
        with sync_playwright() as pw:
            kwargs={'headless':True}
            if args.executable:kwargs['executable_path']=args.executable
            browser=pw.chromium.launch(**kwargs)
            for mode,size in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':390,'height':844})]:
                context=browser.new_context(viewport=size,accept_downloads=True)
                def route(request_route):
                    if urlparse(request_route.request.url).scheme not in ('data','blob') and urlparse(request_route.request.url).netloc!=urlparse(origin).netloc:
                        errors.append('Unexpected external browser request: '+request_route.request.url)
                        request_route.abort()
                    else:request_route.continue_()
                context.route('**/*',route)
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                for name in ['index.html','executive_summary.html','research.html','results.html','knowledge.html','audit.html']:
                    page.goto(origin+'/'+name,wait_until='networkidle')
                    assert page.locator('h1').count()==1, (mode,name,'heading')
                    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'),(mode,name,'horizontal overflow')
                    if name=='index.html':
                        assert page.locator('a[download]').first.is_visible()
                        page.screenshot(path=str(folder/(mode+'-home.png')),full_page=False)
                    checks.append({'viewport':mode,'page':name,'layout_passed':True})
                page.goto(origin+'/executive_summary.html',wait_until='networkidle')
                page.locator('#sb-verify-btn').click()
                page.wait_for_function("document.querySelector('#sb-verify-out').textContent.includes('Complete browser format check passed')",timeout=120000)
                page.select_option('#sb-cand-select','h20-5')
                page.select_option('#sb-fmt-select','tif_allfinite')
                page.locator('.advanced-export summary').click()
                with page.expect_download(timeout=120000) as download_info:
                    page.locator('#sb-export-btn').click()
                download=download_info.value
                assert download.suggested_filename.startswith('gems20-formatcopy-h20-5-') and download.suggested_filename.endswith('-nan.tif')
                target=folder/(mode+'-export.tif');download.save_as(target)
                result=check_variants(target,write_template(folder/(mode+'-template.tif')))
                assert result['official_format_compliant'] and result['submission_authorized_by_this_check'] is False
                assert page.locator('#sb-export-info').is_visible()
                assert 'no upload recommendation' in page.locator('#sb-export-note').inner_text()
                # Uploaded to the LOCAL checker, never a remote competition endpoint.
                page.locator('#checker input[type=file]').set_input_files(str(target))
                page.wait_for_function("document.querySelector('#checker .out').textContent.includes('Complete local format check passed (NaN outside, official convention).')",timeout=120000)
                checks.append({'viewport':mode,'browser_preflight':True,'format_export':True,'python_roundtrip':True,'local_file_checker':True,'filename':download.suggested_filename,'sha256':result['sha256']})
                context.close()
            browser.close()
        assert not errors,errors
        report={'generated_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'real_browser':'Chromium via Playwright','passed':True,'checks':checks,'errors':errors,'contest_access_or_upload':False,'predictions_generated':False,'scope':'Automated UI/desktop/mobile/export smoke checks, not geological validation or manual visual review'}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    except Exception as exc:
        detail=type(exc).__name__+": "+str(exc)
        diagnostics=[]
        try:
            if not page.is_closed():
                diagnostics=page.evaluate("Array.from(document.querySelectorAll('body *')).map(e=>{const r=e.getBoundingClientRect();return {tag:e.tagName,id:e.id,cls:e.className,left:r.left,right:r.right,width:r.width}}).filter(e=>e.right>innerWidth+1||e.left< -1).slice(0,30)")
                page.screenshot(path=str(folder/'failure.png'),full_page=False)
        except Exception:
            pass  # original test failure remains fatal; diagnostics are best-effort
        report={'generated_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'real_browser':'Chromium via Playwright','passed':False,'checks':checks,'errors':errors+[detail],'overflow_diagnostics':diagnostics,'contest_access_or_upload':False}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        def annotation(text):
            return text.replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print('::error file=scripts/check_browser.py::'+annotation(detail),flush=True)
        if diagnostics:
            print('::notice::'+annotation('Browser layout diagnostics: '+json.dumps(diagnostics)),flush=True)
        raise
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':
    main()
