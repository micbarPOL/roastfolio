/* engagement-strip.js — Dashboard engagement strip
 *
 * Renders a horizontal scrollable row of achievement pills at the top of the
 * dashboard tab. Every pill links to achievements.html.
 *
 * Data source priority:
 *   1. window.XPEngine.getResult()  — real computed data (preferred)
 *   2. FALLBACK_DATA                — static mock (shown until data loads)
 *
 * Re-renders automatically on 'xpEngineReady' events.
 */
(function () {
    'use strict';

    // ── Mock data (mirrors achievements.js) ───────────────────
    var DATA = {
        level: {
            name:      'Contributor',
            xp:        1240,
            nextLevel: 'Operator',
            nextAt:    2500,
            prevAt:    1000,
        },
        streaks: [
            {
                id: 'contribution', label: 'Deposits',
                value: 7, unit: 'mo',
                color: '#27ae60',
                bg:    'rgba(39,174,96,0.13)',
                bord:  'rgba(39,174,96,0.32)',
                icon:  'up',
            },
            {
                id: 'checkin', label: 'Check-ins',
                value: 34, unit: 'd',
                color: '#2b88cf',
                bg:    'rgba(43,136,207,0.13)',
                bord:  'rgba(43,136,207,0.32)',
                icon:  'eye',
            },
            {
                id: 'withdrawal', label: 'No withdraw',
                value: 14, unit: 'mo',
                color: '#8a4fff',
                bg:    'rgba(138,79,255,0.13)',
                bord:  'rgba(138,79,255,0.32)',
                icon:  'lock',
            },
            {
                id: 'goal', label: 'Goal',
                value: 4, unit: 'mo',
                color: '#d4ac2a',
                bg:    'rgba(212,172,42,0.13)',
                bord:  'rgba(212,172,42,0.32)',
                icon:  'target',
            },
            {
                id: 'green', label: 'Green months',
                value: 3, unit: 'mo',
                color: '#4caf82',
                bg:    'rgba(76,175,130,0.13)',
                bord:  'rgba(76,175,130,0.32)',
                icon:  'trending',
            },
        ],
        recentBadge: {
            name:  'Committed',
            tier:  'bronze',
            color: '#c8873a',
            bg:    'rgba(200,135,58,0.13)',
            bord:  'rgba(200,135,58,0.32)',
        },
    };

    // ── SVG icon set ──────────────────────────────────────────
    var IC = {
        up:      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>',
        eye:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
        lock:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
        target:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
        trending:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
        award:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>',
        zap:     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
        chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>',
    };

    // ── Helpers ───────────────────────────────────────────────
    function fmtNum(n) {
        return Number(n).toLocaleString('pl-PL');
    }

    function xpPct() {
        var d = DATA.level;
        return Math.round(((d.xp - d.prevAt) / (d.nextAt - d.prevAt)) * 100);
    }

    function pill(href, cls, inlineStyle, ariaLabel, inner) {
        return '<a href="' + href + '" class="eng-pill ' + cls + '"' +
               (inlineStyle ? ' style="' + inlineStyle + '"' : '') +
               ' aria-label="' + ariaLabel + '">' + inner + '</a>';
    }

    function pillLabel(strong, sub) {
        return '<span class="eng-pill__label">' +
               '<span class="eng-pill__strong">' + strong + '</span>' +
               '<span class="eng-pill__sub">' + sub + '</span>' +
               '</span>';
    }

    // ── Static fallback (shown until XPEngine produces real data) ─
    var FALLBACK_DATA = DATA;

    // ── Resolve live data from XPEngine or fallback ───────────
    function resolveData() {
        var engineResult = window.XPEngine && window.XPEngine.getResult();
        if (engineResult && engineResult.hasRealData) {
            // Map engine result to strip format
            var ex = engineResult.xp;
            var pct = Math.round(((ex.current - ex.prevAt) / (ex.nextAt - ex.prevAt)) * 100);
            var streaks = engineResult.streaks.map(function(s, i) {
                return {
                    id:    s.id,
                    label: s.name,
                    value: s.value,
                    unit:  s.unit,
                    color: s.color,
                    bg:    hexToBg(s.color),
                    bord:  hexToBord(s.color),
                    icon:  ['up', 'eye', 'lock', 'target', 'trending'][i] || 'up',
                };
            });
            // Most recently unlocked badge (celebrate=true first, else last unlocked)
            var unlockedBadges = engineResult.badges.filter(function(b) { return b.unlocked; });
            var recentBadge = unlockedBadges.find(function(b) { return b.celebrate; }) || unlockedBadges[unlockedBadges.length - 1];
            var rb = recentBadge
                ? { name: recentBadge.name, tier: recentBadge.tier, color: TIER_COLORS[recentBadge.tier] || '#6a8ba8', bg: hexToBg(TIER_COLORS[recentBadge.tier] || '#6a8ba8'), bord: hexToBord(TIER_COLORS[recentBadge.tier] || '#6a8ba8') }
                : null;
            return {
                level: { name: ex.level, xp: ex.current, nextLevel: ex.nextLevel, nextAt: ex.nextAt, prevAt: ex.prevAt },
                streaks: streaks,
                recentBadge: rb,
            };
        }
        return FALLBACK_DATA;
    }

    var TIER_COLORS = { seed: '#8aa8c8', bronze: '#c8873a', silver: '#a8c8e8', gold: '#d4ac2a', diamond: '#2bcfcf' };

    function hexToBg(hex) {
        var rgb = hexToRgb(hex);
        return rgb ? 'rgba(' + rgb + ',0.13)' : 'rgba(43,136,207,0.13)';
    }
    function hexToBord(hex) {
        var rgb = hexToRgb(hex);
        return rgb ? 'rgba(' + rgb + ',0.32)' : 'rgba(43,136,207,0.32)';
    }
    function hexToRgb(hex) {
        var m = String(hex || '').match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
        return m ? parseInt(m[1], 16) + ',' + parseInt(m[2], 16) + ',' + parseInt(m[3], 16) : null;
    }

    // ── Build strip HTML ──────────────────────────────────────
    function buildStrip() {
        var d   = resolveData();
        var ex  = d.level;
        var pills = [];
        var pct   = Math.round(((ex.xp - ex.prevAt) / (ex.nextAt - ex.prevAt)) * 100);

        // 1 ─ Level pill (always first)
        pills.push(pill(
            'achievements.html',
            'eng-pill--level',
            '',
            'Level: ' + ex.name + ' · ' + fmtNum(ex.xp) + ' XP',
            IC.zap + pillLabel(ex.name, fmtNum(ex.xp) + '\u202fXP · ' + pct + '%') +
            '<span class="eng-pill__xp-track" aria-hidden="true">' +
            '<span class="eng-pill__xp-fill" style="width:' + pct + '%"></span>' +
            '</span>'
        ));

        // 2 ─ Streak pills
        d.streaks.forEach(function (s) {
            pills.push(pill(
                'achievements.html',
                'eng-pill--streak',
                'color:' + s.color + ';background:' + s.bg + ';border-color:' + s.bord,
                s.label + ' streak: ' + s.value + '\u202f' + s.unit,
                IC[s.icon] + pillLabel(s.value + '\u2009' + s.unit, s.label)
            ));
        });

        // 3 ─ Most recent badge
        var b = d.recentBadge;
        if (b) {
            var tierCap = b.tier.charAt(0).toUpperCase() + b.tier.slice(1);
            pills.push(pill(
                'achievements.html',
                'eng-pill--badge',
                'color:' + b.color + ';background:' + b.bg + ';border-color:' + b.bord,
                'Badge: ' + b.name + ' · ' + tierCap,
                IC.award + pillLabel(b.name, tierCap)
            ));
        }

        // 4 ─ "All achievements" tail pill
        pills.push(pill(
            'achievements.html',
            'eng-pill--all',
            '',
            'View all achievements',
            '<span>All achievements</span>' + IC.chevron
        ));

        return '<div class="eng-strip" role="list">' + pills.join('') + '</div>';
    }

    // ── Render ────────────────────────────────────────────────
    function render() {
        var wrap = document.getElementById('engagement-strip');
        if (!wrap) return;

        wrap.innerHTML = buildStrip();

        // Slide-in after paint (only first time)
        if (!wrap.classList.contains('is-visible')) {
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    wrap.classList.add('is-visible');
                });
            });
        }
    }

    // Re-render when XPEngine produces real data
    window.addEventListener('xpEngineReady', function() { render(); });

    // ── Public API ────────────────────────────────────────────
    window.EngagementStrip = { init: render };

    // Auto-init
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', render);
    } else {
        render();
    }
}());
