"""Chart builders — Plotly, dùng chung một template dark.

Quy ước (giữ nguyên khi thêm chart mới):
  · categorical = identity (distribution) → màu theo entity, thứ tự slot cố định
  · sequential  = magnitude (heatmap)     → một hue blue, "gần 0" tối nhất
  · status      = pass/fail               → good/critical, luôn kèm nhãn chữ
  · một trục y duy nhất; grid hairline; threshold mới được dùng nét gạch

Thứ tự bắt buộc: gọi `_style(fig)` TRƯỚC, rồi mới override trục riêng của từng chart
(nếu làm ngược lại, template sẽ ghi đè mất setting riêng).
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from demo.theme import (
    BASELINE,
    CRITICAL,
    DIST_COLOR,
    DIST_LABEL,
    FONT,
    GOOD,
    GRID,
    INK,
    INK_2,
    METRIC_LABEL,
    METRICS,
    MUTED,
    SEQ_BLUE,
    SERIES,
    SURFACE,
    SURFACE_HI,
    WARNING,
    stretch,
)

PLOTLY_CONFIG = {"displayModeBar": False, "displaylogo": False, "responsive": True}

# Ordinal ramp cho percentile (p50 → p99): sáng dần, không bước nào tối hơn step 600.
_ORDINAL = ["#256abf", "#3987e5", "#86b6ef"]


def _style(fig: go.Figure, height: int = 320, y_title: str = "", y_range=None) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=6, r=18, t=34, b=6),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=12, color=INK_2),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.04, x=0, xanchor="left",
            bgcolor="rgba(0,0,0,0)", font=dict(size=11.5, color=INK_2),
            itemsizing="constant",
        ),
        hoverlabel=dict(
            bgcolor=SURFACE_HI, bordercolor=BASELINE,
            font=dict(family=FONT, size=12, color=INK),
        ),
        bargap=0.30,
        bargroupgap=0.08,
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False, showline=True, linecolor=BASELINE, linewidth=1,
        ticks="outside", tickcolor=BASELINE, ticklen=4,
        tickfont=dict(color=MUTED, size=11.5),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False, showline=False,
        tickfont=dict(color=MUTED, size=11.5),
        title=dict(text=y_title, font=dict(color=MUTED, size=11.5)),
    )
    if y_range is not None:
        fig.update_yaxes(range=y_range)
    return fig


def _round_bars(fig: go.Figure) -> None:
    """Bo 4px đầu cột nếu plotly đủ mới; bỏ qua nếu không hỗ trợ."""
    try:
        fig.update_traces(marker_cornerradius=4, selector=dict(type="bar"))
    except (ValueError, TypeError):
        pass


def _threshold(fig: go.Figure, value: float, label: str, position: str = "right") -> None:
    """Nét gạch CHỈ dùng cho ngưỡng — grid và trục luôn là nét liền."""
    fig.add_hline(
        y=value, line=dict(color=WARNING, width=1.5, dash="dash"),
        annotation_text=label, annotation_position=position,
        annotation_font=dict(color=WARNING, size=11),
    )


def show(fig: go.Figure) -> None:
    st.plotly_chart(fig, config=PLOTLY_CONFIG, **stretch())


# ── Phase A ──────────────────────────────────────────────────────────────────


def metrics_by_distribution(per_dist: dict, gate: float = 0.75) -> go.Figure:
    """4 metric × 3 distribution. Một trục 0–1, legend + gate line."""
    fig = go.Figure()
    for dist, agg in per_dist.items():
        fig.add_trace(
            go.Bar(
                name=DIST_LABEL.get(dist, dist),
                x=[METRIC_LABEL[m] for m in METRICS],
                y=[round(agg.get(m, 0), 4) for m in METRICS],
                marker=dict(color=DIST_COLOR.get(dist, SERIES[0])),
                hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.3f}<extra></extra>",
            )
        )
    fig.update_layout(barmode="group")
    _round_bars(fig)
    _style(fig, height=330, y_title="score", y_range=[0, 1.05])
    _threshold(fig, gate, f"gate {gate:g}")
    return fig


def question_dots(rows: list[dict], gate: float = 0.75) -> go.Figure:
    """Điểm trung bình từng câu hỏi. Nhãn trực tiếp chỉ cho câu tệ nhất."""
    fig = go.Figure()
    for dist in DIST_LABEL:
        subset = sorted(
            (r for r in rows if r["distribution"] == dist), key=lambda r: r["question_id"]
        )
        if not subset:
            continue
        fig.add_trace(
            go.Scatter(
                name=DIST_LABEL[dist],
                x=[r["question_id"] for r in subset],
                y=[round(r["avg_score"], 4) for r in subset],
                mode="markers",
                marker=dict(size=9, color=DIST_COLOR[dist], line=dict(width=2, color=SURFACE)),
                customdata=[
                    [
                        r["question"][:70] + ("…" if len(r["question"]) > 70 else ""),
                        METRIC_LABEL[r["worst_metric"]],
                    ]
                    for r in subset
                ],
                hovertemplate=(
                    "<b>Q%{x}</b> · %{fullData.name}<br>%{customdata[0]}"
                    "<br>avg %{y:.3f} · yếu nhất: %{customdata[1]}<extra></extra>"
                ),
            )
        )
    _style(fig, height=310, y_title="avg score", y_range=[0, 1.05])
    _threshold(fig, gate, f"gate {gate:g}")

    if rows:
        worst = min(rows, key=lambda r: r["avg_score"])
        fig.add_annotation(
            x=worst["question_id"], y=worst["avg_score"],
            text=f"Q{worst['question_id']} · {worst['avg_score']:.2f}",
            showarrow=True, arrowhead=0, arrowcolor=MUTED, arrowwidth=1,
            ax=26, ay=26, font=dict(color=INK, size=11),
            bgcolor=SURFACE_HI, bordercolor=BASELINE, borderwidth=1, borderpad=4,
        )
    fig.update_xaxes(title=dict(text="question id", font=dict(color=MUTED, size=11.5)))
    return fig


def failure_heatmap(matrix: dict) -> go.Figure:
    """Ma trận (metric yếu nhất × distribution). Sequential một hue + nhãn từng ô."""
    dists = list(DIST_LABEL)
    z = [[matrix.get(m, {}).get(d, 0) for d in dists] for m in METRICS]
    peak = max((v for row in z for v in row), default=0) or 1

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[DIST_LABEL[d] for d in dists],
            y=[METRIC_LABEL[m] for m in METRICS],
            colorscale=[[i / (len(SEQ_BLUE) - 1), c] for i, c in enumerate(SEQ_BLUE)],
            zmin=0,
            zmax=peak,
            xgap=2,
            ygap=2,
            hovertemplate="%{y} · %{x}<br>%{z} câu<extra></extra>",
            colorbar=dict(
                title=dict(text="số câu", font=dict(color=MUTED, size=11)),
                thickness=8, len=0.7, outlinewidth=0,
                tickfont=dict(color=MUTED, size=11),
            ),
        )
    )
    _style(fig, height=290)
    # Nhãn trong ô: màu chữ đổi theo độ sáng nền để luôn đọc được.
    for metric in METRICS:
        for dist in dists:
            value = matrix.get(metric, {}).get(dist, 0)
            fig.add_annotation(
                x=DIST_LABEL[dist], y=METRIC_LABEL[metric], text=str(value),
                showarrow=False,
                font=dict(color="#0b0b0b" if value / peak > 0.62 else INK, size=13),
            )
    fig.update_xaxes(showline=False, ticks="")
    fig.update_yaxes(showgrid=False, ticks="", autorange="reversed")
    return fig


# ── Phase C ──────────────────────────────────────────────────────────────────


def guard_by_category(rows: list[dict], category_label: dict) -> go.Figure:
    """Pass/fail theo từng loại tấn công — màu status, luôn kèm nhãn."""
    cats = list(dict.fromkeys(r.get("category", "") for r in rows))
    passed = [sum(1 for r in rows if r.get("category") == c and r.get("passed")) for c in cats]
    failed = [sum(1 for r in rows if r.get("category") == c and not r.get("passed")) for c in cats]
    labels = [category_label.get(c, c) for c in cats]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Đúng kỳ vọng", y=labels, x=passed, orientation="h",
            marker=dict(color=GOOD, line=dict(width=2, color=SURFACE)),
            text=[str(v) if v else "" for v in passed], textposition="inside",
            insidetextanchor="middle", textfont=dict(color="#0b0b0b", size=11.5),
            hovertemplate="%{y}<br>đúng kỳ vọng: %{x}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Lệch kỳ vọng", y=labels, x=failed, orientation="h",
            marker=dict(color=CRITICAL, line=dict(width=2, color=SURFACE)),
            text=[str(v) if v else "" for v in failed], textposition="inside",
            insidetextanchor="middle", textfont=dict(color=INK, size=11.5),
            hovertemplate="%{y}<br>lệch kỳ vọng: %{x}<extra></extra>",
        )
    )
    fig.update_layout(barmode="stack", bargap=0.42)
    _round_bars(fig)
    _style(fig, height=260)
    # Bar ngang: trục giá trị là x → grid nằm ở x, không ở y.
    fig.update_xaxes(
        showgrid=True, gridcolor=GRID, dtick=1,
        title=dict(text="số input", font=dict(color=MUTED, size=11.5)),
    )
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return fig


def latency_bars(latency: dict, budget_ms: int = 500) -> go.Figure:
    """P50/P95/P99 theo từng layer + ngưỡng budget (nét gạch = threshold)."""
    layers = [
        ("presidio_ms", "Presidio (PII)"),
        ("nemo_ms", "NeMo (rails)"),
        ("total_ms", "Guard stack"),
    ]
    fig = go.Figure()
    for i, pct in enumerate(["p50", "p95", "p99"]):
        fig.add_trace(
            go.Bar(
                name=pct.upper(),
                x=[label for _, label in layers],
                y=[round(float(latency.get(key, {}).get(pct, 0) or 0), 2) for key, _ in layers],
                marker=dict(color=_ORDINAL[i]),
                hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.1f} ms<extra></extra>",
            )
        )
    fig.update_layout(barmode="group")
    _round_bars(fig)
    _style(fig, height=310, y_title="milliseconds")
    _threshold(fig, budget_ms, f"budget P95 {budget_ms} ms", position="top left")

    total_p95 = float(latency.get("total_ms", {}).get("p95", 0) or 0)
    if total_p95:
        fig.add_annotation(
            x="Guard stack", y=total_p95, text=f"{total_p95:.0f} ms",
            showarrow=False, yshift=16, font=dict(color=INK, size=11.5),
        )
    return fig


# ── Phase B ──────────────────────────────────────────────────────────────────


def judge_agreement(rows: list[dict]) -> go.Figure:
    """So khớp nhãn judge vs human theo từng câu — dot plot 2 series."""
    rows = [r for r in rows if r.get("human_label") is not None]
    fig = go.Figure()
    if not rows:
        return _style(fig, height=220)

    labels = [f"Q{r.get('question_id') or i + 1}" for i, r in enumerate(rows)]
    fig.add_trace(
        go.Scatter(
            name="Human", x=labels, y=[r["human_label"] for r in rows], mode="markers",
            marker=dict(size=13, color=SERIES[0], line=dict(width=2, color=SURFACE)),
            hovertemplate="%{x} · human: %{y}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            name="LLM judge", x=labels, y=[r.get("judge_label") or 0 for r in rows],
            mode="markers",
            marker=dict(size=9, color=SERIES[1], symbol="diamond",
                        line=dict(width=2, color=SURFACE)),
            hovertemplate="%{x} · judge: %{y}<extra></extra>",
        )
    )
    _style(fig, height=230, y_range=[-0.45, 1.62])
    for i, row in enumerate(rows):
        if row.get("judge_label") != row.get("human_label"):
            fig.add_annotation(
                x=labels[i], y=1.36, text="lệch", showarrow=False,
                font=dict(color=CRITICAL, size=10.5),
            )
    fig.update_yaxes(tickvals=[0, 1], ticktext=["0 · bad", "1 · good"])
    return fig
