/* The Listening Atlas — progressive enhancement for static pages.
 * Everything here is optional: pages are complete without JavaScript.
 * The journal lives in localStorage only; nothing is sent over the network.
 */
(() => {
  'use strict';

  const body = document.body;
  const collection = body.dataset.collection;
  if (!collection) return;

  // ---------------------------------------------------------------- storage
  const KEY = `listening-atlas:v1:${collection}`;
  let storageOk = true;
  let journal = { entries: {} };
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) journal = JSON.parse(raw);
    if (!journal || typeof journal.entries !== 'object') journal = { entries: {} };
  } catch (e) {
    storageOk = false;
  }
  const save = () => {
    if (!storageOk) return;
    try { localStorage.setItem(KEY, JSON.stringify(journal)); } catch (e) { storageOk = false; }
  };
  const entry = (id) => (journal.entries[id] ??= {});
  const isDone = (id) => !!journal.entries[id]?.done;
  const prune = (id) => {
    const e = journal.entries[id];
    if (e && !e.done && !e.note) delete journal.entries[id];
  };

  // ---------------------------------------------------------------- helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const norm = (s) => {
    const t = String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ').trim();
    return t.replace(/\b(bwv|anh) (\d)/g, '$1$2');
  };
  const matches = (haystack, query) => query.split(' ').every((tok) => !tok || haystack.includes(tok));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let dataPromise = null;
  const loadData = () => (dataPromise ??= fetch(body.dataset.data).then((r) => {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }));

  // ---------------------------------------------------------------- progress (all pages)
  function updateProgress(data) {
    const byStage = {};
    let done = 0;
    for (const s of data.selections) {
      if (isDone(s.id)) { done += 1; byStage[s.stage] = (byStage[s.stage] || 0) + 1; }
    }
    $$('[data-stage-progress]').forEach((el) => {
      const n = byStage[el.dataset.stageProgress] || 0;
      el.textContent = n ? `${n}/${el.dataset.total}` : '';
      el.setAttribute('aria-label', `${n} of ${el.dataset.total} heard`);
    });
    $$('[data-progress-summary]').forEach((el) => {
      el.textContent = `${done} of ${data.total} selections marked as heard.` + (storageOk ? '' : ' (This browser is not allowing local storage; notes will not be kept.)');
    });
  }
  const refreshProgress = () => loadData().then(updateProgress).catch(() => {});

  // ---------------------------------------------------------------- stage page
  function initStage() {
    const results = $('[data-results]');
    if (!results) return;
    const sels = $$('[data-sel]', results);
    const groups = $$('[data-group]', results);

    const paintGroup = (g) => {
      const items = $$('[data-sel]', g);
      const n = items.filter((el) => isDone(el.dataset.sel)).length;
      const out = $('[data-group-progress]', g);
      if (out) out.textContent = n ? ` · ${n}/${items.length} heard` : '';
    };

    let timer = null;
    for (const el of sels) {
      const id = el.dataset.sel;
      const cb = $('[data-done]', el);
      const ta = $('[data-note]', el);
      const e = journal.entries[id] || {};
      cb.checked = !!e.done;
      ta.value = e.note || '';
      el.classList.toggle('is-done', !!e.done);
      cb.addEventListener('change', () => {
        Object.assign(entry(id), { done: cb.checked, updated: new Date().toISOString() });
        prune(id);
        save();
        el.classList.toggle('is-done', cb.checked);
        paintGroup(el.closest('[data-group]'));
        refreshProgress();
        if ($('[data-unheard]').checked) applyFilter();
      });
      ta.addEventListener('input', () => {
        Object.assign(entry(id), { note: ta.value, updated: new Date().toISOString() });
        prune(id);
        clearTimeout(timer);
        timer = setTimeout(save, 300);
      });
      ta.addEventListener('blur', save);
    }
    groups.forEach(paintGroup);

    const filter = $('[data-filter]');
    const view = $('[data-view]');
    const unheard = $('[data-unheard]');
    const count = $('[data-result-count]');
    const none = $('[data-no-results]');

    function applyFilter() {
      const q = norm(filter.value);
      const onlyUnheard = unheard.checked;
      let shown = 0;
      for (const el of sels) {
        const ok = (!q || matches(el.dataset.q, q)) && (!onlyUnheard || !isDone(el.dataset.sel));
        el.hidden = !ok;
        if (ok) shown += 1;
      }
      for (const g of groups) {
        const any = $$('[data-sel]', g).some((el) => !el.hidden);
        g.hidden = !any;
        if (any && (q || onlyUnheard || results.dataset.mode === 'tracks')) g.open = true;
      }
      none.hidden = shown > 0;
      count.textContent = (q || onlyUnheard) ? `${shown} of ${sels.length} selections shown` : '';
    }
    filter.addEventListener('input', applyFilter);
    unheard.addEventListener('change', applyFilter);
    view.addEventListener('change', () => {
      results.dataset.mode = view.value;
      if (view.value === 'tracks') groups.forEach((g) => { g.open = true; });
      applyFilter();
    });
    filter.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && filter.value) { filter.value = ''; applyFilter(); }
    });

    // Open the group containing a linked selection (#s-xxxxxxx).
    const reveal = () => {
      const id = decodeURIComponent(location.hash.slice(1));
      const target = id && document.getElementById(id);
      if (target && target.matches('[data-sel]')) {
        const g = target.closest('details');
        if (g) g.open = true;
        target.scrollIntoView({ block: 'start', behavior: 'instant' });
        $('[data-done]', target)?.focus({ preventScroll: true });
      }
    };
    window.addEventListener('hashchange', reveal);
    reveal();
  }

  // "/" focuses the page's search box, unless the user is typing.
  document.addEventListener('keydown', (ev) => {
    if (ev.key !== '/' || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const t = ev.target;
    if (t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    const box = $('[data-filter]') || $('[data-global-search]');
    if (box) { ev.preventDefault(); box.focus(); box.select(); }
  });

  // ---------------------------------------------------------------- search page
  function initSearch() {
    const input = $('[data-global-search]');
    if (!input) return;
    const list = $('[data-search-results]');
    const count = $('[data-search-count]');
    const params = new URLSearchParams(location.search);
    if (params.get('q')) input.value = params.get('q');
    loadData().then((data) => {
      const run = () => {
        const q = norm(input.value);
        if (!q) { list.innerHTML = ''; count.textContent = ''; return; }
        const hits = data.selections.filter((s) => matches(s.q, q));
        count.textContent = `${hits.length} selection${hits.length === 1 ? '' : 's'} found` + (hits.length > 200 ? ' (showing first 200)' : '');
        list.innerHTML = hits.slice(0, 200).map((s) => `<li>
          <a href="../${esc(s.stage)}/index.html#${esc(s.id)}"><strong>${esc(s.p)}. ${esc(s.title)}</strong></a>
          <div class="meta">${esc(s.artist)} · ${esc(s.album)}${s.d ? ' · ' + esc(s.d) : ''}</div>
          <div class="meta">${esc(s.stageName)} · ${esc(s.work)}${isDone(s.id) ? ' · heard ✓' : ''}</div></li>`).join('');
        const url = new URL(location.href);
        url.searchParams.set('q', input.value);
        history.replaceState(null, '', url);
      };
      input.addEventListener('input', run);
      run();
    }).catch(() => { count.textContent = 'Search data could not be loaded. If you opened this file directly from disk, serve the site over HTTP (see README).'; });
  }

  // ---------------------------------------------------------------- journal page
  function initJournal() {
    const list = $('[data-journal-list]');
    if (!list) return;
    const result = $('[data-import-result]');
    loadData().then((data) => {
      const byId = Object.fromEntries(data.selections.map((s) => [s.id, s]));
      const render = () => {
        const items = data.selections.filter((s) => journal.entries[s.id]?.note);
        list.innerHTML = items.length ? items.map((s) => `<li>
          <a href="../${esc(s.stage)}/index.html#${esc(s.id)}"><strong>${esc(s.p)}. ${esc(s.title)}</strong></a>
          <div class="meta">${esc(s.stageName)} · ${esc(s.artist)}${isDone(s.id) ? ' · heard ✓' : ''}</div>
          <p style="white-space:pre-wrap">${esc(journal.entries[s.id].note)}</p></li>`).join('')
          : '<li class="muted">No notes yet. Write them on the stage pages, beneath each selection.</li>';
        const orphans = Object.keys(journal.entries).filter((id) => !byId[id]);
        if (orphans.length) list.insertAdjacentHTML('beforeend', `<li class="muted small">${orphans.length} entr${orphans.length === 1 ? 'y belongs' : 'ies belong'} to selections no longer in the playlist; they are kept in exports.</li>`);
        updateProgress(data);
      };
      render();

      $('[data-export]').addEventListener('click', () => {
        const payload = { format: 'listening-atlas-journal', version: 1, collection, exported: new Date().toISOString(), entries: journal.entries };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `listening-journal-${collection}.json`;
        document.body.append(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      });

      $('[data-import]').addEventListener('change', async (ev) => {
        const file = ev.target.files[0];
        if (!file) return;
        let parsed;
        try { parsed = JSON.parse(await file.text()); } catch (e) { return report('That file is not valid JSON.'); }
        let incoming = {};
        let skipped = 0;
        if (parsed && parsed.format === 'listening-atlas-journal') {
          if (parsed.collection !== collection) return report(`That journal belongs to “${parsed.collection}”, not this volume.`);
          incoming = parsed.entries || {};
        } else if (parsed && parsed.journal && typeof parsed.journal === 'object') {
          // Original single-file guide: entries keyed by playlist position in the 669-row snapshot.
          for (const [pos, val] of Object.entries(parsed.journal)) {
            const id = data.legacy.positions[pos];
            if (id) incoming[id] = { done: !!val.done, note: val.note || '' };
            else skipped += 1;
          }
        } else {
          return report('Unrecognised journal format.');
        }
        let merged = 0;
        for (const [id, val] of Object.entries(incoming)) {
          const cur = entry(id);
          cur.done = !!(cur.done || val.done);
          const a = (cur.note || '').trim();
          const b = (val.note || '').trim();
          if (b && !a) cur.note = b;
          else if (b && a && a !== b && !a.includes(b)) cur.note = `${a}\n\n— imported —\n${b}`;
          cur.updated = new Date().toISOString();
          prune(id);
          merged += 1;
        }
        save();
        render();
        report(`Imported ${merged} entr${merged === 1 ? 'y' : 'ies'}` + (skipped ? `; ${skipped} could not be matched to a selection.` : '.'));
        ev.target.value = '';
      });

      $('[data-clear]').addEventListener('click', () => {
        if (!confirm('Delete every note and “heard” mark for this volume in this browser? Export first if you want a backup.')) return;
        journal = { entries: {} };
        save();
        render();
        report('Journal cleared.');
      });
    }).catch(() => report('Journal data could not be loaded. If you opened this file directly from disk, serve the site over HTTP (see README).'));

    function report(msg) {
      result.hidden = false;
      result.textContent = msg;
    }
  }

  initStage();
  initSearch();
  initJournal();
  refreshProgress();
})();
