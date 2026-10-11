/* The Listening Atlas — progressive enhancement for a read-only site.
 * Adds stage filtering, the "All tracks" view and global search. Pages are complete without it.
 * Nothing is stored and nothing is sent anywhere.
 */
(() => {
  'use strict';

  const body = document.body;
  if (!body.dataset.collection) return;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const norm = (s) => {
    const t = String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ').trim();
    return t.replace(/\b(bwv|anh) (\d)/g, '$1$2');
  };
  const matches = (haystack, query) => query.split(' ').every((tok) => !tok || haystack.includes(tok));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ---------------------------------------------------------------- stage page
  function initStage() {
    const results = $('[data-results]');
    if (!results) return;
    const sels = $$('[data-sel]', results);
    const groups = $$('[data-group]', results);
    const filter = $('[data-filter]');
    const view = $('[data-view]');
    const count = $('[data-result-count]');
    const none = $('[data-no-results]');

    function applyFilter() {
      const q = norm(filter.value);
      let shown = 0;
      for (const el of sels) {
        el.hidden = !!q && !matches(el.dataset.q, q);
        if (!el.hidden) shown += 1;
      }
      for (const g of groups) {
        const any = $$('[data-sel]', g).some((el) => !el.hidden);
        g.hidden = !any;
        if (any && (q || results.dataset.mode === 'tracks')) g.open = true;
      }
      none.hidden = shown > 0;
      count.textContent = q ? `${shown} of ${sels.length} selections shown` : '';
    }
    filter.addEventListener('input', applyFilter);
    filter.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && filter.value) { filter.value = ''; applyFilter(); }
    });
    view.addEventListener('change', () => {
      results.dataset.mode = view.value;
      if (view.value === 'tracks') groups.forEach((g) => { g.open = true; });
      applyFilter();
    });

    // Open the group containing a linked selection (#s-xxxxxxx).
    const reveal = () => {
      const id = decodeURIComponent(location.hash.slice(1));
      const target = id && document.getElementById(id);
      if (target && target.matches('[data-sel]')) {
        const g = target.closest('details');
        if (g) g.open = true;
        target.scrollIntoView({ block: 'start', behavior: 'instant' });
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
    fetch(body.dataset.data).then((r) => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then((data) => {
      const run = () => {
        const q = norm(input.value);
        if (!q) { list.innerHTML = ''; count.textContent = ''; return; }
        const hits = data.selections.filter((s) => matches(s.q, q));
        count.textContent = `${hits.length} selection${hits.length === 1 ? '' : 's'} found` + (hits.length > 200 ? ' (showing first 200)' : '');
        list.innerHTML = hits.slice(0, 200).map((s) => `<li>
          <a href="../${esc(s.stage)}/index.html#${esc(s.id)}"><strong>${esc(s.p)}. ${esc(s.title)}</strong></a>
          <div class="meta">${esc(s.artist)} · ${esc(s.album)}${s.d ? ' · ' + esc(s.d) : ''}</div>
          <div class="meta">${esc(s.stageName)} · ${esc(s.work)}</div></li>`).join('');
        const url = new URL(location.href);
        url.searchParams.set('q', input.value);
        history.replaceState(null, '', url);
      };
      input.addEventListener('input', run);
      run();
    }).catch(() => { count.textContent = 'Search data could not be loaded. If you opened this file directly from disk, serve the site over HTTP (see README).'; });
  }

  initStage();
  initSearch();
})();
