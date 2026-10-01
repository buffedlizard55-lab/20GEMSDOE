"""Check that every OFFICIAL source URL in registry/sources.json is still reachable (weekly CI job; also runnable by hand).

Deliberately skips drivendata.org hosts: DrivenData's Terms of Use forbid robots/spiders, so those links are checked by a
person.  Writes docs/data/source_health.json.  Sequential identifying requests; HEAD with a bounded GET fallback, at most two per URL. Failures produce nonzero exit status.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SKIP_HOSTS = ("drivendata.org",)
UA = "20GEMSDOE-source-health/2.0 (+https://github.com/buffedlizard55-lab/20GEMSDOE; weekly link check of official data sources)"


def blocked_host(url: str) -> bool:
    host=(urlparse(url).hostname or "").lower()
    return any(host==h or host.endswith("."+h) for h in SKIP_HOSTS)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if blocked_host(newurl):
            raise urllib.error.HTTPError(newurl,403,"Contest-host redirect blocked by Terms of Use",headers,fp)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def probe(url: str) -> dict:
    out = {"url": url, "ok": False, "status": None, "final_url": None, "content_type": None, "error": None}
    if blocked_host(url):
        raise ValueError("DrivenData automated access is forbidden")
    opener=urllib.request.build_opener(SafeRedirect())
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url.split("#")[0], method=method, headers={"User-Agent": UA, "Range": "bytes=0-0"} if method == "GET" else {"User-Agent": UA})
        try:
            with opener.open(req, timeout=15) as r:
                out.update(ok=200 <= r.status < 400, status=r.status, final_url=r.geturl(), content_type=r.headers.get("Content-Type"), error=None)
                return out
        except urllib.error.HTTPError as e:
            out.update(status=e.code, error=f"HTTP {e.code}")
            if method == "HEAD" and e.code in (403, 405, 400, 501):
                continue
            return out
        except Exception as e:  # noqa: BLE001
            out.update(error=repr(e)[:160])
            if method == "HEAD":
                continue
            return out
    return out


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"docs/data/source_health.json")
    args=parser.parse_args()
    rows = json.loads((ROOT / "registry" / "sources.json").read_text())["rows"]
    seen, results, skipped = set(), [], []
    for r in rows:
        url = r["url"].split("#")[0]
        if blocked_host(url):
            skipped.append({"id": r["id"], "url": url, "reason": "DrivenData Terms of Use forbid automated access"})
            continue
        if url in seen:
            continue
        seen.add(url)
        res = probe(url)
        res["id"] = r["id"]
        results.append(res)
        time.sleep(0.5)
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "results": results, "skipped_drivendata": skipped}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n")
    bad = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(bad)}/{len(results)} reachable; skipped (ToU): {len(skipped)}")
    for b in bad:
        print("  UNREACHABLE", b["id"], b["url"], b["error"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
