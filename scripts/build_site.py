"""Generate the static GitHub Pages site for 20GEMSDOE from verified JSON evidence.

Run:
    python3 scripts/build_site.py
    python3 scripts/check_site.py
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DOCS = ROOT / "docs"
DATA = DOCS / "data"
REG = ROOT / "registry"
EVI = ROOT / "evidence"
REPO_URL = "https://github.com/buffedlizard55-lab/20GEMSDOE"
BLOB = REPO_URL + "/blob/arena/01a0f501-20gemsdoe/"
COMP = "https://www.drivendata.org/competitions/306/competition-doe-gems/"
DEADLINE_ISO = "2026-12-03T23:59:00Z"


def J(p: Path):
    return json.loads(p.read_text())


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def inline(x) -> str:
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(x))


def fmt_mb(n: int) -> str:
    return f"{n / 1e6:.2f} MB"


def git_short() -> str:
    try:
        return (
            subprocess.run(["git", "rev-parse", "--short=9", "HEAD"], cwd=ROOT, capture_output=True, text=True)
            .stdout.strip()
            or "unknown"
        )
    except Exception:
        return "unknown"


subs = J(DATA / "submissions.json")
forn = J(DATA / "forensics.json")
lb = J(DATA / "leaderboard.json")
foot = J(DATA / "footprint.json")
sources = J(REG / "sources.json")
flags = J(REG / "irregularities.json")
holdout_res = J(EVI / "spatial_holdout_results.json")
thermal_rep = J(EVI / "backward_thermal_geochem_report.json")
ci = J(EVI / "ci" / "external_verification.json")
calib = J(EVI / "proxy_calibration_vs_lb.json")
signal_attribution = J(EVI / "lb_signal_attribution.json")

DL_ICON = '<svg class="ico" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M12 3v12m0 0l-5-5m5 5l5-5M4 20h16" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
NAV = [
    ("index.html", "Home & Download Hub"),
    ("executive_summary.html", "Executive Summary & Upload Guide"),
    ("research.html", "Hypotheses & Evidence"),
    ("results.html", "Leaderboard & Forensics"),
    ("knowledge.html", "Knowledge Base"),
    ("audit.html", "Sources & Irregularities"),
]


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    h = "".join(f"<th>{x}</th>" for x in headers)
    b = "".join(
        "<tr"
        + (f' class="{r[-1]}"' if len(r) > len(headers) else "")
        + ">"
        + "".join(f"<td>{c}</td>" for c in r[: len(headers)])
        + "</tr>"
        for r in rows
    )
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def candidates_js_payload() -> str:
    # Expose only fields consumed by the browser widget; do not serialize historical
    # H20 holdout, vault, or synthetic-calibration records into every generated page.
    cs = {}
    for candidate in subs["candidates"]:
        if candidate["key"] not in ("h20-1", "h20-5"):
            continue
        cs[candidate["key"]] = {
            "key": candidate["key"],
            "note": candidate["note"],
            "scored_pixels_predicted": candidate["scored_pixels_predicted"],
            "share_of_footprint_pct": candidate["share_of_footprint_pct"],
            "files": {
                kind: {field: candidate["files"][kind][field] for field in ("name", "bytes", "sha256", "href")}
                for kind in ("tif", "zip", "tif_allfinite")
            },
        }
    return f"<script>window.GEMS20_CANDIDATES = {json.dumps(cs)};</script>"


ADVISORY_NOTE = {
    "variant_strict_whole_array_no_nan_allowed": "Diagnostic only: a strict whole-array check rejects outside-footprint NaNs, including the NaNs in the official sample. The underlying historical server-error cause is unknown.",
    "profile_matches_official_sample": "Recorded local profile comparison with the supplied template; not a guarantee of server acceptance.",
    "outside_is_nan_official_text": "The supplied contest template uses NaN outside its finite footprint; use that convention for the primary artifact.",
    "nodata_tag_is_nan": "The local artifact's nodata tag is NaN, matching the supplied template.",
}


def shell(title: str, active: str, body: str, *, scripts: str = "", desc: str = "") -> str:
    nav = "".join(
        f'<a href="{h}"' + (' aria-current="page"' if h == active else "") + f">{t}</a>"
        for h, t in NAV
    )
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    top = lb["top"][0]
    group_best = lb["group"][0]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · 20GEMSDOE</title><meta name="description" content="{esc(desc or 'DOE GEMS fault-mapping research, evidence status, and format-checked GeoTIFF artifacts.')}">
<link rel="stylesheet" href="assets/site.css"></head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="in"><a class="brand" href="index.html">20GEMSDOE</a><nav class="main" aria-label="Main">{nav}<a href="{REPO_URL}" rel="noopener">GitHub</a></nav></div></header>
<div class="strip"><div class="in"><span>DOE GEMS Prize · DrivenData #306</span><span>Ends <strong>Dec 3, 2026 23:59 UTC</strong> · <strong id="countdown" data-end="{DEADLINE_ISO}"></strong></span><span>Limit: <strong>3 uploads / rolling 7 days</strong></span><span>Manual snapshot 2026-10-01: leader <strong>{top[3]:.4f}</strong> · group-linked best <strong>{group_best['score']:.4f}</strong></span><a href="{COMP}" rel="noopener">Competition</a></div></div>
<main id="main" class="wrap">{body}
<footer><p>Built {built} from commit <code>{git_short()}</code> on branch <code>arena/01a0f501-20gemsdoe</code>. Snapshot and claim limitations are stated in <a href="audit.html">Sources &amp; Irregularities</a>. Project brief &amp; Arena Core Values: <a href="{BLOB}README.md">README.md</a>.</p></footer></main>
{candidates_js_payload()}<script src="js/gems-tiff.js"></script><script src="js/site.js"></script>{scripts}</body></html>
"""


def check_list(c: dict) -> str:
    checks = c["checks_official_format"]["checks"]
    hard = [v for v in checks.values() if v["hard"]]
    passed = all(v["pass"] for v in hard)
    outside = checks.get("outside_is_nan_official_text", {})
    uniqueness = c.get("uniqueness", {})
    items = [
        f'<li><strong>Recorded local format/range checks:</strong> {"all recorded hard checks pass" if passed else "one or more hard checks fail"} ({len(hard)} checks); values inside the footprint are finite and in <code>[0, 1]</code>. This is not a model-quality, server-acceptance, or score result.</li>',
        f'<li><strong>Outside-footprint convention:</strong> {"the local TIFF has NaN outside the footprint, matching the supplied template" if outside.get("pass") else "the local artifact does not pass the recorded NaN-outside check"}. The historical server-side range-error cause remains unknown.</li>',
        f'<li><strong>Archived artifact comparison:</strong> content ID <code>{esc(c.get("content_id", "unknown"))}</code>; recorded uniqueness verdict <code>{esc(uniqueness.get("verdict", "not recorded"))}</code>. This is a file-similarity check only, not evidence of expected DTI gain.</li>',
        '<li><strong>Submission decision:</strong> not recommended. The stored H20 proxy metrics are unreproduced, and H20-5 calibration was evaluated against a synthetic target.</li>',
    ]
    return '<ul class="check">' + "".join(items) + "</ul>"


def build_interactive_builder_widget() -> str:
    cs = {c["key"]: c for c in subs["candidates"]}
    c1 = cs["h20-1"]
    c2 = cs["h20-5"]
    f1 = c1["files"]["tif"]
    return f"""<section class="card cand" id="interactive-submission-builder" style="border-width:2px;margin-bottom:1.25rem">
<span class="badge b-warn">FORMAT-CHECKED RESEARCH ARTIFACTS · NO SCORE RECOMMENDATION</span>
<h2 style="margin-top:.35rem">Download and pre-flight existing GeoTIFF artifacts</h2>
<p class="muted" style="margin-top:0">This browser tool packages and checks files already in <code>docs/downloads/</code>; it does not train a model or create predictions. Local checks confirm the current file's structure and <code>[0, 1]</code> values inside the template footprint. Stored H20 holdout values are unreproduced known-fault proxies; H20-5's calibration target is synthetic. <strong>Neither artifact is recommended for a weekly submission.</strong></p>
<div class="grid g2" style="margin:.75rem 0">
  <div>
    <label for="sb-cand-select"><strong>1. Select a format-checked research artifact:</strong></label><br>
    <select id="sb-cand-select" style="width:100%;padding:.5rem;margin-top:.25rem;border-radius:6px;border:1px solid #cbd5e1;font-size:.95rem">
      <option value="h20-1">H20-1 — stored SAR-nnPU/multi-line raster (not recommended)</option>
      <option value="h20-5">H20-5 — continuous proxy raster; calibration unverified (not recommended)</option>
    </select>
  </div>
  <div>
    <label for="sb-fmt-select"><strong>2. Select file packaging:</strong></label><br>
    <select id="sb-fmt-select" style="width:100%;padding:.5rem;margin-top:.25rem;border-radius:6px;border:1px solid #cbd5e1;font-size:.95rem">
      <option value="tif">GeoTIFF with official NaN/null outside-footprint convention</option>
      <option value="zip">ZIP containing the official-convention GeoTIFF</option>
      <option value="tif_allfinite">All-finite diagnostic twin (zeros outside; not the official convention)</option>
    </select>
  </div>
</div>
<div class="row" style="margin:.75rem 0">
  <a id="sb-dl-btn" class="btn primary" href="{esc(f1['href'])}" download="{esc(f1['name'])}">{DL_ICON}Download format-checked artifact ({esc(f1['name'])} · {fmt_mb(f1['bytes'])})</a>
  <button id="sb-verify-btn" class="btn" type="button">Run browser-side GeoTIFF pre-flight</button>
  <a class="btn" href="{COMP}submissions/" rel="noopener">Open DrivenData submissions page ↗</a>
</div>
<div id="sb-verify-out" aria-live="polite"></div>
<dl class="kv" style="margin-top:.6rem">
  <dt>Unique file name</dt><dd><code id="sb-fn">{esc(f1['name'])}</code> <button class="btn" type="button" data-copy="sb-fn">Copy filename</button></dd>
  <dt>Pasteable note</dt><dd><code class="note" id="sb-note">{esc(c1['note'])}</code> <button class="btn" type="button" data-copy="sb-note">Copy note</button></dd>
  <dt>SHA-256</dt><dd><code id="sb-sha">{esc(f1['sha256'])}</code> <button class="btn" type="button" data-copy="sb-sha">Copy checksum</button></dd>
</dl>
<p id="sb-stats" class="small muted" style="margin-bottom:0"><strong>Footprint range check:</strong> finite values in <code>[0.0, 1.0]</code> on <code>{foot['footprint_pixels']:,}</code> template cells; outside cells follow the selected packaging. This is a file-format check, not a model-quality or score validation.</p>
</section>"""


def cand_card(c: dict, label: str, cls: str, badge: str) -> str:
    files = c["files"]
    key = c["key"]
    checks_rows = []
    for name, detail in c["checks_official_format"]["checks"].items():
        kind = "hard local check" if detail["hard"] else "advisory"
        status = "pass" if detail["pass"] else ("fail" if detail["hard"] else "not applicable")
        note = ADVISORY_NOTE.get(name, detail["detail"])
        checks_rows.append([esc(name.replace("_", " ")), kind, status, esc(note)])
    return f"""<article class="card cand {cls}" id="cand-{key}">
<span class="badge {badge}">{esc(label)}</span>
<h3>{esc(c["title"])}</h3>
<p class="muted">{esc(c["one_liner"])}</p>
<div class="row"><a class="btn primary" href="{esc(files['tif']['href'])}" download>{DL_ICON}Download format-checked research artifact (.tif · {fmt_mb(files['tif']['bytes'])})</a>
<a class="btn" href="{esc(files['zip']['href'])}" download>Download .zip ({fmt_mb(files['zip']['bytes'])})</a>
<a class="btn" href="{esc(files['tif_allfinite']['href'])}" download title="Diagnostic twin: same in-footprint values, zeros rather than NaN outside.">Download all-finite diagnostic twin (.tif)</a></div>
<dl class="kv"><dt>Unique file name</dt><dd><code id="fn-{key}">{esc(files['tif']['name'])}</code> <button class="btn" type="button" data-copy="fn-{key}">Copy filename</button></dd>
<dt>Pasteable note</dt><dd><code class="note" id="note-{key}">{esc(c['note'])}</code> <button class="btn" type="button" data-copy="note-{key}">Copy note</button></dd>
<dt>In-footprint positive-valued cells</dt><dd><code>{c['scored_pixels_predicted']:,}</code> (<code>{c['share_of_footprint_pct']}%</code> of footprint; <code>{c.get('unique_probability_levels', 2):,}</code> distinct values) · content ID <code>{esc(c['content_id'])}</code></dd>
<dt>GeoTIFF SHA-256</dt><dd><code>{esc(files['tif']['sha256'])}</code></dd></dl>
{check_list(c)}
<details><summary>Recorded local format checks (not a score/eligibility check)</summary>{table(["Check", "Kind", "Result", "Detail"], checks_rows)}</details>
</article>"""


def build_index() -> str:
    cs = {c["key"]: c for c in subs["candidates"]}
    top = lb["top"][0]
    group_best = lb["group"][0]
    body = f"""
<h1>20GEMSDOE — DOE GEMS research and GeoTIFF download hub</h1>
<p class="lead">A source-audited research log and simple downloader for existing, format-checked raster artifacts. <strong>No current candidate is recommended for upload.</strong> Holdout evidence is proxy-based and unreproduced; H20-5's stated calibration uses a synthetic target. These artifacts are not hidden-fault validation.</p>
<div class="alert warn"><strong>Evidence correction:</strong> Earlier site copy overstated H20 calibration, pre-registration, vault and upload eligibility. The old “hidden-fault hit rate” was computed against a synthetic target; the same stored vault was evaluated for two candidates. See <a href="audit.html#F25">F25–F29</a>. No hidden-fault score or reliability claim is established.</div>
{build_interactive_builder_widget()}
<div class="grid g2">{cand_card(cs['h20-1'], 'H20-1 · format-checked research raster · not recommended', '', 'b-warn')}{cand_card(cs['h20-5'], 'H20-5 · format-checked continuous raster · calibration claim withdrawn', '', 'b-warn')}</div>
<h2>Where the public leaderboard stands</h2>
<div class="grid g3">
<div class="card"><span class="muted small">Manual official snapshot · 2026-10-01</span><p style="font-size:2rem;margin:.1em 0"><strong>{top[3]:.4f}</strong></p><p class="small">Leader <code>{esc(top[1])}</code> (rank {top[0]}). The starting value 0.3049 is stale.</p></div>
<div class="card"><span class="muted small">Highest group-associated account snapshot</span><p style="font-size:2rem;margin:.1em 0"><strong>{group_best['score']:.4f}</strong></p><p class="small"><code>{esc(group_best['participant'])}</code>, rank {group_best['rank']}; repository mapping is owner-reported.</p></div>
<div class="card"><span class="muted small">Submission status</span><p style="font-size:1.25rem;margin:.2em 0"><strong>No recommendation</strong></p><p class="small">H20 values are historical known-catalogue proxy reports, not reproduced hidden-fault evidence. No H21 slot is authorized.</p></div>
</div>
<h2>Why the historical 0.1563 score repeated</h2>
<p>The archived <code>GEMSDOE1</code> and <code>5GEMSDOE</code> rasters are byte-identical; <code>8GEMSDOE</code> has a different file hash but matches their predictions at all official scored pixels after the pixel-exact known-fault mask. The archived <code>17GEMSDOE</code> raster also matches on scored pixels, but is distinct from <code>17GEMSDOE-F</code> (reported 0.0187). <code>GEMSDOE2</code> is a 0.9464-Jaccard near-duplicate with a reported 0.1560. This is an artifact-level explanation, not proof of model lineage or account attribution. <a href="results.html#duplicates">See the scored-pixel comparison</a>.</p>
<h2>What is and is not established</h2>
<div class="grid g2">
<div class="card"><h3>Established locally</h3><ul><li>Current downloadable TIFFs match the template grid and pass recorded footprint range/format checks.</li><li>All 13 DEM10 channels were verified; `prepare_data.py` completed.</li><li>Official staff clarified exact known-fault masking, new-fault definition and rolling submission allowance.</li></ul></div>
<div class="card"><h3>Not established</h3><ul><li>H20 holdout numbers are not reproduced; their target is known-catalogue transfer, not hidden new faults.</li><li>H20-5 calibration is to a synthetic target and is not evidence of hidden-fault probability calibration.</li><li>The H20 “Vault” is not untouched; H20-1 and H20-5 share its stored evaluation.</li><li>The cause of a historical server-side [0,1] error is unknown.</li></ul></div>
</div>
<p class="small muted">Leaderboard snapshots are manual: DrivenData Terms of Use prohibit robots/spiders and other automatic website access. See the <a href="executive_summary.html">Executive Summary</a>, <a href="research.html">H21 hypotheses</a>, <a href="results.html">forensics</a>, and <a href="audit.html">source/irregularity ledger</a>.</p>
"""
    return shell(
        "Research & GeoTIFF Download Hub",
        "index.html",
        body,
        desc="Evidence-audited DOE GEMS research, spatial holdout limits, and format-checked GeoTIFF artifacts; no candidate is currently recommended.",
    )


def build_submit() -> str:
    c1 = next(c for c in subs["candidates"] if c["key"] == "h20-1")
    c2 = next(c for c in subs["candidates"] if c["key"] == "h20-5")
    body = f"""
<h1>Executive Summary — GeoTIFF download and upload guide</h1>
<div class="alert warn"><strong>Decision first:</strong> the listed H20 files pass local format checks, but neither is currently recommended for a submission slot. Stored H20 holdout numbers are unreproduced known-catalogue proxies; H20-5's Brier target is synthetic; the stored Vault was used for two candidates. See <a href="audit.html#F17">F17 and F25–F29</a>.</div>
<p class="lead">This page makes the existing files easy to inspect and, if you independently decide to use one, explains the upload steps. The web tool does not train a model, generate a new surface or prove a contest score.</p>
{build_interactive_builder_widget()}
<div class="grid g2">{cand_card(c1, 'H20-1 · format-checked research raster · no upload recommendation', '', 'b-warn')}{cand_card(c2, 'H20-5 · format-checked continuous proxy raster · no upload recommendation', '', 'b-warn')}</div>

<div class="card"><h2 style="margin-top:0">Upload steps (only if you independently elect to proceed)</h2><ol class="steps">
<li><strong>Choose the NaN-outside GeoTIFF.</strong> The contest file specification says pixels outside the bounds should be null/NaN. Use the individual <code>.tif</code>, not a screenshot or the diagnostic all-finite twin.</li>
<li><strong>Run the local pre-flight.</strong> Click <strong>Run browser-side GeoTIFF pre-flight</strong> or use the checker below. It verifies the template grid and finite values in <code>[0,1]</code> within the footprint; it does not reproduce the server's hidden validator or establish prediction quality.</li>
<li><strong>Open the official submissions page:</strong> <a href="{COMP}submissions/" rel="noopener">{COMP}submissions/</a> and choose <strong>Make new submission</strong>.</li>
<li><strong>Select the file and note.</strong> Choose the unique filename shown on the artifact card. Copy its note only if you upload; the note explicitly labels the file as an unreproduced research proxy.</li>
<li><strong>Record the outcome manually.</strong> The site does not poll DrivenData. If a file is accepted/scored, record that result through the repository's manual score-recording workflow and keep the exact artifact hash.</li>
</ol></div>

<h2 id="checker-title">Interactive drag-and-drop GeoTIFF checker (runs in your browser)</h2>
<div id="checker" class="card"><div class="drop"><p><strong>Drop a .tif file here</strong> or choose a file from disk</p><p><input type="file" accept=".tif,.tiff,image/tiff" aria-label="Choose a GeoTIFF to check"></p><p class="small muted">Uses <code>js/gems-tiff.js</code> and <code>data/footprint.bin</code>; the file is read locally in your browser, not uploaded to this site. Checks CRS, dimensions, dtype, geotransform and footprint values.</p></div><div class="out" aria-live="polite"></div></div>

<h2>About the earlier “Predicted values must be in range [0, 1]” message</h2>
<p><strong>The original cause is unknown.</strong> The rejected file and server-side validator are unavailable, so the repository cannot prove why that earlier message appeared. Possible problems include non-finite/out-of-range values inside the scored footprint, a mask/grid mismatch, or a validator treating allowed outside-footprint NaNs as ordinary values; these are hypotheses, not a root-cause diagnosis.</p>
{table(["Check", "What is verified for the current artifact", "What this does not prove"], [
  ["Footprint values", f"{foot['footprint_pixels']:,} template cells are finite float32 values in [0, 1].", "It does not identify the contents of a different historical rejected file."],
  ["Outside convention", f"The official-convention TIF uses NaN outside the {foot['footprint_pixels']:,}-cell footprint, matching the local template.", "A strict whole-array validator that rejects any NaN is not established as the contest validator."],
  ["All-finite twin", "The optional twin uses 0.0 outside the footprint for diagnostics only.", "Zeros outside do not follow the stated null/NaN convention; this version is not the preferred contest artifact."],
])}
<div class="alert info"><strong>Keep the claims separate:</strong> format checks show that this local file meets the recorded structural/range checks. They do not prove that the server will accept a different file, that a hidden-fault score will be high, or that the old error has been fixed at its source.</div>
"""
    return shell(
        "Executive Summary & Upload Guide",
        "executive_summary.html",
        body,
        scripts='<script src="js/check.js"></script>',
        desc="Step-by-step upload guide and browser-side checks for existing GeoTIFF research artifacts; no model or score recommendation.",
    )


def build_research() -> str:
    summary = holdout_res.get("summary", {})
    h20_1 = summary.get("H20_1_SAR_nnPU_MultiLine_Corroborated", {})
    h20_5 = summary.get("H20_5_Calibrated_Continuous_SoftTail_nnpu", {})
    if h20_1 and h20_5:
        stored_tbl = table(
            ["Stored candidate", "Mean Dense DTI", "Mean Sparse DTI", "Evidence status"],
            [
                ["H20-1", f"{h20_1['mean_dense_dti']:.5f}", f"{h20_1['mean_sparse_dti']:.5f}", "historical report; not reproduced; known-fault transfer proxy"],
                ["H20-5", f"{h20_5['mean_dense_dti']:.5f}", f"{h20_5['mean_sparse_dti']:.5f}", "historical report; not reproduced; known-fault transfer proxy"],
            ],
        )
    else:
        stored_tbl = '<p>Stored H20 summary is unavailable; no H20 metric is shown.</p>'
    h21_path = EVI / "h21_seismic_ridge_holdout.json"
    if h21_path.exists():
        h21 = J(h21_path)
        ev = h21["evaluation"]["h21_multiscale_ridge"]
        raw = h21["evaluation"]["raw_seismic_ieq_control"]
        comparisons = h21["evaluation"].get("comparison_to_stored_references", {})
        h20_gate = comparisons.get("gate_vs_stored_h20_best", {})
        h16_gate = comparisons.get("gate_vs_reproduced_h16_1", {})
        if h20_gate and h16_gate:
            gate_text = "passed both comparator screens" if comparisons.get("conservative_screen_passed") else "did not pass both comparator screens"
        else:
            gate_text = "could not be compared against both required references"
        h21_block = f"""<p><strong>H21-1 proxy result:</strong> Dense <code>{ev['mean_dense_dti']:.5f}</code>, Sparse <code>{ev['mean_sparse_dti']:.5f}</code>; raw scalar control Dense <code>{raw['mean_dense_dti']:.5f}</code>, Sparse <code>{raw['mean_sparse_dti']:.5f}</code>. It {gate_text}. The H20 comparator remains historical and unreproduced; H16-1 is the current reproduced known-catalogue baseline. Even passing both would be only a necessary proxy screen, not hidden-fault validation or automatic upload authorization. Full report: <a href="{BLOB}evidence/h21_seismic_ridge_holdout.json">evidence/h21_seismic_ridge_holdout.json</a>.</p>"""
    else:
        h21_block = '<p><strong>H21-1 status:</strong> preregistered; no result file exists yet. The first run is a spatial-transfer proxy against known catalogue faults, not hidden-fault validation. No submission is authorized.</p>'

    md = (DOCS / "research" / "hypothesis_register.md").read_text()
    md_html = markdown.markdown(md, extensions=["tables", "toc", "fenced_code", "sane_lists", "md_in_html"])
    # The register is authored beside research/*.md, while this HTML page is one level up.
    md_html = md_html.replace('href="../../', 'href="../')
    md_html = md_html.replace('href="../audit.html', 'href="audit.html')
    md_html = md_html.replace('href="../research/', 'href="research/')
    md_html = md_html.replace('href="preregistration_h21.md', 'href="research/preregistration_h21.md')
    signal_min_p = min(r["p_uncorrected"] for r in signal_attribution["top_by_abs_rho"])
    signal_bonferroni = signal_attribution["bonferroni_p_threshold_0_05"]
    signal_summary = f"""<h2>Exploratory archived-raster signal attribution</h2>
<p>This cross-file screen is exploratory hypothesis generation across {signal_attribution['n_files']} archived rasters, not an independent hidden-fault test or model-selection rule. Nothing is significant after correction among the reported feature associations: the smallest listed uncorrected p-value is <code>{signal_min_p:.4g}</code>, above the Bonferroni threshold <code>{signal_bonferroni:.4g}</code>. See <a href="{BLOB}evidence/lb_signal_attribution.json">the preserved analysis</a>.</p>"""
    body = f"""
<h1>Research — hypotheses, PU framing and validation limits</h1>
<p class="lead">This page separates geological reasoning from observed evidence. The competition's hidden new-fault labels are not available for pre-submission calibration; known-fault spatial holdouts are proxies only.</p>
<div class="alert warn"><strong>Correction to earlier copy:</strong> the H20 “hidden-fault calibration” used a synthetic outcome generated from catalogue/SGMC proximity and model-based Bernoulli probabilities. Its REL/ECE values are not empirical hidden-fault calibration. The stored “untouched Vault” was evaluated for H20-1 and H20-5. Prior result chronology is not independently proven by this checkout. See <a href="audit.html#F25">F25–F29</a>.</div>
<h2>Stored H20 spatial-transfer results (not reproduced)</h2>
<p>The values below are copied from <code>evidence/spatial_holdout_results.json</code>. They score withheld portions of the known-fault raster and a synthetic sparse-component proxy; official staff says those known-fault pixels are excluded from competition scoring. Do not interpret these as hidden-fault DTI or a leaderboard forecast.</p>
{stored_tbl}
<p class="small muted">Source: <a href="{BLOB}evidence/spatial_holdout_results.json">evidence/spatial_holdout_results.json</a>. OOF caches required to regenerate the values are incomplete in this checkout.</p>
<h2>Why consider positive-unlabeled learning?</h2>
<p><strong>Inference:</strong> an incomplete catalogue makes it plausible that pixels outside known traces include both background and unlabelled faults. That motivates testing PU methods. Kiryo et al.'s nnPU estimator addresses PU risk under mixture assumptions and a specified or estimated class prior; the method does not validate those assumptions for this dataset.</p>
<p>The frequently cited <code>π = 0.0363</code> is a power-law extrapolation below a selected trace-completeness cutoff, not an observed hidden-pixel prevalence. Treat it as a prior scenario. The local implementation is in <code>src/gems/pu_learning.py</code>; see <a href="https://proceedings.neurips.cc/paper/2017/file/7cce53cf90577442771720a370c3c723-Paper.pdf" rel="noopener">Kiryo et al. (2017)</a>.</p>
<h2>Calibration report status</h2>
<p>The previous report constructs <code>s_hit</code> from distance to known catalogue/SGMC features, computes a selected-prior-based <code>p_hidden_u</code>, then samples <code>y_pu_hidden_truth = s_hit OR Bernoulli(p_hidden_u)</code>. Its Brier score, Murphy REL/ECE and “0.70-bin hit rate” therefore measure agreement with a synthetic proxy target. They do <strong>not</strong> verify calibrated probabilities on recovered or observed hidden faults. We withdraw the phrase “Brier-verified.” No independent hidden-fault reliability diagram is available.</p>
<h2>H21-1 preregistered test</h2>
<p>The frozen H21-1 transform uses multi-scale Hessian line ridges from band 16, <code>ieq_n100a15</code>, and compares against the scalar seismic-intensity feature at the same fixed budget. Its protocol is in <a href="research/preregistration_h21.md">research/preregistration_h21.md</a>. USGS Great Basin studies motivate a test of seismicity/structure relationships but do not show that this particular layer or transform improves contest DTI.</p>
{h21_block}
{signal_summary}
<h2>Ranked candidate hypotheses and source availability</h2>
<div class="md">{md_html}</div>
"""
    return shell(
        "Hypotheses & Evidence Status",
        "research.html",
        body,
        desc="Ranked H21 hypotheses, conditional PU rationale, synthetic calibration correction, and known-catalogue spatial holdout limitations.",
    )


OUTSIDE_LABEL = {"nan": "NaN (official)", "zero": "zeros", "other": "other (non-NaN, non-zero)"}


def build_proxy_table() -> str:
    rows = []
    owner_reported_scores = {"h16-1": 0.1855, "h19-4": 0.1894}
    for c in calib["candidates_on_the_same_scales"]:
        lb_val = owner_reported_scores.get(c["key"])
        lb_str = "Not live-scored" if c["key"].startswith("h20-") else ("—" if lb_val is None else f"<strong>{lb_val:.4f}</strong> (account mapping owner-reported)")
        cls = "hl" if c["key"].startswith("h20-") or c["key"] in ("h19-4", "h16-1") else ""
        row = [
            f"<code>candidate:{esc(c['key'])} ({esc(c['content_id'])})</code>",
            lb_str,
            f"{c['n_pred_scored']:,}",
            f"<strong>{c['sgmc_gap']:.5f}</strong>",
            f"<strong>{c['sgmc_offcat']:.5f}</strong>",
            f"<strong>{c['known_dense']:.5f}</strong>",
        ]
        if cls:
            row.append(cls)
        rows.append(row)
    for r in calib["per_file"]:
        lb_str = "—" if r["lb_score"] is None else f"<strong>{r['lb_score']:.4f}</strong> (historical reported)"
        row = [
            f"<code>{esc(r['id'])}</code>",
            lb_str,
            f"{r['n_pred_scored']:,}",
            f"{r['sgmc_gap']:.5f}",
            f"{r['sgmc_offcat']:.5f}",
            f"{r['known_dense']:.5f}",
        ]
        rows.append(row)
    return table(
        [
            "Archived raster / candidate ID",
            "Reported public score (owner mapping noted)",
            "Positive scored pixels",
            "SGMC-gap proxy DTI",
            "SGMC off-catalogue proxy DTI",
            "Known-catalogue Dense DTI",
        ],
        rows,
    )


def build_results() -> str:
    top_rows = [[str(r[0]), esc(r[1]), str(r[2]), f"{r[3]:.4f}"] for r in lb["top"]]
    grp_rows = [
        [str(g["rank"]), esc(g["participant"]), str(g["submissions"]), f"{g['score']:.4f}", esc(g["status"]), "hl"]
        for g in lb["group"]
    ]
    lb_tbl = table(["Rank", "Participant", "Submissions", "Best public DW-Tversky"], top_rows)
    grp_tbl = table(["Rank", "Account", "Submissions", "Best score", "Attribution status"], grp_rows)
    ent = forn["entries"]
    by_dup = {}
    for grp in forn["identical_on_scored_pixel_groups"]:
        for i in grp:
            by_dup[i] = "same predictions on scored pixels: " + ", ".join(x for x in grp if x != i)
    for p in forn["near_duplicate_pairs"]:
        for a, b in ((p["a"], p["b"]), (p["b"], p["a"])):
            by_dup.setdefault(a, f"near-duplicate of {b} (J={p['jaccard_positive']:.2f})")
    rows = []
    for e in sorted(ent, key=lambda e: -(e["lb_score"] if e["lb_score"] is not None else -1)):
        cls = "hl" if e["id"] in ("19GEMSDOE-H19-4", "16GEMSDOE") else ("dup" if e["id"] in by_dup else "")
        rows.append(
            [
                esc(e["display_name"]),
                "—" if e["lb_score"] is None else f"<strong>{e['lb_score']:.4f}</strong>",
                f"{e['positive_scored_pixels']:,}",
                f"{100 * e['frac_near_le_300m']:.1f}%",
                f"{100 * e['frac_far_gt_1500m']:.1f}%",
                OUTSIDE_LABEL.get(e["outside_mode"], esc(e["outside_mode"])),
                f"<code>{esc(e['sha256'][:12])}…</code>",
                esc(by_dup.get(e["id"], "distinct on scored pixels")),
                f'<a href="https://github.com/buffedlizard55-lab/{esc(e["github_repo"])}" rel="noopener">repo</a>',
                cls,
            ]
        )
    ent_tbl = table(
        ["Archived entry", "Reported public score", "Positive scored px", "≤300 m of catalogue", ">1.5 km", "Outside values", "SHA-256", "Scored-surface relation", "Source"],
        rows,
    )
    lin = []
    for l in forn["lineage"][:8]:
        lin.append(
            [
                f"<code>{esc(l['git_blob_sha1'][:10])}…</code>",
                str(l["copies"]),
                esc(", ".join(l["repos"])),
                esc(", ".join(l["registry_entries"]) or "—"),
                ", ".join(f"{s:.4f}" for s in l["lb_scores"]) or "—",
            ]
        )
    lin_tbl = table(["Git blob", "Copies", "Repositories", "Registered entries", "Reported score(s)"], lin)
    body = f"""
<h1>Results — manual leaderboard snapshot and artifact forensics</h1>
<p class="lead">The public leaderboard and archived group rasters answer different questions. The leaderboard is a dated official page snapshot; raster comparisons establish artifact identity on scored cells, not necessarily which file/account was uploaded.</p>
<h2>Manual official leaderboard snapshot — 2026-10-01</h2>
<p>DARD was <strong>0.3168</strong> at rank 1. The current page showed <code>smrtdoog5</code> at <strong>0.1894</strong> (rank 23) and <code>extradr19</code> at <strong>0.1855</strong> (rank 25); mapping those accounts to 19GEMSDOE and 16GEMSDOE respectively is owner-reported. Scores/ranks may change; this page is not automatically refreshed.</p>
{lb_tbl}
<h3>Group-associated accounts (file mapping status stated explicitly)</h3>{grp_tbl}
<h2 id="duplicates">27 archived raster entries compared on official scored pixels</h2>
<p>The comparison mask is the finite template footprint minus the supplied known-fault pixels, matching the pixel-exact exclusion described by DrivenData staff. Positive-mask Jaccard is a diagnostic for binary support; exact scored-surface identity additionally checks values on the score mask.</p>
{ent_tbl}
<div class="alert info"><strong>Why the 0.1563 score repeated:</strong> archived <code>GEMSDOE1</code> and <code>5GEMSDOE</code> have identical bytes (Git blob <code>812e61b740…</code>, SHA-256 <code>7f00890a…</code>). <code>8GEMSDOE</code> has a different file hash but the same prediction on all scored pixels; its differences are on masked known-fault cells. The archived <code>17GEMSDOE</code> file also has the same scored surface, but is not the separately named <code>17GEMSDOE-F</code> artifact (reported score 0.0187). <code>GEMSDOE2</code> is near-duplicate (Jaccard 0.9464), not identical, and its reported score is 0.1560. The strongest artifact-level explanation is therefore duplicate-effective predictions, not a new model score. Historic file/account attribution is partly owner-reported.</div>
<div class="grid g2"><div class="card"><h3>Why did the public score rise from 0.1563 to 0.1855?</h3><p>The archived 16GEMSDOE raster is distinct and has fewer positive scored pixels than the 0.1563 ensemble raster (123,939 vs 166,519 in this archive); its owner-associated public score is higher. This is an observed association, not a causal explanation. No matched live A/B or independently validated ablation in this checkout isolates whether lidar, DEM10, ridge thinning, budget, or another change caused the difference.</p><p>The same caution applies to the later 0.1894 H19-4 score: its account/file mapping is owner-reported and the local H20/H19 spatial results are not a hidden-test substitute.</p></div><div class="card"><h3>Observed low-score patterns are not causal diagnoses</h3><p>The archived 18GEMSDOE raster covers 8.76% of the footprint and has reported score 0.0297; 17GEMSDOE-F has 61.5% of its positives within 300 m of known traces and reported score 0.0187. These are measurable geometry/score associations. They do not establish that overprediction or near-catalogue concentration alone caused the result.</p></div></div>
<h2>Repository artifact lineage</h2>{lin_tbl}
<h2>External geological proxies — descriptive only, not “calibration”</h2>
<p>These proxy scores compare candidate rasters with known catalogue/SGMC-derived layers. They are not independent hidden-new-fault truth, are not a calibration to the public score, and do not establish a submission's expected leaderboard result. The stored H20 comparison has not been reproduced.</p>
{build_proxy_table()}
"""
    return shell(
        "Leaderboard & Forensic Results",
        "results.html",
        body,
        desc="Dated public leaderboard snapshot, exact scored-pixel artifact comparisons, repeated-score explanation and validation caveats.",
    )


def build_knowledge() -> str:
    text = (DOCS / "knowledge" / "knowledge_base.md").read_text()
    md_html = markdown.markdown(text, extensions=["tables", "toc", "fenced_code", "sane_lists", "md_in_html"])
    md_html = md_html.replace('href="../../', 'href="../')
    md_html = md_html.replace('href="../audit.html', 'href="audit.html')
    md_html = md_html.replace('href="../data/', 'href="data/')
    md_html = md_html.replace('href="../research/', 'href="research/')
    md_html = md_html.replace('href="../registry/', 'href="../registry/')
    return shell(
        "Knowledge Base — Evidence & Limitations",
        "knowledge.html",
        f'<div class="md">{md_html}</div>',
        desc="Evidence and limitations for competition rules, data provenance, PU assumptions, spatial validation, geology and external data.",
    )


def build_audit() -> str:
    st_badge = {"verified": "b-ok", "flagged": "b-warn", "computed": "b-info"}
    src_rows = [
        [
            esc(r["id"]),
            esc(r["topic"]),
            inline(r["claim"]),
            f'<a href="{esc(r["url"])}" rel="noopener">link</a>',
            inline(r["how_verified"]),
            f'<span class="badge {st_badge.get(r["status"], "b-info")}">{esc(r["status"])}</span>'
            + (f'<br><span class="small muted">{inline(r["note"])}</span>' if r["note"] else ""),
        ]
        for r in sources["rows"]
    ]
    sev = {"high": "b-bad", "medium": "b-warn", "low": "b-info", "info": "b-info"}
    flag_rows = []
    for f in flags["flags"]:
        links = " ".join(f'<a href="{esc(u)}" rel="noopener">[{i + 1}]</a>' for i, u in enumerate(f["links"]))
        flag_rows.append(
            [
                f'<a id="{esc(f["id"])}"></a><strong>{esc(f["id"])}</strong>',
                f'<span class="badge {sev[f["severity"]]}">{esc(f["severity"])}</span><br><span class="small muted">{esc(f["status"])}</span>',
                f"<strong>{inline(f['title'])}</strong><br>{inline(f['evidence'])}",
                inline(f["action"]) + (f"<br>{links}" if links else ""),
            ]
        )
    ci_dl = "".join(
        f'<tr><td>{esc(k)}</td><td>{"✔" if v["ok"] else "✖"}</td><td class="num">{v.get("bytes", 0):,}</td><td><a href="{esc(v["url"])}" rel="noopener">source</a></td></tr>'
        for k, v in ci["downloads"].items()
    )
    open_high = sum(1 for f in flags["flags"] if f["severity"] == "high" and f["status"] == "open")
    body = f"""
<h1>Audit — source registry and irregularities</h1>
<p class="lead">This page separates verified source statements, repository computations and flagged claims. A populated source table is not a guarantee that every statement in the repository is correct. As of the 2026-10-01 review, the registry contains {len(sources['rows'])} source/computation records and {len(flags['flags'])} flags; {open_high} high-severity items remain open.</p>
<div class="alert warn"><strong>Priority open flags:</strong> synthetic H20 calibration target (F25), unvalidated power-law class prior (F26), reused stored Vault (F27), incomplete H20 OOF caches (F28), unverified preregistration chronology (F29), bridge-copy data provenance (F30), unknown historical range-error cause (F31), and previously overstated site copy (F32).</div>
<h2>Flagged irregularities</h2>{table(["ID", "Severity / Status", "Evidence and issue", "Action and links"], flag_rows)}
<h2>Source and computed-evidence registry</h2>
<p>Rows marked <code>flagged</code> intentionally retain claims only to explain why they are not currently supported. For all competition scores, check the timestamped leaderboard snapshot and the official live page manually. Automatic scraping is not used.</p>
<div class="tw"><table><thead><tr><th>ID</th><th>Topic</th><th>Claim or finding</th><th>Source link</th><th>How checked</th><th>Status and note</th></tr></thead><tbody>{"".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in src_rows)}</tbody></table></div>
<h2>Historical official-host download checks (CI record)</h2>
<p>These are archived network/download checks, not a guarantee that every source is current or every file is present in this sandbox. Core competition inputs here came from a hash-pinned team bridge, not an independent official-host comparison.</p>
<div class="tw"><table><thead><tr><th>Dataset / layer</th><th>CI check</th><th>Bytes</th><th>Recorded upstream</th></tr></thead><tbody>{ci_dl}</tbody></table></div>
<p class="small muted">Machine-readable records: <a href="{BLOB}registry/sources.json">registry/sources.json</a>, <a href="{BLOB}registry/irregularities.json">registry/irregularities.json</a>, <a href="{BLOB}evidence/ci/external_verification.json">evidence/ci/external_verification.json</a>, and <a href="{BLOB}evidence/ci/dem1m_tile_audit.json">evidence/ci/dem1m_tile_audit.json</a>.</p>
"""
    return shell("Sources & Irregularities", "audit.html", body, desc="Source verification status and known irregularities; includes open limitations and historical download checks.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the static 20GEMSDOE research and download site.")
    parser.add_argument("--check-only", action="store_true", help="Load and validate source JSON, then exit without writing site files.")
    args = parser.parse_args(argv)
    if args.check_only:
        print("source data loaded; no site files written")
        return
    pages = {
        "index.html": build_index(),
        "executive_summary.html": build_submit(),
        "results.html": build_results(),
        "research.html": build_research(),
        "knowledge.html": build_knowledge(),
        "audit.html": build_audit(),
    }
    for name, content in pages.items():
        (DOCS / name).write_text(content)
        print(f"wrote docs/{name} ({len(content):,} bytes)")
    # Also write docs/submit.html redirect so any bookmark to submit.html works seamlessly
    (DOCS / "submit.html").write_text(
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=executive_summary.html">'
        '<link rel="canonical" href="executive_summary.html"><title>20GEMSDOE Executive Summary</title></head><body>'
        '<p>Redirecting to the <a href="executive_summary.html">20GEMSDOE Executive Summary &amp; Upload Guide</a>…</p></body></html>\n'
    )
    (ROOT / "index.html").write_text(
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=docs/index.html">'
        '<link rel="canonical" href="docs/index.html"><title>20GEMSDOE</title></head><body>'
        '<p>Redirecting to the <a href="docs/index.html">20GEMSDOE submission hub</a>…</p></body></html>\n'
    )
    (ROOT / ".nojekyll").write_text("")


if __name__ == "__main__":
    main()
