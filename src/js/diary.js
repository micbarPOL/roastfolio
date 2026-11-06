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
        mobileDetailOpen: false,
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
            style.textContent += `
        .diary-v3{max-width:1440px;margin:0 auto;padding:var(--space-6);color:var(--text-primary)}
        .diary-v3,.diary-v3 *{min-width:0;letter-spacing:0}
        .diary-v3 [hidden]{display:none!important}
        .diary-v3 h1{margin:0;color:var(--text-primary);font-size:36px;line-height:1.2;font-weight:650}
        .diary-v3 h2{margin:0;color:var(--text-primary);font-size:var(--fs-xl);line-height:1.35;font-weight:600}
        .diary-v3 h3{margin:0;color:var(--text-primary);font-size:var(--fs-md);font-weight:600}
        .diary-v3 .diary-screen-heading,.diary-v3 .diary-ledger-heading,.diary-v3 .diary-detail-header,.diary-v3 .diary-detail-top,.diary-v3 .diary-section-heading,.diary-v3 .diary-composer-heading{display:flex;align-items:center;justify-content:space-between;gap:var(--space-4)}
        .diary-v3 .diary-screen-heading{align-items:flex-end;margin-bottom:var(--space-5)}
        .diary-v3 .diary-eyebrow{display:block;margin-bottom:var(--space-2);color:var(--text-secondary);font-size:var(--fs-xs)}
        .diary-v3 .diary-intro,.diary-v3 .diary-muted{margin:0;color:var(--text-secondary);font-size:var(--fs-xs);line-height:1.6}
        .diary-v3 .diary-overview{display:flex;flex-wrap:wrap;gap:var(--space-5);margin:0 0 var(--space-4);padding:0 0 var(--space-4);border-bottom:1px solid var(--border-subtle)}
        .diary-v3 .diary-overview-item{display:flex;align-items:baseline;gap:var(--space-2);color:var(--text-secondary);font-size:var(--fs-xs)}
        .diary-v3 .diary-overview-item strong{color:var(--text-primary);font-size:var(--fs-sm);font-variant-numeric:tabular-nums}
        .diary-v3 .diary-split{display:grid;grid-template-columns:minmax(290px,36%) minmax(0,64%);gap:var(--space-6);min-height:640px;border:0}
        .diary-v3 .diary-pane{min-width:0;border:0;border-radius:0;background:transparent;backdrop-filter:none}
        .diary-v3 .diary-ledger-pane{padding-right:var(--space-4);border-right:1px solid var(--border-subtle)}
        .diary-v3 .diary-pane-head{padding:0 0 var(--space-3);border:0;background:transparent}
        .diary-v3 .diary-pane-head strong{color:var(--text-primary);font-size:var(--fs-md)}
        .diary-v3 .diary-ledger-heading{margin-bottom:var(--space-3)}
        .diary-v3 .diary-ledger-filter{width:100%;min-height:var(--touch-min);padding:var(--space-2) var(--space-3);border:1px solid var(--border-strong);border-radius:var(--radius-sm);background:var(--bg-surface-1);color:var(--text-primary);font:inherit;font-size:var(--fs-sm)}
        .diary-v3 .diary-ledger-tools{display:grid;gap:var(--space-2);padding:var(--space-2) 0}
        .diary-v3 .diary-open-filter{display:flex;align-items:center;gap:var(--space-2);min-height:var(--touch-min);color:var(--text-secondary);font-size:var(--fs-xs)}
        .diary-v3 .diary-open-filter input{width:18px;height:18px;accent-color:var(--accent-primary)}
        .diary-v3 .diary-tags-cloud{display:flex;flex-wrap:wrap;gap:var(--space-2);max-height:104px;padding:0 0 var(--space-2);overflow:auto}
        .diary-v3 .diary-tags-cloud button{min-height:32px;padding:var(--space-1) var(--space-2);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);background:transparent;color:var(--text-secondary);font:inherit;font-size:var(--fs-xs)}
        .diary-v3 .diary-tags-cloud button.match{border-color:var(--accent-primary);background:var(--accent-glow);color:var(--text-primary)}
        .diary-v3 .diary-ledger-list{display:grid;gap:0;max-height:calc(100dvh - 380px);padding:0;overflow:auto;overscroll-behavior:contain}
        .diary-v3 .diary-ledger-card{display:grid;gap:var(--space-2);padding:var(--space-4) var(--space-2);border:0;border-top:1px solid var(--border-subtle);border-left:2px solid transparent;border-radius:0;background:transparent;box-shadow:none;animation:none;cursor:pointer}
        .diary-v3 .diary-ledger-card.is-selected{border-left-color:var(--accent-primary);background:var(--bg-surface-1);box-shadow:none}
        .diary-v3 .diary-ledger-card.is-inactive{filter:none;opacity:.68}
        @media(hover:hover){.diary-v3 .diary-ledger-card:hover{transform:none;border-color:var(--border-subtle);border-left-color:var(--accent-hover);background:var(--bg-surface-1)}}
        .diary-v3 .diary-row-top,.diary-v3 .diary-row-meta,.diary-v3 .diary-row-badges,.diary-v3 .diary-row-tags{display:flex;align-items:center;flex-wrap:wrap;gap:var(--space-2)}
        .diary-v3 .diary-row-top{justify-content:space-between}
        .diary-v3 .diary-row-title{color:var(--text-primary);font-size:var(--fs-sm);font-weight:600;line-height:1.4}
        .diary-v3 .diary-row-preview{display:-webkit-box;margin:0;color:var(--text-secondary);font-size:var(--fs-xs);line-height:1.6;overflow:hidden;-webkit-line-clamp:2;-webkit-box-orient:vertical}
        .diary-v3 .diary-row-meta{color:var(--text-secondary);font-size:11px}
        .diary-v3 .diary-empty-list{padding:var(--space-4) var(--space-2);color:var(--text-secondary);font-size:var(--fs-sm);line-height:1.6}
        .diary-v3 .diary-badge,.diary-v3 .diary-inactive-pill{display:inline-flex;align-items:center;min-height:24px;padding:2px var(--space-2);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);background:transparent;color:var(--text-secondary);font-size:11px}
        .diary-v3 .diary-inactive-pill{border-color:var(--border-subtle);background:transparent;color:var(--text-secondary)}
        .diary-v3 .diary-active-pill{border-color:color-mix(in srgb,var(--color-success) 40%,transparent);color:var(--color-success)}
        .diary-v3 .diary-comments-pill{border-color:color-mix(in srgb,var(--accent-primary) 40%,transparent);color:var(--accent-primary)}
        .diary-v3 .diary-checklist-pill{border-color:color-mix(in srgb,var(--color-warning) 42%,transparent);color:var(--color-warning)}
        .diary-v3 .diary-detail-header{position:sticky;top:var(--tflow-header-h,0px);z-index:5;align-items:flex-start;padding:var(--space-4) 0;border-bottom:1px solid var(--border-strong);background:var(--bg-canvas)}
        .diary-v3 .diary-detail-title{display:grid;gap:var(--space-2)}
        .diary-v3 .diary-detail-title h2{font-size:var(--fs-xl)}
        .diary-v3 .diary-detail-actions{display:flex;align-items:center;gap:var(--space-2)}
        .diary-v3 .diary-detail-body{display:grid;gap:var(--space-5);padding:var(--space-4) 0}
        .diary-v3 .diary-detail-section{display:grid;gap:var(--space-3);padding-top:var(--space-4);border-top:1px solid var(--border-subtle)}
        .diary-v3 .diary-section-heading{justify-content:flex-start}
        .diary-v3 .diary-section-index{color:var(--text-secondary);font-size:var(--fs-xs);font-variant-numeric:tabular-nums}
        .diary-v3 .diary-section-heading .diary-muted{margin-left:auto}
        .diary-v3 .diary-detail-body textarea,.diary-v3 .diary-detail-body input{width:100%;min-height:var(--touch-min);padding:var(--space-3);border:1px solid var(--border-strong);border-radius:var(--radius-sm);background:var(--bg-surface-1);color:var(--text-primary);font:inherit;font-size:var(--fs-sm);line-height:1.6}
        .diary-v3 .diary-detail-body textarea{min-height:78px;resize:vertical}
        .diary-v3 .diary-detail-body #diary-focus-note{min-height:104px}
        .diary-v3 .diary-detail-body label{display:grid;gap:var(--space-2);color:var(--text-secondary);font-size:var(--fs-xs)}
        .diary-v3 .diary-thesis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-3)}
        .diary-v3 .diary-thesis-grid .diary-risk-field{grid-column:1/-1}
        .diary-v3 .diary-note-save-row{display:flex;justify-content:flex-end}
        .diary-v3 .diary-focus-tags{display:flex;flex-wrap:wrap;gap:var(--space-2)}
        .diary-v3 .diary-focus-tags:empty{display:none}
        .diary-v3 .diary-mention{display:inline-flex;align-items:center;gap:var(--space-2);min-height:32px;padding:var(--space-1) var(--space-2);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);color:var(--accent-primary);text-decoration:none;font-size:var(--fs-xs)}
        .diary-v3 .diary-check-item{grid-template-columns:auto minmax(0,1fr) auto;gap:var(--space-3);padding:var(--space-3);border-color:var(--border-subtle);border-radius:var(--radius-sm);background:transparent}
        .diary-v3 .diary-check-item input[type="checkbox"]{width:18px;height:18px;accent-color:var(--accent-primary)}
        .diary-v3 .diary-chat-compose{display:flex;gap:var(--space-2)}
        .diary-v3 .diary-chat-compose input{flex:1;min-width:0}
        .diary-v3 .coping-chat-container{max-height:220px;padding:0;}
        .diary-v3 .coping-chat-entry{padding:var(--space-3) 0;border-top:1px solid var(--border-subtle)}
        .diary-v3 .coping-chat-head{align-items:center}
        .diary-v3 .coping-chat-date{color:var(--text-secondary);font-variant-numeric:tabular-nums}
        .diary-v3 .coping-chat-text{color:var(--text-primary);font-size:var(--fs-sm);line-height:1.6;white-space:pre-wrap}
        .diary-v3 .diary-focus-empty{display:grid;align-content:center;min-height:420px;max-width:440px;gap:var(--space-3);padding:var(--space-5) 0}
        .diary-v3 .diary-focus-empty h2{font-size:var(--fs-xl)}
        .diary-v3 .diary-focus-empty p{margin:0;color:var(--text-secondary);font-size:var(--fs-sm);line-height:1.6}
        .diary-v3 .diary-detail-back,.diary-v3 .diary-mobile-new-note{display:none}
        .diary-v3 .diary-mobile-nav{display:none}
        .diary-v3 .diary-composer-backdrop{position:fixed;inset:0;z-index:40;background:var(--bg-glass)}
        .diary-v3 .diary-compose{position:fixed;inset:0 0 0 auto;z-index:41;width:min(480px,100%);height:100dvh;padding:var(--space-5);overflow:auto;border:0;border-left:1px solid var(--border-strong);background:var(--bg-surface-2);box-shadow:var(--shadow-md)}
        .diary-v3 .diary-compose-head{display:flex;justify-content:space-between;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4)}
        .diary-v3 .diary-compose-close{min-width:var(--touch-min);min-height:var(--touch-min);border:0;border-radius:var(--radius-sm);background:transparent;color:var(--text-secondary)}
        .diary-v3 .diary-compose input,.diary-v3 .diary-compose textarea{width:100%;min-height:var(--touch-min);padding:var(--space-3);border:1px solid var(--border-strong);border-radius:var(--radius-sm);background:var(--bg-surface-1);color:var(--text-primary);font:inherit;font-size:var(--fs-sm)}
        .diary-v3 .diary-compose textarea{min-height:150px;resize:vertical}
        .diary-v3 :focus-visible{outline:2px solid var(--accent-primary);outline-offset:3px}
        .diary-v3 button,.diary-v3 input,.diary-v3 textarea{touch-action:manipulation}
        @media(max-width:980px){.diary-v3 .diary-split{grid-template-columns:minmax(270px,38%) minmax(0,62%);gap:var(--space-4)}.diary-v3 .diary-pane-head{padding:0 0 var(--space-3)}.diary-v3 .diary-detail-body{padding:var(--space-4) 0}}
        @media(max-width:767px){.diary-v3{padding:var(--space-4) var(--space-3) calc(var(--bottom-tabs-h) + var(--space-5))}.diary-v3 .diary-screen-heading{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start}.diary-v3 .diary-screen-heading .diary-prompt{grid-column:1}.diary-v3 .diary-screen-heading .diary-new-note{grid-column:2;grid-row:1/3}.diary-v3 .diary-overview{gap:var(--space-3)}.diary-v3 .diary-overview-item{display:grid;gap:2px}.diary-v3 .diary-split{display:block;min-height:0}.diary-v3 .diary-ledger-pane{padding:var(--space-2) 0;border:0}.diary-v3 .diary-split[data-mobile-detail="true"] .diary-ledger-pane{display:none}.diary-v3 .diary-split:not([data-mobile-detail="true"]) .diary-focus-pane{display:none}.diary-v3 .diary-detail-header{top:0;flex-wrap:wrap}.diary-v3 .diary-detail-back,.diary-v3 .diary-mobile-new-note{display:inline-flex}.diary-v3 .diary-detail-body{padding:var(--space-3) 0}.diary-v3 .diary-thesis-grid{grid-template-columns:minmax(0,1fr)}.diary-v3 .diary-thesis-grid .diary-risk-field{grid-column:auto}.diary-v3 .diary-check-add-row{grid-template-columns:minmax(0,1fr) auto!important}.diary-v3 .diary-check-add-row input[type="date"]{grid-column:1}.diary-v3 .diary-chat-compose{flex-direction:row}.diary-v3 .diary-chat-compose button{width:auto}.diary-v3 .diary-ledger-list{max-height:none;overflow:visible}.diary-v3 .diary-compose{inset:auto 0 0;width:100%;height:auto;max-height:92dvh;padding:var(--space-4) var(--space-3) calc(var(--space-5) + env(safe-area-inset-bottom));border:1px solid var(--border-strong);border-bottom:0;border-radius:var(--radius-md) var(--radius-md) 0 0}.diary-v3 .diary-mobile-nav{position:fixed;z-index:50;inset:auto 0 0;display:flex;justify-content:space-around;min-height:var(--bottom-tabs-h);padding-bottom:env(safe-area-inset-bottom);border-top:1px solid var(--border-strong);background:var(--bg-canvas)}.diary-v3 .diary-mobile-nav a{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:var(--touch-min);gap:var(--space-1);color:var(--text-secondary);font-size:11px;text-decoration:none}.diary-v3 .diary-mobile-nav a[aria-current="page"]{color:var(--text-primary)}.diary-v3 .diary-mobile-nav svg{width:18px;height:18px}}
        @media(prefers-reduced-motion:reduce){.diary-v3 *{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
        `;
        document.head.appendChild(style);
    }

    function mountShell() {
        const root = document.getElementById('diary-app-root');
        if (!root) return null;
        root.classList.add('diary-v3');
        root.innerHTML = '' +
            '  <header class="diary-screen-heading">' +
            '    <div class="diary-prompt"><span class="diary-eyebrow">DECISION JOURNAL</span><h1>Coping Diary</h1><p class="diary-intro">The market changes. Your reasoning stays on record.</p></div>' +
            '    <button id="diary-new-note" class="mgmt-btn mgmt-btn-primary diary-new-note" type="button" aria-expanded="false"><span aria-hidden="true">+</span> New note</button>' +
            '  </header>' +
            '  <div class="diary-overview" id="diary-overview" aria-live="polite"></div>' +
            '  <div class="diary-split" id="diary-split">' +
            '    <aside class="diary-pane diary-ledger-pane" aria-labelledby="diary-ledger-title">' +
            '      <div class="diary-ledger-heading"><div><h2 id="diary-ledger-title">Conviction ledger</h2><p id="diary-ledger-count" class="diary-muted" aria-live="polite"></p></div><button id="diary-mobile-new-note" type="button" class="mgmt-btn mgmt-btn-secondary diary-mobile-new-note" aria-label="New note" title="New note">+</button></div>' +
            '      <div id="diary-compose-backdrop" class="diary-composer-backdrop" hidden></div>' +
            '      <section id="diary-compose" class="diary-compose" role="dialog" aria-modal="true" aria-labelledby="diary-compose-title" aria-hidden="true" hidden>' +
            '        <div class="diary-compose-head"><h2 id="diary-compose-title">New diary entry</h2><button id="diary-compose-close" class="diary-compose-close" type="button" aria-label="Close composer" title="Close">&times;</button></div>' +
            '      <div style="display:grid;gap:8px;">' +
            '        <label><span class="diary-muted">Topic or ticker</span><input id="diary-new-ticker" type="text" placeholder="e.g. NVDA" aria-required="true"></label>' +
            '        <div id="diary-compose-error" style="display:none;color:#fca5a5;font-size:12px;line-height:1.4;">Topic is required.</div>' +
            '        <label><span class="diary-muted">Your note</span><textarea id="diary-new-text" placeholder="What are you thinking? Add #tags or @holdings."></textarea></label>' +
            '        <div id="diary-compose-tags" class="diary-tags-cloud"></div>' +
            '        <div style="display:flex;justify-content:flex-end;gap:8px;">' +
            '          <button id="diary-compose-cancel" type="button" class="mgmt-btn mgmt-btn-secondary">Cancel</button>' +
            '          <button id="diary-compose-save" type="button" class="mgmt-btn mgmt-btn-primary">Create entry</button>' +
            '        </div>' +
            '      </div>' +
            '      </section>' +
            '      <div class="diary-ledger-tools">' +
            '      <input id="diary-ledger-filter" class="diary-ledger-filter" type="search" placeholder="Search notes and tags" aria-label="Search notes and tags">' +
            '      <label class="diary-open-filter">' +
            '        <input id="diary-filter-unchecked" type="checkbox">' +
            '        <span>Open checklist items</span>' +
            '      </label>' +
            '      <div id="diary-tags-cloud" class="diary-tags-cloud"></div>' +
            '      </div>' +
            '      <div id="diary-ledger-empty" class="diary-empty-list" role="status">Loading diary entries...</div>' +
            '      <div id="diary-ledger-list" class="diary-ledger-list" hidden></div>' +
            '    </aside>' +
            '    <section class="diary-pane diary-focus-pane" aria-label="Focus Sheet">' +
            '      <div id="diary-detail"></div>' +
            '    </section>' +
            '  </div>';
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
        root.innerHTML = '<button type="button" class="' + (!state.activeTagFilter ? 'match' : '') + '" data-filter-tag="">All notes</button>' + sorted.map((it) => {
            const match = q && it.tag.toLowerCase().includes(q) ? 'match' : '';
            const isActive = String(state.activeTagFilter || '').toLowerCase() === it.tag.toLowerCase();
            const activeClass = isActive ? 'match' : '';
            return '<button type="button" class="' + match + ' ' + activeClass + '" data-filter-tag="' + escapeHtml(it.tag) + '">' + escapeHtml(it.tag) + ' <span aria-hidden="true">' + it.count + '</span></button>';
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
        const empty = document.getElementById('diary-ledger-empty');
        const previous = new Map();
        Array.from(list.children).forEach((el) => {
            const id = el.getAttribute('data-note-id');
            if (!id) return;
            previous.set(id, el.getBoundingClientRect().top);
        });

        const sorted = sortForLedger(filteredNotes(notes));
        list.hidden = sorted.length === 0;
        if (empty) {
            empty.hidden = sorted.length > 0;
            empty.textContent = notes.length
                ? 'No entries match these filters.'
                : 'No entries yet. Start by writing down a thesis or an open question.';
        }
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
            const activePill = note.is_active && held ? '<span class="diary-badge diary-active-pill">Held</span>' : '';
            const commentsPill = commentCount > 0 ? '<span class="diary-badge diary-comments-pill">' + commentCount + ' comments</span>' : '';
            const checklistPill = uncheckedCount > 0
                ? '<span class="diary-badge diary-checklist-pill">' + uncheckedCount + ' open</span>'
                : '';
            return '' +
                '<article class="' + classes + '" data-note-id="' + escapeHtml(note.note_id) + '" role="button" tabindex="0" aria-pressed="' + (state.selectedNoteId === note.note_id ? 'true' : 'false') + '">' +
                '  <div class="diary-row-top"><strong class="diary-row-title">' + escapeHtml(note.title || note.ticker || 'Untitled note') + '</strong><div class="diary-row-badges">' + inactivePill + activePill + commentsPill + checklistPill + '</div></div>' +
                '  <p class="diary-row-preview">' + preview + '</p>' +
                '  <div class="diary-row-tags">' + (note.user_tags || []).slice(0, 4).map((t) => '<span class="diary-badge">' + escapeHtml(t) + '</span>').join(' ') + '</div>' +
                '  <div class="diary-row-meta">' + (shortUpdated ? ('Updated ' + escapeHtml(shortUpdated)) : '') + '</div>' +
                '</article>';
        }).join('');

        list.querySelectorAll('[data-note-id]').forEach((card) => {
            card.addEventListener('click', () => selectNote(card.getAttribute('data-note-id')));
            card.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                selectNote(card.getAttribute('data-note-id'));
            });
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
            root.innerHTML = '<div class="diary-focus-empty"><span class="diary-eyebrow">FOCUS SHEET</span><h2>Keep the reasoning close.</h2><p>Select an entry to review its thesis, open questions, and checkpoints.</p></div>';
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
            ? '<div class="diary-focus-tags" aria-label="Linked holdings"><span class="diary-muted">Linked holdings</span>' + mentionButtons + '</div>'
            : '';
        const noteTags = (note.user_tags || []).map((tag) => '<span class="diary-badge">' + escapeHtml(tag) + '</span>').join('');
        const commentCount = Array.isArray(note.comments) ? note.comments.length : 0;

        root.innerHTML = '' +
            '<div class="diary-detail-header">' +
            '  <button id="diary-detail-back" type="button" class="mgmt-btn mgmt-btn-secondary diary-detail-back" aria-label="Back to entries">Back</button>' +
            '  <div class="diary-detail-title"><span class="diary-eyebrow">FOCUS SHEET</span><h2 id="diary-detail-ticker">' + escapeHtml(note.title || note.ticker || 'Untitled note') + '</h2><div class="diary-row-badges"><span class="diary-badge">' + (note.is_active ? 'Active thesis' : 'Archived thesis') + '</span>' + (commentCount ? '<span class="diary-badge diary-comments-pill">' + commentCount + ' comments</span>' : '') + '</div></div>' +
            '  <div class="diary-detail-actions"><label class="diary-glass-toggle" title="Toggle active hypothesis" aria-label="Active thesis"><input id="diary-active-toggle" type="checkbox" ' + (note.is_active ? 'checked' : '') + '><span class="diary-glass-slider"></span></label><span class="diary-toggle-status">' + (note.is_active ? 'Active' : 'Inactive') + '</span><button id="diary-delete-note" type="button" class="mgmt-btn mgmt-btn-secondary" aria-label="Delete entry" title="Delete entry">Delete</button></div>' +
            '</div>' +
            '<div class="diary-detail-body">' +
            '  <section class="diary-detail-section"><div class="diary-section-heading"><span class="diary-section-index">01</span><h3>Diary note</h3></div>' +
            '    <textarea id="diary-focus-note" aria-label="Diary note">' + escapeHtml(note.note_text || '') + '</textarea>' +
            '    <div class="diary-focus-tags">' + noteTags + '</div>' + mentionsBlock +
            '    <div class="diary-note-save-row"><button id="diary-save-focus" type="button" class="mgmt-btn mgmt-btn-primary">Save changes</button></div>' +
            '  </section>' +
            '  <section class="diary-detail-section"><div class="diary-section-heading"><span class="diary-section-index">02</span><h3>Thesis</h3><span class="diary-muted">What would change your mind?</span></div>' +
            '  <div class="diary-thesis-grid">' +
            '    <label><span>Why buy</span><textarea id="diary-why-buy" aria-label="Why buy">' + escapeHtml(note.hypothesis.why_buy || '') + '</textarea></label>' +
            '    <label><span>Exit plan</span><textarea id="diary-exit-plan" aria-label="Exit plan">' + escapeHtml(note.hypothesis.exit_plan || '') + '</textarea></label>' +
            '    <label class="diary-risk-field"><span>Risk factors</span><textarea id="diary-risk-factors" aria-label="Risk factors">' + escapeHtml(note.hypothesis.risk_factors || '') + '</textarea></label>' +
            '  </div>' +
            '  <div class="diary-note-save-row"><button id="diary-save-thesis" type="button" class="mgmt-btn mgmt-btn-primary">Save thesis</button></div>' +
            '  </section>' +
            '  <section class="diary-detail-section"><div class="diary-section-heading"><span class="diary-section-index">03</span><h3>Coping thread</h3><span class="diary-muted">' + commentCount + ' notes</span></div>' +
            '    <div id="coping-chat-log" class="coping-chat-container">' + chat + '</div>' +
            '    <div class="diary-chat-compose">' +
            '      <input id="diary-chat-input" type="text" placeholder="Add an update or thought" aria-label="Add comment">' +
            '      <button id="diary-chat-send" type="button" class="mgmt-btn mgmt-btn-secondary" aria-label="Send comment" title="Send comment">Send</button>' +
            '    </div>' +
            '  </section>' +
            '  <section class="diary-detail-section"><div class="diary-section-heading"><span class="diary-section-index">04</span><h3>Checkpoints</h3><span class="diary-muted">' + countUncheckedChecklistItems(note) + ' open</span></div>' +
            '    <div id="diary-checklist">' + checklist + '</div>' +
            '    <div class="diary-check-add-row" style="display:grid;grid-template-columns:minmax(0,1fr) minmax(140px,180px) auto;gap:8px;">' +
            '      <input id="diary-new-check-text" type="text" placeholder="Add a checkpoint" aria-label="New checkpoint">' +
            '      <input id="diary-new-check-date" type="date" aria-label="Checkpoint due date">' +
            '      <button id="diary-add-check" type="button" class="mgmt-btn mgmt-btn-secondary">Add checkpoint</button>' +
            '    </div>' +
            '    <div id="diary-checklist-add-error" style="display:none;color:#fca5a5;font-size:12px;line-height:1.4;"></div>' +
            '  </section>' +
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

        document.querySelectorAll('#diary-save-focus, #diary-save-thesis').forEach((button) => {
            button.addEventListener('click', () => onSaveFocus(note));
        });

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
        const backdrop = document.getElementById('diary-compose-backdrop');
        const btn = document.getElementById('diary-new-note');
        if (box) {
            box.hidden = !state.composeOpen;
            box.setAttribute('aria-hidden', state.composeOpen ? 'false' : 'true');
        }
        if (backdrop) backdrop.hidden = !state.composeOpen;
        if (btn) btn.setAttribute('aria-expanded', state.composeOpen ? 'true' : 'false');
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
        state.mobileDetailOpen = true;
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
        state.mobileDetailOpen = true;
        if (tickerEl) tickerEl.value = '';
        if (textEl) textEl.value = '';
        toggleComposer(false);
        rerender();
    }

    function rerender() {
        const all = state.notes;
        renderTagCloud(all);
        renderNoteCards(all);
        const visibleCount = filteredNotes(all).length;
        const ledgerCount = document.getElementById('diary-ledger-count');
        const split = document.getElementById('diary-split');
        if (ledgerCount) ledgerCount.textContent = visibleCount + ' of ' + all.length + ' entries';
        if (split) split.setAttribute('data-mobile-detail', state.mobileDetailOpen ? 'true' : 'false');
        const overview = document.getElementById('diary-overview');
        if (overview) {
            const activeCount = all.filter((note) => note.is_active).length;
            const openCount = all.reduce((count, note) => count + countUncheckedChecklistItems(note), 0);
            overview.innerHTML = '<div class="diary-overview-item"><strong>' + all.length + '</strong><span>entries</span></div>' +
                '<div class="diary-overview-item"><strong>' + activeCount + '</strong><span>active theses</span></div>' +
                '<div class="diary-overview-item"><strong>' + openCount + '</strong><span>open checkpoints</span></div>';
        }
        const visibleNotes = sortForLedger(filteredNotes(all));
        if (visibleNotes.length && !visibleNotes.some((note) => String(note.note_id) === String(state.selectedNoteId))) {
            state.selectedNoteId = visibleNotes[0].note_id;
        }
        const selected = findSelectedNote();
        if (selected) state.selectedNoteId = selected.note_id;
        renderDetail(selected);
    }

    async function init() {
        const root = document.getElementById('diary-app-root');
        if (!root) return;
        if (state.loaded) return;
        state.loaded = true;
        root.setAttribute('aria-busy', 'true');

        ensureStyles();
        mountShell();

        const notes = await fetchNotes();
        state.notes = notes;
        root.setAttribute('aria-busy', 'false');
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
        const mobileAddBtn = document.getElementById('diary-mobile-new-note');
        if (mobileAddBtn) mobileAddBtn.addEventListener('click', () => toggleComposer(true));

        const closeComposerBtn = document.getElementById('diary-compose-close');
        if (closeComposerBtn) closeComposerBtn.addEventListener('click', () => toggleComposer(false));
        const composeBackdrop = document.getElementById('diary-compose-backdrop');
        if (composeBackdrop) composeBackdrop.addEventListener('click', () => toggleComposer(false));
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && state.composeOpen) toggleComposer(false);
        });
        root.addEventListener('click', (event) => {
            if (!event.target.closest('#diary-detail-back')) return;
            state.mobileDetailOpen = false;
            rerender();
        });

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
