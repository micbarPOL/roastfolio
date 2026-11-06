(function () {
    'use strict';
    let historyRows = null;
    let latestDrawdown = null;

    function levels(drawdown, low) {
        if (!Number.isFinite(drawdown)) return { state: 'pending', zone: 'pending' };
        const value = Math.min(0, drawdown);
        const deepest = Math.max(15, -value, Number.isFinite(low) ? -low : 0);
        const maximum = Math.ceil(deepest / 15) * 15;
        const step = maximum / 3;
        const position = amount => 180 - amount * 270 / maximum;
        return {
            value,
            state: value === 0 ? 'ashore' : value >= -2 ? 'snorkeling' : 'diving',
            zone: value === 0 ? 'relax' : value >= -5 ? 'explore' : 'danger',
            nowY: position(value),
            lowY: Number.isFinite(low) ? position(Math.min(0, low)) : null,
            ticks: [step, step * 2, maximum].map(amount => ({ value: -amount, position: position(-amount) }))
        };
    }

    function recentLow(rows, drawdown, now = new Date()) {
        if (!Array.isArray(rows)) return null;
        const today = now.toISOString().slice(0, 10);
        const cutoff = new Date(`${today}T00:00:00Z`);
        cutoff.setUTCDate(cutoff.getUTCDate() - 29);
        const firstDay = cutoff.toISOString().slice(0, 10);
        const snapshots = rows.filter(row => row && /^\d{4}-\d{2}-\d{2}$/.test(row.date)
            && row.date <= today && Number.isFinite(row.value) && row.value >= 0)
            .slice().sort((left, right) => left.date.localeCompare(right.date));
        let peak = 0;
        let low = null;
        for (const row of snapshots) {
            peak = Math.max(peak, row.value);
            if (row.date >= firstDay && peak > 0) {
                const value = (row.value / peak - 1) * 100;
                low = low === null ? value : Math.min(low, value);
            }
        }
        return low === null ? null : Math.min(low, Number.isFinite(drawdown) ? drawdown : 0, 0);
    }

    function render(drawdown) {
        latestDrawdown = drawdown;
        const ocean = document.getElementById('dash-ath-lake');
        if (!ocean) return;
        const low = recentLow(historyRows, drawdown);
        const model = levels(drawdown, low);
        const pending = model.state === 'pending';
        const find = name => ocean.querySelector(`#ath-ocean-${name}`);
        const format = value => `${value < 0 ? '\u2212' : ''}${Math.abs(value).toFixed(2)}%`;
        ocean.dataset.state = model.state;
        ocean.dataset.zone = model.zone;
        ocean.dataset.criticalDrawdown = String(!pending && model.value < -12);
        ocean.querySelector('.ath-ocean-scene').toggleAttribute('hidden', pending);
        ocean.querySelector('.ath-ocean-pending').hidden = !pending;
        ocean.querySelector('[data-ocean-zone]').textContent = {
            pending: 'Awaiting ATH', relax: 'Relax.', explore: 'Explore.', danger: 'Danger.'
        }[model.zone];
        ocean.querySelector('[data-ocean-low]').textContent = !pending && low !== null ? format(low) : '\u2014';
        ocean.querySelector('[data-ocean-low]').title = low === null ? 'No recent snapshot history available' : '';
        if (pending) return;
        find('expedition-diver').setAttribute('transform', `translate(180 ${model.nowY})`);
        find('drawdown-marker').setAttribute('transform', `translate(0 ${model.nowY})`);
        find('depth-readout').textContent = format(model.value);
        const tickLabels = ocean.querySelectorAll('.scale-label');
        model.ticks.forEach((tick, index) => {
            tickLabels[index + 1].textContent = `\u2212${Math.abs(tick.value)}%`;
        });
        const lowMarker = find('low-marker');
        lowMarker.toggleAttribute('hidden', model.lowY === null);
        if (model.lowY !== null) {
            lowMarker.setAttribute('transform', `translate(0 ${model.lowY})`);
            find('low-label').textContent = `30D LOW \u00b7 ${format(low)}`;
        }
        find('expedition-description').textContent = `Drawdown ${format(model.value)}. ${model.zone} zone. `
            + (low === null ? 'Recent snapshot history unavailable. ' : `30-day low ${format(low)}. `)
            + 'The diamond marks the current drawdown on a linear scale. At or above the recorded ATH: beach. '
            + 'Down to 2% below ATH: snorkeling. Below 2%: scuba diving. Danger below 5%. '
            + 'Small fish swim in the shallows; sharks patrol above a wreck. Scenery is a metaphor, not a risk rating.';
    }

    function setHistory(rows) {
        historyRows = Array.isArray(rows) ? rows : null;
        render(latestDrawdown);
    }

    window.AthOcean = { levels, recentLow, render, setHistory };
}());