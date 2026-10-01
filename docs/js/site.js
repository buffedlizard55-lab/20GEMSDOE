/* Progressive enhancements. Downloads work without JS; no automated DrivenData access. */
(function () {
  'use strict';
  function esc(s) { return String(s).replace(/[&<>"']/g,function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function fallbackCopy(text) {
    var t=document.createElement('textarea');t.value=text;t.setAttribute('readonly','');t.style.position='fixed';t.style.opacity='0';document.body.appendChild(t);t.select();
    var ok=false;try { ok=document.execCommand('copy'); } catch (e) {} t.remove();return ok;
  }
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text).then(function () { return true; },function () { return fallbackCopy(text); });
    return Promise.resolve(fallbackCopy(text));
  }
  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click',function () {
      var el=document.getElementById(btn.getAttribute('data-copy')),text=el ? (el.value || el.textContent).trim() : '',old=btn.textContent;
      copy(text).then(function (ok) { btn.textContent=ok ? 'Copied ✓' : 'Copy unavailable: select the text';setTimeout(function () { btn.textContent=old; },2200); });
    });
  });
  var cd=document.getElementById('countdown');
  if (cd) { var end=Date.parse(cd.getAttribute('data-end')),days=Math.max(0,Math.ceil((end-Date.now())/86400000));cd.textContent=days ? days+' days left' : 'Deadline reached'; }
  document.querySelectorAll('[data-table-filter]').forEach(function (input) {
    var table=document.getElementById(input.getAttribute('data-table-filter'));
    if (!table) return;
    input.addEventListener('input',function () {
      var term=input.value.trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function (row) { row.hidden=term && row.textContent.toLowerCase().indexOf(term)===-1; });
    });
  });

  var sb=document.getElementById('interactive-submission-builder');
  if (!sb || !window.GEMS20_CANDIDATES) return;
  var cands=window.GEMS20_CANDIDATES,candSel=document.getElementById('sb-cand-select'),fmtSel=document.getElementById('sb-fmt-select');
  var dl=document.getElementById('sb-dl-btn'),verify=document.getElementById('sb-verify-btn'),out=document.getElementById('sb-verify-out');
  var exportBtn=document.getElementById('sb-export-btn'),exportInfo=document.getElementById('sb-export-info');
  var sequence=0,controller=null;
  function chosen() { var c=cands[candSel.value];if (!c) throw new Error('Unknown artifact');return c; }
  function update() {
    sequence++;if (controller) controller.abort();controller=null;
    var c=chosen(),f=c.files[fmtSel.value];
    dl.href=f.href;dl.download=f.name;dl.textContent='↓ Download format-checked artifact (.tif / selected packaging · '+(f.bytes/1e6).toFixed(2)+' MB)';
    document.getElementById('sb-fn').textContent=f.name;document.getElementById('sb-note').textContent=c.note;document.getElementById('sb-sha').textContent=f.sha256;
    document.getElementById('sb-stats').textContent='Recorded format check: '+c.scored_pixels_predicted.toLocaleString()+' positive-valued in-footprint cells ('+c.share_of_footprint_pct+'%). File similarity is not hidden-fault performance. No upload recommendation.';
    out.textContent='';verify.disabled=false;if (exportBtn) exportBtn.disabled=false;if (exportInfo) exportInfo.hidden=true;
  }
  candSel.addEventListener('change',update);fmtSel.addEventListener('change',update);update();
  async function action(generate) {
    var token=++sequence,c=chosen(),fmt=fmtSel.value==='zip' ? 'tif' : fmtSel.value,f=c.files[fmt];
    if (controller) controller.abort();controller=new AbortController();
    verify.disabled=true;if (exportBtn) exportBtn.disabled=true;
    out.textContent='Fetching, SHA-256 checking and decoding '+f.name+' locally…';
    try {
      if (!window.GemsTiff) throw new Error('Local TIFF parser unavailable; no live check performed.');
      var responses=await Promise.all([fetch(f.href,{signal:controller.signal}),GemsTiff.loadFootprint()]);
      if (!responses[0].ok) throw new Error('Artifact download HTTP '+responses[0].status);
      var bytes=new Uint8Array(await responses[0].arrayBuffer()),fp=responses[1];
      if (token!==sequence) return;
      if (bytes.length!==f.bytes || await GemsTiff.sha256(bytes)!==f.sha256) throw new Error('Artifact size/SHA-256 differs from published manifest. Stop; do not upload.');
      var res=await GemsTiff.checkFile(bytes,fp,{includeRaster:generate});
      if (token!==sequence) return;
      if (!res.ok) { out.innerHTML='<div class="alert bad">Pre-flight FAIL: '+esc(res.hardFailures.join(', '))+'. No pixel-format acceptance or export.</div>';return; }
      out.innerHTML='<div class="alert '+(res.officialFormatCompliant ? 'ok' : 'warn')+'"><strong>Complete browser format check passed'+(res.officialFormatCompliant ? ', including NaN-outside convention' : '; outside values differ from the official NaN convention')+'.</strong> SHA-256 matches the published artifact; '+res.stats.footprintPixels.toLocaleString()+' template pixels decoded, '+res.stats.positives.toLocaleString()+' positive-valued. This does not validate hidden-fault quality, authorize a slot or diagnose the historical server error.</div>';
      if (generate) {
        out.insertAdjacentHTML('beforeend','<p>Generating template-matched float32 TIFF (~49 MB), preserving all in-footprint predictions…</p>');
        await new Promise(function (resolve) { setTimeout(resolve,0); });
        if (token!==sequence) return;
        var generated=GemsTiff.writeSubmission(res.raster,fp),digest=await GemsTiff.sha256(generated);
        var roundtrip=await GemsTiff.checkFile(generated,fp);
        if (!roundtrip.ok || !roundtrip.officialFormatCompliant) throw new Error('Generated TIFF round-trip check failed; download refused.');
        if (token!==sequence) return;
        var stamp=new Date().toISOString().replace(/[-:.]/g,''),name='gems20-formatcopy-'+c.key+'-'+stamp+'-'+digest.slice(0,12)+'-nan.tif';
        var note='20GEMSDOE '+c.key+' format-only copy | identical in-footprint predictions | no upload recommendation | file '+digest.slice(0,12);
        var link=document.createElement('a'),url=URL.createObjectURL(new Blob([generated],{type:'image/tiff'}));link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(function () { URL.revokeObjectURL(url); },60000);
        if (exportInfo) {
          document.getElementById('sb-export-name').textContent=name;document.getElementById('sb-export-note').textContent=note;document.getElementById('sb-export-sha').textContent=digest;exportInfo.hidden=false;
        }
        out.insertAdjacentHTML('beforeend','<p><strong>Generated TIFF downloaded.</strong> Fresh filename/container does not make a new prediction: this is an effective duplicate of the selected artifact, not another candidate or recommended submission.</p>');
      }
    } catch (e) { if (token===sequence && e.name!=='AbortError') out.innerHTML='<p class="res-bad">Check/export stopped: '+esc(e.message || e)+'</p>'; }
    finally { if (token===sequence) { verify.disabled=false;if (exportBtn) exportBtn.disabled=false; } }
  }
  verify.addEventListener('click',function () { action(false); });
  if (exportBtn) exportBtn.addEventListener('click',function () { action(true); });
})();
