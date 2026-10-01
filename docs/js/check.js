/* Local drag-and-drop checker. Complete pixel + authenticated-mask checks or FAIL. */
(function () {
  'use strict';
  var mount=document.getElementById('checker');
  if (!mount || !window.GemsTiff) return;
  var drop=mount.querySelector('.drop'),input=mount.querySelector('input[type=file]'),out=mount.querySelector('.out'),sequence=0;
  function esc(s) { return String(s).replace(/[&<>"']/g,function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function render(name,size,res) {
    var h='<h3>'+esc(name)+' <span class="muted small">('+(size/1048576).toFixed(2)+' MiB)</span></h3>';
    h+='<p class="'+(res.ok ? 'res-ok' : 'res-bad')+'">'+(res.ok ? 'Complete local format check passed'+(res.officialFormatCompliant ? ' (NaN outside, official convention).' : '; outside NaN convention is NOT met.') : 'FAIL / could not verify: '+esc(res.hardFailures.join(', '))+'.')+'</p>';
    h+='<div class="tw"><table><thead><tr><th>Check</th><th>Result</th><th>Detail</th></tr></thead><tbody>';
    res.checks.forEach(function (c) {
      var state=c.pass ? '✓ pass' : c.hard ? '✗ FAIL' : '○ advisory';
      h+='<tr><td>'+esc(c.title)+(c.hard ? '' : ' (advisory)')+'</td><td class="'+(c.pass ? 'res-ok' : c.hard ? 'res-bad' : '')+'">'+state+'</td><td>'+esc(c.detail)+(c.pass || !c.fix ? '' : '<br>Fix: '+esc(c.fix))+'</td></tr>';
    });
    h+='</tbody></table></div>';
    if (res.stats) h+='<p class="small muted">Footprint: '+res.stats.footprintPixels.toLocaleString()+' pixels · positive-valued: '+res.stats.positives.toLocaleString()+' · outside NaN: '+res.stats.outNaN.toLocaleString()+'</p>';
    h+='<p class="small muted">Format only. No novelty/performance recommendation, private-server acceptance guarantee or historical range-error diagnosis. Unsupported files fail closed; use the Python validator for additional formats.</p>';
    out.innerHTML=h;
  }
  async function handle(file) {
    if (!file) return;
    var token=++sequence;
    if (/\.zip$/i.test(file.name)) { out.textContent='Unzip it and choose the single .tif. This checker does not inspect ZIP archives.';return; }
    if (file.size>256*1048576) { out.textContent='File exceeds the local browser memory safety limit (256 MiB). Use the Python validator.';return; }
    out.textContent='Reading '+file.name+' and verifying the template footprint…';
    try {
      var r=await Promise.all([file.arrayBuffer(),GemsTiff.loadFootprint()]);
      if (token!==sequence) return;
      var result=await GemsTiff.checkFile(new Uint8Array(r[0]),r[1]);
      if (token===sequence) render(file.name,file.size,result);
    } catch (e) { if (token===sequence) out.innerHTML='<p class="res-bad">Could not verify: '+esc(e.message || e)+'</p>'; }
  }
  input.addEventListener('change',function () { handle(input.files[0]); });
  ['dragenter','dragover'].forEach(function (ev) { drop.addEventListener(ev,function (e) { e.preventDefault();drop.classList.add('over'); }); });
  ['dragleave','drop'].forEach(function (ev) { drop.addEventListener(ev,function (e) { e.preventDefault();drop.classList.remove('over'); }); });
  drop.addEventListener('drop',function (e) { handle(e.dataTransfer.files[0]); });
})();
