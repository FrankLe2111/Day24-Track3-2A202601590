"""Design system cho demo app: palette, CSS, plotly template, UI components.

Palette là bản dark đã được validate (CVD-safe adjacent pairs, contrast ≥ 3:1
trên surface #1a1a19). Muốn đổi sang brand khác: thay giá trị trong khối
"Tokens" bên dưới, không cần sửa gì khác.
"""

from __future__ import annotations

import html
import re

import streamlit as st

# ── Tokens ───────────────────────────────────────────────────────────────────

PAGE = "#0d0d0d"        # page plane
SURFACE = "#1a1a19"     # chart / card surface
SURFACE_HI = "#232322"  # elevated surface
INK = "#ffffff"         # primary ink
INK_2 = "#c3c2b7"       # secondary ink
MUTED = "#898781"       # axis / labels
GRID = "#2c2c2a"        # hairline gridline
BASELINE = "#383835"    # baseline / axis rule
BORDER = "rgba(255,255,255,0.10)"

# Categorical slots — thứ tự cố định, không bao giờ cycle.
SERIES = [
    "#3987e5",  # 1 blue
    "#d95926",  # 2 orange
    "#199e70",  # 3 aqua
    "#c98500",  # 4 yellow
    "#d55181",  # 5 magenta
    "#008300",  # 6 green
    "#9085e9",  # 7 violet
    "#e66767",  # 8 red
]

# Status — dành riêng, không dùng làm màu series.
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"

# Sequential: một hue (blue), trên surface tối thì "gần 0" là bước tối nhất.
SEQ_BLUE = [
    "#0d366b", "#104281", "#184f95", "#1c5cab", "#256abf",
    "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef",
]

FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
MONO = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'

# ── Domain vocabulary ────────────────────────────────────────────────────────

DISTRIBUTIONS = ["factual", "multi_hop", "adversarial"]
DIST_LABEL = {"factual": "Factual", "multi_hop": "Multi-hop", "adversarial": "Adversarial"}
# Màu đi theo entity (distribution), không đi theo rank — filter không đổi màu.
DIST_COLOR = {"factual": SERIES[0], "multi_hop": SERIES[1], "adversarial": SERIES[2]}

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
METRIC_LABEL = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer relevancy",
    "context_precision": "Context precision",
    "context_recall": "Context recall",
}

CATEGORY_LABEL = {
    "pii_injection": "PII injection",
    "jailbreak": "Jailbreak",
    "off_topic": "Off-topic",
    "prompt_injection": "Prompt injection",
}

# Thang Landis–Koch cho Cohen's κ.
KAPPA_BANDS = [
    (-1.0, 0.0, "Poor"),
    (0.0, 0.20, "Slight"),
    (0.20, 0.40, "Fair"),
    (0.40, 0.60, "Moderate"),
    (0.60, 0.80, "Substantial"),
    (0.80, 1.0, "Almost perfect"),
]

# ── Streamlit version shims ──────────────────────────────────────────────────

_V = tuple(int(x) for x in (re.findall(r"\d+", st.__version__) + ["0", "0"])[:2])


def stretch() -> dict:
    """Kwargs "chiếm hết chiều ngang container", tương thích nhiều version."""
    return {"width": "stretch"} if _V >= (1, 49) else {"use_container_width": True}


def rerun() -> None:
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn is not None:
        fn()


def flash(message: str, kind: str = "success") -> None:
    """Nhớ một thông báo để hiện sau khi rerun."""
    st.session_state["l24_flash"] = (kind, message)


def show_flash() -> None:
    payload = st.session_state.pop("l24_flash", None)
    if payload:
        kind, message = payload
        getattr(st, kind, st.info)(message)


# ── CSS ──────────────────────────────────────────────────────────────────────

_CSS = f"""
<style>
:root {{
  --l24-page: {PAGE};
  --l24-surface: {SURFACE};
  --l24-surface-hi: {SURFACE_HI};
  --l24-ink: {INK};
  --l24-ink-2: {INK_2};
  --l24-muted: {MUTED};
  --l24-border: {BORDER};
  --l24-grid: {GRID};
  --l24-accent: {SERIES[0]};
  --l24-good: {GOOD};
  --l24-warning: {WARNING};
  --l24-serious: {SERIOUS};
  --l24-critical: {CRITICAL};
}}

html, body, [class*="css"] {{ font-family: {FONT}; }}

/* Bớt khoảng trắng mặc định phía trên, giữ padding hai bên thoáng */
.block-container {{ padding-top: 1.6rem; padding-bottom: 4rem; max-width: 1360px; }}
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; height: 0; }}

section[data-testid="stSidebar"] {{
  background: var(--l24-page);
  border-right: 1px solid var(--l24-border);
}}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}

/* ── Page header ── */
.l24-head {{ margin: 0 0 1.4rem; }}
.l24-eyebrow {{
  font-size: .72rem; letter-spacing: .14em; text-transform: uppercase;
  color: var(--l24-muted); font-weight: 600;
}}
.l24-title {{
  font-size: 1.9rem; font-weight: 650; line-height: 1.15;
  color: var(--l24-ink); margin: .35rem 0 .4rem;
}}
.l24-sub {{ font-size: .93rem; color: var(--l24-ink-2); max-width: 76ch; line-height: 1.5; }}
.l24-rule {{
  height: 1px; margin: 1.1rem 0 0;
  background: linear-gradient(90deg, {SERIES[0]}, {SERIES[2]} 38%, transparent 78%);
  opacity: .55;
}}

/* ── Section ── */
.l24-sec {{ margin: 2.1rem 0 .9rem; }}
.l24-sec h3 {{
  font-size: 1.02rem; font-weight: 620; color: var(--l24-ink);
  margin: 0; letter-spacing: -.01em;
}}
.l24-sec p {{ font-size: .84rem; color: var(--l24-muted); margin: .25rem 0 0; }}

/* ── Card / KPI ── */
.l24-card {{
  background: var(--l24-surface); border: 1px solid var(--l24-border);
  border-radius: 14px; padding: 16px 18px;
}}
.l24-kpi {{
  background: var(--l24-surface); border: 1px solid var(--l24-border);
  border-radius: 14px; padding: 15px 17px 13px; height: 100%;
}}
.l24-kpi-head {{
  display: flex; align-items: center; justify-content: space-between; gap: .5rem;
  margin-bottom: .45rem;
}}
.l24-kpi-label {{
  font-size: .74rem; letter-spacing: .06em; text-transform: uppercase;
  color: var(--l24-muted); font-weight: 600;
}}
.l24-kpi-value {{
  font-size: 2rem; font-weight: 600; line-height: 1.05; color: var(--l24-ink);
  font-variant-numeric: proportional-nums;
}}
.l24-kpi-unit {{ font-size: .95rem; color: var(--l24-ink-2); font-weight: 500; margin-left: .15rem; }}
.l24-kpi-foot {{ font-size: .78rem; color: var(--l24-muted); margin-top: .45rem; }}
.l24-meter {{
  height: 3px; border-radius: 2px; background: var(--l24-grid);
  margin-top: .7rem; overflow: hidden;
}}
.l24-meter > span {{ display: block; height: 100%; border-radius: 2px; }}

/* ── Badge / chip ── */
.l24-badge {{
  display: inline-flex; align-items: center; gap: .35rem; white-space: nowrap;
  font-size: .7rem; font-weight: 650; letter-spacing: .04em;
  padding: .2rem .5rem; border-radius: 999px;
  border: 1px solid var(--l24-border); background: rgba(255,255,255,.03);
}}
.l24-dot {{ width: 7px; height: 7px; border-radius: 50%; flex: 0 0 7px; }}
.l24-chip {{
  display: inline-flex; align-items: center; gap: .4rem;
  font-size: .76rem; color: var(--l24-ink-2);
  padding: .28rem .6rem; border-radius: 8px;
  border: 1px solid var(--l24-border); background: var(--l24-surface);
}}
.l24-chip code {{ font-family: {MONO}; font-size: .72rem; color: var(--l24-ink-2); }}

/* ── Gate row ── */
.l24-gate {{
  display: flex; align-items: center; gap: .75rem;
  padding: .7rem .2rem; border-bottom: 1px solid var(--l24-border);
}}
.l24-gate:last-child {{ border-bottom: none; }}
.l24-gate-name {{ flex: 1 1 auto; font-size: .88rem; color: var(--l24-ink); }}
.l24-gate-name small {{ display: block; color: var(--l24-muted); font-size: .76rem; margin-top: .12rem; }}
.l24-gate-val {{
  font-family: {MONO}; font-size: .84rem; color: var(--l24-ink-2);
  font-variant-numeric: tabular-nums; text-align: right; min-width: 7.5rem;
}}

/* ── Guard stack flow ── */
.l24-flow {{ display: flex; gap: 10px; flex-wrap: wrap; }}
.l24-node {{
  flex: 1 1 190px; background: var(--l24-surface); border: 1px solid var(--l24-border);
  border-radius: 12px; padding: 13px 15px; position: relative;
}}
.l24-node::before {{
  content: ""; position: absolute; left: 15px; right: 15px; top: 0; height: 2px;
  border-radius: 0 0 2px 2px; background: var(--l24-accent);
}}
.l24-node .n {{ font-size: .7rem; color: var(--l24-muted); font-weight: 650; letter-spacing: .08em; }}
.l24-node .t {{ font-size: .92rem; color: var(--l24-ink); font-weight: 600; margin: .3rem 0 .18rem; }}
.l24-node .d {{ font-size: .76rem; color: var(--l24-muted); line-height: 1.45; }}
.l24-node .m {{
  font-family: {MONO}; font-size: .74rem; color: var(--l24-ink-2);
  margin-top: .5rem; font-variant-numeric: tabular-nums;
}}

/* ── Empty state ── */
.l24-empty {{
  background: var(--l24-surface); border: 1px dashed rgba(255,255,255,.14);
  border-radius: 14px; padding: 26px 24px; text-align: center;
}}
.l24-empty .i {{ font-size: 1.5rem; opacity: .8; }}
.l24-empty .t {{ font-size: .96rem; color: var(--l24-ink); font-weight: 600; margin: .5rem 0 .3rem; }}
.l24-empty .d {{ font-size: .84rem; color: var(--l24-muted); line-height: 1.55; max-width: 62ch; margin: 0 auto; }}
.l24-empty code {{
  font-family: {MONO}; font-size: .8rem; color: var(--l24-ink-2);
  background: rgba(255,255,255,.05); padding: .1rem .35rem; border-radius: 5px;
}}

/* ── Callout ── */
.l24-note {{
  border-left: 2px solid var(--l24-accent); border-radius: 0 10px 10px 0;
  background: rgba(57,135,229,.07); padding: 12px 15px;
  font-size: .86rem; color: var(--l24-ink-2); line-height: 1.55;
}}
.l24-note.warn {{ border-left-color: var(--l24-warning); background: rgba(250,178,25,.07); }}
.l24-note.bad {{ border-left-color: var(--l24-critical); background: rgba(208,59,59,.08); }}
.l24-note b {{ color: var(--l24-ink); font-weight: 620; }}

/* ── PII highlight / text blocks ── */
.l24-text {{
  font-family: {MONO}; font-size: .84rem; line-height: 1.75; color: var(--l24-ink-2);
  background: var(--l24-surface); border: 1px solid var(--l24-border);
  border-radius: 10px; padding: 13px 15px; white-space: pre-wrap; word-break: break-word;
}}
.l24-pii {{
  background: rgba(208,59,59,.22); border-bottom: 2px solid var(--l24-critical);
  border-radius: 3px; padding: 0 2px; color: var(--l24-ink);
}}
.l24-redact {{ color: var(--l24-good); font-weight: 650; }}

/* ── Layer timeline ── */
.l24-layer {{
  display: flex; align-items: flex-start; gap: .8rem; padding: .65rem .1rem;
  border-bottom: 1px solid var(--l24-border);
}}
.l24-layer:last-child {{ border-bottom: none; }}
.l24-layer .ico {{
  width: 22px; height: 22px; border-radius: 50%; flex: 0 0 22px;
  display: flex; align-items: center; justify-content: center;
  font-size: .72rem; font-weight: 700; color: {PAGE};
}}
.l24-layer .body {{ flex: 1 1 auto; }}
.l24-layer .name {{ font-size: .87rem; color: var(--l24-ink); font-weight: 580; }}
.l24-layer .why {{ font-size: .78rem; color: var(--l24-muted); margin-top: .15rem; line-height: 1.45; }}
.l24-layer .ms {{
  font-family: {MONO}; font-size: .78rem; color: var(--l24-ink-2);
  font-variant-numeric: tabular-nums; white-space: nowrap;
}}

/* ── Kappa band strip ── */
.l24-band {{ display: flex; gap: 2px; margin: .55rem 0 .3rem; }}
.l24-band > div {{ flex: 1 1 0; height: 8px; border-radius: 2px; }}
.l24-band-lbl {{ display: flex; gap: 2px; }}
.l24-band-lbl > div {{
  flex: 1 1 0; font-size: .66rem; color: var(--l24-muted);
  text-align: center; letter-spacing: -.01em;
}}
.l24-band-lbl > div.on {{ color: var(--l24-ink); font-weight: 650; }}

/* ── 2x2 matrix ── */
.l24-mx {{ display: grid; grid-template-columns: auto 1fr 1fr; gap: 4px; }}
.l24-mx .h {{
  font-size: .72rem; color: var(--l24-muted); text-transform: uppercase;
  letter-spacing: .06em; padding: .3rem .4rem; align-self: end;
}}
.l24-mx .c {{
  border-radius: 10px; padding: 14px 12px; text-align: center;
  border: 1px solid var(--l24-border);
}}
.l24-mx .c .v {{ font-size: 1.4rem; font-weight: 620; color: var(--l24-ink); }}
.l24-mx .c .k {{ font-size: .7rem; color: var(--l24-ink-2); margin-top: .18rem; }}

/* ── Streamlit widget polish ── */
.stTabs [data-baseweb="tab-list"] {{ gap: 1.4rem; border-bottom: 1px solid var(--l24-border); }}
.stTabs [data-baseweb="tab"] {{ padding: .5rem 0; font-size: .88rem; }}
div[data-testid="stExpander"] details {{
  border: 1px solid var(--l24-border); border-radius: 12px; background: var(--l24-surface);
}}
div[data-testid="stDataFrame"] {{ border: 1px solid var(--l24-border); border-radius: 12px; }}
.stButton > button {{
  border-radius: 9px; border: 1px solid var(--l24-border); font-weight: 580;
  font-size: .85rem; padding: .42rem 1rem;
}}
.stDownloadButton > button {{ border-radius: 9px; font-size: .85rem; }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Components ───────────────────────────────────────────────────────────────


def esc(text: object) -> str:
    """Escape trước khi nhúng vào HTML — nội dung corpus/user có thể chứa <, &, ."""
    return html.escape(str(text if text is not None else ""))


def page_head(eyebrow: str, title: str, sub: str = "") -> None:
    st.markdown(
        f'<div class="l24-head"><div class="l24-eyebrow">{eyebrow}</div>'
        f'<div class="l24-title">{title}</div>'
        f'<div class="l24-sub">{sub}</div><div class="l24-rule"></div></div>',
        unsafe_allow_html=True,
    )


def section(title: str, sub: str = "") -> None:
    st.markdown(
        f'<div class="l24-sec"><h3>{title}</h3>'
        + (f"<p>{sub}</p>" if sub else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def badge(label: str, color: str) -> str:
    """Status chip: luôn có dot + text, không bao giờ chỉ dựa vào màu."""
    return (
        f'<span class="l24-badge" style="color:{color}">'
        f'<span class="l24-dot" style="background:{color}"></span>{label}</span>'
    )


def kpi(
    label: str,
    value: str,
    unit: str = "",
    foot: str = "",
    status: str | None = None,
    status_label: str = "",
    meter: float | None = None,
) -> None:
    """Stat tile — dùng khi câu chuyện là MỘT con số (không vẽ chart 1 cột)."""
    chip = badge(status_label, status) if status and status_label else ""
    bar = ""
    if meter is not None:
        pct = max(0.0, min(1.0, meter)) * 100
        bar = (
            f'<div class="l24-meter"><span style="width:{pct:.1f}%;'
            f'background:{status or SERIES[0]}"></span></div>'
        )
    st.markdown(
        f'<div class="l24-kpi"><div class="l24-kpi-head">'
        f'<span class="l24-kpi-label">{label}</span>{chip}</div>'
        f'<div class="l24-kpi-value">{value}<span class="l24-kpi-unit">{unit}</span></div>'
        f'<div class="l24-kpi-foot">{foot}</div>{bar}</div>',
        unsafe_allow_html=True,
    )


def gate(name: str, hint: str, value: str, status: str, status_label: str) -> str:
    return (
        f'<div class="l24-gate"><span class="l24-dot" style="background:{status}"></span>'
        f'<span class="l24-gate-name">{name}<small>{hint}</small></span>'
        f'<span class="l24-gate-val">{value}</span>'
        f'{badge(status_label, status)}</div>'
    )


def empty_state(title: str, detail: str, icon: str = "○") -> None:
    st.markdown(
        f'<div class="l24-empty"><div class="i">{icon}</div>'
        f'<div class="t">{title}</div><div class="d">{detail}</div></div>',
        unsafe_allow_html=True,
    )


def note(text: str, kind: str = "info") -> None:
    cls = {"info": "", "warn": " warn", "bad": " bad"}.get(kind, "")
    st.markdown(f'<div class="l24-note{cls}">{text}</div>', unsafe_allow_html=True)


def card(html: str) -> None:
    st.markdown(f'<div class="l24-card">{html}</div>', unsafe_allow_html=True)


def score_status(value: float, gate_value: float) -> tuple[str, str]:
    """Map điểm → (màu status, nhãn). Luôn trả cả nhãn để không dựa vào màu."""
    if value >= gate_value:
        return GOOD, "PASS"
    if value >= gate_value - 0.10:
        return WARNING, "NEAR"
    return CRITICAL, "FAIL"


# Màu cho nguồn dữ liệu — xanh = số thật, vàng = mẫu/mô phỏng, xám = chưa có.
SOURCE_COLOR = {"live": GOOD, "report": GOOD, "sim": WARNING, "sample": WARNING, "none": MUTED}


def source_color(kind: str) -> str:
    return SOURCE_COLOR.get(kind, MUTED)


def source_chip(source, extra: str = "") -> None:
    """Chip "Nguồn: …" dùng ở đầu mỗi trang."""
    st.markdown(
        f'<div style="display:flex;gap:.45rem;flex-wrap:wrap;margin:-.4rem 0 1rem">'
        f'<span class="l24-chip"><span class="l24-dot" style="background:'
        f'{source_color(source.kind)}"></span>Nguồn: {source.label}</span>'
        + (f'<span class="l24-chip">{extra}</span>' if extra else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def kappa_band(kappa: float) -> str:
    """Thang Landis–Koch: ordinal ramp + marker vị trí κ hiện tại."""
    steps = ["#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#86b6ef"]
    active = next(
        (i for i, (lo, hi, _) in enumerate(KAPPA_BANDS) if lo <= kappa < hi),
        len(KAPPA_BANDS) - 1,
    )
    bars, labels = [], []
    for i, (_, _, name) in enumerate(KAPPA_BANDS):
        opacity = "1" if i == active else ".38"
        bars.append(f'<div style="background:{steps[i]};opacity:{opacity}"></div>')
        labels.append(f'<div class="{"on" if i == active else ""}">{name}</div>')
    return (
        f'<div class="l24-band">{"".join(bars)}</div>'
        f'<div class="l24-band-lbl">{"".join(labels)}</div>'
    )
