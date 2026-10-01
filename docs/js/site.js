/* Small progressive enhancements: copy buttons, live countdown, and the 20GEMSDOE Interactive Submission Builder. The page is fully usable without JS. */
(function () {
  'use strict';

  function selectNode(el) {
    var r = document.createRange();
    r.selectNodeContents(el);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }

  function execCopy(text) {
    var t = document.createElement('textarea');
    t.value = text;
    t.setAttribute('readonly', '');
    t.style.position = 'fixed';
    t.style.opacity = '0';
    document.body.appendChild(t);
    t.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    t.remove();
    return ok;
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return execCopy(text); });
    }
    return Promise.resolve(execCopy(text));
  }

  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var el = document.getElementById(btn.getAttribute('data-copy'));
      var text = el ? (el.value || el.textContent).trim() : '';
      var old = btn.textContent;
      copyText(text).then(function (ok) {
        if (!ok && el) selectNode(el);
        btn.textContent = ok ? 'Copied \u2714' : 'Selected: press Ctrl/Cmd+C';
        setTimeout(function () { btn.textContent = old; }, 2200);
      });
    });
  });

  var cd = document.getElementById('countdown');
  if (cd) {
    var end = Date.parse(cd.getAttribute('data-end'));
    var days = Math.max(0, Math.ceil((end - Date.now()) / 86400000));
    cd.textContent = days + ' day' + (days === 1 ? '' : 's') + ' left';
  }

  // Interactive Submission Builder
  var sb = document.getElementById('interactive-submission-builder');
  if (sb && window.GEMS20_CANDIDATES) {
    var cands = window.GEMS20_CANDIDATES;
    var candSel = document.getElementById('sb-cand-select');
    var fmtSel = document.getElementById('sb-fmt-select');
    var dlBtn = document.getElementById('sb-dl-btn');
    var fnEl = document.getElementById('sb-fn');
    var noteEl = document.getElementById('sb-note');
    var shaEl = document.getElementById('sb-sha');
    var statsEl = document.getElementById('sb-stats');
    var verifyBtn = document.getElementById('sb-verify-btn');
    var verifyOut = document.getElementById('sb-verify-out');
    var footprintCache = null;

    function updateBuilder() {
      var key = candSel ? candSel.value : 'h20-1';
      var fmt = fmtSel ? fmtSel.value : 'tif';
      var c = cands[key] || cands['h20-1'];
      if (!c) return;
      var f = c.files[fmt] || c.files.tif;
      var mb = (f.bytes / 1e6).toFixed(2) + ' MB';
      if (dlBtn) {
        dlBtn.setAttribute('href', f.href);
        dlBtn.setAttribute('download', f.name);
        dlBtn.innerHTML = '\u2B07 Download format-checked research artifact (' + f.name + ' \u00b7 ' + mb + ')';
      }
      if (fnEl) fnEl.textContent = f.name;
      if (noteEl) noteEl.textContent = c.note;
      if (shaEl) shaEl.textContent = f.sha256;
      if (statsEl) {
        statsEl.innerHTML = '<strong>Recorded local format check:</strong> finite values in <code>[0.0, 1.0]</code> within the template footprint \u00b7 ' +
          'In-footprint positive-valued cells: <code>' + c.scored_pixels_predicted.toLocaleString() + '</code> (<code>' + c.share_of_footprint_pct + '%</code>) \u00b7 ' +
          '<strong>No upload recommendation.</strong> Stored holdout figures are unreproduced known-catalogue proxies; no hidden-fault score is established.';
      }
      if (verifyOut) verifyOut.innerHTML = '';
    }

    if (candSel) candSel.addEventListener('change', updateBuilder);
    if (fmtSel) fmtSel.addEventListener('change', updateBuilder);
    updateBuilder();

    if (verifyBtn && verifyOut) {
      verifyBtn.addEventListener('click', function () {
        var key = candSel ? candSel.value : 'h20-1';
        var fmt = fmtSel ? fmtSel.value : 'tif';
        if (fmt === 'zip') fmt = 'tif';
        var c = cands[key] || cands['h20-1'];
        var f = c.files[fmt];
        if (!window.GemsTiff) {
          verifyOut.innerHTML = '<p class="res-info">The browser TIFF parser is unavailable. Recorded local checks list this file as format-checked (SHA-256 ' + f.sha256.slice(0, 16) + '\u2026); no live recheck or score validation was performed.</p>';
          return;
        }
        verifyOut.innerHTML = '<p class="small muted">Fetching &amp; parsing <code>' + f.name + '</code> in browser via <code>GemsTiff</code>\u2026</p>';
        var fpPromise = footprintCache ? Promise.resolve(footprintCache) :
          fetch('data/footprint.bin').then(function (r) { return r.arrayBuffer(); }).then(function (b) {
            footprintCache = window.GemsTiff.decodeMaskRuns(new Uint8Array(b), window.GemsTiff.EXPECT.width * window.GemsTiff.EXPECT.height);
            return footprintCache;
          });
        Promise.all([
          fetch(f.href).then(function (r) { return r.arrayBuffer(); }),
          fpPromise
        ]).then(function (arrs) {
          return window.GemsTiff.checkFile(new Uint8Array(arrs[0]), arrs[1]);
        }).then(function (res) {
          if (res.ok) {
            verifyOut.innerHTML = '<div class="alert ok" style="margin-top:.6rem"><strong>Browser-side file check passed:</strong> <code>' + f.name + '</code> \u2014 CRS <code>EPSG:32611</code>, shape <code>3292\u00d73730</code>, dtype <code>float32</code>, footprint finite pixels: <code>' + res.stats.footprintPixels.toLocaleString() + '</code>, positive-valued pixels: <code>' + res.stats.positives.toLocaleString() + '</code>, outside NaN: <code>' + res.stats.outNaN.toLocaleString() + '</code>. This checks file format/range only; historical server-error cause and prediction quality remain unknown.</div>';
          } else {
            verifyOut.innerHTML = '<div class="alert bad" style="margin-top:.6rem">FAIL: ' + res.hardFailures.join(', ') + '</div>';
          }
        }).catch(function (err) {
          verifyOut.innerHTML = '<p class="res-bad">Error verifying GeoTIFF: ' + (err.message || err) + '</p>';
        });
      });
    }
  }
})();
