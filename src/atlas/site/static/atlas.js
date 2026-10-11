/* The Listening Atlas — progressive enhancement for a read-only site.
 * Adds inline search, menu behaviour, and opening of linked selections. Pages are complete without it.
 * Nothing is stored and nothing is sent anywhere.
 */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const norm = (s) => {
    const t = String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ').trim();
    return t.replace(/\b(bwv|anh) (\d)/g, '$1$2');
  };
  const matches = (haystack, query) => query.split(' ').every((tok) => !tok || haystack.includes(tok));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ---------------------------------------------------------------- menu
  const menu = $('[data-menu]');
  if (menu) {
    document.addEventListener('click', (ev) => {
      if (menu.open && !menu.contains(ev.target)) menu.open = false;
    });
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && menu.open) { menu.open = false; $('summary', menu).focus(); }
    });
  }

  // ---------------------------------------------------------------- inline search
  const input = $('[data-search]');
  if (input) {
    const list = $('[data-search-results]');
    const count = $('[data-search-count]');
    const only = input.dataset.collection;
    const root = input.dataset.root || '';
    const LIMIT = 100;
    let data = null;
    const load = () => (data ??= fetch(input.dataset.src).then((r) => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then((d) => (only ? d.selections.filter((s) => s.c === only) : d.selections)));

    const run = () => {
      const q = norm(input.value);
      if (!q) { list.innerHTML = ''; count.textContent = ''; return; }
      load().then((rows) => {
        if (norm(input.value) !== q) return; // a newer query is running
        // A bare number is a playlist track number (as shown in Apple Music); exact positions come first.
        const byPos = /^\d+$/.test(q) ? rows.filter((s) => String(s.p) === q) : [];
        const hits = [...byPos, ...rows.filter((s) => !byPos.includes(s) && matches(s.q, q))];
        const many = !only && new Set(rows.map((s) => s.c)).size > 1;
        count.textContent = `${hits.length} selection${hits.length === 1 ? '' : 's'} found` + (hits.length > LIMIT ? ` (showing the first ${LIMIT})` : '');
        list.innerHTML = hits.slice(0, LIMIT).map((s) => `<li>
          <span class="pos">${esc(s.p)}</span>
          <div><a href="${esc(root + s.path)}"><strong>${esc(s.title)}</strong></a>
          <div class="meta">${esc(s.artist)} · ${esc(s.album)}${s.d ? ' · ' + esc(s.d) : ''}</div>
          <div class="meta">${many ? esc(s.cTitle) + ' · ' : ''}Stage ${esc(s.stageName)}</div></div></li>`).join('');
        const url = new URL(location.href);
        url.searchParams.set('q', input.value);
        history.replaceState(null, '', url);
      }).catch(() => {
        count.textContent = 'Search could not load its data. If you opened this file directly from disk, preview with `atlas serve` (see README).';
      });
    };
    input.addEventListener('input', run);
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && input.value) { input.value = ''; run(); history.replaceState(null, '', location.pathname); }
      if (ev.key === 'Enter') {
        const first = $('a', list);
        if (first) { ev.preventDefault(); first.click(); }
      }
    });
    const initial = new URLSearchParams(location.search).get('q');
    if (initial) { input.value = initial; run(); }
  }

  // "/" focuses search, unless the user is typing.
  document.addEventListener('keydown', (ev) => {
    if (ev.key !== '/' || ev.metaKey || ev.ctrlKey || ev.altKey || !input) return;
    const t = ev.target;
    if (t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    ev.preventDefault();
    input.focus();
    input.select();
  });

  // ---------------------------------------------------------------- linked selection (#s-xxxxxxx)
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
})();
