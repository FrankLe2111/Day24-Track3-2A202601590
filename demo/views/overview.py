"""Trang Overview — trạng thái toàn stack: CI gates, guard stack, dataset, tasks."""

from __future__ import annotations

from collections import Counter

import streamlit as st

from demo import data as D
from demo import theme as T


def _seg_bar(items: list[tuple[str, int, str]]) -> str:
    """Thanh part-to-whole + legend có nhãn số (không dựa vào màu để đọc số)."""
    total = sum(c for _, c, _ in items) or 1
    bars = "".join(
        f'<div style="flex:{c} 1 0;height:8px;border-radius:2px;background:{color}"></div>'
        for _, c, color in items
        if c
    )
    legend = "".join(
        f'<span class="l24-badge" style="color:{T.INK_2}">'
        f'<span class="l24-dot" style="background:{color}"></span>{label} · {c}</span>'
        for label, c, color in items
    )
    return (
        f'<div style="display:flex;gap:2px;margin:.2rem 0 .6rem">{bars}</div>'
        f'<div style="display:flex;gap:.4rem;flex-wrap:wrap">{legend}</div>'
        f'<div style="font-size:.78rem;color:{T.MUTED};margin-top:.5rem">Tổng {total} câu</div>'
    )


def _kpi_faithfulness(pa) -> None:
    value = pa.overall.get("faithfulness")
    if value is None:
        T.kpi("Faithfulness", "—", foot="Chưa chạy Phase A", status=T.MUTED, status_label="N/A")
        return
    color, label = T.score_status(value, D.GATE_FAITHFULNESS)
    T.kpi(
        "Faithfulness", f"{value:.3f}",
        foot=f"gate ≥ {D.GATE_FAITHFULNESS:.2f} · {value - D.GATE_FAITHFULNESS:+.3f}",
        status=color, status_label=label, meter=value,
    )


def _kpi_adversarial(pc) -> None:
    if not pc.rows:
        T.kpi("Adversarial suite", "—", foot="Chưa chạy Phase C", status=T.MUTED, status_label="N/A")
        return
    rate = pc.passed / len(pc.rows)
    color, label = T.score_status(rate, D.GATE_ADVERSARIAL)
    T.kpi(
        "Adversarial suite", f"{pc.passed}", unit=f"/{len(pc.rows)}",
        foot=f"pass rate {rate:.0%} · gate ≥ {D.GATE_ADVERSARIAL:.0%}",
        status=color, status_label=label, meter=rate,
    )


def _kpi_latency(pc) -> None:
    p95 = float(pc.latency.get("total_ms", {}).get("p95", 0) or 0)
    if not p95:
        T.kpi("Guard P95", "—", unit="ms", foot="Chưa đo latency", status=T.MUTED, status_label="N/A")
        return
    ok = p95 < D.GATE_LATENCY_MS
    margin = D.GATE_LATENCY_MS - p95
    T.kpi(
        "Guard P95", f"{p95:.0f}", unit="ms",
        foot=f"budget < {D.GATE_LATENCY_MS} ms · "
             + (f"còn {margin:.0f} ms" if ok else f"vượt {-margin:.0f} ms"),
        status=T.GOOD if ok else T.CRITICAL, status_label="PASS" if ok else "OVER",
        meter=min(1.0, p95 / D.GATE_LATENCY_MS),
    )


def _kpi_kappa(pb) -> None:
    if pb.kappa is None:
        T.kpi("Cohen's κ", "—", foot="Chưa chạy Phase B", status=T.MUTED, status_label="N/A")
        return
    band = next((n for lo, hi, n in T.KAPPA_BANDS if lo <= pb.kappa < hi), "Almost perfect")
    ok = pb.kappa >= D.GATE_KAPPA
    color = T.GOOD if ok else (T.WARNING if pb.kappa >= 0.4 else T.CRITICAL)
    T.kpi(
        "Cohen's κ", f"{pb.kappa:.3f}",
        foot=f"{band} · bonus ≥ {D.GATE_KAPPA:.1f}",
        status=color, status_label="PASS" if ok else "NEAR" if pb.kappa >= 0.4 else "LOW",
        meter=max(0.0, pb.kappa),
    )


def render(use_sample: bool) -> None:
    pa = D.phase_a(use_sample)
    pb = D.phase_b(use_sample)
    pc = D.phase_c(use_sample)

    T.page_head(
        "Lab 24 · Track 3",
        "Production Eval + Guardrail Stack",
        "Một bảng điều khiển cho ba lớp: RAGAS đo chất lượng pipeline, LLM-as-Judge đo "
        "độ tin cậy của chính phép đo, NeMo + Presidio chặn input độc hại trước khi vào RAG.",
    )

    # ── CI gates ─────────────────────────────────────────────────────────────
    T.section("CI gates", "Bốn cửa phải xanh trước khi merge vào main.")
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        _kpi_faithfulness(pa)
    with c2:
        _kpi_adversarial(pc)
    with c3:
        _kpi_latency(pc)
    with c4:
        _kpi_kappa(pb)

    sources = [
        ("Phase A", pa.source),
        ("Phase B", pb.source),
        ("Phase C", pc.source),
    ]
    chips = "".join(
        f'<span class="l24-chip"><span class="l24-dot" style="background:'
        f'{T.source_color(s.kind)}"></span>{name} · {s.label}</span>'
        for name, s in sources
    )
    st.markdown(
        f'<div style="display:flex;gap:.45rem;flex-wrap:wrap;margin-top:1rem">{chips}</div>',
        unsafe_allow_html=True,
    )

    # ── Guard stack ──────────────────────────────────────────────────────────
    T.section("Guard stack", "Thứ tự thực thi và ngân sách latency của từng lớp.")
    lat = pc.latency
    measured = {
        "presidio": lat.get("presidio_ms", {}).get("p95"),
        "nemo": lat.get("nemo_ms", {}).get("p95"),
    }
    nodes = [
        ("01", "Presidio PII", "Regex + NER cục bộ. Bắt VN_CCCD, VN_PHONE, EMAIL.",
         f"P95 {measured['presidio']:.1f} ms" if measured["presidio"] else "budget < 10 ms",
         "Reject + log"),
        ("02", "NeMo input rail", "Topic guard + jailbreak guard qua Colang flows.",
         f"P95 {measured['nemo']:.0f} ms" if measured["nemo"] else "budget < 300 ms",
         "503 + reason"),
        ("03", "RAG pipeline", "M1→M5 của Day 18: chunk, hybrid search, rerank, generate.",
         "budget < 2000 ms", "Fallback"),
        ("04", "NeMo output rail", "Kiểm tra answer trước khi trả về: PII, nội dung, hallucination.",
         "budget < 300 ms", "Block + log"),
    ]
    html = "".join(
        f'<div class="l24-node"><div class="n">{n}</div><div class="t">{t}</div>'
        f'<div class="d">{d}</div><div class="m">{m} · {action}</div></div>'
        for n, t, d, m, action in nodes
    )
    st.markdown(f'<div class="l24-flow">{html}</div>', unsafe_allow_html=True)

    # ── Dataset + tiến độ task ───────────────────────────────────────────────
    left, right = st.columns([1.15, 1], gap="medium")

    with left:
        T.section("Dataset", "Bốn file input của lab và số bản ghi đọc được.")
        rows = ""
        for item in D.dataset_status():
            ok = item["exists"] and item["count"] > 0
            color = T.GOOD if ok else T.CRITICAL
            value = f'{item["count"]} bản ghi' if ok else "thiếu file"
            rows += T.gate(
                item["label"], f'{item["file"]} · {item["hint"]}', value, color,
                "OK" if ok else "MISSING",
            )
        T.card(rows)

        counts = Counter(t.get("distribution") for t in D.test_set())
        st.markdown(
            f'<div class="l24-card" style="margin-top:.7rem">'
            f'<div class="l24-kpi-label">Phân bố test set</div>'
            + _seg_bar([
                (T.DIST_LABEL[d], counts.get(d, 0), T.DIST_COLOR[d]) for d in T.DISTRIBUTIONS
            ])
            + "</div>",
            unsafe_allow_html=True,
        )

    with right:
        T.section("Tiến độ implement", "Đọc trực tiếp từ source `src/phase_*.py`.")
        rows = ""
        for phase, label, file in [
            ("A", "Phase A · RAGAS 50q", "src/phase_a_ragas.py"),
            ("B", "Phase B · LLM-as-Judge", "src/phase_b_judge.py"),
            ("C", "Phase C · Guardrails", "src/phase_c_guard.py"),
        ]:
            done, total = D.tasks_done(phase)
            color = T.GOOD if done == total else (T.WARNING if done else T.CRITICAL)
            rows += T.gate(
                label, file, f"{done}/{total} task", color,
                "DONE" if done == total else "WIP" if done else "TODO",
            )
        T.card(rows)

        st.markdown(
            '<div class="l24-card" style="margin-top:.7rem">'
            '<div class="l24-kpi-label">Môi trường</div>'
            + "".join(
                T.gate(e["name"], e["hint"], "", T.GOOD if e["ok"] else T.WARNING,
                       "OK" if e["ok"] else "THIẾU")
                for e in D.env_status()
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Chi tiết 13 task"):
        st.dataframe(
            [
                {
                    "Phase": r["phase"],
                    "Task": r["task"],
                    "Trạng thái": "✓ implemented" if r["done"] else "· còn TODO",
                    "Ghi chú": r["error"],
                }
                for r in D.task_status()
            ],
            hide_index=True,
            **T.stretch(),
        )
