# Roastfolio 2026 Design System Architecture
**Version**: 9.1.0 (v9.0 Adaptive UX, Motion, Glassmorphic Islands 2.0, Empty States & LLM Code Spec + Decision Log, Screen Registry & Consistency Contract)  
**Target Architecture**: Single-Page App (SPA) / PWA / Web-First Fintech  
**Design Philosophy**: Dark-First & Light-Adaptive, Containerless Tonal Elevation, High-Density Data Precision, Adaptive Hybrid UX, Sarcastic Fintech Personality.

---

## 1. System Overview & Core Philosophy

The Roastfolio 2026 Design System is built for AI-driven development and precision engineering. It bridges high-end financial analytics (Revolut, Bloomberg, Linear) with behavioral gamification and dark humor.

### 1.1 Key Architectural Principles:
1. **Adaptive Hybrid UX Architecture**: One codebase, one set of tokens, and unified application state, but **context-adapted layout patterns** for Desktop (multi-column, high density, mouse/keyboard) and Mobile (1-column stack, thumb-zone bottom navigation, touch targets ≥ 44px).
2. **Progressive Disclosure (3-Tier Information Flow)**: Information is revealed on demand across 3 layers:
   - *Tier 1 (Hero State)*: At-a-glance status answering "How am I doing today?" in < 2 seconds.
   - *Tier 2 (In-Place Context)*: Expanding cards in grid or multi-region benchmark matrix on demand without leaving context.
   - *Tier 3 (Deep Action Flow)*: Task-focused sheets (Bottom Sheets / Modals) for trade execution, sprawozdania finansowe, or Coping Diary audits.
3. **Containerless / Frameless Tonal Surfaces**: Depth is established through **luminance steps** (stepping background fill brightness up or down by 4%–8%) and subtle spacing rather than hard 1px outline boxes.
4. **Deterministic Token Mapping**: All visual parameters are mapped to CSS Custom Properties (`var(--...)`). Hardcoded hex colors or inline styles are strictly prohibited.
5. **4-Mode Responsive Matrix**: Every component is specified across four operational modes:
   - `desktop-dark` (Default baseline context)
   - `desktop-light` (Clean, high-contrast, professional)
   - `mobile-dark` (Thumb-optimized, deep OLED slate)
   - `mobile-light` (iOS/Android native-feel light theme)
6. **Data-Density & Tabular Rigor**: Financial figures utilize `font-variant-numeric: tabular-nums` to ensure strict vertical alignment during live price updates.

---

## 1.2 Adaptive UX Architecture Specification

Roastfolio uses an **Adaptive Hybrid Model**. Rather than building two disconnected apps or blindly squeezing desktop layouts onto mobile screens, components adapt their presentation and interaction pattern based on viewport and input capability.

```
                                [ ONE DESIGN SYSTEM / ROASTFOLIO 2026 ]
                                (Shared Tokens, Colors, Typography, Logic)
                                                     │
                         ┌───────────────────────────┴───────────────────────────┐
                         ▼                                                       ▼
                [ DESKTOP CONTEXT ]                                     [ MOBILE CONTEXT ]
   - Ergonomics: Mouse + Keyboard                         - Ergonomics: One Thumb (Thumb Zone)
   - Layout: Wide 2-3 column grid                         - Layout: VERTICAL (1-column stack)
   - Navigation: Collapsible Sidebar (240px/64px)         - Navigation: Fixed Bottom Tabs + Side Drawer
   - Display: Data tables with filters & sorting          - Display: Cards with touch targets >=44px
   - Interaction: In-Place Card Expansion / Hover         - Interaction: Bottom Sheets / Swipe Gestures + Haptics
```

### Contextual Rules Table:

| UI Dimension | Desktop Context (≥ 768px) | Mobile Context (< 768px) |
| :--- | :--- | :--- |
| **Grid & Layout** | Multi-column grid (2–3 columns side-by-side) | Single column vertical stack (`100%` width) |
| **Primary Navigation** | Collapsible Side Navigation Panel (`240px` expanded / `64px` collapsed icon-rail) + Top Action Bar | Fixed Bottom Tab Bar (`64px` in Thumb Zone) + Slide-Over Side Drawer (`280px` max-width) |
| **Secondary Navigation** | Horizontal Segmented Controls / Top Sub-tabs | Full-width Segmented Controls / Sliding Pill Strips |
| **Data Lists** | High-density data tables (`<thead>`, `<tr>`, `<td>`) with sortable column headers | Card-stack layout (`.holding-card`) with allocation progress bars and large touch targets |
| **Task & Form Entry** | Centered Glassmorphic Modal (`max-width: 540px`) or In-Place Expansion | Bottom Sheet (`max-height: 92dvh`) sliding from screen bottom with drag handle |
| **Click/Touch Target** | Minimum `32px × 32px` | Minimum `44px × 44px` (iOS HIG / Android Accessibility Standard) |
| **Hover & Gestures** | Mouse `:hover` elevation & glow effects enabled (`@media (hover: hover)`) | Touch-safe active states (`:active`), native momentum scrolling, and horizontal snap sliders |

---

## 2. Design Tokens & CSS Variable Registry

```css
:root {
  /* ==========================================================================
     1. DESKTOP & MOBILE DARK MODE (Default System State)
     ========================================================================== */
  --bg-canvas: #090f18;          /* Base app background (Roastfolio Dark Slate) */
  --bg-surface-1: #0e1a2a;       /* Secondary background / cards */
  --bg-surface-2: #132032;       /* Elevated surfaces, hover states, chips */
  --bg-surface-3: #1a2c42;       /* Modals, popups, active states */
  --bg-glass: rgba(14, 26, 42, 0.75); /* Glassmorphism backdrop fill */
  
  /* Text Hierarchy (Dark) */
  --text-primary: #e8f0f8;     /* High-contrast headings & financial figures */
  --text-secondary: #a8c0d8;   /* Field labels, captions, metadata */
  --text-muted: #6a8ba8;       /* Disabled text, inactive placeholders */
  --text-inverse: #090f18;     /* Dark text on bright accent buttons */

  /* Brand Accents (Dark) */
  --accent-primary: #2b88cf;   /* Core brand electric blue */
  --accent-hover: #36a3f0;     /* Hover state for primary actions */
  --accent-glow: rgba(43, 136, 207, 0.25);
  --color-bottle-green: #0d5c3a; /* Deep bottle green for Candlestick Logo Body */

  /* Semantic Financial Colors (Dark - Muzli 2026 Vivid Boost) */
  --color-success: #10b981;    /* Emerald green: Profit / Buy / True */
  --color-success-bg: rgba(16, 185, 129, 0.12);
  --color-danger: #ef4444;     /* Vivid coral/red: Loss / Sell / Anchor */
  --color-danger-bg: rgba(239, 68, 68, 0.12);
  --color-warning: #f59e0b;    /* Amber: Caution / Overdue / #Coping tag */
  --color-warning-bg: rgba(245, 158, 11, 0.12);
  --color-purple: #a855f7;     /* Gamification / Coping Diary / Hypotheses */
  --color-purple-bg: rgba(168, 85, 247, 0.12);

  /* Recap poster (theme-independent, D-047): pastel mood paper with dark ink */
  --recap-up: #d0f5b0;         /* Month up: lime paper */
  --recap-down: #f2c5b0;       /* Month down: peach paper */
  --recap-flat: #d4caf2;       /* Flat or no data: lavender paper */
  --recap-ink: #1c2c22;        /* Poster text and line work */
  --recap-ink-soft: #344634;   /* Poster captions, 6.4:1 or better on every paper */

  /* Borders & Shadows (Dark) */
  --border-subtle: rgba(74, 159, 212, 0.12);
  --border-strong: rgba(74, 159, 212, 0.25);
  --border-glow: rgba(168, 85, 247, 0.3);
  --shadow-sm: 0 1px 4px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.6);
  --shadow-accent: 0 8px 24px rgba(43, 136, 207, 0.3);

  /* Layout & Glass Filter */
  --blur-glass: blur(12px);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 24px;

  /* Typography, Spacing, Layout & Motion (theme-independent) */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --fs-xs: 12px;
  --fs-sm: 13px;
  --fs-md: 15px;
  --fs-lg: 18px;
  --fs-xl: 24px;
  --fs-hero: clamp(2rem, 5vw, 3rem);
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --sidebar-w: 240px;
  --sidebar-w-collapsed: 64px;
  --bottom-tabs-h: 64px;
  --touch-min: 44px;
  --dur-fast: 150ms;
  --dur-base: 200ms;
  --dur-slow: 250ms;
  --ease-enter: cubic-bezier(0.32, 0.72, 0, 1);
  --ease-hover: cubic-bezier(0.2, 0, 0, 1);
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* ==========================================================================
   2. LIGHT MODE OVERRIDES (:root[data-theme="light"], same switch as the app)
   ========================================================================== */
:root[data-theme="light"] {
  --bg-canvas: #f8fafc;          /* Clean light gray canvas */
  --bg-surface-1: #ffffff;       /* Pure white card container */
  --bg-surface-2: #f1f5f9;       /* Elevated light gray fill */
  --bg-surface-3: #e2e8f0;       /* Active / hover surface */
  --bg-glass: rgba(255, 255, 255, 0.85);

  /* Text Hierarchy (Light) */
  --text-primary: #0f172a;     /* Deep slate for WCAG AA readability */
  --text-secondary: #475569;   /* Muted dark slate for captions */
  --text-muted: #5b6b82;       /* Subtle placeholders, 4.95:1 or better on surfaces 0-2 */
  --text-inverse: #ffffff;

  /* Brand Accents (Light) */
  --accent-primary: #1d72b8;   /* Deepened electric blue for 4.5:1 contrast */
  --accent-hover: #155a92;
  --accent-glow: rgba(29, 114, 184, 0.15);
  --color-bottle-green: #064e3b;

  /* Semantic Financial Colors (Light) */
  --color-success: #047857;    /* Deeper emerald green, 5.24:1 on canvas */
  --color-success-bg: rgba(4, 120, 87, 0.1);
  --color-danger: #dc2626;     /* Deep crimson red */
  --color-danger-bg: rgba(220, 38, 38, 0.1);
  --color-warning: #b45309;    /* Darker amber, 4.80:1 on canvas */
  --color-warning-bg: rgba(180, 83, 9, 0.1);
  --color-purple: #9333ea;     /* Vibrant purple */
  --color-purple-bg: rgba(147, 51, 234, 0.1);

  /* Borders & Shadows (Light) */
  --border-subtle: rgba(15, 23, 42, 0.08);
  --border-strong: rgba(15, 23, 42, 0.16);
  --border-glow: rgba(147, 51, 234, 0.25);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.12);
  --shadow-accent: 0 6px 20px rgba(29, 114, 184, 0.2);
}
```

---

## 3. Navigation Consistency & Rationale Framework

To prevent visual clutter, Roastfolio establishes strict functional rules for every navigation paradigm:

| Navigation Type | UX Purpose & Justification | Desktop Implementation | Mobile Implementation |
| :--- | :--- | :--- | :--- |
| **Primary App Navigation** | Top-level context switching between major screens (Dashboard, Wallets, Transactions, History, Analysis, Coping Diary). | Collapsible Side Navigation Panel (`240px` expanded / `64px` collapsed). Toggleable via `⌘B` or toggle button. Active item gets elevated fill + electric blue left accent bar. | Fixed bottom tab bar (4-5 key icons) in primary Thumb Zone + Slide-Over Side Drawer for secondary modules and settings. |
| **Tabs (Segmented Control)** | Toggling between mutually exclusive sub-views of equal hierarchy within the same screen (e.g., Active Holdings vs The Cemetery). | Full pill strip (`var(--bg-surface-2)`), active tab gets elevated background and accent text. | Full-width segmented pill control, minimum tap height `40px`, sliding pill animation. |
| **Horizontal Touch Sliders / Swiping** | Micro-content discovery without sacrificing vertical scroll real estate (e.g., Streak pills, Daily Mover cards). | Mouse drag / wheel horizontal scroll with subtle right-edge fade mask (`mask-image`). | Native CSS scroll snap (`scroll-snap-type: x mandatory`), touch momentum scrolling enabled. |
| **Carousels** | Sequential story-driven slides where cards must be reviewed step-by-step (e.g., Monthly Recaps / Memory Lane). | Multi-card grid side-by-side or arrow-navigated slide card deck with pagination dots. | 1-card full view with horizontal swipe, page dots at bottom, snap-center alignment. |
| **In-Place Card Expansion (Accordion Grid)** | Secondary detail inspection without leaving dashboard context (e.g., Wallet details, Daily Movers). | Card expands vertically in grid, revealing mini-chart, cash balance, and quick action buttons. | Card expands vertically in stack, pushing lower cards down smoothly. |
| **Bottom Sheets (Slide-up Overlays)** | Temporary task flows originating from touch interactions (e.g., New Transaction form, Holding actions). | Centered glassmorphic modal overlay (`max-width: 540px`) with dim backdrop blur. | Full-width slide-up drawer from bottom (`max-height: 92dvh`), top drag handle, swipe-down dismiss. |
| **Timeline Picker** | Chronological historical navigation for archived reports (e.g. Memory Lane recaps). | Year badge + horizontal month pill strip with active neon outline. | Touch-scrollable horizontal month pill strip with snap to active month. |

---

## 4. Comprehensive Component Catalog across 4 Modes

### 4.1 Headers (Primary & Secondary)
- **UI 20 shell** (D-030): The header is one compact, left-aligned row at
  every width (at most 52px): the current screen title first and the
  live/last-updated status immediately beside it. On mobile the menu button
  comes first. The wordmark and logo live only in the sidebar and the drawer,
  never in the header. The market commentary sits directly under the row with
  the same left padding. Long status messages may wrap rather than overflow.
- **Primary App Header**: Contains App logo (`Roastfolio 📊`), portfolio selector dropdown, global net worth indicator, and settings/theme toggle.
- **Secondary Screen Header**: Displays screen title (e.g., "Asset Analysis"), back button, quick action buttons, and last-updated timestamp.

### 4.2 Data Tables & Grid Systems
- Used in Holdings, Transactions Log, and The Cemetery (AVCO Ledger).
- Supports column sorting (click header to toggle ASC/DESC with chevron), column filtering, search filtering, and inline editing.
- **Mobile Adaptive Switch**: Automatically converts from tabular rows (`<thead>`/`<tbody>`) on desktop to stacked glass cards (`.holding-card`) on mobile screens `< 768px`.

### 4.3 Charts & Interactive Visualizations
- **Performance Line Charts**: Electric blue stroke (`#2b88cf`) with gradient area fill.
- **Scatter Plot & Transaction Markers**: 🟢 BUY (green arrow up), 🔴 SELL (red arrow down), 🟠 SAME-DAY (orange circle).
- **Carry & Drag Bars**: Central split axis showing positive PLN contribution (emerald) vs negative contribution (coral).
- **Topographical Drawdown Lakes**: Gregory Gundersen style descending polygon paths showing peak depth and days underwater.

### 4.4 Calendar & Timeline Pickers
- **Audit Datepicker**: Used for Coping Diary checkpoints with pulsing red overdue indicators.
- **Timeline Picker**: Horizontal month pill strip for archived monthly wraps (`WRAP#MONTH#YYYY-MM`).

### 4.5 Menus, Overlays & Bottom Sheets
- **Contextual Dropdowns**: Translucent glass container (`backdrop-filter: blur(12px)`).
- **"Roastfolio Says" Cards**: Sarcastic commentary cards with left vertical accent bar.
- **Bottom Sheets**: Spring curve animation `cubic-bezier(0.32, 0.72, 0, 1)` with top drag handle pill.

### 4.6 Chips, Badges & Search Inputs
- **Pill Badges**: `TRUE` (emerald green), `FALSE` (amber `#Coping`), `OVERDUE` (pulsing red), `[Nieaktywna hipoteza]` (dark charcoal with `grayscale(0.6)`).
- **Autocomplete Inputs**: Global Ticker Search (Yahoo Finance + Polish TFI) and Coping Diary `@` asset mention autocomplete.

---

## 4.7 Asynchronous States: Loader & Empty State Reuse Policy

To ensure strict visual consistency across the entire application, all asynchronous loading states and empty data views must adhere to the following rules:

### A. Mandatory Reuse of Existing Roastfolio Loader
- **Existing Component**: Roastfolio features a built-in candlestick loader (`.cl-loader`, shown inside a `.card-cl-overlay` on cards and charts, and on the splash screen). See `src/styles/main.css`.
- **Reuse Policy**: Creating new spinners, custom CSS loading wheels, or alternative animated loaders is **strictly prohibited**. Skeleton shapes (`.skeleton-shimmer`, Section 4.15) are allowed only as layout placeholders behind the candle loader (D-011).
- **Execution**: Every async data fetch (API queries, wallet switches, chart re-renders, Analysis lookups) MUST reuse the standard candle loader.

### B. Empty State "Reuse or Create" Protocol
When a component has no data to display (e.g. empty portfolio, no transactions, zero diary entries):
1. **Check Existing Component First**: If an empty state (`.empty-state-card`, mounted as `#dash-empty-state` on the Dashboard) already exists for that component (e.g. Holdings table, Coping Diary empty state), **reuse it immediately**.
2. **Create New Empty State if Absent**: If a newly added component lacks an empty state, create one following the standard 4-part structure:
   - **Muted Icon/Illustration**: Translucent icon with subtle glow.
   - **Sarcastic Heading**: A dry, humorous observation in true Roastfolio tone.
   - **Helpful Context Text**: Explains what data will populate this container.
   - **Primary Action Button (CTA)**: Direct action button to resolve the empty state (e.g., `[ + Create First Portfolio ]`, `[ + New Transaction ]`).

---

## 4.8 Data Table Pagination & Infinite Load Standardization

### A. Desktop Pagination Bar (`.table-pagination-bar`)
- **Location**: Sticky footer bar attached to the bottom edge of data table containers (Holdings, Transactions, The Cemetery).
- **Page Navigation**: `[‹ Previous]` button, interactive page number pills (`1`, `2`, `...`, `12`), and `[Next ›]`. The active page is highlighted with `--accent-primary`.
- **Density Selector**: Glassmorphic dropdown `[ Show: 10 | 25 | 50 | 100 ]` rows per page.
- **Counter**: Precise record indicator: `Showing 1–25 of 184 items` using `tabular-nums`.

### B. Mobile Progressive Load (`.mobile-infinite-trigger`)
- **Card-Stack Footer**: Instead of multi-button pagination, mobile card stacks end with a `44px` touch-optimized action button: `[ Load More (10) ]`.
- **Progress Counter**: Compact text indicator: `Showing 20 of 85 items (23%)`.
- **Intersection Observer**: Optional auto-fetch trigger when scrolling within 100px of the list bottom.

---

## 4.9 Stock Ticker Tape & Market Speedometer Gauge

### A. Ticker Tape (`.ticker-tape-container`)
- **Placement & Motion**: Horizontal bar pinned directly below the primary application header with a smooth, continuous CSS animation (`@keyframes tickerTape`). Pauses automatically on hover (`animation-play-state: paused`).
- **Index Badges**: Real-time ticker cards for the six indices the app tracks (WIG, WIG20, S&P 500, NASDAQ, DAX, MSCI World; see D-017) featuring 24h change pills and, when available, the current price (`WIG20 2,410.50 PLN ▲ +1.2%` in emerald or `S&P 500 5,820.10 USD ▼ -0.4%` in coral red).
- **Interaction**: Clicking any index pill opens a micro-modal with a 5-day mini line chart.

### B. Speedometer Gauge (`.speedometer-gauge-widget`)
- **SVG Arc Surface**: 180° semi-circular gauge with a gradient transitioning from Coral Red (`#EF4444`, Extreme Fear / Deep Drawdown) to Emerald Green (`#10B981`, Peak ATH).
- **Dynamic Needle**: Pulsing purple needle (`#A855F7`) driven by physics-based spring transitions (`cubic-bezier(0.34, 1.56, 0.64, 1)`).
- **Dual Display Modes** (D-006), switched with a segmented control (`role="tablist"`):
  1. *Daily vs Benchmark*: Today's portfolio change against the selected benchmark (current app behaviour).
  2. *Portfolio ATH Distance*: Displays exact portfolio percentage distance from all-time high (e.g. `-5.8% do ATH`).
  A Fear & Greed mode is parked (OQ-5).
- **Viewport Adaptation**: Full `180px` diameter widget on desktop; compact `120px` arc widget on mobile screens.

---

## 4.10 Contextual Help, Tooltips & Rich Hover Cards

### A. Elevation & Anti-Glare Visual Tokens
- **Background Fill**: Elevated surface token `--bg-surface-3` (`#1A2C42` / `rgba(26, 44, 66, 0.85)` with `backdrop-filter: blur(12px)`).
- **Border & Glow**: `1px solid var(--border-strong)` (`rgba(74, 159, 212, 0.25)`) with subtle glow shadow `var(--shadow-md)`.
- **Typography**: `13px` Semi-Bold heading (`--text-primary: #e8f0f8`) with `tabular-nums` for numeric figures; `12px` Regular body text (`--text-secondary: #a8c0d8`) with `1.4` line height. Pure white (`#FFFFFF`) is strictly avoided to eliminate glare on dark OLED screens.
- **Pointer Arrow**: `6px` SVG arrow matching the card background.

### B. Functional Variants
1. **Micro Tooltip**: Compact label (`padding: 6px 10px`, `border-radius: 6px`) for icon-only buttons or acronyms (e.g. `TWR: Time-Weighted Return`).
2. **Rich Hover Card**: Detailed diagnostic card (`max-width: 280px`, `padding: 12px 16px`) showing metric definitions, trend indicators (`🟢 +2.4%`), and an optional sarcastic *"Roastfolio Says"* tip in purple (`var(--color-purple)`).
3. **Interactive Hotspot (`(?)` Iskra)**: Educational onboarding trigger featuring a pulsing purple dot (`var(--color-purple)`) or `(?)` badge.

### C. Interaction Dynamics & Mobile Protocol
- **Intent Delay**: `200ms` hover delay before popping up to avoid accidental flickering when moving the cursor across dense data tables.
- **Animation**: `150ms` spring enter transition (`scale(0.96) → scale(1.0)` with `cubic-bezier(0.2, 0, 0, 1)`), `100ms` exit.
- **Mobile No-Hover Protocol**: On touch devices (`@media (hover: none)`), tooltips are triggered via a `300ms` press-and-hold gesture with haptic feedback (`UIImpactFeedbackGenerator`), or tapping a dedicated `(?)` icon, displaying as a Bottom Sheet.

---

## 4.11 Progressive User Guide & On-Demand Help Center Architecture

To eliminate monolithic, scrolling "walls of text" in traditional documentation, Roastfolio replaces static user guides with a **3-Tier Interactive Progressive Disclosure Help System**:

```
                                [ ROASTFOLIO USER GUIDE ARCHITECTURE ]
                                                   │
      ┌────────────────────────────────────────────┼────────────────────────────────────────────┐
      ▼                                            ▼                                            ▼
[ TIER 1: IN-CONTEXT HOTSPOTS ]           [ TIER 2: SEARCH-FIRST HELPBAR ]           [ TIER 3: ACCORDION KNOWLEDGE HUB ]
• Pulsing (?) icons next to complex terms  • Instant ⌘K / Top Search Command Bar     • Categorized expandable cards
• Short 1-2 sentence micro-tooltips        • Instant answer pills with deep-links    • Filterable by feature / wallet type
• Triggered on hover (desktop) / tap (mob) • Zero scrolling needed                   • Searchable FAQ & step-by-step guides
```

### A. Tier 1: In-Context Hotspots & Micro-Tooltips (Proactive Assistance)
- **Inline Placement**: Dotted underlines or pulsing `(?)` hotspots directly adjacent to UI metrics (e.g. *TWR Return*, *AVCO Ledger*, *ATH Drawdown*, *Coping Checkpoints*).
- **Zero Scroll Context**: Hovering or tapping reveals instant contextual guidance right where the user is working.

### B. Tier 2: Search-First Command Palette / HelpBar (`⌘K` / Global Search)
- **On-Demand Search**: Triggered by pressing `⌘K` (Desktop) or tapping the Search icon in the header (Mobile).
- **Live Answer Cards**: As the user types (e.g. *"How do I edit ATH?"* or *"What is AVCO?"*), matching answer pills display key steps instantly with direct CTA action buttons (e.g., `[ Take me to ATH Editor → ]`).

### C. Tier 3: Adaptive Accordion Knowledge Hub (Categorized Reference)
- **Categorized Sections**: Content is broken into 5 collapsible glassmorphic accordion cards:
  1. 🚀 **Getting Started & CSV Imports** *(Holdings, Brokerage Files)*
  2. 📊 **Understanding Metrics** *(TWR, Benchmarks, Carry & Drag)*
  3. 💼 **Wallet Management & AVCO** *(Active Holdings vs The Cemetery)*
  4. 🧠 **Coping Diary & Hypotheses** *(Tags, Checkpoints, Overdue Audits)*
  5. 🛡️ **Security & Privacy** *(AWS Cognito, JWT, Data Isolation)*
- **Viewport Behavior**:
  - *Desktop*: 2-column layout with left sticky category navigation and right expandable accordion cards.
  - *Mobile*: Single-column vertical stack where tapping a category smoothly expands its sub-items without horizontal overflow or infinite scrolling.

---

## 4.12 Dropdown Overflow & Picker Specification

Section 8.3 rejects full-screen mega-menus for long option lists. This section is the replacement and applies to every picker (wallet filter, benchmark selector, global ticker search).

### A. Desktop: Max-Height Sticky Search Dropdown
- **Container**: Anchored to its trigger, `--bg-surface-3` fill with `--shadow-md`, `max-height: min(360px, 60dvh)`, internal vertical scroll.
- **Sticky Search**: A search input stays pinned at the top of the list so the user can filter without scrolling back.
- **Dismissal**: `Esc`, outside click, or selecting an option. The page behind stays fully visible.

### B. Mobile: Slide-Up Bottom Sheet
- **Container**: Bottom sheet (`max-height: 92dvh`) with a drag handle, entering with `--ease-enter` and leaving with `--ease-exit`.
- **Targets**: Every option row is at least `--touch-min` (44px) tall.

The wording of this section is reconstructed from the reference in Section 8.3 and is awaiting confirmation (OQ-2).

---


## 4.13 Collapsible Side Navigation Panel & Mobile Drawer Specification

To maximize screen real estate and maintain clean spatial hierarchy across desktop, tablet, and mobile views, Roastfolio utilizes a **Collapsible Side Navigation Panel (Sidebar)**.

### A. Desktop Sidebar Architecture (`.sidebar-nav`)
- **Dual Operational Modes**:
  - **Expanded State (`width: 240px`)**: Displays the full `roastfolio` wordmark, Candlestick "R" logo, quick Portfolio Selector dropdown pill, primary module links with icons + text, and a bottom utility section.
  - **Collapsed Icon Rail (`width: 64px`)**: Reduces the sidebar to a sleek icon-only column. Ideal for high-density analysis and multi-column grid views.
- **Keyboard Shortcut & Collapse Toggle**:
  - Global hotkey `⌘B` (or `Ctrl+B`) instantly toggles between Expanded and Collapsed states.
  - A subtle `[ ◄ / ► ]` collapse button is anchored at the bottom of the sidebar.
- **Visual Elevation & Tokens**:
  - **Background Fill**: `--bg-glass` (`rgba(14, 26, 42, 0.75)`) with `backdrop-filter: blur(16px)`.
  - **Border**: `1px solid var(--border-subtle)` on the right edge.
  - **Active State Indicator**: Active nav link features an elevated fill (`var(--bg-surface-2)`), electric blue text (`var(--accent-primary)` / `#2B88CF`), and a `3px` vertical left accent bar (`var(--accent-primary)`).
  - **Collapsed Hover Tooltips**: In icon-rail mode, hovering over an icon displays a Rich Micro-Tooltip (`.sidebar-tooltip`) after a `150ms` delay specifying the screen name.

```
┌─────────────────────────────────────────┐  ┌──────────────────────┐
│  roastfolio 📊              [ ◄ Collapse ]│  │  📊    [ ► Expand ]  │
├─────────────────────────────────────────┤  ├──────────────────────┤
│  ▼ Portfolio: Main Wealth (PLN)         │  │  ▼ (Main)            │
├─────────────────────────────────────────┤  ├──────────────────────┤
│  ▌ 🏠 Control Room                      │  │  ▌ 🏠  (Dashboard)   │
│    💼 Wallets & AVCO Hub                │  │    💼  (Wallets)      │
│    📑 Transactions Log                  │  │    📑  (Transactions) │
│    📈 Asset Analysis                    │  │    📈  (Analysis)     │
│    🧠 Coping Diary (#Hypotheses)        │  │    🧠  (Coping)       │
│    📜 Memory Lane Recaps                │  │    📜  (Recaps)       │
├─────────────────────────────────────────┤  ├──────────────────────┤
│  ❓ Help & Guide (⌘K)                   │  │  ❓  (Help)          │
│  ⚙️ Settings                            │  │  ⚙️  (Settings)      │
└─────────────────────────────────────────┘  └──────────────────────┘
            EXPANDED (240px)                       COLLAPSED (64px)
```

### B. Tablet & iPadOS Adaptability
- **Auto-Collapse Heuristic**: On tablet viewports (768px – 1023px in portrait or Stage Manager split view), the sidebar automatically defaults to the `64px` Collapsed Icon Rail to preserve canvas width.
- **Slide-Over Overlay Mode**: Tapping the top hamburger icon (`☰`) smoothly expands the `240px` sidebar as a floating overlay drawer with an ambient backdrop dim (`rgba(9, 15, 24, 0.6)`), closing automatically upon route selection.

### C. Mobile Slide-Over Drawer (`.mobile-side-drawer`)
- **Thumb-Zone Integration**: The mobile primary workflow relies on the **Fixed Bottom Tab Bar (`64px`)** for the 4 primary destinations (Dashboard, Wallets, Coping Diary, Analysis).
- **Secondary Drawer Trigger**: Tapping the `☰` icon in the top header or performing a right-swipe edge gesture opens the **Slide-Over Side Drawer** (`width: 280px`, `max-width: 85vw`).
- **Drawer Contents**: Houses secondary features (*The Cemetery, Memory Lane Recaps, CSV Data Importer, Account Settings, Theme Toggle, and User Guide*).
- **Dismissal Physics**: Smooth spring physics (`cubic-bezier(0.32, 0.72, 0, 1)`), dismissible via backdrop tap, left-swipe gesture, or `[ ✕ ]` close button.

---


## 4.14 Motion Architecture & Animation System ("Vibe Design" Physics)

To achieve a modern, expensive, and high-performance aesthetic (benchmarked against 2026 Muzli trends and products like Linear, Arc, and Raycast), Roastfolio treats motion not as decoration, but as a functional interaction layer.

```
                              [ ROASTFOLIO MOTION ARCHITECTURE ]
                                              │
       ┌──────────────────────────────────────┼──────────────────────────────────────┐
       ▼                                      ▼                                      ▼
[ TIMING & SPRINGS ]                   [ COMPOSITED GPU TRANSFORMS ]          [ HAPTIC & MICRO-JOBS ]
• 150ms – 300ms duration rule          • animate ONLY transform & opacity     • 4 Jobs: Feedback, Status,
• cubic-bezier(0.32, 0.72, 0, 1) enter • zero layout thrashing (60 FPS)       Error-reduction, Humanizing
• cubic-bezier(0.2, 0, 0, 1) hover     • transform: translate3d / scale       • UIImpactFeedbackGenerator
```

### A. Timing Windows & Spring Physics Rules
1. **The 150ms–300ms Golden Window**:
   - All transition durations MUST fall within **150ms to 300ms** (Material Design 3 / Userpilot 2026 benchmark).
   - Transitions faster than `150ms` appear jarring or invisible; transitions slower than `300ms` feel laggy and introduce perceived latency.
   - **One-shot data entrances** (D-034) are the only exception: when data first arrives, a graphic may settle into place for up to `1.2s` (the ATH lake filling, the ATH breakout line drawing, the gauge needle sweep). They run once, never block input, use only `transform` and `opacity` (or SVG stroke offsets) and are removed by `prefers-reduced-motion`. Later updates of the same graphic use the 150ms–300ms window.
2. **Bezier Curve Registry**:
   - **Enter / Expand Curve**: `cubic-bezier(0.32, 0.72, 0, 1)` — Physics-based spring enter that decelerates smoothly into place.
   - **Micro-Hover Curve**: `cubic-bezier(0.2, 0, 0, 1)` — Rapid, tight response for cursor hover cards and button micro-scales (`scale(1.02)`).
   - **Exit / Dismiss Curve**: `cubic-bezier(0.4, 0, 1, 1)` — Accelerating exit curve (`150ms` duration).

### B. GPU-Accelerated Compositing & 60 FPS Rule
- **Composited Properties ONLY**: Animations MUST alter only GPU-composited CSS properties: `transform` (`translate3d`, `scale3d`, `rotate3d`), `opacity`, and `backdrop-filter`.
- **Forbidden Animated Properties**: Never animate `width`, `height`, `margin`, `padding`, or `top/left/right/bottom` directly. Animating box-model layout properties triggers expensive CPU reflows and drops frame rates below 60 FPS on mobile OLED devices.
- **Hardware Acceleration**: Use `will-change: transform, opacity` or `transform: translateZ(0)` on complex cards (Hero Card, Glassmorphic Islands, Ticker Tape).

### C. Haptic Feedback & Gesture Discovery
- **Touch Haptics**: Pair all mobile touch interactions (swiping bottom sheets, pill switching, Coping Diary tag selection, FAB taps) with system-level haptics (`UIImpactFeedbackGenerator` light/medium/heavy).
- **Contextual Gesture Discovery**: Provide a subtle pulse animation (`.gesture-hint`) the first time a user encounters a swipeable card or bottom sheet handle.

---

## 4.15 Shared Element Transitions, Morphs & FLIP Execution

When expanding cards into detail views (e.g. expanding a Wallet Tile into full sub-account analytics, or clicking a Coping Diary hypothesis card), Roastfolio utilizes the **FLIP Technique** (First, Last, Invert, Play) to morph elements seamlessly without context loss.

### A. Card-to-Modal Morphing Specs
```
┌──────────────────┐                                                     ┌──────────────────────────┐
│  Wallet: IKE     │  ──( Tap / Click )──► [ FLIP Invert Matrix ] ──►     │  Full Sub-Account Hub    │
│  42,850 PLN      │                       Animate Bounds & Blur          │  Chart, Holdings, Actions│
└──────────────────┘                                                     └──────────────────────────┘
   FIRST STATE                             INVERT TRANSFORMATION                     LAST STATE
```

1. **First State**: Card sits in its grid/stack bounds (`getBoundingClientRect()`).
2. **Last State**: Detail view opens as a centered modal or slide-up bottom sheet.
3. **Invert**: The browser calculates scale and translate offsets between First and Last bounds.
4. **Play**: The element animates smoothly over `250ms` using `cubic-bezier(0.32, 0.72, 0, 1)` while morphing `border-radius` (from `16px` to `24px`) and backdrop blur (`backdrop-filter: blur(16px)`).

### B. Production CSS & React Specification for LLMs (Claude 3.5 / 3.7 Sonnet)

```css
/* ==========================================================================
   ROASTFOLIO UTILITY ANIMATIONS (Muzli 2026 Standard)
   ========================================================================== */

/* 1. Glassmorphic Island Hover Micro-Elevation */
.glass-island {
  background: var(--bg-glass);
  backdrop-filter: var(--blur-glass);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  transition: transform 200ms cubic-bezier(0.2, 0, 0, 1),
              border-color 200ms ease,
              box-shadow 200ms ease;
  will-change: transform, box-shadow;
}

.glass-island:hover {
  transform: translateY(-2px) scale(1.01);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md), 0 0 20px var(--accent-glow);
}

/* 2. Pulsing Educational Hotspot (?) */
@keyframes hotspotPulse {
  0% { transform: scale(1); box-shadow: 0 0 0 0 var(--color-purple-bg); }
  70% { transform: scale(1.15); box-shadow: 0 0 0 8px rgba(168, 85, 247, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(168, 85, 247, 0); }
}

.hotspot-pulse {
  animation: hotspotPulse 2s infinite cubic-bezier(0.4, 0, 0.6, 1);
  color: var(--color-purple);
  cursor: pointer;
}

/* 3. Skeleton shape placeholder (sits behind the candle loader, never replaces it) */
@keyframes shimmerWave {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-shimmer {
  background: linear-gradient(
    90deg,
    var(--bg-surface-1) 25%,
    var(--bg-surface-2) 37%,
    var(--bg-surface-1) 63%
  );
  background-size: 200% 100%;
  animation: shimmerWave 1.8s infinite ease-in-out;
  border-radius: var(--radius-sm);
}
```

---

## 4.16 Modern "Expensive" Aesthetic & Dark-First Hierarchy (Muzli 2026 Benchmark)

To ensure Roastfolio feels like a $100M luxury financial tool (inspired by Linear, Arc Browser, and Raycast), the visual architecture strictly enforces **Muzli 2026 Dark-First Design System Standards**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ BASE APP CANVAS (--bg-canvas: #090f18 - Dark Obsidian Slate with ambient radial glow gradients) │
│                                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ ELEVATED SURFACE 1 (--bg-surface-1: #0e1a2a - 5% Luminance Step, Card Container)        │   │
│   │                                                                                         │   │
│   │   ┌─────────────────────────────────────────────────────────────────────────────────┐   │   │
│   │   │ GLASSmorphic ISLAND 2.0 (--bg-glass: rgba(14,26,42,0.75) + blur(16px))          │   │   │
│   │   │ 1px solid var(--border-subtle: rgba(74,159,212,0.12)) + Subtle Ambient Glow      │   │   │
│   │   │ Text: #E8F0F8 (Off-White Glare-Free) | Figures: tabular-nums                       │   │   │
│   │   └─────────────────────────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### A. The 4-Tier Luminance Elevation Architecture
- **Pure Black (#000000) Prohibition**: Pure pitch-black backgrounds cause severe eye strain and text halation effects.
- **Dark Obsidian Canvas (`--bg-canvas: #090f18`)**: Base background uses a rich, dark slate blue tone that feels organic and high-end on OLED hardware.
- **Luminance Elevation Steps**: Depth is established by stepping surface fills up by **5% to 8% luminance**:
  1. `--bg-canvas` (`#090f18`): Deep app canvas.
  2. `--bg-surface-1` (`#0e1a2a`): Primary cards, sidebars, data table containers.
  3. `--bg-surface-2` (`#132032`): Elevated chips, hover states, active tab pills.
  4. `--bg-surface-3` (`#1a2c42`): Command Palette (`⌘K`), dropdowns, modals, floating tooltips.

### B. Glassmorphism 2.0 (Surgical Backdrop Blur)
- **Surgical Restraint**: Glassmorphism is used exclusively for floating, temporary, or elevated containers (Hero Net Worth Card, Hover Cards, Command Palette, Bottom Sheets).
- **Data Table Isolation**: Dense data tables and financial ledgers use solid opaque surfaces (`--bg-surface-1`) to guarantee 100% legibility and prevent background noise from bleeding through numbers.
- **Hardware Fallback**: On budget mobile devices, `backdrop-filter: blur(...)` gracefully falls back to solid `--bg-surface-1` (`#0e1a2a`).

### C. Anti-Glare Micro-Typography & Precision Borders
- **Glare-Free Off-White Text (`#E8F0F8`)**: Primary text uses an off-white tint (`#E8F0F8` to `#A8C0D8`) rather than pure `#FFFFFF` to reduce eye fatigue while maintaining WCAG AA **4.5:1 contrast**.
- **Micro-Borders**: Separators use ultra-subtle `1px` translucent borders (`rgba(74, 159, 212, 0.12)` for subtle, `rgba(74, 159, 212, 0.25)` for strong) to create crisp outline precision without heavy black shadows.
- **Tabular Figures**: All financial metrics, returns, and ticker prices enforce `font-variant-numeric: tabular-nums` for rock-solid vertical alignment.
- **Brand Identity Anchor**: Integrates the official **Candlestick "R" Monogram Logo** (Bottle Green `#0D5C3A` body, Neon Purple `#A855F7` wicks) alongside the lowercase **`roastfolio`** brand wordmark.

---

## 5. Screen Layout Architecture & Model Delegation

Screen-level layouts and specific view compositions are delegated to the core product domain model. The Design System provides the foundational token layer, layout grids, responsive breakpoints, and component library (Sections 1 to 4, 7 and 8) that any screen specification model can compose dynamically.

Each screen that has been through the mockup workflow (D-008) is registered in its own screen registry (Appendix A for the Dashboard, Appendix B for Wallets) with its data inventory, so the redesign can never silently drop information that the current app shows.

---
## 6. Implementation Checklist for LLM AI Generators (Claude 3.5 / 3.7 Sonnet)

When generating HTML, CSS, React, or JS code from this design system:
- [ ] **Dark-First Tokens**: Use `var(--bg-canvas: #090f18)` as base and enforce 4-tier tonal elevation (`var(--bg-surface-1)` to `3`). Never hardcode hex values.
- [ ] **Glassmorphic Islands**: Apply `.glass-island` (`backdrop-filter: blur(16px)` + `1px solid var(--border-subtle)`) to elevated Hero cards, modals, and hover cards.
- [ ] **Animation Constraints**: Animate ONLY `transform`, `opacity`, and `backdrop-filter`. Keep duration within `150ms – 300ms` using `cubic-bezier(0.32, 0.72, 0, 1)`.
- [ ] **Tabular Numerics**: Apply `font-variant-numeric: tabular-nums` to all prices, percentages, balances, and dates.
- [ ] **Thumb Target Ergonomics**: Enforce minimum `44px × 44px` touch targets on mobile with `touch-action: manipulation`.
- [ ] **Async & Empty States**: Reuse the candle loader (`.cl-loader` inside `.card-cl-overlay`) for loading states and build empty states using the 4-part `.empty-state-card` structure.
- [ ] **Wordmark & Logo**: Render brand title as lowercase **`roastfolio`** and use the Candlestick "R" logo token palette (`#0D5C3A` + `#A855F7`).

---

## 7. Official Brand Logo Specification

### A. Logo Geometry & Concept (Candlestick Monogram "R")
- **Visual Fusion**: Combines the iconic candlestick chart (*candlestick body*) with the monogram letter **R** into a single, clean monoline symbol.
- **Hollow Candlestick Body**: The vertical stem of the letter R forms a hollow, contoured candlestick body with top and bottom wicks.
- **Letter Loop & Leg**: The top loop and right leg of the letter R smoothly close the monogram geometry.

### B. Color Tokens & Brand Palette
- **Candlestick Body**: Deep Bottle Green (`#0D5C3A` / `--color-bottle-green`) contour fill, symbolizing mature financial growth, portfolio stability, and positive TWR.
- **Monogram "R" & Wicks**: Electric Neon Purple (`#A855F7` / `--color-purple`), ensuring 100% contrast against dark OLED slate backgrounds and aligning with the Coping Diary reflection theme.
- **PWA Tile Canvas**: Dark Obsidian Slate (`#090F18` / `--bg-canvas`) tile with `24px` border radius and subtle ambient glow shadow.

### C. Brand Wordmark & Case Rule
Aligning with 2026 dark-first fintech design trends (Muzli, Linear, Arc):
- **App Header & Navigation Wordmark**: Rendered strictly in all-lowercase `roastfolio` (never uppercased by CSS `text-transform`).
- **PWA App Icon Title**: `roastfolio` (matches `name` and `short_name` in `src/manifest.json`).
- **Wrapped & Shareable Cards**: Wordmark variants for chat-native social sharing are not decided yet (OQ-1). The current monthly recap cover uses plain `roastfolio`.
- **Formal Documentation & Legal**: Standard sentence case `Roastfolio` is reserved exclusively for investor briefs, legal terms, and press releases.


---

## 8. Comprehensive Architecture & UI/UX Design Alternatives Analysis

This section serves as a permanent reference library documenting the alternative layout paradigms, interaction models, and architectural patterns evaluated during the design of Roastfolio 2026. Each entry provides a thorough technical analysis of how the pattern operates, its visual mechanics, pros and cons, and the engineering rationale for Roastfolio's selected approach.

---

### 8.1 Layout & Spatial Structural Alternatives

#### Alternative 1: Morphing Card Pattern (Shared Element Transitions / In-Place Card Expansion)



* **Detailed Mechanics & Technical Operation**:
  - Upon user interaction (click/tap), the card element computes its initial bounding client rect (`getBoundingClientRect()`).
  - The DOM node modifies its layout properties to target expanded dimensions (`width`, `height`).
  - An invert transform matrix calculates scale and translate offsets (`translate3d`, `scale3d`).
  - A 60 FPS GPU-accelerated spring animation (`cubic-bezier(0.32, 0.72, 0, 1)`, 250ms) plays, morphing border-radius, background translucency, and internal element visibility (`opacity`). The FLIP diagram is in Section 4.15.
* **Pros & User Experience Strengths**:
  - Provides a seamless spatial mental model where data never leaves its visual origin point.
  - Eliminates jarring full-page context switches, preserving cognitive flow when inspecting individual wallet balances or daily movers.
  - Delivers a premium, native iOS App Store / Linear-style micro-interaction that boosts perceived performance.
* **Cons & Engineering Trade-offs**:
  - High GPU re-paint and compositor overhead when multiple morphing cards trigger simultaneously on low-end mobile hardware or battery-saver modes.
  - Complex CSS grid reflow: Expanding a card inline within a multi-column CSS grid requires surrounding sibling cards to smoothly shift positions, often causing layout jitter.
  - Difficult edge-case handling on iPad Split View and Stage Manager where dynamic viewport resizing interrupts active transition keyframes.
* **Roastfolio Architectural Verdict**:
  - **Adopted as Tier 2 In-Place Expansion (Constrained Vertical Accordion)**: Selected for Dashboard Wallet Tiles and Daily Mover cards, but strictly constrained to vertical accordion expansion within the container grid rather than unconstrained 3D viewport morphing. This preserves spatial continuity while maintaining 60 FPS performance across all devices.

---

#### Alternative 2: Master-Detail Split Pattern (Two-Column Columnar Flow / Split-Pane View)



* **Detailed Mechanics & Technical Operation**:
  - The viewport is permanently split into a primary Master List Pane (30%–40% width) and a secondary Detail Content Pane (60%–70% width).
  - Selecting an entity in the Master List updates the application state (`selectedEntityId`) without triggering page navigation.
  - The Detail Pane listens to state changes and re-renders its view in-place, maintaining scroll position in the Master List.
* **Pros & User Experience Strengths**:
  - Exceptional operational density for desktop power users and landscape iPad workflows (e.g. reviewing dozens of Coping Diary hypotheses or AVCO trades sequentially).
  - Reduces click depth to zero: switching between items requires a single click with zero loading lag.
  - Maximizes wide-screen desktop real estate without leaving empty horizontal whitespace.
* **Cons & Engineering Trade-offs**:
  - Fails on mobile viewports (< 768px): Dual panes cannot coexist in narrow portrait screens without reducing font sizes below WCAG readability limits or forcing horizontal scrollbars.
  - Demands strict state isolation to prevent memory leaks when rapidly clicking through complex chart-rendering detail views.
* **Roastfolio Architectural Verdict**:
  - **Adopted for Desktop & iPad Landscape (Coping Diary & Asset Analysis)**: Implemented as the primary layout for wide screens, paired with an **Adaptive Mobile Switch** that automatically collapses the Master-Detail split into a single-column drill-down stack with native back-button navigation on mobile screens (< 768px).

---

#### Alternative 3: Floating Glassmorphic Islands (Decoupled Canvas Layout)

* **Detailed Mechanics & Technical Operation**:
  - UI containers are completely detached from traditional full-width structural blocks and rendered as self-contained "islands" floating over a deep ambient background canvas (`--bg-canvas`).
  - Depth is established using heavy backdrop filters (`backdrop-filter: blur(16px)`), translucent fill layers (`--bg-glass`), and multi-layered ambient drop shadows (`--shadow-lg`).
* **Pros & User Experience Strengths**:
  - High aesthetic polish aligning with 2026 cutting-edge SaaS design trends (Arc Browser, Linear, macOS Sonoma).
  - Creates clear visual separation between distinct functional domains (e.g. Hero Net Worth vs Benchmark Matrix) without requiring heavy 1px border dividers.
  - Allows subtle background lighting gradients (e.g. emerald glow for profit, purple glow for Coping Diary) to bleed through containers softly.
* **Cons & Engineering Trade-offs**:
  - Heavy GPU rendering burden: Overlapping multiple `.glass-island` containers triggers expensive compositor passes, dropping scroll frame rates on mid-range smartphones.
  - Contrast degradation: Translucent glass floating over variable background glows can violate WCAG AA text contrast thresholds (4.5:1) if background color bleeding is unconstrained.
* **Roastfolio Architectural Verdict**:
  - **Adopted with Containerless Luminance Guidance**: Selected for elevated Hero cards, Command Palettes, and Modals, but constrained to solid luminance-step surface fills (`--bg-surface-1`, `--bg-surface-2`) on mobile to ensure 60 FPS scrolling and rock-solid WCAG AA text readability.

---

### 8.2 User Guide & Onboarding Architecture Alternatives

#### Alternative 1: Monolithic Single-Page User Manual (Wall of Text)
* **Detailed Mechanics**: A long, continuous documentation web page containing all user guides, feature explanations, and FAQ lists in a single scrollable container.
* **Pros**: Simple to generate and publish statically; easy for search engines to index.
* **Cons**: Severe scroll fatigue; user research demonstrates >82% mobile drop-off rate when users are forced to leave their active task context to read a documentation wall.
* **Roastfolio Architectural Verdict**: **Rejected for In-App Use (Retained only as printable PDF export)**. Replaced by Section 4.11's 3-Tier Progressive User Guide (In-Context Hotspots, Search-First HelpBar (`⌘K`), and Accordion Knowledge Hub).

#### Alternative 2: Modal Overlay Product Tour (Multi-Step Wizard)
* **Detailed Mechanics**: A sequential series of modal dialogs or dimmed backdrop spotlights forcing the user to click "Next" through 5–10 steps upon first launch.
* **Pros**: Guarantees that every new user is exposed to key feature locations.
* **Cons**: High user annoyance; over 88% of users instinctively click "Skip Tour" or "Close" within 2 seconds without absorbing information, creating friction before time-to-first-value.
* **Roastfolio Architectural Verdict**: **Rejected**. Replaced by non-intrusive, on-demand contextual hotspots (`(?)` icons) and interactive empty states that guide users as they interact naturally with data.

---

### 8.3 Navigation & Dropdown Overflow Alternatives

#### Alternative 1: Full-Screen Overlay Mega-Menu
* **Detailed Mechanics**: Opening a dropdown (such as the Portfolio Picker) covers the entire screen with a semi-opaque modal overlay displaying all accounts and options.
* **Pros**: Provides unlimited space for listing dozens of options without internal scrolling.
* **Cons**: Completely obscures the user's active financial context (e.g. Net Worth figures or trade charts); feels jarring and disruptive, especially on iPad Stage Manager and desktop windows.
* **Roastfolio Architectural Verdict**: **Rejected**. Replaced by Section 4.12's Max-Height Sticky Search Dropdowns on Desktop and Slide-Up Bottom Sheets on Mobile.

---

### 8.4 Dashboard Market Visualization Alternatives

#### Alternative 1: Embedded Heavy Canvas Candlestick Chart (TradingView Widget)
* **Detailed Mechanics**: Embedding a full interactive HTML5 Canvas candlestick charting engine directly inside the main Dashboard hero card.
* **Pros**: Gives immediate access to technical analysis drawing tools, volume indicators, and minute-by-minute price candles on the home screen.
* **Cons**: Violates the Tier 1 Hero State principle ("At-a-glance status answering 'How am I doing today?' in < 2 seconds"); introduces 2MB+ JavaScript bundle overhead, slowing cold app boot times significantly.
* **Roastfolio Architectural Verdict**: **Rejected for Dashboard Home**. Replaced on the Dashboard by the lightweight Performance Line Chart and Multi-Region Benchmark Matrix. The heavy candlestick charting engine is housed exclusively on the dedicated Asset Analysis screen.

---

## 9. Decision Log

Every design decision taken while reviewing mockups is recorded here. The `Check` column is executable: `./test.sh design` evaluates it against the current mockups, so a later change that contradicts an earlier decision fails the test.

Status values: `active` (approved by the owner), `provisional` (proposed by the assistant, awaiting owner confirmation), `superseded` (replaced, kept for history; no check).

Check syntax: `dom: <css selector>` (at least one match in the mockup), `count: <css selector> = <n>` (exactly n matches), `no-dom: <css selector>` (no match), `css: <regex>` (matches the mockup or token CSS), `none`. A check applies to the dashboard mockup unless it starts with a scope prefix such as `@wallets dom: ...`.

| ID | Status | Decision | Check |
| :--- | :--- | :--- | :--- |
| D-001 | active | The app adopts v9 tokens through a mapping layer: v9 `--bg-*` and `--text-*` tokens coexist with legacy `--brand-*` and `--fintech-*` until every screen is migrated. The accent is `#2b88cf`. | `css: --accent-primary:\s*#2b88cf` |
| D-002 | active | Desktop primary navigation is the collapsible sidebar (240px expanded, 64px icon rail). It ships together with the Dashboard redesign. | `dom: nav.sidebar-nav[data-state]` |
| D-003 | active | Mobile primary navigation is a fixed bottom tab bar with 4 destinations plus a slide-over drawer for the rest. | `dom: nav.bottom-tabs a` |
| D-004 | active | Monthly and Yearly Summary share one card with a segmented control. | `dom: .period-card [role="tablist"] [role="tab"]` |
| D-005 | active | The engagement strip becomes compact chips inside the hero card. | `dom: .hero-card .eng-chips .eng-chip` |
| D-006 | superseded | The gauge had two modes: daily vs benchmark, and distance to ATH. Replaced by D-022 (gauge shows only today vs benchmark) and D-027 (ATH distance is the lake). | none |
| D-007 | active | Roast reaction buttons stay hidden until the roast card is tapped. | `dom: .roast-card .roast-reactions[hidden]` |
| D-008 | active | Mockup first: every screen gets an HTML mockup in `design/mockups/` that the owner approves before anything is implemented in `src/`. | `dom: html[data-mockup="dashboard"]` |
| D-009 | provisional | The light theme switches with `:root[data-theme="light"]` (as the app does) instead of `body.light-theme`. | `css: :root\[data-theme="light"\]` |
| D-010 | provisional | Light-mode `--text-muted`, `--color-success` and `--color-warning` are darkened so they meet the 4.5:1 rule of Section 4.16.C (see Section 10). | `css: --color-success:\s*#047857` |
| D-011 | provisional | The existing candle loader (`.cl-loader` in `.card-cl-overlay`) is the only loader. Skeleton shapes may sit behind it as placeholders. | `dom: .card-cl-overlay .cl-loader` |
| D-012 | provisional | Collapsing the sidebar swaps its width instantly and fades labels with `opacity`, because animating `width` is forbidden by Section 4.14.B. | `dom: .sidebar-nav .nav-label` |
| D-013 | provisional | All motion honours `prefers-reduced-motion`. | `css: prefers-reduced-motion` |
| D-014 | provisional | The ticker tape is mounted once. The current app mounts it twice (top on mobile, inside the gauge card on desktop). | `count: .ticker-tape-container = 1` |
| D-015 | provisional | The mobile gauge-per-wallet carousel is removed. Wallet gauges live only in the Control Room cards. | `no-dom: .gauge-carousel-track` |
| D-016 | provisional | Drawdown from ATH is shown with a "lake" graphic whose water level reflects the depth, tying to the Drawdown Lakes in Statistics. | `dom: .hero-card .ath-lake` |
| D-017 | provisional | The ticker tape lists the six indices the app tracks: WIG, WIG20, S&P 500, NASDAQ, DAX and MSCI World. | `dom: .ticker-tape-container [data-index-id="MSCI_WORLD"]` |
| D-018 | provisional | Section 2 gains typography, spacing, layout and motion tokens (`--fs-*`, `--space-*`, `--dur-*`, `--ease-*`) so mockups never hardcode them. | `css: --dur-base:\s*200ms` |
| D-019 | provisional | The active navigation item keeps `--text-primary` text and shows the accent only on its icon and left bar, because `--accent-primary` text on `--bg-surface-2` is 4.32:1 in dark mode (Section 10). | `css: \.nav-item\[aria-current="page"\] \.ico` |
| D-020 | provisional | Accordion content (Control Room wallets, benchmark lists) appears with a short fade-and-rise and never animates `height`. | `dom: .wallet-card .wallet-more[hidden]` |
| D-021 | active | The Dashboard hero follows direction C: the roast is the headline, with total value and today's change under it. | `@dashboard-d-player-v2 dom: .hero .hero-roast [data-field="roast-message"]` |
| D-022 | active | The hero also shows today's portfolio return against the benchmark return (the comparison the roast talks about) as a gauge with both values and the difference in percentage points. | `@dashboard-d-player-v2 dom: .hero .gauge-widget [data-field="gauge-benchmark-pct"]` |
| D-023 | active | Main column order: hero, benchmark chart, ATH with the last 6 months, and the Summary (month and year against benchmarks) at the very bottom. | `@dashboard-d-player-v2 dom: .col-main > .hero + .bench + .ath-six + .summary` |
| D-024 | active | The right column holds Today's Movers, then Accounts. | `@dashboard-d-player-v2 dom: .col-rail > .movers + .accounts` |
| D-025 | superseded | The benchmark chart showed only the benchmark with a "coming soon" slot for the portfolio line. Replaced by D-029. | none |
| D-026 | active | Frameless layout (Section 1.1, principle 3): no cards, borders or shadows around areas. Space and hairlines separate sections. Rounded shapes remain only for chips, pills, buttons, avatars and floating islands (sidebar, drawer, bottom tabs, player). The browser test scans every screen that carries `data-frameless`. | `@dashboard-d-player-v2 dom: html[data-frameless]` |
| D-027 | provisional | ATH distance is shown by the lake graphic with its numbers, not by a second gauge mode. | `@dashboard-d-player-v2 dom: .ath-six .ath-lake[data-field="gauge-ath"]` |
| D-028 | provisional | On mobile the order is hero, benchmark chart, Today's Movers, Accounts, ATH, last 6 months, Summary. Daily information comes first, analysis last. | `@dashboard-d-player-v2 css: \[data-o="6"\]` |
| D-029 | active | Under the benchmark chart, "Portfolio vs benchmark · since open" plots the portfolio return against the benchmark return at 1-minute resolution. The curve is synthesised in the browser from the minute bars and cash already loaded (no backend storage). Both lines start at 0% at the benchmark open and are delayed 15 minutes to match the Yahoo quotes. The benchmark line ends at its session close; a "Portfolio window" setting lets the portfolio line run for 24 hours. The opening-gap explanation sits behind an info button, not in the page. | `@dashboard-d-player-v2 dom: .bench .intraday-comparison [data-field="intraday-window"]` |
| D-030 | active | The header is one compact left-aligned row at every width: title and live status, with the menu button first on mobile. The wordmark appears only in the sidebar and drawer (Section 4.1). | `@dashboard-d-player-v2 no-dom: .top-bar .brand` |
| D-031 | active | On phones the hero keeps the roast and the gauge side by side (gauge column about 148px), with total value and today's change spanning underneath. | `@dashboard-d-player-v2 css: grid-template-areas:\s*"say gauge"` |
| D-032 | active | The ATH lake uses a logarithmic distance scale so a 0.3% dip on a large portfolio is visible and a 50% drawdown still fits. States: `pending`, `below` (water with rising bubbles), `at` and `above` (a green tide rises over the dashed ATH line). Answers the former question about the ATH gauge scale. | `@dashboard-d-player-v2 dom: .ath-lake[data-state]` |
| D-033 | active | A new all-time high shows a one-shot breakout banner: a sparkline draws through the dashed ATH ceiling, then the badge shimmers. It replays only when the recorded ATH changes. | `@dashboard-d-player-v2 dom: .ath-celebration .ath-ceiling` |
| D-034 | provisional | One-shot data entrance animations may last up to 1.2s; interactive transitions stay within 150ms to 300ms (Section 4.14). | `@dashboard-d-player-v2 css: @keyframes ath-draw` |
| D-035 | provisional | Wallets uses the dashboard's frameless language (D-026): one `h1` in the top bar, a glowing hero with the selected wallet's total, then hairline-separated sections in a main column and a 340px rail. Below 1100px the rail drops under the main column. | `@wallets count: h1 = 1` |
| D-036 | provisional | Wallets are switched with a row of pill chips (name and total) acting as one tablist. "All wallets" is first; "New wallet" opens an inline form next to it instead of a separate panel. | `@wallets dom: .w-switcher [role="tab"][aria-selected="true"]` |
| D-037 | provisional | Wallet allocation is a single stacked bar with a legend, and each holding row repeats its share as a thin bar. It replaces the donut, which was hard to read with more than five holdings. | `@wallets dom: .w-alloc .alloc-bar` |
| D-038 | provisional | "All wallets" is read-only. One note above the holdings explains it, and trade buttons, Quick entry, rename and delete are hidden, instead of a "Read only" badge on every row. | `@wallets dom: .w-readonly-note` |
| D-039 | provisional | Transactions are entered in a glass sheet (right side on desktop, bottom sheet on phones) with the type as a segmented tablist and a live review before saving. Wallet settings (benchmark, ATH, rename, delete) are inline in the rail, not in a modal. | `@wallets dom: .tx-sheet[role="dialog"][aria-modal="true"] [data-field="tx-type"]` |
| D-040 | provisional | On phones "New transaction" is a glass pill above the bottom tabs, and the page reserves bottom padding so it never covers the last row. | `@wallets css: \.w-fab` |
| D-041 | provisional | History splits into Overview (performance charts) and Summaries (monthly recap) with one page-level segmented tablist under the commentary. Both panels are frameless, like the dashboard (D-026). | `@history dom: .hx-sections[role="tablist"] [aria-selected="true"]` |
| D-042 | provisional | One sticky filter bar (wallet chips and a single ALL/5Y/3Y/1Y/YTD/1M/1W range, default 1Y) drives every Overview chart. It replaces the separate range pickers of the value, return and benchmark charts. | `@history dom: .hx-filters [data-field="history-range"]` |
| D-043 | provisional | The Overview opens with a value hero: total, gain in the range, invested capital, deposits and market gain, next to a value area chart with a dashed invested-capital line, deposit markers and a scrub readout. | `@history dom: .hx-hero [data-field="history-value-chart"]` |
| D-044 | provisional | Cumulative return and Return vs Benchmark merge into one Return chart with a %/PLN toggle. Benchmark series chips appear only in % mode; PLN mode shows a note that benchmarks have no PLN value. | `@history dom: .hx-return [data-field="history-benchmark-series"]` |
| D-045 | provisional | Monthly and Daily change sit side by side as a compact pair (one column on phones). Monthly is a bar chart. Daily is a scatter of one dot per session, with halos on the best and worst day and a dashed average line. Daily % and Daily PLN merge behind one toggle and show at most 90 sessions. | `@history dom: .hx-pair .hx-monthly + .hx-daily .hx-scatter-svg` |
| D-046 | provisional | Summaries is an editorial recap: a poster cover (D-047), a strip of three big numbers, then numbered chapters 01–07 separated by hairlines in a two-column grid, with no cards. The journey chart fills the gap between the portfolio and the benchmark as "Your lead". | `@history dom: .rc-story .rc-numbers + .rc-grid` |
| D-047 | provisional | The recap poster is the one printed object allowed on a frameless screen, together with its mini preview in the share invite. Its pastel paper follows the period mood (`--recap-up`, `--recap-down`, `--recap-flat`) in both themes, all text uses `--recap-ink` or `--recap-ink-soft`, and the Spotify-style type runs the TWR up to 7rem. A "Beat the WIG" sticker shows only when the benchmark was beaten. | `@history dom: .rc-poster[data-mood] [data-field="recap-twr"]` |
| D-048 | provisional | Recap periods use a navigator, not a select: a Monthly / Yearly segmented control, a timeline strip that shows each period's return with year marks and a dot on the live period, and previous / next buttons. A share invite ends the recap with a poster preview and a switch for PLN amounts, which stay hidden by default. The headline is built from data, in priority order: (1) beat or trailed the benchmark, plus the carry holding's share of the gain or the anchor's cost; (2) a new all-time high; (3) the sign-based fallback. Stories that need new backend logic, such as positions sold just before a rally, are future work. | `@history dom: .rc-nav [data-field="recap-period-type"]` |

## 10. Consistency Contract

The tests in `tests/test_design_system_doc.py`, `tests/test_design_mockups_contract.py` and `tests/test_design_mockups_browser.py` enforce this document. Run them with `./test.sh design`, after every mockup change and periodically.

What is enforced:
- **Document health**: section numbers are unique, every `Section N.M` reference resolves, no inline code was lost, Decision Log syntax is valid, and class names the document calls "existing" exist in `src/styles/main.css`.
- **Token parity**: the CSS blocks in Section 2 are identical to `design/tokens-v9.css`. Regenerate the file with `.venv/bin/python design/design_system.py --write-tokens`.
- **Mockup rules**: no hardcoded colours, only defined tokens, no forbidden animated properties, `transition` durations of 150ms to 300ms, hover effects only inside `@media (hover: hover)`, tabular numerals on financial figures, lowercase wordmark, no new spinners, `touch-action: manipulation` on controls.
- **Decisions and data**: every `active` or `provisional` decision check in Section 9 passes, and every field in the screen's registry exists in its mockup. Every screen mockup also carries the Shell and Market ticker fields of Appendix A.
- **Browser checks**: no horizontal overflow at 1440px, 1024px, 768px and 390px, text contrast of at least 4.5:1 (3:1 for large text) in both themes, measured on the rendered pixels behind each text box (so gradients and glass count), touch targets of at least 44px on mobile, and working segmented controls and theme switch.
- **Explorations**: files in `design/explorations/` are unapproved design directions. They must obey every rule above and keep every field of their screen's registry, but they are exempt from the Decision Log checks until one direction is chosen. Decisions about an exploration use the scope prefix, for example `@dashboard-d-player-v2 dom: ...`.
- **Frameless**: on a screen marked `data-frameless` the browser test fails on any element of at least 160x72px with a corner radius of 12px or more that also has a background, border or shadow, unless it is a glass island, the empty state card or the loading overlay.

Process: the owner comments on a mockup, the assistant changes the mockup and, when a decision changes, updates Section 9 and the screen's registry in the same change. The test run proves the three still agree.

### Contrast Contract

Foreground tokens must reach the ratio on every listed background token, in that theme.

| Theme | Foreground | Backgrounds | Ratio |
| :--- | :--- | :--- | :--- |
| dark | --text-primary, --text-secondary, --text-muted | --bg-canvas, --bg-surface-1, --bg-surface-2 | 4.5 |
| dark | --accent-primary, --color-success, --color-danger, --color-warning | --bg-canvas, --bg-surface-1 | 4.5 |
| dark | --color-purple | --bg-canvas | 4.5 |
| dark | --text-inverse | --accent-primary | 4.5 |
| light | --text-primary, --text-secondary, --text-muted | --bg-canvas, --bg-surface-1, --bg-surface-2 | 4.5 |
| light | --accent-primary, --color-success, --color-danger, --color-warning, --color-purple | --bg-canvas, --bg-surface-1 | 4.5 |
| light | --text-inverse | --accent-primary | 4.5 |

### Known Contrast Limits

These pairs are below 4.5:1. They may carry text only when it is at least 24px, or at least 18.66px and bold (3:1 large-text rule), or purely decorative. The measured ratio is verified by the test, so this table cannot drift.

| Theme | Foreground | Background | Ratio |
| :--- | :--- | :--- | :--- |
| dark | --color-purple | --bg-surface-1 | 4.42 |
| dark | --accent-primary | --bg-surface-2 | 4.32 |
| dark | --color-danger | --bg-surface-2 | 4.36 |
| light | --color-danger | --bg-surface-2 | 4.41 |

## 11. Open Questions

| ID | Question |
| :--- | :--- |
| OQ-1 | Which wordmark variants should Wrapped and shareable cards use? The values were lost from the source file. |
| OQ-2 | Please confirm the reconstructed wording of Section 4.12 and of the repaired inline code in Section 8. |
| OQ-3 | v9 Section 4.13 shows a portfolio selector pill at the top of the sidebar. The app has wallets, not portfolios. Keep a wallet filter there or drop it? |
| OQ-5 | Should the Fear and Greed gauge mode from v9.0 return later? It is parked for now. |

## Appendix A. Screen Registry: Dashboard

Every row is a piece of information that the current Dashboard shows (source: `src/index.html` and `src/scripts/dashboard.js`). The mockup must expose each one as `data-field="<field>"`. Removing a row requires an explicit decision in Section 9.

### Shell
| Field | Shows |
| :--- | :--- |
| `brand-wordmark` | Lowercase `roastfolio` wordmark and logo |
| `live-data-status` | Live price refresh status |
| `market-commentary` | Market commentary line |
| `nav-dashboard` | Navigation: Dashboard |
| `nav-wallets` | Navigation: Wallets |
| `nav-portfolio` | Navigation: Portfolio |
| `nav-history` | Navigation: History |
| `nav-statistics` | Navigation: Statistics |
| `nav-retirement` | Navigation: Retirement |
| `nav-transactions` | Navigation: Transactions |
| `nav-analysis` | Navigation: Analysis |
| `nav-diary` | Navigation: Coping Diary |
| `nav-guide` | Navigation: User Guide |
| `theme-switch` | Dark and Light switch |
| `user-card` | User name and role |
| `brand-footer` | Powered by TOMINEX and the version tag |

### Market ticker
| Field | Shows |
| :--- | :--- |
| `index-WIG` | WIG change |
| `index-WIG20` | WIG20 change |
| `index-SP500` | S&P 500 change |
| `index-NASDAQ` | NASDAQ change |
| `index-DAX` | DAX change |
| `index-MSCI_WORLD` | MSCI World change |

### Engagement
| Field | Shows |
| :--- | :--- |
| `eng-level` | Level name, XP and progress to the next level |
| `eng-streak-contribution` | Deposit streak |
| `eng-streak-checkin` | Active days streak |
| `eng-streak-withdrawal` | Withdrawal-free streak |
| `eng-streak-goal` | Goal streak |
| `eng-streak-green` | Green months streak |
| `eng-badge` | Most recent badge and tier |
| `eng-all` | Link to all achievements |

### Hero
| Field | Shows |
| :--- | :--- |
| `total-value` | Portfolio total value |
| `daily-pln` | Daily change in PLN |
| `daily-pct` | Daily change in percent |
| `ath-drawdown-pct` | Drawdown from ATH in percent |
| `ath-drawdown-pln` | Drawdown from ATH in PLN |
| `ath-value` | Last recorded ATH value |
| `ath-date` | Last recorded ATH date |
| `ath-celebration` | New all-time-high banner |
| `sparkline-6m` | Six-month returns sparkline |

### Gauge and roast
| Field | Shows |
| :--- | :--- |
| `gauge-daily` | Daily change gauge |
| `gauge-benchmark-name` | Selected benchmark name |
| `gauge-benchmark-pct` | Selected benchmark daily change |
| `gauge-ath` | ATH distance lake (D-032) |
| `roast-message` | Roast comment |
| `roast-reactions` | Good, Repetitive, Wrong and Boring feedback buttons |

### Portfolios Control Room
| Field | Shows |
| :--- | :--- |
| `wallet-name` | Wallet name |
| `wallet-dial` | Daily change dial |
| `wallet-total` | Wallet total value |
| `wallet-daily-pct` | Wallet daily change in percent |
| `wallet-daily-pln` | Wallet daily change in PLN |
| `wallet-ath-status` | Wallet ATH status or drawdown |

### Monthly and Yearly summary
| Field | Shows |
| :--- | :--- |
| `monthly-return-pln` | Monthly return in PLN |
| `monthly-return-pct` | Monthly return in percent |
| `monthly-benchmark-score` | Benchmarks overtaken versus lost |
| `monthly-benchmark-list` | Per-benchmark list |
| `monthly-goal-deposit` | Monthly deposit goal progress |
| `monthly-goal-return` | Monthly return goal progress |
| `yearly-return-pln` | Yearly return in PLN |
| `yearly-return-pct` | Yearly return in percent |
| `yearly-benchmark-score` | Benchmarks overtaken versus lost |
| `yearly-benchmark-list` | Per-benchmark list |
| `yearly-goal-deposit` | Yearly deposit goal progress |
| `yearly-goal-return` | Yearly return goal progress |

### Today's Movers
| Field | Shows |
| :--- | :--- |
| `mover-logo` | Company logo |
| `mover-name` | Company name |
| `mover-spark` | Price sparkline |
| `mover-range-toggle` | 1D and 1Y toggle |
| `mover-price-pln` | Price in PLN |
| `mover-price-orig` | Price in original currency |
| `mover-pct` | Daily change in percent |
| `mover-volume` | Volume pace badge |
| `mover-daily-pln` | Daily change in PLN |

### Benchmark chart
| Field | Shows |
| :--- | :--- |
| `bench-title` | Benchmark title |
| `bench-change` | Change badge |
| `bench-ohlc` | OHLC legend |
| `bench-range` | 1D, YTD and 1Y range buttons |
| `bench-type` | Line and Candle switch |
| `intraday-comparison` | Portfolio vs benchmark since the open, minute by minute (D-029) |
| `intraday-window` | Portfolio window: benchmark session or 24 hours |
| `intraday-status` | Latest values of both lines and the 15-minute delay note |

### States
| Field | Shows |
| :--- | :--- |
| `state-loading` | Candle loader state |
| `state-empty` | Empty portfolio state |

## Appendix B. Screen Registry: Wallets

Every row is a piece of information or a control that the current Wallets screen offers (source: `src/index.html` and `src/scripts/manage.js`). The mockup `design/mockups/wallets.html` must expose each one as `data-field="<field>"`, together with the Shell and Market ticker fields of Appendix A. Removing a row requires an explicit decision in Section 9.

### Wallet switcher and hero
| Field | Shows |
| :--- | :--- |
| `wallet-switcher` | All wallets first, then each wallet with its total |
| `wallet-create` | New wallet name, create button and validation message |
| `wallet-name` | Selected wallet name |
| `wallet-total` | Selected wallet total value |
| `wallet-daily` | Today's change in PLN and % |
| `wallet-annual-return` | Annualised return |
| `wallet-ath` | Distance from the all-time high, ATH value and date |
| `wallet-counts` | Number of holdings, cash positions and transactions |
| `wallet-value-history` | Value history chart with deposit markers |
| `wallet-allocation` | Allocation by holding, cash included |
| `wallet-history-link` | Link to the wallet's transaction history |
| `tx-open` | Opens the transaction form |

### Holdings
| Field | Shows |
| :--- | :--- |
| `holdings-view` | Active holdings or The Cemetery |
| `holding-company` | Logo, company name and ticker |
| `holding-realized` | Past realized profit or loss (AVCO) on a position still held |
| `holding-units` | Shares held |
| `holding-value` | Current value |
| `holding-today` | Today's change in PLN and % |
| `holding-alloc` | Share of the wallet |
| `holding-actions` | Buy more and Sell, or the Cash tag |

### The Cemetery
| Field | Shows |
| :--- | :--- |
| `cemetery-count` | Number of closed positions and net realized result |
| `cemetery-filter` | Show all, still held or closed |
| `cemetery-asset` | Asset name, ticker and status |
| `cemetery-lifespan` | Opened and closed dates and duration (sortable) |
| `cemetery-return` | Total realized return in PLN and % (sortable) |

### Quick entry
| Field | Shows |
| :--- | :--- |
| `quick-entry-input` | Plain-language transaction input |
| `quick-entry-examples` | Example phrases that fill the input |
| `quick-entry-actions` | Full form and Save entry |
| `quick-entry-status` | Parse result or error |

### Wallet settings
| Field | Shows |
| :--- | :--- |
| `wallet-settings` | Settings for the selected wallet |
| `wallet-benchmark` | Benchmark used for comparisons |
| `wallet-ath-setting` | Automatic ATH or a manual ATH date and value |
| `wallet-rename` | Rename the wallet |
| `wallet-delete` | Delete the wallet |

### Transaction form
| Field | Shows |
| :--- | :--- |
| `tx-type` | Buy, Sell, Deposit, Withdrawal or Dividend |
| `tx-date` | Transaction date |
| `tx-asset-search` | Source (Yahoo Finance or Polish TFI) and asset search results |
| `tx-quantity` | Quantity with Max for sells |
| `tx-price` | Price per share and currency |
| `tx-total` | Trade value |
| `tx-advanced` | Commission and comment |
| `tx-auto-cash` | Add missing cash automatically before a buy |
| `tx-review` | Review of type, asset, quantity, value and cash effect |
| `tx-submit` | Cancel and Save |

### States
| Field | Shows |
| :--- | :--- |
| `wallets-loading` | Candle loader state |
| `wallets-empty` | No wallets yet |

## Appendix C. Screen Registry: History

Every row is a piece of information or a control that the current History screen offers (source: `src/index.html`, `src/scripts/chart.js` and `src/scripts/monthly-audit.js`). The mockup `design/mockups/history.html` must expose each one as `data-field="<field>"`, together with the Shell and Market ticker fields of Appendix A. Removing a row requires an explicit decision in Section 9.

### Overview
| Field | Shows |
| :--- | :--- |
| `history-sections` | Overview and Summaries tabs |
| `history-wallet-filter` | All wallets or a single wallet |
| `history-range` | Shared time range for every chart |
| `history-value` | Total value, gain in the range, invested capital, deposits and market gain |
| `history-value-chart` | Value over time with invested capital and deposit markers |
| `history-return-mode` | Return in % or PLN |
| `history-benchmark-series` | Benchmarks drawn next to the portfolio |
| `history-return-chart` | Cumulative return of the portfolio and benchmarks |
| `history-monthly-metric` | Monthly gain or deposits |
| `history-monthly-chart` | Monthly bars with best, worst and positive months |
| `history-daily-mode` | Daily change in % or PLN |
| `history-daily-chart` | Daily dots with best, worst, up days and the average |

### Summaries
| Field | Shows |
| :--- | :--- |
| `recap-period-type` | Monthly or yearly recaps |
| `recap-month-picker` | Month timeline with each month's return, previous and next |
| `recap-year-picker` | Year timeline with each year's return |
| `recap-share` | Share the recap |
| `recap-title` | Month and year |
| `recap-headline` | One-line verdict on the month |
| `recap-twr` | Time-weighted return for the month |
| `recap-nominal` | Nominal change, net of deposits |
| `recap-benchmarks` | Benchmark returns and the gap to each |
| `recap-commentary` | Roast commentary |
| `recap-numbers` | Three headline numbers: green sessions, carry share, best day |
| `recap-journey` | Day-by-day portfolio vs benchmark with a day slider |
| `recap-ath-status` | All-time high status in the month |
| `recap-best-worst` | Best and worst day |
| `recap-calendar` | Daily heatmap calendar |
| `recap-movers` | Holdings that moved the month most |
| `recap-goal` | Retirement goal progress |
| `recap-avco` | Realized and unrealized gains, dividends, Belka tax estimate |
| `recap-markets` | Major markets in the month |
| `recap-seasonality` | How the same month did in previous years |
| `recap-flows` | Deposits and withdrawals |
| `recap-efficiency` | Efficiency leader and profit engine |
| `recap-wallets` | Per-wallet return, deposits and change |
| `recap-trading` | Turnover, buys and sells, largest transactions |
| `recap-share-invite` | Poster preview, amounts switch, share and download |

### States
| Field | Shows |
| :--- | :--- |
| `history-loading` | Candle loader state |
| `history-empty` | No history yet |
