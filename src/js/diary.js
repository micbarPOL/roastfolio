(function () {
    const DIARY_LOCAL_KEY = 'roastfolio-coping-diary-notes-v4';
    const OVERDUE_STATUSES = new Set(['PENDING', 'OVERDUE']);

    const state = {
        notes: [],
        selectedNoteId: '',
        holdings: new Set(),
        loaded: false,
        filterQuery: '',
        activeTagFilter: '',
        filterUncheckedOnly: false,
        saving: false,
        composeOpen: false,
    };

    function chooseDiaryEmptyGraphic(theme) {
        const darkCandidates = [
            'data/diary/coping-diary-empty.png',
            'data/diary/coping-diary-empty-dark.png',
            'data/diary/diary-empty.png',
            'data/diary/empty-diary.png',
            'data/diary-empty.png'
        ];
        const lightCandidates = [
            'data/diary/coping-diary-empty-light.png',
            'data/diary/diary-empty-light.png',
            'data/diary/empty-diary-light.png',
            'data/diary-empty-light.png'
        ];
        return theme === 'light' ? lightCandidates : darkCandidates;
    }

    function loadFirstExistingImage(candidates, onSuccess, onFail) {
        const queue = Array.from(candidates || []);
        function tryNext() {
            const next = queue.shift();
            if (!next) {
                onFail();
                return;
            }
            const probe = new Image();
            probe.onload = () => onSuccess(next);
            probe.onerror = () => tryNext();
            probe.src = next;
        }
        tryNext();
    }

    function apiBase() {
        const cfg = window.__CONFIG__ || window.APP_CONFIG || {};
        return String(cfg.apiUrl || '').replace(/\/prices$/, '');
    }

    function authHeaders(extra) {
        const token = window.AuthGuard && typeof window.AuthGuard.getIdToken === 'function'
            ? window.AuthGuard.getIdToken()
            : null;
        const headers = Object.assign({}, extra || {});
        if (token) headers.Authorization = 'Bearer ' + token;
        return headers;
    }

    function todayYmd() {
        return new Date().toISOString().slice(0, 10);
    }

    function toIsoNow() {
        return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    }

    function formatShortDate(value) {
        const raw = String(value || '').trim();
        if (!raw) return '';
        const parsed = new Date(raw);
        if (!Number.isNaN(parsed.getTime())) {
            return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(parsed);
        }
        const ymd = raw.slice(0, 10);
        if (/^\d{4}-\d{2}-\d{2}$/.test(ymd)) {
            const fallback = new Date(ymd + 'T00:00:00Z');
            if (!Number.isNaN(fallback.getTime())) {
                return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(fallback);
            }
        }
        return '';
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function normalizeTicker(raw) {
        const t = String(raw || '').trim().toUpperCase();
        if (!t) return '';
        return t.replace(/[^A-Z0-9.]/g, '');
    }

    function sanitizeTag(raw) {
        const cleaned = String(raw || '')
            .trim()
            .replace(/\s+/g, '_')
            .replace(/[^A-Za-z0-9_#.$:-]/g, '');
        if (!cleaned) return '';
        return cleaned.startsWith('#') ? cleaned : ('#' + cleaned);
    }

    function parseTagsFromText(text) {
        const matches = String(text || '').match(/#[A-Za-z0-9_.$:-]+/g) || [];
        const out = [];
        const seen = new Set();
        for (const m of matches) {
            const t = sanitizeTag(m);
            if (!t || seen.has(t)) continue;
            seen.add(t);
            out.push(t);
        }
        return out;
    }

    function parseMentionTickers(text) {
        const matches = String(text || '').match(/@([A-Za-z][A-Za-z0-9.]*)/g) || [];
        const out = [];
        const seen = new Set();
        for (const raw of matches) {
            const ticker = normalizeTicker(raw.slice(1));
            if (!ticker || seen.has(ticker)) continue;
            seen.add(ticker);
            out.push(ticker);
        }
        return out;
    }

    function resolvePrimaryAsset(note) {
        const firstLinked = Array.isArray(note.linked_assets) ? normalizeTicker(note.linked_assets[0]) : '';
        return firstLinked;
    }

    function resolveTitle(note, primaryAsset) {
        const rawTitle = String(note.title || note.topic || note.ticker || '').trim();
        if (!rawTitle) return primaryAsset || 'Untitled note';
        if (primaryAsset) {
            const normalizedTitle = normalizeTicker(rawTitle);
            const titleBase = normalizedTitle.split('.', 1)[0];
            const assetBase = primaryAsset.split('.', 1)[0];
            if (titleBase && titleBase === assetBase) {
                return primaryAsset;
            }
        }
        return rawTitle;
    }

    function normalizeNote(raw) {
        const ticker = resolvePrimaryAsset(raw);
        const now = toIsoNow();
        const hypothesis = raw.hypothesis || {};
        const title = resolveTitle(raw, ticker);
        return {
            note_id: String(raw.note_id || raw.id || Math.random().toString(36).slice(2, 10)),
            title: title,
            ticker: ticker,
            note_text: String(raw.note_text || raw.text || ''),
            linked_assets: Array.isArray(raw.linked_assets) ? raw.linked_assets : (ticker ? [ticker] : []),
            user_tags: Array.isArray(raw.user_tags) ? raw.user_tags : parseTagsFromText(raw.note_text || raw.text || ''),
            hypothesis: {
                why_buy: String(hypothesis.why_buy || ''),
                exit_plan: String(hypothesis.exit_plan || ''),
                risk_factors: String(hypothesis.risk_factors || ''),
            },
            hypothesis_checkpoints: Array.isArray(raw.hypothesis_checkpoints) ? raw.hypothesis_checkpoints : [],
            comments: Array.isArray(raw.comments) ? raw.comments.slice().sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || ''))) : [],
            is_active: Boolean(raw.is_active !== undefined ? raw.is_active : ticker),
            user_override_active: Boolean(raw.user_override_active),
            createdAt: String(raw.createdAt || now),
            updatedAt: String(raw.updatedAt || raw.createdAt || now),
        };
    }

    function setLocalNotes(notes) {
        try {
            localStorage.setItem(DIARY_LOCAL_KEY, JSON.stringify(notes));
        } catch (e) {}
    }

    function getLocalNotes() {
        try {
            const raw = localStorage.getItem(DIARY_LOCAL_KEY);
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed.map(normalizeNote) : [];
        } catch (e) {
            return [];
        }
    }

    async function apiFetch(path, options) {
        const base = apiBase();
        if (!base) throw new Error('Missing API base');
        const req = Object.assign({ method: 'GET' }, options || {});
        req.headers = authHeaders(req.headers || {});
        const res = await fetch(base + path, req);
        if (!res.ok) {
            const text = await res.text();
            throw new Error(text || ('HTTP ' + res.status));
        }
        return res.json();
    }

    async function fetchNotes() {
        try {
            const data = await apiFetch('/diary?includeClosed=true', { method: 'GET' });
            const notes = Array.isArray(data.notes) ? data.notes.map(normalizeNote) : [];
            setLocalNotes(notes);
            return notes;
        } catch (e) {
            return getLocalNotes();
        }
    }

    async function saveNotePatch(noteId, patch) {
        const payload = Object.assign({}, patch || {});
        try {
            const data = await apiFetch('/diary/' + encodeURIComponent(noteId), {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            return data && data.note ? normalizeNote(data.note) : null;
        } catch (e) {
            return null;
        }
    }

    async function createNote(payload) {
        try {
            const data = await apiFetch('/diary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            return data && data.note ? normalizeNote(data.note) : null;
        } catch (e) {
            return null;
        }
    }

    async function appendComment(note, text) {
        const noteId = note.note_id;
        try {
            const data = await apiFetch('/diary/' + encodeURIComponent(noteId) + '/comment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text }),
            });
            return data && data.note ? normalizeNote(data.note) : null;
        } catch (e) {
            return null;
        }
    }

    async function toggleActive(note, isActive) {
        const noteId = note.note_id;
        try {
            const data = await apiFetch('/diary/' + encodeURIComponent(noteId) + '/toggle-active', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: Boolean(isActive) }),
            });
            return data && data.note ? normalizeNote(data.note) : null;
        } catch (e) {
            return null;
        }
    }

    async function deleteNoteById(noteId) {
        try {
            await apiFetch('/diary/' + encodeURIComponent(noteId), {
                method: 'DELETE',
            });
            return true;
        } catch (e) {
            return false;
        }
    }

    function collectActiveHoldings() {
        const set = new Set();
        const source = window.WALLET_HOLDINGS || {};
        for (const rows of Object.values(source)) {
            for (const h of (rows || [])) {
                const ticker = normalizeTicker(h && h.ticker);
                if (!ticker) continue;
                const units = Number(h && h.units);
                if (Number.isFinite(units) && units <= 0) continue;
                set.add(ticker);
            }
        }
        return set;
    }

    function sortForLedger(notes) {
        const held = state.holdings;
        return notes.slice().sort((a, b) => {
            const aHeldActive = a.is_active && held.has(a.ticker);
            const bHeldActive = b.is_active && held.has(b.ticker);
            const aInactive = !a.is_active;
            const bInactive = !b.is_active;

            const aTier = aHeldActive ? 0 : (aInactive ? 2 : 1);
            const bTier = bHeldActive ? 0 : (bInactive ? 2 : 1);
            if (aTier !== bTier) return aTier - bTier;

            return String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''));
        });
    }

    function ensureStyles() {
        if (document.getElementById('diary-v2-styles')) return;
        const style = document.createElement('style');
        style.id = 'diary-v2-styles';
        style.textContent = '' +
            '.diary-split{display:grid;grid-template-columns:minmax(310px,36%) minmax(0,64%);gap:14px;min-height:520px;}' +
            '.diary-pane{border:1px solid rgba(127,143,164,.35);border-radius:14px;background:rgba(9,20,35,.28);backdrop-filter:blur(8px);}' +
            '.diary-pane-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;border-bottom:1px solid rgba(127,143,164,.25);}' +
            '.diary-ledger-list{padding:10px;display:grid;gap:8px;max-height:70vh;overflow:auto;}' +
            '.diary-ledger-card{border:1px solid rgba(127,143,164,.35);border-radius:12px;background:rgba(10,22,38,.45);padding:10px;cursor:pointer;transition:transform .22s ease,opacity .22s ease,filter .22s ease,border-color .22s ease;animation:diaryCardIn .24s ease;}' +
            '.diary-ledger-card:hover{transform:translateY(-2px);border-color:rgba(168,85,247,.7);}' +
            '.diary-ledger-card.is-selected{border-color:rgba(168,85,247,.95);box-shadow:0 0 0 1px rgba(168,85,247,.35) inset;}' +
            '.diary-ledger-card.is-inactive{filter:grayscale(.6) opacity(.7);}' +
            '.diary-inactive-pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;background:#2c2f33;color:#d2d5d9;border:1px solid #43474d;}' +
            '.diary-badge{display:inline-block;border:1px solid rgba(127,143,164,.45);border-radius:999px;padding:2px 8px;font-size:12px;}' +
            '.diary-detail-body{padding:12px 14px;display:grid;gap:12px;}' +
            '.diary-glass-toggle{position:relative;width:56px;height:30px;display:inline-block;}' +
            '.diary-glass-toggle input{opacity:0;width:0;height:0;}' +
            '.diary-glass-slider{position:absolute;inset:0;border-radius:999px;background:#1f2937;transition:all .25s ease;box-shadow:inset 0 0 0 1px rgba(255,255,255,.08);}' +
            '.diary-glass-slider:before{content:"";position:absolute;height:24px;width:24px;left:3px;top:3px;border-radius:50%;background:#eef2ff;transition:all .25s ease;box-shadow:0 4px 14px rgba(0,0,0,.35);}' +
            '.diary-glass-toggle input:checked + .diary-glass-slider{background:#A855F7;box-shadow:0 0 14px rgba(168,85,247,.7);}' +
            '.diary-glass-toggle input:checked + .diary-glass-slider:before{transform:translateX(26px);}' +
            '.coping-chat-container{max-height:240px;overflow:auto;display:grid;gap:8px;padding:2px 0;}' +
            '.coping-chat-entry{display:grid;gap:4px;}' +
            '.coping-chat-head{display:flex;align-items:center;justify-content:space-between;gap:8px;}' +
            '.coping-chat-date{display:block;font-size:11px;color:#8ea1bb;}' +
            '.coping-chat-text{margin:0;font-size:14px;line-height:1.4;}' +
            '.coping-chat-actions{display:flex;gap:8px;align-items:center;}' +
            '.coping-chat-edit-row{display:flex;gap:8px;align-items:center;}' +
            '.diary-toggle-status{font-size:12px;color:#cbd5e1;min-width:66px;text-align:right;}' +
            '.diary-chat-compose{display:flex;gap:8px;}' +
            '.diary-chat-compose input{flex:1;min-width:0;}' +
            '.diary-amber-pulse{box-shadow:0 0 0 rgba(245,158,11,.15);animation:diaryPulse 1.6s ease-in-out infinite;}' +
            '.diary-check-item{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;padding:8px;border:1px solid rgba(127,143,164,.35);border-radius:10px;background:rgba(8,20,33,.2);}' +
            '.diary-ledger-filter{width:100%;border:1px solid rgba(127,143,164,.45);border-radius:8px;padding:8px;background:transparent;color:inherit;}' +
            '.diary-tags-cloud{display:flex;gap:6px;flex-wrap:wrap;max-height:120px;overflow:auto;padding-right:4px;}' +
            '.diary-tags-cloud .match{background:rgba(168,85,247,.18);border-color:rgba(168,85,247,.85);color:#d9b8ff;}' +
            '.diary-mention{color:#5aa0ff;font-weight:700;text-decoration:underline;cursor:pointer;white-space:nowrap;background:none;border:none;padding:0;}' +
            '@keyframes diaryPulse{0%,100%{box-shadow:0 0 0 rgba(245,158,11,.15)}50%{box-shadow:0 0 20px rgba(245,158,11,.45)}}' +
            '@keyframes diaryCardIn{from{opacity:.3;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}' +
            '@media (max-width: 980px){.diary-split{grid-template-columns:1fr;gap:10px;min-height:auto}.diary-ledger-list{max-height:42vh}.diary-pane-head{padding:10px 12px}.diary-detail-body{padding:10px 12px}}' +
            '@media (max-width: 640px){.diary-split{gap:8px}.diary-pane{border-radius:12px}.diary-pane-head{flex-wrap:wrap}.diary-pane-head strong{font-size:15px}.diary-ledger-list{padding:8px;max-height:36vh}.diary-ledger-card{padding:8px;border-radius:10px}.diary-detail-body{gap:10px}.diary-glass-toggle{width:52px;height:28px}.diary-toggle-status{min-width:0;font-size:11px}.diary-chat-compose{flex-direction:column}.diary-chat-compose input,.diary-chat-compose button{width:100%}.diary-check-item{grid-template-columns:auto 1fr;gap:6px}.diary-check-item input[type="date"]{grid-column:2 / -1;width:100%}.diary-check-add-row{grid-template-columns:1fr !important}.diary-check-add-row input,.diary-check-add-row button{width:100%}}' +
            '@media (max-width: 760px){.diary-check-add-row{grid-template-columns:1fr !important}.diary-check-add-row input,.diary-check-add-row button{width:100%}}';
        document.head.appendChild(style);
    }

    function mountShell() {
        const root = document.getElementById('diary-app-root');
        if (!root) return null;
        root.innerHTML = '' +
            '<div class="diary-split">' +
            '  <aside class="diary-pane">' +
            '    <div class="diary-pane-head"><strong>Conviction Ledger</strong><button id="diary-new-note" class="mgmt-btn mgmt-btn-primary" type="button">+ Note</button></div>' +
            '    <div id="diary-compose" style="display:none;padding:10px;border-bottom:1px solid rgba(127,143,164,.2);background:rgba(8,18,31,.22);">' +
            '      <div style="display:grid;gap:8px;">' +
            '        <input id="diary-new-ticker" type="text" placeholder="Topic or ticker (required)" aria-required="true" style="border:1px solid rgba(127,143,164,.4);border-radius:8px;background:transparent;color:inherit;padding:8px;">' +
            '        <div id="diary-compose-error" style="display:none;color:#fca5a5;font-size:12px;line-height:1.4;">Topic is required.</div>' +
            '        <textarea id="diary-new-text" placeholder="Write quick note and add #tags..." style="min-height:80px;border:1px solid rgba(127,143,164,.4);border-radius:8px;background:transparent;color:inherit;padding:8px;resize:vertical;"></textarea>' +
            '        <div id="diary-compose-tags" style="display:flex;gap:6px;flex-wrap:wrap;max-height:120px;overflow:auto;"></div>' +
            '        <div style="display:flex;justify-content:flex-end;gap:8px;">' +
            '          <button id="diary-compose-cancel" type="button" class="mgmt-btn mgmt-btn-secondary">Cancel</button>' +
            '          <button id="diary-compose-save" type="button" class="mgmt-btn mgmt-btn-primary">Create</button>' +
            '        </div>' +
            '      </div>' +
            '    </div>' +
            '    <div style="padding:10px;display:grid;gap:8px;">' +
            '      <input id="diary-ledger-filter" class="diary-ledger-filter" type="text" placeholder="Filter by tag or free text">' +
            '      <label style="display:flex;align-items:center;gap:8px;font-size:12px;color:#cbd5e1;">' +
            '        <input id="diary-filter-unchecked" type="checkbox">' +
            '        <span>Only open checklist items</span>' +
            '      </label>' +
            '      <div id="diary-tags-cloud" class="diary-tags-cloud"></div>' +
            '    </div>' +
            '    <div id="diary-ledger-list" class="diary-ledger-list"></div>' +
            '  </aside>' +
            '  <section class="diary-pane">' +
            '    <div id="diary-detail"></div>' +
            '  </section>' +
            '</div>';
        return root;
    }

    function filteredNotes(notes) {
        const q = String(state.filterQuery || '').trim().toLowerCase();
        const activeTag = String(state.activeTagFilter || '').trim().toLowerCase();
        return notes.filter((n) => {
            const tags = (n.user_tags || []).map((t) => sanitizeTag(t).toLowerCase()).filter(Boolean);
            const hasSelectedTag = !activeTag || tags.includes(activeTag);
            const hasOpenChecklist = countUncheckedChecklistItems(n) > 0;
            const matchesChecklistFilter = !state.filterUncheckedOnly || hasOpenChecklist;
            if (!q) return hasSelectedTag && matchesChecklistFilter;

            const byText = String(n.note_text || '').toLowerCase().includes(q)
                || String(n.title || '').toLowerCase().includes(q)
                || String(n.ticker || '').toLowerCase().includes(q);
            const byTagText = tags.some((tag) => tag.includes(q) || tag.replace(/^#/, '').includes(q));

            return hasSelectedTag && matchesChecklistFilter && (byText || byTagText);
        });
    }

    function collectTagStats(notes) {
        const counts = new Map();
        for (const n of notes) {
            for (const tagRaw of (n.user_tags || [])) {
                const tag = sanitizeTag(tagRaw);
                if (!tag) continue;
                counts.set(tag, (counts.get(tag) || 0) + 1);
            }
        }
        return Array.from(counts.entries())
            .map(([tag, count]) => ({ tag, count }))
            .sort((a, b) => (b.count - a.count) || a.tag.localeCompare(b.tag));
    }

    function renderTagCloud(notes) {
        const root = document.getElementById('diary-tags-cloud');
        if (!root) return;
        const stats = collectTagStats(notes);
        const q = String(state.filterQuery || '').trim().toLowerCase();
        const sorted = stats.slice().sort((a, b) => {
            const am = q && a.tag.toLowerCase().includes(q);
            const bm = q && b.tag.toLowerCase().includes(q);
            if (am !== bm) return am ? -1 : 1;
            return (b.count - a.count) || a.tag.localeCompare(b.tag);
        });
        root.innerHTML = sorted.map((it) => {
            const match = q && it.tag.toLowerCase().includes(q) ? 'match' : '';
            const isActive = String(state.activeTagFilter || '').toLowerCase() === it.tag.toLowerCase();
            const activeClass = isActive ? 'match' : '';
            return '<button type="button" class="mgmt-btn mgmt-btn-secondary ' + match + ' ' + activeClass + '" data-filter-tag="' + escapeHtml(it.tag) + '" style="padding:3px 8px;font-size:12px;">' + escapeHtml(it.tag) + ' (' + it.count + ')</button>';
        }).join('');
        root.querySelectorAll('[data-filter-tag]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const tag = btn.getAttribute('data-filter-tag');
                const normalizedTag = sanitizeTag(tag);
                if (String(state.activeTagFilter || '').toLowerCase() === String(normalizedTag || '').toLowerCase()) {
                    state.activeTagFilter = '';
                } else {
                    state.activeTagFilter = normalizedTag;
                }
                rerender();
            });
        });
    }

    function renderNoteCards(notes) {
        const list = document.getElementById('diary-ledger-list');
        if (!list) return;
        const previous = new Map();
        Array.from(list.children).forEach((el) => {
            const id = el.getAttribute('data-note-id');
            if (!id) return;
            previous.set(id, el.getBoundingClientRect().top);
        });

        const sorted = sortForLedger(filteredNotes(notes));
        list.innerHTML = sorted.map((note) => {
            const held = state.holdings.has(note.ticker);
            const isInactive = !note.is_active;
            const uncheckedCount = countUncheckedChecklistItems(note);
            const commentCount = Array.isArray(note.comments) ? note.comments.length : 0;
            const shortUpdated = formatShortDate(note.updatedAt || note.createdAt);
            const classes = [
                'diary-ledger-card',
                state.selectedNoteId === note.note_id ? 'is-selected' : '',
                isInactive ? 'is-inactive' : '',
            ].filter(Boolean).join(' ');
            const preview = escapeHtml(String(note.note_text || '').slice(0, 110) || 'No summary yet');
            const inactivePill = isInactive ? '<span class="diary-inactive-pill">Inactive hypothesis</span>' : '';
            const activePill = note.is_active && held ? '<span class="diary-badge" style="border-color:rgba(34,197,94,.5);color:#86efac;">Active conviction</span>' : '';
            const commentsPill = '<span class="diary-badge" style="border-color:rgba(96,165,250,.45);color:#bfdbfe;">Comments: ' + commentCount + '</span>';
            const checklistPill = uncheckedCount > 0
                ? '<span class="diary-badge" style="border-color:rgba(245,158,11,.6);color:#fcd34d;">Open checklist: ' + uncheckedCount + '</span>'
                : '';
            return '' +
                '<article class="' + classes + '" data-note-id="' + escapeHtml(note.note_id) + '">' +
                '  <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start;">' +
                '    <strong>' + escapeHtml(note.title || note.ticker || 'Untitled note') + '</strong>' +
                '    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;">' + inactivePill + activePill + commentsPill + checklistPill + '</div>' +
                '  </div>' +
                '  <p style="margin:7px 0 6px;color:#8ea1bb;font-size:13px;">' + preview + '</p>' +
                '  <div style="display:flex;gap:6px;flex-wrap:wrap;">' +
                (note.user_tags || []).slice(0, 4).map((t) => '<span class="diary-badge">' + escapeHtml(t) + '</span>').join(' ') +
                '  </div>' +
                '  <div style="margin-top:6px;font-size:11px;color:#8ea1bb;">' + (shortUpdated ? ('Last updated: ' + escapeHtml(shortUpdated)) : '') + '</div>' +
                '</article>';
        }).join('');

        list.querySelectorAll('[data-note-id]').forEach((card) => {
            card.addEventListener('click', () => selectNote(card.getAttribute('data-note-id')));
        });

        requestAnimationFrame(() => {
            Array.from(list.children).forEach((el) => {
                const id = el.getAttribute('data-note-id');
                const oldTop = previous.get(id);
                if (oldTop === undefined) return;
                const newTop = el.getBoundingClientRect().top;
                const delta = oldTop - newTop;
                if (!delta) return;
                el.style.transform = 'translateY(' + delta + 'px)';
                el.style.transition = 'transform 0s';
                requestAnimationFrame(() => {
                    el.style.transform = '';
                    el.style.transition = 'transform .24s ease';
                });
            });
        });
    }

    function renderMentions(text) {
        const raw = String(text || '');
        return raw.replace(/@([A-Za-z0-9][A-Za-z0-9._-]{0,19})/g, function (_m, t) {
            const ticker = normalizeTicker(t);
            return '<button type="button" class="diary-mention" data-mention="' + escapeHtml(ticker) + '">@' + escapeHtml(ticker) + '</button>';
        }).replace(/\n/g, '<br>');
    }

    function checkpointState(item) {
        const due = String(item.due_date || '');
        const now = todayYmd();
        const status = String(item.status || 'PENDING').toUpperCase();
        if (OVERDUE_STATUSES.has(status) && due && due < now) return 'OVERDUE';
        return status;
    }

    function countUncheckedChecklistItems(note) {
        const list = Array.isArray(note && note.hypothesis_checkpoints) ? note.hypothesis_checkpoints : [];
        let count = 0;
        for (const item of list) {
            if (checkpointState(item) !== 'TRUE') count += 1;
        }
        return count;
    }

    function renderDetail(note) {
        const root = document.getElementById('diary-detail');
        if (!root) return;
        if (!note) {
            root.innerHTML = '' +
                '<div style="padding:12px;display:flex;justify-content:center;align-items:center;min-height:420px;">' +
                '  <img id="diary-empty-right-graphic" alt="Coping Diary empty state" style="display:none;width:min(100%,960px);height:auto;border-radius:12px;">' +
                '  <p id="diary-empty-right-fallback" style="display:none;margin:0;color:#7f8c8d;">Select a ledger card to open Focus Sheet.</p>' +
                '</div>';

            const img = document.getElementById('diary-empty-right-graphic');
            const fallback = document.getElementById('diary-empty-right-fallback');
            if (img && fallback) {
                const theme = (document.documentElement.dataset.theme || 'dark') === 'light' ? 'light' : 'dark';
                const candidates = chooseDiaryEmptyGraphic(theme);
                loadFirstExistingImage(
                    candidates,
                    (resolved) => {
                        img.src = resolved;
                        img.style.display = 'block';
                        fallback.style.display = 'none';
                    },
                    () => {
                        img.style.display = 'none';
                        fallback.style.display = 'block';
                    }
                );
            }
            return;
        }

        const chat = (note.comments || []).map((c) => {
            const date = String(c.created_at || '').slice(0, 16).replace('T', ' ');
            const cid = escapeHtml(c.comment_id || '');
            return '' +
                '<article class="coping-chat-entry" data-comment-id="' + cid + '">' +
                '  <div class="coping-chat-head">' +
                '    <span class="coping-chat-date">' + escapeHtml(date) + '</span>' +
                '    <div class="coping-chat-actions">' +
                '      <button type="button" class="mgmt-btn mgmt-btn-secondary" data-comment-edit="' + cid + '" style="padding:2px 8px;font-size:12px;">Edit</button>' +
                '    </div>' +
                '  </div>' +
                '  <p class="coping-chat-text" data-comment-text="' + cid + '">' + escapeHtml(c.text || '') + '</p>' +
                '  <div class="coping-chat-edit-row" data-comment-edit-row="' + cid + '" style="display:none;">' +
                '    <input type="text" data-comment-edit-input="' + cid + '" value="' + escapeHtml(c.text || '') + '" style="flex:1;min-width:0;border:1px solid rgba(127,143,164,.35);border-radius:8px;background:transparent;color:inherit;padding:6px;">' +
                '    <button type="button" class="mgmt-btn mgmt-btn-primary" data-comment-edit-save="' + cid + '" style="padding:2px 8px;font-size:12px;">Save</button>' +
                '    <button type="button" class="mgmt-btn mgmt-btn-secondary" data-comment-edit-cancel="' + cid + '" style="padding:2px 8px;font-size:12px;">Cancel</button>' +
                '    <button type="button" class="mgmt-btn mgmt-btn-secondary" data-comment-edit-delete="' + cid + '" style="padding:2px 8px;font-size:12px;border-color:rgba(239,68,68,.6);color:#fecaca;">Delete</button>' +
                '  </div>' +
                '</article>';
        }).join('');

        const checklist = (note.hypothesis_checkpoints || []).map((cp) => {
            const cpStatus = checkpointState(cp);
            const checked = cpStatus === 'TRUE' ? 'checked' : '';
            const overdueCls = cpStatus === 'OVERDUE' ? 'diary-amber-pulse' : '';
            return '' +
                '<label class="diary-check-item ' + overdueCls + '" data-check-id="' + escapeHtml(cp.checkpoint_id) + '">' +
                '  <input type="checkbox" data-check-toggle="' + escapeHtml(cp.checkpoint_id) + '" ' + checked + '>' +
                '  <span>' + escapeHtml(cp.text || '') + '</span>' +
                '  <input type="date" data-check-due="' + escapeHtml(cp.checkpoint_id) + '" value="' + escapeHtml(cp.due_date || '') + '" style="background:transparent;color:inherit;border:1px solid rgba(127,143,164,.35);border-radius:7px;padding:4px 6px;">' +
                '</label>';
        }).join('');

        const mentionButtons = parseMentionTickers(note.note_text)
            .map((ticker) => '<button type="button" class="diary-mention" data-mention="' + escapeHtml(ticker) + '">@' + escapeHtml(ticker) + '</button>')
            .join(' ');
        const mentionsBlock = mentionButtons
            ? '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;"><span style="font-size:12px;color:#8ea1bb;">Linked holdings:</span>' + mentionButtons + '</div>'
            : '';
        const commentCount = Array.isArray(note.comments) ? note.comments.length : 0;

        root.innerHTML = '' +
            '<div class="diary-pane-head">' +
            '  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">' +
            '    <strong>Focus Sheet</strong>' +
            '    <span class="diary-badge" id="diary-detail-ticker">' + escapeHtml(note.title || note.ticker || 'Untitled note') + '</span>' +
            '    <span class="diary-badge" style="border-color:rgba(96,165,250,.45);color:#bfdbfe;">Comments: ' + commentCount + '</span>' +
            '  </div>' +
            '  <div style="display:flex;align-items:center;gap:8px;">' +
            '    <span class="diary-toggle-status">' + (note.is_active ? 'Active' : 'Inactive') + '</span>' +
            '    <label class="diary-glass-toggle" title="Toggle active hypothesis">' +
            '      <input id="diary-active-toggle" type="checkbox" ' + (note.is_active ? 'checked' : '') + '>' +
            '      <span class="diary-glass-slider"></span>' +
            '    </label>' +
            '    <button id="diary-delete-note" type="button" class="mgmt-btn mgmt-btn-secondary" style="border-color:rgba(239,68,68,.6);color:#fecaca;">Delete</button>' +
            '  </div>' +
            '</div>' +
            '<div class="diary-detail-body">' +
            '  <label style="display:grid;gap:6px;"><span style="font-size:12px;color:#8ea1bb;">Diary note</span><textarea id="diary-focus-note" style="min-height:90px;border:1px solid rgba(127,143,164,.35);border-radius:10px;background:transparent;color:inherit;padding:8px;resize:vertical;">' + escapeHtml(note.note_text || '') + '</textarea></label>' +
            mentionsBlock +
            '  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;">' +
            '    <label style="display:grid;gap:6px;"><span style="font-size:12px;color:#8ea1bb;">Why buy</span><textarea id="diary-why-buy" style="min-height:78px;border:1px solid rgba(127,143,164,.35);border-radius:10px;background:transparent;color:inherit;padding:8px;resize:vertical;">' + escapeHtml(note.hypothesis.why_buy || '') + '</textarea></label>' +
            '    <label style="display:grid;gap:6px;"><span style="font-size:12px;color:#8ea1bb;">Exit plan</span><textarea id="diary-exit-plan" style="min-height:78px;border:1px solid rgba(127,143,164,.35);border-radius:10px;background:transparent;color:inherit;padding:8px;resize:vertical;">' + escapeHtml(note.hypothesis.exit_plan || '') + '</textarea></label>' +
            '    <label style="display:grid;gap:6px;"><span style="font-size:12px;color:#8ea1bb;">Risk factors</span><textarea id="diary-risk-factors" style="min-height:78px;border:1px solid rgba(127,143,164,.35);border-radius:10px;background:transparent;color:inherit;padding:8px;resize:vertical;">' + escapeHtml(note.hypothesis.risk_factors || '') + '</textarea></label>' +
            '  </div>' +
            '  <div style="display:flex;justify-content:flex-end;"><button id="diary-save-focus" type="button" class="mgmt-btn mgmt-btn-primary">Save Focus Sheet</button></div>' +
            '  <div style="display:grid;gap:8px;">' +
            '    <strong>Coping Chat Thread</strong>' +
            '    <div id="coping-chat-log" class="coping-chat-container">' + chat + '</div>' +
            '    <div class="diary-chat-compose">' +
            '      <input id="diary-chat-input" type="text" placeholder="+ Add updates / thoughts..." style="border:1px solid rgba(127,143,164,.35);border-radius:10px;background:transparent;color:inherit;padding:8px;">' +
            '      <button id="diary-chat-send" type="button" class="mgmt-btn mgmt-btn-secondary" aria-label="Send">Send</button>' +
            '    </div>' +
            '  </div>' +
            '  <div style="display:grid;gap:8px;">' +
            '    <strong>Checklist</strong>' +
            '    <div id="diary-checklist">' + checklist + '</div>' +
            '    <div class="diary-check-add-row" style="display:grid;grid-template-columns:minmax(0,1fr) minmax(140px,180px) auto;gap:8px;">' +
            '      <input id="diary-new-check-text" type="text" placeholder="Check Q3 reports" style="border:1px solid rgba(127,143,164,.35);border-radius:10px;background:transparent;color:inherit;padding:8px;min-width:0;">' +
            '      <input id="diary-new-check-date" type="date" style="border:1px solid rgba(127,143,164,.35);border-radius:10px;background:transparent;color:inherit;padding:8px;min-width:0;">' +
            '      <button id="diary-add-check" type="button" class="mgmt-btn mgmt-btn-secondary">Add</button>' +
            '    </div>' +
            '    <div id="diary-checklist-add-error" style="display:none;color:#fca5a5;font-size:12px;line-height:1.4;"></div>' +
            '  </div>' +
            '</div>';

        bindDetailEvents(note);

        const log = document.getElementById('coping-chat-log');
        if (log) log.scrollTo({ top: log.scrollHeight });
    }

    function replaceNote(updated) {
        const next = normalizeNote(updated);
        const idx = state.notes.findIndex((n) => String(n.note_id) === String(next.note_id));
        if (idx >= 0) state.notes[idx] = next;
        else state.notes.unshift(next);
        state.selectedNoteId = next.note_id;
        setLocalNotes(state.notes);
    }

    async function onToggleActive(note, targetChecked) {
        if (state.saving) return;
        state.saving = true;
        const updated = await toggleActive(note, targetChecked);
        if (updated) {
            replaceNote(updated);
            rerender();
        } else {
            note.is_active = targetChecked;
            note.updatedAt = toIsoNow();
            replaceNote(note);
            rerender();
        }
        state.saving = false;
    }

    async function onSaveFocus(note) {
        if (state.saving) return;
        const noteTextEl = document.getElementById('diary-focus-note');
        const whyEl = document.getElementById('diary-why-buy');
        const exitEl = document.getElementById('diary-exit-plan');
        const riskEl = document.getElementById('diary-risk-factors');
        const patch = {
            note_text: noteTextEl ? noteTextEl.value : note.note_text,
            user_tags: parseTagsFromText(noteTextEl ? noteTextEl.value : note.note_text),
            hypothesis: {
                why_buy: whyEl ? whyEl.value : note.hypothesis.why_buy,
                exit_plan: exitEl ? exitEl.value : note.hypothesis.exit_plan,
                risk_factors: riskEl ? riskEl.value : note.hypothesis.risk_factors,
            },
        };
        state.saving = true;
        const updated = await saveNotePatch(note.note_id, patch);
        if (updated) {
            replaceNote(updated);
        } else {
            note.note_text = patch.note_text;
            note.user_tags = patch.user_tags;
            note.hypothesis = patch.hypothesis;
            note.updatedAt = toIsoNow();
            replaceNote(note);
        }
        state.saving = false;
        rerender();
    }

    async function onDeleteNote(note) {
        if (!note || !note.note_id) return;
        if (!window.confirm('Delete this note permanently?')) return;
        const ok = await deleteNoteById(note.note_id);
        if (!ok) return;

        state.notes = state.notes.filter((n) => String(n.note_id) !== String(note.note_id));
        const next = state.notes[0] || null;
        state.selectedNoteId = next ? next.note_id : '';
        setLocalNotes(state.notes);
        rerender();
    }

    async function onSendComment(note) {
        const input = document.getElementById('diary-chat-input');
        if (!input) return;
        const text = String(input.value || '').trim();
        if (!text) return;
        input.value = '';

        const updated = await appendComment(note, text);
        if (updated) {
            replaceNote(updated);
        } else {
            note.comments = (note.comments || []).concat([{
                comment_id: Math.random().toString(36).slice(2, 10),
                text: text,
                created_at: toIsoNow(),
                author: 'self',
                parent_comment_id: null,
            }]);
            note.updatedAt = toIsoNow();
            replaceNote(note);
        }
        rerender();
        const log = document.getElementById('coping-chat-log');
        if (log) {
            log.scrollTo({ top: log.scrollHeight, behavior: 'smooth' });
        }
    }

    async function onEditComment(note, commentId, nextText) {
        const cleanText = String(nextText || '').trim();
        if (!cleanText || !commentId) return;

        const comments = (note.comments || []).map((c) => {
            if (String(c.comment_id) !== String(commentId)) return c;
            return Object.assign({}, c, { text: cleanText });
        });

        const updated = await saveNotePatch(note.note_id, { comments: comments });
        if (updated) {
            replaceNote(updated);
        } else {
            note.comments = comments;
            note.updatedAt = toIsoNow();
            replaceNote(note);
        }
        rerender();
    }

    async function onDeleteComment(note, commentId) {
        if (!commentId) return;
        if (!window.confirm('Delete this comment?')) return;

        const comments = (note.comments || []).filter((c) => String(c.comment_id) !== String(commentId));
        const updated = await saveNotePatch(note.note_id, { comments: comments });
        if (updated) {
            replaceNote(updated);
        } else {
            note.comments = comments;
            note.updatedAt = toIsoNow();
            replaceNote(note);
        }
        rerender();
    }

    async function saveChecklist(note, list) {
        const updated = await saveNotePatch(note.note_id, { hypothesis_checkpoints: list });
        if (updated) {
            replaceNote(updated);
        } else {
            note.hypothesis_checkpoints = list;
            note.updatedAt = toIsoNow();
            replaceNote(note);
        }
        rerender();
    }

    function collectChecklistFromDom(note) {
        const out = [];
        const root = document.getElementById('diary-checklist');
        if (!root) return out;
        root.querySelectorAll('[data-check-id]').forEach((row) => {
            const id = row.getAttribute('data-check-id');
            const base = (note.hypothesis_checkpoints || []).find((c) => String(c.checkpoint_id) === String(id)) || {};
            const checked = row.querySelector('[data-check-toggle]');
            const due = row.querySelector('[data-check-due]');
            const dueDate = due ? String(due.value || '').trim() : String(base.due_date || '');
            let status = checked && checked.checked ? 'TRUE' : 'PENDING';
            if (status === 'PENDING' && dueDate && dueDate < todayYmd()) status = 'OVERDUE';
            out.push({
                checkpoint_id: id,
                text: String(base.text || '').trim(),
                due_date: dueDate,
                status: status,
                resolved_at: status === 'TRUE' ? toIsoNow() : null,
            });
        });
        return out;
    }

    function setChecklistAddError(message) {
        const errorEl = document.getElementById('diary-checklist-add-error');
        if (!errorEl) return;
        const text = String(message || '').trim();
        errorEl.textContent = text;
        errorEl.style.display = text ? 'block' : 'none';
    }

    function bindDetailEvents(note) {
        const toggle = document.getElementById('diary-active-toggle');
        if (toggle) {
            toggle.addEventListener('change', () => onToggleActive(note, toggle.checked));
        }

        const saveFocusBtn = document.getElementById('diary-save-focus');
        if (saveFocusBtn) saveFocusBtn.addEventListener('click', () => onSaveFocus(note));

        const deleteBtn = document.getElementById('diary-delete-note');
        if (deleteBtn) deleteBtn.addEventListener('click', () => onDeleteNote(note));

        const sendBtn = document.getElementById('diary-chat-send');
        const chatInput = document.getElementById('diary-chat-input');
        if (sendBtn) sendBtn.addEventListener('click', () => onSendComment(note));
        if (chatInput) {
            chatInput.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter') return;
                event.preventDefault();
                onSendComment(note);
            });
        }

        const setCommentEditMode = (commentId, editing) => {
            const row = document.querySelector('[data-comment-edit-row="' + String(commentId) + '"]');
            const actions = document.querySelector('[data-comment-edit="' + String(commentId) + '"]');
            if (row) row.style.display = editing ? 'flex' : 'none';
            if (actions) actions.style.display = editing ? 'none' : 'inline-block';
            if (editing) {
                const input = document.querySelector('[data-comment-edit-input="' + String(commentId) + '"]');
                if (input) input.focus();
            }
        };

        document.querySelectorAll('[data-comment-edit]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const commentId = btn.getAttribute('data-comment-edit');
                setCommentEditMode(commentId, true);
            });
        });

        document.querySelectorAll('[data-comment-edit-cancel]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const commentId = btn.getAttribute('data-comment-edit-cancel');
                const source = (note.comments || []).find((c) => String(c.comment_id) === String(commentId));
                const input = document.querySelector('[data-comment-edit-input="' + String(commentId) + '"]');
                if (input && source) input.value = String(source.text || '');
                setCommentEditMode(commentId, false);
            });
        });

        document.querySelectorAll('[data-comment-edit-save]').forEach((btn) => {
            btn.addEventListener('click', async () => {
                const commentId = btn.getAttribute('data-comment-edit-save');
                const input = document.querySelector('[data-comment-edit-input="' + String(commentId) + '"]');
                const nextText = input ? input.value : '';
                await onEditComment(note, commentId, nextText);
            });
        });

        document.querySelectorAll('[data-comment-edit-delete]').forEach((btn) => {
            btn.addEventListener('click', async () => {
                const commentId = btn.getAttribute('data-comment-edit-delete');
                await onDeleteComment(note, commentId);
            });
        });

        document.querySelectorAll('[data-comment-edit-input]').forEach((input) => {
            input.addEventListener('keydown', async (event) => {
                if (event.key !== 'Enter') return;
                event.preventDefault();
                const commentId = input.getAttribute('data-comment-edit-input');
                await onEditComment(note, commentId, input.value);
            });
        });

        const addCheckBtn = document.getElementById('diary-add-check');
        if (addCheckBtn) {
            addCheckBtn.addEventListener('click', () => {
                const textEl = document.getElementById('diary-new-check-text');
                const dateEl = document.getElementById('diary-new-check-date');
                const text = textEl ? String(textEl.value || '').trim() : '';
                const dueDate = dateEl ? String(dateEl.value || '').trim() : '';
                if (!text && !dueDate) {
                    setChecklistAddError('Please add comment and date.');
                    if (textEl) textEl.focus();
                    return;
                }
                if (!text) {
                    setChecklistAddError('Comment is required.');
                    if (textEl) textEl.focus();
                    return;
                }
                if (!dueDate) {
                    setChecklistAddError('Date is required.');
                    if (dateEl) dateEl.focus();
                    return;
                }
                setChecklistAddError('');
                const next = (note.hypothesis_checkpoints || []).slice();
                next.push({
                    checkpoint_id: Math.random().toString(36).slice(2, 10),
                    text: text,
                    due_date: dueDate,
                    status: dueDate < todayYmd() ? 'OVERDUE' : 'PENDING',
                    resolved_at: null,
                });
                if (textEl) textEl.value = '';
                if (dateEl) dateEl.value = '';
                saveChecklist(note, next);
            });
        }

        const checklistRoot = document.getElementById('diary-checklist');
        if (checklistRoot) {
            checklistRoot.querySelectorAll('[data-check-toggle], [data-check-due]').forEach((el) => {
                el.addEventListener('change', () => {
                    const next = collectChecklistFromDom(note);
                    saveChecklist(note, next);
                });
            });
        }

        const focusNote = document.getElementById('diary-focus-note');
        if (focusNote) {
            focusNote.addEventListener('blur', () => {
                if (!focusNote.value) return;
                // Keep tags in sync with free-text note body.
                note.user_tags = parseTagsFromText(focusNote.value);
            });
        }

        document.querySelectorAll('[data-mention]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const ticker = normalizeTicker(btn.getAttribute('data-mention'));
                if (!ticker) return;
                if (typeof window.openAnalysisForTicker === 'function') {
                    window.openAnalysisForTicker(ticker);
                } else if (typeof window.showTab === 'function') {
                    window.showTab('analysis');
                }
            });
        });
    }

    function findSelectedNote() {
        if (!state.notes.length) return null;
        const found = state.notes.find((n) => String(n.note_id) === String(state.selectedNoteId));
        return found || state.notes[0];
    }

    function collectPredefinedComposerTags() {
        const tags = [];
        const seen = new Set();

        const holdingsByWallet = window.WALLET_HOLDINGS || {};
        Object.values(holdingsByWallet).forEach((rows) => {
            (rows || []).forEach((h) => {
                const ticker = normalizeTicker(h && h.ticker);
                if (!ticker || ticker === 'CASH') return;
                const tag = sanitizeTag('#' + ticker);
                if (!tag || seen.has(tag)) return;
                seen.add(tag);
                tags.push(tag);
            });
        });

        const wallets = window.WALLET_SUMMARIES || {};
        Object.keys(wallets).forEach((name) => {
            if (String(name).toLowerCase() === 'summary') return;
            const tag = sanitizeTag('#WALLET_' + name);
            if (!tag || seen.has(tag)) return;
            seen.add(tag);
            tags.push(tag);
        });

        const globalMarket = '#GLOBAL_MARKET';
        if (!seen.has(globalMarket)) tags.push(globalMarket);
        return tags;
    }

    function appendTagToNewNote(tag) {
        const area = document.getElementById('diary-new-text');
        if (!area || !tag) return;
        const current = String(area.value || '');
        const spacer = current.length && !current.endsWith(' ') && !current.endsWith('\n') ? ' ' : '';
        area.value = current + spacer + tag + ' ';
        area.focus();
    }

    function renderComposerTags() {
        const root = document.getElementById('diary-compose-tags');
        if (!root) return;
        const tags = collectPredefinedComposerTags();
        root.innerHTML = tags.map((tag) =>
            '<button type="button" class="mgmt-btn mgmt-btn-secondary" data-compose-tag="' + escapeHtml(tag) + '" style="padding:4px 8px;font-size:12px;">' + escapeHtml(tag) + '</button>'
        ).join('');
        root.querySelectorAll('[data-compose-tag]').forEach((btn) => {
            btn.addEventListener('click', () => appendTagToNewNote(btn.getAttribute('data-compose-tag')));
        });
    }

    function toggleComposer(show) {
        state.composeOpen = Boolean(show);
        const box = document.getElementById('diary-compose');
        const btn = document.getElementById('diary-new-note');
        if (box) box.style.display = state.composeOpen ? 'block' : 'none';
        if (btn) btn.textContent = state.composeOpen ? 'Close' : '+ Note';
        setComposerError('');
        if (state.composeOpen) {
            renderComposerTags();
            const tickerInput = document.getElementById('diary-new-ticker');
            if (tickerInput) tickerInput.focus();
        }
    }

    function setComposerError(message) {
        const errorEl = document.getElementById('diary-compose-error');
        const tickerEl = document.getElementById('diary-new-ticker');
        const hasError = Boolean(message);
        if (errorEl) {
            errorEl.textContent = message || '';
            errorEl.style.display = hasError ? 'block' : 'none';
        }
        if (tickerEl) {
            tickerEl.setAttribute('aria-invalid', hasError ? 'true' : 'false');
            tickerEl.style.borderColor = hasError ? 'rgba(239,68,68,.95)' : 'rgba(127,143,164,.4)';
        }
    }

    function selectNote(noteId) {
        state.selectedNoteId = String(noteId || '');
        rerender();
    }

    async function createNewTickerNoteFromComposer() {
        const tickerEl = document.getElementById('diary-new-ticker');
        const textEl = document.getElementById('diary-new-text');
        const title = String(tickerEl && tickerEl.value || '').trim();
        const ticker = normalizeTicker(title);
        const noteText = String(textEl && textEl.value || '').trim();
        if (!title) {
            setComposerError('Topic is required.');
            if (tickerEl) tickerEl.focus();
            return;
        }

        setComposerError('');

        const mergedTags = parseTagsFromText(noteText);
        const payload = {
            title: title,
            note_text: noteText,
            linked_assets: ticker ? [ticker] : [],
            user_tags: mergedTags,
            is_active: Boolean(ticker),
            user_override_active: false,
            hypothesis: {
                why_buy: '',
                exit_plan: '',
                risk_factors: '',
            },
            hypothesis_checkpoints: [],
            comments: [],
        };
        const created = await createNote(payload);
        if (!created) {
            setComposerError('Could not save note. Try again.');
            return;
        }
        const note = created;
        replaceNote(note);
        state.selectedNoteId = note.note_id;
        if (tickerEl) tickerEl.value = '';
        if (textEl) textEl.value = '';
        toggleComposer(false);
        rerender();
    }

    function rerender() {
        const all = state.notes;
        renderTagCloud(all);
        renderNoteCards(all);
        const selected = findSelectedNote();
        if (selected) state.selectedNoteId = selected.note_id;
        renderDetail(selected);

        const list = document.getElementById('diary-ledger-list');
        if (list && !all.length) {
            list.innerHTML = '<article style="padding:10px;color:#8ea1bb;">No diary notes yet. Use + Note.</article>';
        }
    }

    async function init() {
        const root = document.getElementById('diary-app-root');
        if (!root) return;
        if (state.loaded) return;
        state.loaded = true;

        ensureStyles();
        mountShell();

        const notes = await fetchNotes();
        state.notes = notes;
        state.holdings = collectActiveHoldings();
        if (!state.selectedNoteId && notes.length) state.selectedNoteId = notes[0].note_id;

        const filterInput = document.getElementById('diary-ledger-filter');
        if (filterInput) {
            filterInput.addEventListener('input', () => {
                state.filterQuery = String(filterInput.value || '').trim();
                rerender();
            });
        }

        const uncheckedToggle = document.getElementById('diary-filter-unchecked');
        if (uncheckedToggle) {
            uncheckedToggle.checked = Boolean(state.filterUncheckedOnly);
            uncheckedToggle.addEventListener('change', () => {
                state.filterUncheckedOnly = Boolean(uncheckedToggle.checked);
                rerender();
            });
        }

        const addBtn = document.getElementById('diary-new-note');
        if (addBtn) {
            addBtn.addEventListener('click', () => toggleComposer(!state.composeOpen));
        }

        const saveComposeBtn = document.getElementById('diary-compose-save');
        if (saveComposeBtn) {
            saveComposeBtn.addEventListener('click', createNewTickerNoteFromComposer);
        }

        const cancelComposeBtn = document.getElementById('diary-compose-cancel');
        if (cancelComposeBtn) {
            cancelComposeBtn.addEventListener('click', () => toggleComposer(false));
        }

        const tickerInput = document.getElementById('diary-new-ticker');
        const noteInput = document.getElementById('diary-new-text');
        if (noteInput) {
            noteInput.addEventListener('keydown', (event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                    event.preventDefault();
                    createNewTickerNoteFromComposer();
                }
            });
        }
        if (tickerInput) {
            tickerInput.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter') return;
                event.preventDefault();
                if (noteInput) noteInput.focus();
            });
        }

        window.addEventListener('roastfolio:wallets-updated', () => {
            state.holdings = collectActiveHoldings();
            rerender();
        });

        rerender();
    }

    // Public overrides used by existing inline wiring.
    window.renderNoteCards = function (notes) {
        renderNoteCards((notes || []).map(normalizeNote));
    };
    window._renderDiaryNotes = function () {
        if (!state.loaded) return;
        rerender();
    };
    window._renderDiaryTagPalette = function () {
        // Legacy hook kept for compatibility with showTab lazy refresh.
    };
    window.initCopingDiary = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
