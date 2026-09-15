function drawTopographicalLake(canvasId, drawdownPoints) {
    const container = document.getElementById(canvasId);
    if (!container) return;

    const points = Array.isArray(drawdownPoints) && drawdownPoints.length ? drawdownPoints : [0, -2, -5, -8, -12, -9, -6, -3, 0];
    const width = 260;
    const height = 150;
    const leftPad = 10;
    const rightPad = 10;
    const topPad = 18;
    const bottomPad = 22;
    const maxValue = 0;
    const minValue = Math.min(...points, 0);
    const span = Math.abs(minValue - maxValue) || 1;
    const gradientId = `lakeGradient-${Math.random().toString(16).slice(2)}`;

    const lakePath = points.map((point, idx) => {
        const x = leftPad + (idx / (points.length - 1)) * (width - leftPad - rightPad);
        const y = topPad + (Math.abs(point - maxValue) / span) * (height - topPad - bottomPad);
        return `${idx === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');

    const bucketBottom = `L ${width - rightPad} ${height - bottomPad} L ${leftPad} ${height - bottomPad} Z`;
    const deepest = Math.min(...points);
    const deepestIndex = points.indexOf(deepest);
    const deepestX = leftPad + (deepestIndex / (points.length - 1)) * (width - leftPad - rightPad);
    const deepestY = topPad + (Math.abs(deepest - maxValue) / span) * (height - topPad - bottomPad);

    let widestStart = 0;
    let widestLen = 0;
    let currentStart = 0;
    let currentLen = 0;
    for (let i = 0; i < points.length; i += 1) {
        if (points[i] < 0) {
            if (currentLen === 0) currentStart = i;
            currentLen += 1;
        } else {
            if (currentLen > widestLen) {
                widestLen = currentLen;
                widestStart = currentStart;
            }
            currentLen = 0;
        }
    }
    if (currentLen > widestLen) {
        widestLen = currentLen;
        widestStart = currentStart;
    }

    const widestLeftX = leftPad + (widestStart / (points.length - 1)) * (width - leftPad - rightPad);
    const widestRightX = leftPad + ((widestStart + widestLen - 1) / (points.length - 1)) * (width - leftPad - rightPad);
    const bracketY = height - bottomPad + 8;

    container.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Yearly drawdown lake visualization" style="width:100%;height:100%;display:block;">
            <defs>
                <linearGradient id="${gradientId}" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stop-color="rgba(255,255,255,0)" />
                    <stop offset="16%" stop-color="rgba(103,232,249,0.12)" />
                    <stop offset="48%" stop-color="rgba(34,211,238,0.28)" />
                    <stop offset="100%" stop-color="rgba(56,189,248,0.52)" />
                </linearGradient>
                <filter id="lakeGlow-${gradientId}" x="-30%" y="-30%" width="160%" height="180%">
                    <feGaussianBlur stdDeviation="4.8" result="blur"/>
                    <feColorMatrix in="blur" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.8 0" result="glow"/>
                    <feMerge>
                        <feMergeNode in="glow"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
                <linearGradient id="lakeStroke-${gradientId}" x1="0" x2="1" y1="0" y2="0">
                    <stop offset="0%" stop-color="rgba(103,232,249,0.72)" />
                    <stop offset="50%" stop-color="rgba(164,243,255,0.98)" />
                    <stop offset="100%" stop-color="rgba(34,211,238,0.9)" />
                </linearGradient>
            </defs>
            <style>
                .lake-sheen { animation: lakeFloat 4.8s ease-in-out infinite; transform-origin: center; }
                @keyframes lakeFloat { 0%, 100% { opacity: 0.9; transform: translateY(0px); } 50% { opacity: 1; transform: translateY(-2px); } }
            </style>
            <line x1="${leftPad}" y1="${topPad}" x2="${width - rightPad}" y2="${topPad}" stroke="rgba(255,255,255,0.2)" stroke-width="1.2"/>
            <path d="${lakePath} ${bucketBottom}" class="lake-sheen" fill="url(#${gradientId})" filter="url(#lakeGlow-${gradientId})" opacity="0.95"></path>
            <path d="${lakePath}" class="lake-sheen" fill="none" stroke="url(#lakeStroke-${gradientId})" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"></path>
            <line x1="${deepestX}" y1="${deepestY}" x2="${deepestX}" y2="${deepestY + 16}" stroke="rgba(125,211,252,0.9)" stroke-dasharray="4 4" stroke-width="1.2"></line>
            <circle cx="${deepestX}" cy="${deepestY}" r="4" fill="rgba(103,232,249,0.95)" stroke="rgba(255,255,255,0.7)" stroke-width="1"></circle>
            <text x="${deepestX + 8}" y="${deepestY - 10}" fill="#dbeafe" font-size="11" font-weight="700">Deepest Lake</text>
            <text x="${deepestX + 8}" y="${deepestY + 10}" fill="#dbeafe" font-size="10">${deepest.toFixed(0)}%</text>
            <line x1="${widestLeftX}" y1="${bracketY}" x2="${widestRightX}" y2="${bracketY}" stroke="rgba(255,255,255,0.35)" stroke-width="1.5"></line>
            <line x1="${widestLeftX}" y1="${bracketY - 9}" x2="${widestLeftX}" y2="${bracketY + 9}" stroke="rgba(255,255,255,0.35)" stroke-width="1.5"></line>
            <line x1="${widestRightX}" y1="${bracketY - 9}" x2="${widestRightX}" y2="${bracketY + 9}" stroke="rgba(255,255,255,0.35)" stroke-width="1.5"></line>
            <rect x="${widestLeftX + 2}" y="${bracketY - 22}" width="${Math.max(widestRightX - widestLeftX - 4, 50)}" height="16" rx="8" fill="rgba(15,23,42,0.44)" stroke="rgba(255,255,255,0.12)"></rect>
            <text x="${(widestLeftX + widestRightX) / 2}" y="${bracketY - 9}" fill="#e2e8f0" font-size="9" text-anchor="middle">Widest Lake ${widestLen}d</text>
        </svg>
    `;
}

function drawCarryAndDragSVG(containerId, carryName, carryPct, dragName, dragPct) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const safeCarry = Number.isFinite(Number(carryPct)) ? Number(carryPct) : 12.4;
    const safeDrag = Number.isFinite(Number(dragPct)) ? Number(dragPct) : -8.1;
    const carryAbs = Math.max(Math.abs(safeCarry), 1);
    const dragAbs = Math.max(Math.abs(safeDrag), 1);
    const maxAbs = Math.max(carryAbs, dragAbs, 1);
    const centerX = 160;
    const leftBase = 40;
    const rightBase = 280;
    const carryWidth = (Math.abs(safeCarry) / maxAbs) * 100;
    const dragWidth = (Math.abs(safeDrag) / maxAbs) * 100;
    const carryEnd = centerX + (carryWidth / 100) * (rightBase - centerX);
    const dragEnd = centerX - (dragWidth / 100) * (centerX - leftBase);
    const carryLabelX = carryEnd + 8;
    const dragLabelX = dragEnd - 8;

    container.innerHTML = `
        <svg viewBox="0 0 320 74" preserveAspectRatio="none" role="img" aria-label="Carry and drag performance comparison" style="width:100%;height:100%;display:block;">
            <defs>
                <filter id="carryGlow" x="-30%" y="-30%" width="160%" height="200%">
                    <feGaussianBlur stdDeviation="2.5" result="blur"/>
                    <feMerge>
                        <feMergeNode in="blur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            <style>
                .carry-bar { animation: glideIn 1s ease-out both; }
                @keyframes glideIn { from { opacity: 0; transform: scaleX(0.85); transform-origin: center; } to { opacity: 1; transform: scaleX(1); } }
            </style>
            <line x1="160" y1="32" x2="160" y2="58" stroke="rgba(255,255,255,0.28)" stroke-width="1.4"/>
            <line x1="${leftBase}" y1="32" x2="${rightBase}" y2="32" stroke="rgba(255,255,255,0.12)" stroke-width="10" stroke-linecap="round"/>
            <line class="carry-bar" x1="${centerX}" y1="32" x2="${carryEnd}" y2="32" stroke="#10B981" stroke-width="10" stroke-linecap="round" filter="url(#carryGlow)"/>
            <line class="carry-bar" x1="${centerX}" y1="32" x2="${dragEnd}" y2="32" stroke="#EF4444" stroke-width="10" stroke-linecap="round" filter="url(#carryGlow)"/>
            <circle cx="${centerX}" cy="32" r="6" fill="rgba(148,163,184,0.9)"/>
            <text x="${Math.min(carryLabelX, 300)}" y="25" fill="#d1fae5" font-size="11" font-weight="700">${carryName}</text>
            <text x="${Math.min(carryLabelX, 300)}" y="43" fill="#d1fae5" font-size="10">+${Number(safeCarry).toFixed(1)}%</text>
            <text x="${Math.max(dragLabelX, 20)}" y="25" fill="#fecaca" font-size="11" font-weight="700" text-anchor="end">${dragName}</text>
            <text x="${Math.max(dragLabelX, 20)}" y="43" fill="#fecaca" font-size="10" text-anchor="end">${Number(safeDrag).toFixed(1)}%</text>
        </svg>
    `;
}

function drawRadialGoal(containerId, currentDeposited, targetGoal) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const current = Number(currentDeposited) || 0;
    const target = Number(targetGoal) || 1;
    const progress = Math.min(Math.max(current / target, 0), 1);
    const size = 120;
    const radius = 44;
    const circumference = 2 * Math.PI * radius;
    const strokeOffset = circumference * (1 - progress);
    const percent = Math.round((progress || 0) * 100);

    container.innerHTML = `
        <svg viewBox="0 0 ${size} ${size}" role="img" aria-label="Monthly deposit goal gauge" style="width:100%;height:100%;display:block;">
            <defs>
                <linearGradient id="goalGradient" x1="0" x2="1" y1="0" y2="1">
                    <stop offset="0%" stop-color="#A855F7" />
                    <stop offset="50%" stop-color="#8B5CF6" />
                    <stop offset="100%" stop-color="#10B981" />
                </linearGradient>
                <filter id="goalGlow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="2.4" result="blur"/>
                    <feMerge>
                        <feMergeNode in="blur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            <circle cx="60" cy="60" r="${radius}" fill="none" stroke="rgba(148,163,184,0.18)" stroke-width="12"/>
            <circle class="goal-ring-arc" cx="60" cy="60" r="${radius}" fill="none" stroke="url(#goalGradient)" stroke-width="12" stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${strokeOffset}" transform="rotate(-90 60 60)" style="transition: stroke-dashoffset 1.6s cubic-bezier(0.2, 0.8, 0.2, 1); filter: url(#goalGlow);"/>
            <circle cx="60" cy="60" r="${radius - 3}" fill="rgba(15,23,42,0.18)" stroke="rgba(255,255,255,0.08)" stroke-width="0.8"/>
            <text x="60" y="58" text-anchor="middle" fill="#f8fafc" font-size="20" font-weight="800">${percent}%</text>
            <text x="60" y="76" text-anchor="middle" fill="rgba(191,219,254,0.8)" font-size="8.5">PLN deposited</text>
        </svg>
    `;
}
