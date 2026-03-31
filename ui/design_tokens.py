"""
StableVault Design Token System v1.0
=====================================
Single source of truth for ALL visual tokens.
Every UI file imports from here — no hardcoded values anywhere.

Based on StableVault Design Specification:
  - Palette: #0D0E12 (bg), #1C1D22 (card), #A8E6CF (brand mint)
  - Typography: Inter, 8 sizes
  - Spacing: 4px base grid
  - Radius: 4 tiers
  - Motion: 3 tiers (micro/standard/dramatic)
"""

# ═══════════════════════════════════════════════════════════════
# COLOR TOKENS
# ═══════════════════════════════════════════════════════════════

# Backgrounds — elevation layers (darker = lower)
BG_BASE = "#0D0E12"       # Page / app background
BG_CARD = "#1C1D22"       # Cards, sidebar, panels
BG_ELEVATED = "#22242A"   # Hover states, nested cards
BG_OVERLAY = "#2C2D35"    # Modals, dropdowns, tooltips

# Brand
BRAND = "#A8E6CF"         # Primary mint green — nav active, highlights
BRAND_DIM = "rgba(168,230,207,0.10)"   # Brand tinted backgrounds
BRAND_GLOW = "rgba(168,230,207,0.25)"  # Brand hover / focus ring

# Semantic — directional (中国习惯：红涨绿跌)
UP = "#FF6B6B"            # Positive / buy / profit — 红色
UP_DIM = "rgba(255,107,107,0.10)"
UP_GLOW = "rgba(255,107,107,0.25)"

DOWN = "#4CAF50"          # Negative / sell / loss — 绿色
DOWN_DIM = "rgba(76,175,80,0.10)"
DOWN_GLOW = "rgba(76,175,80,0.25)"

WARN = "#F59E0B"          # Caution / hold / wait
WARN_DIM = "rgba(245,158,11,0.10)"
WARN_GLOW = "rgba(245,158,11,0.25)"

INFO = "#60A5FA"          # Informational / neutral accent
INFO_DIM = "rgba(96,165,250,0.10)"
INFO_GLOW = "rgba(96,165,250,0.25)"

# Text
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A0A0A0"
TEXT_MUTED = "#6B7280"
TEXT_DIM = "#4B5563"

# Borders
BORDER = "#2C2D35"
BORDER_HOVER = "#3C3D45"
BORDER_ACTIVE = BRAND

# Scores — 4D scoring system dimension colors
SCORE_MACRO = "#60A5FA"   # M dimension — blue
SCORE_SECTOR = "#A78BFA"  # S dimension — purple
SCORE_TECH = "#F472B6"    # T dimension — pink
SCORE_FUND = "#34D399"    # F dimension — emerald

# Chart palette (ordered, for multi-series)
CHART_PALETTE = [BRAND, UP, INFO, WARN, DOWN, "#A78BFA", "#F472B6", "#34D399"]


# ═══════════════════════════════════════════════════════════════
# TYPOGRAPHY TOKENS
# ═══════════════════════════════════════════════════════════════

FONT_FAMILY = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_MONO = "'JetBrains Mono', 'SF Mono', 'Fira Code', 'Menlo', monospace"

# 8-step type scale (px)
FONT_SIZE_XS = "11px"     # Footnotes, timestamps
FONT_SIZE_SM = "12px"     # Badges, labels, captions
FONT_SIZE_BASE = "14px"   # Body text, table cells
FONT_SIZE_MD = "16px"     # Section headers, nav items
FONT_SIZE_LG = "20px"     # Card titles, sub-headings
FONT_SIZE_XL = "24px"     # Page titles
FONT_SIZE_2XL = "32px"    # Hero numbers
FONT_SIZE_3XL = "40px"    # Splash / loading logo

# Weights
FONT_REGULAR = "400"
FONT_MEDIUM = "500"
FONT_SEMIBOLD = "600"
FONT_BOLD = "700"

# Line heights
LINE_HEIGHT_TIGHT = "1.2"
LINE_HEIGHT_NORMAL = "1.5"
LINE_HEIGHT_RELAXED = "1.75"


# ═══════════════════════════════════════════════════════════════
# SPACING TOKENS — 4px base grid
# ═══════════════════════════════════════════════════════════════

SP_1 = "4px"
SP_2 = "8px"
SP_3 = "12px"
SP_4 = "16px"      # Base unit
SP_5 = "20px"
SP_6 = "24px"      # Section gap
SP_8 = "32px"      # Large gap
SP_10 = "40px"     # Page padding
SP_12 = "48px"


# ═══════════════════════════════════════════════════════════════
# BORDER RADIUS — 4 tiers
# ═══════════════════════════════════════════════════════════════

RADIUS_SM = "6px"    # Badges, small elements
RADIUS_MD = "10px"   # Buttons, inputs
RADIUS_LG = "14px"   # Cards, panels
RADIUS_XL = "20px"   # Modals, large containers
RADIUS_FULL = "9999px"  # Pills, dots


# ═══════════════════════════════════════════════════════════════
# SHADOWS — elevation system
# ═══════════════════════════════════════════════════════════════

SHADOW_SM = "0 1px 3px rgba(0,0,0,0.12)"
SHADOW_MD = "0 4px 12px rgba(0,0,0,0.16)"
SHADOW_LG = "0 8px 24px rgba(0,0,0,0.20)"
SHADOW_XL = "0 16px 40px rgba(0,0,0,0.25)"
SHADOW_GLOW_BRAND = f"0 0 20px {BRAND_DIM}"
SHADOW_GLOW_UP = f"0 0 20px {UP_DIM}"
SHADOW_GLOW_DOWN = f"0 0 20px {DOWN_DIM}"


# ═══════════════════════════════════════════════════════════════
# MOTION — 3 tiers
# ═══════════════════════════════════════════════════════════════

DURATION_MICRO = "0.15s"   # Hover, focus, opacity
DURATION_STANDARD = "0.3s" # Expand, slide, fade-in
DURATION_DRAMATIC = "0.6s" # Page transitions, loading

EASE_DEFAULT = "cubic-bezier(0.4, 0, 0.2, 1)"
EASE_BOUNCE = "cubic-bezier(0.34, 1.56, 0.64, 1)"
EASE_DECEL = "cubic-bezier(0, 0, 0.2, 1)"
EASE_ELASTIC = "cubic-bezier(0.68, -0.55, 0.27, 1.55)"  # Time picker slider

# Specific animation durations (from spec)
DURATION_LOGO_FADE = "0.5s"      # Logo intro fade-in
DURATION_LOGO_MOVE = "0.4s"      # Logo move to sidebar
DURATION_CHART_DRAW = "1.5s"     # K-line / SVG chart drawing
DURATION_DOUGHNUT = "1.2s"       # Doughnut ring expansion
DURATION_COUNTUP = "1.5s"        # Number count-up scroll
DURATION_LIST_ITEM = "0.3s"      # Per-item list slide-in
DURATION_CLICK = "0.1s"          # Button click feedback
DURATION_WATERFALL_DELAY = "0.08s"  # Per-card stagger delay

# Interaction constants
BUTTON_CLICK_SCALE = "0.98"      # Button press shrink
CARD_HOVER_BRIGHTNESS = "1.02"   # Card hover +2% brightness
CARD_HOVER_LIFT = "-2px"         # Card hover Y translation
FOCUS_GLOW_SPREAD = "4px"        # Input focus ring spread


# ═══════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════

SIDEBAR_WIDTH = "240px"
SIDEBAR_COLLAPSED = "64px"
CONTENT_MAX_WIDTH = "1400px"
CARD_MIN_WIDTH = "280px"


# ═══════════════════════════════════════════════════════════════
# COMPONENT PRESETS — reusable style dicts for st.markdown HTML
# ═══════════════════════════════════════════════════════════════

def score_color(score: float) -> str:
    """Return semantic color based on score value (0-100)."""
    if score >= 70:
        return UP
    elif score >= 40:
        return WARN
    else:
        return DOWN


def verdict_style(verdict: str) -> dict:
    """Return color + bg for a verdict string."""
    v = verdict.lower()
    if "买" in v or "buy" in v or "加" in v:
        return {"color": UP, "bg": UP_DIM, "border": UP_GLOW}
    elif "卖" in v or "sell" in v or "减" in v:
        return {"color": DOWN, "bg": DOWN_DIM, "border": DOWN_GLOW}
    else:
        return {"color": WARN, "bg": WARN_DIM, "border": WARN_GLOW}


def dim_color(key: str) -> str:
    """Return 4D dimension color by key letter."""
    return {
        "M": SCORE_MACRO,
        "S": SCORE_SECTOR,
        "T": SCORE_TECH,
        "F": SCORE_FUND,
    }.get(key.upper(), INFO)


# ═══════════════════════════════════════════════════════════════
# CSS VARIABLE BLOCK — inject into Streamlit via st.markdown
# ═══════════════════════════════════════════════════════════════

CSS_VARIABLES = f"""
:root {{
    /* Backgrounds */
    --bg-base: {BG_BASE};
    --bg-card: {BG_CARD};
    --bg-elevated: {BG_ELEVATED};
    --bg-overlay: {BG_OVERLAY};

    /* Brand */
    --brand: {BRAND};
    --brand-dim: {BRAND_DIM};
    --brand-glow: {BRAND_GLOW};

    /* Semantic */
    --up: {UP};
    --up-dim: {UP_DIM};
    --up-glow: {UP_GLOW};
    --down: {DOWN};
    --down-dim: {DOWN_DIM};
    --down-glow: {DOWN_GLOW};
    --warn: {WARN};
    --warn-dim: {WARN_DIM};
    --warn-glow: {WARN_GLOW};
    --info: {INFO};
    --info-dim: {INFO_DIM};
    --info-glow: {INFO_GLOW};

    /* Text */
    --text-primary: {TEXT_PRIMARY};
    --text-secondary: {TEXT_SECONDARY};
    --text-muted: {TEXT_MUTED};
    --text-dim: {TEXT_DIM};

    /* Borders */
    --border: {BORDER};
    --border-hover: {BORDER_HOVER};
    --border-active: {BORDER_ACTIVE};

    /* Score dimensions */
    --score-macro: {SCORE_MACRO};
    --score-sector: {SCORE_SECTOR};
    --score-tech: {SCORE_TECH};
    --score-fund: {SCORE_FUND};

    /* Typography */
    --font-family: {FONT_FAMILY};
    --font-mono: {FONT_MONO};
    --font-xs: {FONT_SIZE_XS};
    --font-sm: {FONT_SIZE_SM};
    --font-base: {FONT_SIZE_BASE};
    --font-md: {FONT_SIZE_MD};
    --font-lg: {FONT_SIZE_LG};
    --font-xl: {FONT_SIZE_XL};
    --font-2xl: {FONT_SIZE_2XL};
    --font-3xl: {FONT_SIZE_3XL};

    /* Spacing */
    --sp-1: {SP_1};
    --sp-2: {SP_2};
    --sp-3: {SP_3};
    --sp-4: {SP_4};
    --sp-5: {SP_5};
    --sp-6: {SP_6};
    --sp-8: {SP_8};
    --sp-10: {SP_10};
    --sp-12: {SP_12};

    /* Radius */
    --radius-sm: {RADIUS_SM};
    --radius-md: {RADIUS_MD};
    --radius-lg: {RADIUS_LG};
    --radius-xl: {RADIUS_XL};
    --radius-full: {RADIUS_FULL};

    /* Shadows */
    --shadow-sm: {SHADOW_SM};
    --shadow-md: {SHADOW_MD};
    --shadow-lg: {SHADOW_LG};
    --shadow-xl: {SHADOW_XL};

    /* Motion */
    --duration-micro: {DURATION_MICRO};
    --duration-standard: {DURATION_STANDARD};
    --duration-dramatic: {DURATION_DRAMATIC};
    --ease-default: {EASE_DEFAULT};
    --ease-bounce: {EASE_BOUNCE};
    --ease-decel: {EASE_DECEL};

    /* Layout */
    --sidebar-width: {SIDEBAR_WIDTH};
    --content-max-width: {CONTENT_MAX_WIDTH};

    /* Interaction */
    --btn-click-scale: {BUTTON_CLICK_SCALE};
    --card-hover-brightness: {CARD_HOVER_BRIGHTNESS};
    --card-hover-lift: {CARD_HOVER_LIFT};
    --focus-glow-spread: {FOCUS_GLOW_SPREAD};
    --duration-click: {DURATION_CLICK};
    --duration-chart-draw: {DURATION_CHART_DRAW};
    --duration-doughnut: {DURATION_DOUGHNUT};
    --duration-countup: {DURATION_COUNTUP};
    --duration-list-item: {DURATION_LIST_ITEM};
    --waterfall-delay: {DURATION_WATERFALL_DELAY};
    --ease-elastic: {EASE_ELASTIC};
}}
"""


# ═══════════════════════════════════════════════════════════════
# REUSABLE ANIMATION CSS — inject alongside CSS_VARIABLES
# ═══════════════════════════════════════════════════════════════

CSS_ANIMATIONS = """
/* ═══════════ LOADING SEQUENCE ═══════════ */
@keyframes sv-logo-fade {
    from { opacity: 0; transform: translateY(-10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes sv-logo-move {
    from { transform: translate(-50%, -50%) scale(1.5); opacity: 1; }
    to   { transform: translate(0, 0) scale(1); opacity: 1; }
}
@keyframes sv-spinner {
    to { transform: rotate(360deg); }
}
@keyframes sv-loading-hide {
    to { opacity: 0; pointer-events: none; }
}

/* ═══════════ WATERFALL ENTRY ═══════════ */
@keyframes sv-waterfall {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ═══════════ SIDEBAR SLIDE-IN ═══════════ */
@keyframes sv-sidebar-in {
    from { opacity: 0; transform: translateX(-20px); }
    to   { opacity: 1; transform: translateX(0); }
}

/* ═══════════ NUMBER COUNT-UP (CSS fallback) ═══════════ */
@keyframes sv-countup-flash {
    0%   { color: var(--brand); }
    100% { color: var(--text-primary); }
}

/* ═══════════ CHART DRAW — SVG stroke ═══════════ */
@keyframes sv-stroke-draw {
    from { stroke-dashoffset: var(--path-length, 1000); }
    to   { stroke-dashoffset: 0; }
}

/* ═══════════ DOUGHNUT EXPAND ═══════════ */
@keyframes sv-doughnut-expand {
    from { stroke-dasharray: 0 999; }
    to   { stroke-dasharray: var(--segment-length, 100) 999; }
}

/* ═══════════ LIST ITEM SLIDE-IN ═══════════ */
@keyframes sv-list-in {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ═══════════ PRICE FLASH ═══════════ */
@keyframes sv-flash-up {
    0%   { background-color: transparent; }
    20%  { background-color: var(--up-dim); }
    100% { background-color: transparent; }
}
@keyframes sv-flash-down {
    0%   { background-color: transparent; }
    20%  { background-color: var(--down-dim); }
    100% { background-color: transparent; }
}

/* ═══════════ PULSE (status dots) ═══════════ */
@keyframes sv-pulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.4; }
}

/* ═══════════ BUTTON INTERACTIONS ═══════════ */
.sv-btn-primary {
    background: var(--brand);
    color: var(--bg-base);
    border: none;
    padding: var(--sp-2) var(--sp-4);
    border-radius: var(--radius-md);
    font-weight: 600;
    font-size: var(--font-base);
    cursor: pointer;
    transition: all var(--duration-micro) var(--ease-default);
}
.sv-btn-primary:hover {
    filter: brightness(1.05);
    box-shadow: 0 0 12px var(--brand-glow);
}
.sv-btn-primary:active {
    transform: scale(var(--btn-click-scale));
    transition-duration: var(--duration-click);
}

.sv-btn-ghost {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
    padding: var(--sp-2) var(--sp-4);
    border-radius: var(--radius-md);
    font-weight: 500;
    font-size: var(--font-base);
    cursor: pointer;
    transition: all var(--duration-micro) var(--ease-default);
}
.sv-btn-ghost:hover {
    border-color: var(--brand);
    color: var(--text-primary);
    background: var(--brand-dim);
}
.sv-btn-ghost:active {
    transform: scale(var(--btn-click-scale));
    transition-duration: var(--duration-click);
}

/* ═══════════ INPUT FOCUS ═══════════ */
.sv-input-focus:focus {
    border-color: var(--brand) !important;
    box-shadow: 0 0 0 var(--focus-glow-spread) var(--brand-dim) !important;
    outline: none;
    transition: all var(--duration-micro) var(--ease-default);
}

/* ═══════════ NAV ITEM STATES ═══════════ */
.sv-nav-item {
    display: flex;
    align-items: center;
    gap: var(--sp-3);
    padding: var(--sp-3) var(--sp-4);
    margin-bottom: var(--sp-2);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--font-base);
    color: var(--text-secondary);
    border-left: 3px solid transparent;
    transition: all 0.2s ease;
    position: relative;
}
.sv-nav-item:hover {
    color: var(--text-primary);
    background: var(--bg-elevated);
}
.sv-nav-item.active {
    color: var(--brand);
    background: var(--brand-dim);
    border-left-color: var(--brand);
    font-weight: 600;
}

/* ═══════════ TIME PICKER SLIDER ═══════════ */
.sv-time-picker {
    display: inline-flex;
    background: var(--bg-elevated);
    border-radius: var(--radius-md);
    padding: 2px;
    border: 1px solid var(--border);
    position: relative;
}
.sv-time-option {
    padding: var(--sp-1) var(--sp-3);
    border-radius: var(--radius-sm);
    font-size: var(--font-sm);
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55);
    z-index: 1;
    position: relative;
}
.sv-time-option.active {
    color: var(--bg-base);
    background: var(--brand);
}
.sv-time-option:hover:not(.active) {
    color: var(--text-primary);
}

/* ═══════════ CARD HOVER (universal) ═══════════ */
.sv-card-hover {
    transition: all var(--duration-micro) var(--ease-default);
}
.sv-card-hover:hover {
    filter: brightness(var(--card-hover-brightness));
    transform: translateY(var(--card-hover-lift));
    box-shadow: var(--shadow-md);
}

/* ═══════════ WATERFALL STAGGER CLASSES ═══════════ */
.sv-wf { animation: sv-waterfall var(--duration-standard) var(--ease-decel) forwards; opacity: 0; }
.sv-wf:nth-child(1)  { animation-delay: calc(var(--waterfall-delay) * 1); }
.sv-wf:nth-child(2)  { animation-delay: calc(var(--waterfall-delay) * 2); }
.sv-wf:nth-child(3)  { animation-delay: calc(var(--waterfall-delay) * 3); }
.sv-wf:nth-child(4)  { animation-delay: calc(var(--waterfall-delay) * 4); }
.sv-wf:nth-child(5)  { animation-delay: calc(var(--waterfall-delay) * 5); }
.sv-wf:nth-child(6)  { animation-delay: calc(var(--waterfall-delay) * 6); }
.sv-wf:nth-child(7)  { animation-delay: calc(var(--waterfall-delay) * 7); }
.sv-wf:nth-child(8)  { animation-delay: calc(var(--waterfall-delay) * 8); }
.sv-wf:nth-child(9)  { animation-delay: calc(var(--waterfall-delay) * 9); }
.sv-wf:nth-child(10) { animation-delay: calc(var(--waterfall-delay) * 10); }

/* ═══════════ LIST STAGGER ═══════════ */
.sv-list-item { animation: sv-list-in var(--duration-list-item) var(--ease-decel) forwards; opacity: 0; }
.sv-list-item:nth-child(1)  { animation-delay: 0.05s; }
.sv-list-item:nth-child(2)  { animation-delay: 0.10s; }
.sv-list-item:nth-child(3)  { animation-delay: 0.15s; }
.sv-list-item:nth-child(4)  { animation-delay: 0.20s; }
.sv-list-item:nth-child(5)  { animation-delay: 0.25s; }
.sv-list-item:nth-child(6)  { animation-delay: 0.30s; }
.sv-list-item:nth-child(7)  { animation-delay: 0.35s; }
.sv-list-item:nth-child(8)  { animation-delay: 0.40s; }
.sv-list-item:nth-child(9)  { animation-delay: 0.45s; }
.sv-list-item:nth-child(10) { animation-delay: 0.50s; }

/* ═══════════ PRICE FLASH CLASSES ═══════════ */
.sv-flash-up   { animation: sv-flash-up 0.8s ease; }
.sv-flash-down { animation: sv-flash-down 0.8s ease; }

/* ═══════════ SVG CHART DRAW ═══════════ */
.sv-chart-line {
    stroke-dasharray: var(--path-length, 1000);
    stroke-dashoffset: var(--path-length, 1000);
    animation: sv-stroke-draw var(--duration-chart-draw) ease-out forwards;
}
.sv-doughnut-segment {
    animation: sv-doughnut-expand var(--duration-doughnut) ease-in-out forwards;
}
"""


# ═══════════════════════════════════════════════════════════════
# NUMBER COUNT-UP — JavaScript snippet for st.markdown injection
# ═══════════════════════════════════════════════════════════════

JS_COUNTUP = """
<script>
(function(){
  // Auto-detect elements with data-countup attribute
  document.querySelectorAll('[data-countup]').forEach(function(el){
    var target = parseFloat(el.getAttribute('data-countup'));
    var prefix = el.getAttribute('data-prefix') || '';
    var suffix = el.getAttribute('data-suffix') || '';
    var decimals = parseInt(el.getAttribute('data-decimals') || '0');
    var duration = parseFloat(el.getAttribute('data-duration') || '1.5') * 1000;
    var start = 0;
    var startTime = null;
    function step(ts){
      if(!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      // ease-out quad
      var eased = 1 - (1 - progress) * (1 - progress);
      var current = start + (target - start) * eased;
      el.textContent = prefix + current.toLocaleString('zh-CN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      }) + suffix;
      if(progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
})();
</script>
"""


# ═══════════════════════════════════════════════════════════════
# LOADING OVERLAY — HTML snippet for st.markdown injection
# ═══════════════════════════════════════════════════════════════

LOADING_OVERLAY_HTML = f"""
<div id="sv-loading" style="
    position:fixed; top:0; left:0; width:100%; height:100%;
    background:{BG_BASE}; display:flex; flex-direction:column;
    align-items:center; justify-content:center; z-index:9999;
    transition: opacity 0.6s ease-out;
">
    <div style="font-size:32px; font-weight:700; color:{TEXT_PRIMARY};
         animation: sv-logo-fade 0.5s ease-out forwards; opacity:0;">
        Stable<span style='color:{BRAND};'>Vault</span>
    </div>
    <div style="width:40px; height:40px; border:2px solid {BORDER};
         border-top-color:{BRAND}; border-radius:50%;
         animation: sv-spinner 1s linear infinite; margin-top:20px;">
    </div>
</div>
<script>
setTimeout(function(){{
    var el = document.getElementById('sv-loading');
    if(el){{ el.style.opacity='0'; setTimeout(function(){{ el.remove(); }}, 600); }}
}}, 2400);
</script>
"""
