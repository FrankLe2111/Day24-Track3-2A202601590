"""Phase A — RAGAS 50q: 4 metric × 3 distribution, failure clusters, bottom 10."""

from __future__ import annotations

import streamlit as st

from demo import charts as C
from demo import data as D
from demo import theme as T


def _source_bar(source) -> None:
    T.source_chip(
        source,
        "Chỉ có số tổng hợp — chưa có điểm từng câu" if source.partial else "",
    )


def _run_panel() -> None:
    with st.expander("Chạy Phase A trên answers_50q.json"):
        st.markdown(
            '<div class="l24-note warn">Gọi <b>run_ragas_50q()</b> thật trong '
            "<code>src/phase_a_ragas.py</code>: 4 metric × 50 câu qua RAGAS, "
            "tốn API credit và khoảng 5–10 phút. Kết quả lưu trong session.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Chạy RAGAS 50 câu", key="run_a"):
            with st.spinner("Đang chạy RAGAS…"):
                count, error = D.run_phase_a()
            if error:
                st.error(error)
            else:
                st.success(f"Xong — {count} kết quả.")


def render(use_sample: bool) -> None:
    T.page_head(
        "Phase A · Tasks 1–4",
        "RAGAS production eval",
        "Chạy 4 metric trên 50 câu hỏi chia theo ba distribution, rồi truy ngược lỗi: "
        "distribution nào yếu nhất, metric nào là nguyên nhân chủ đạo.",
    )
    _run_panel()

    pa = D.phase_a(use_sample)
    _source_bar(pa.source)

    if not pa.has_data:
        T.empty_state(
            "Chưa có kết quả Phase A",
            "Cần một trong ba: implement <code>run_ragas_50q()</code> rồi bấm "
            "<i>Chạy RAGAS 50 câu</i> ở trên, hoặc chạy <code>python src/phase_a_ragas.py</code> "
            "để sinh <code>reports/ragas_50q.json</code>, hoặc bật <i>Dữ liệu mẫu</i> ở sidebar "
            "để xem trước layout.",
        )
        return

    # ── Filter row: một hàng duy nhất, scope cho toàn bộ chart bên dưới ──
    dists = list(pa.per_dist) or T.DISTRIBUTIONS
    if pa.rows:
        picked = st.multiselect(
            "Distribution",
            options=dists,
            default=dists,
            format_func=lambda d: T.DIST_LABEL.get(d, d),
            label_visibility="collapsed",
        ) or dists
    else:
        picked = dists

    rows = [r for r in pa.rows if r["distribution"] in picked]
    per_dist = {d: v for d, v in pa.per_dist.items() if d in picked}
    overall = (
        {m: sum(r[m] for r in rows) / len(rows) for m in T.METRICS}
        if rows
        else pa.overall
    )

    # ── 4 metric tổng quan ───────────────────────────────────────────────────
    T.section(
        "Điểm tổng quan",
        f"{len(rows) or sum(v.get('count', 0) for v in per_dist.values())} câu · "
        f"gate faithfulness ≥ {D.GATE_FAITHFULNESS:.2f}",
    )
    cols = st.columns(4, gap="small")
    for col, metric in zip(cols, T.METRICS):
        value = overall.get(metric, 0.0)
        color, label = T.score_status(value, D.GATE_FAITHFULNESS)
        with col:
            T.kpi(
                T.METRIC_LABEL[metric], f"{value:.3f}",
                foot=f"{value - D.GATE_FAITHFULNESS:+.3f} so với gate",
                status=color, status_label=label, meter=value,
            )

    # ── Metric × distribution + failure clusters ──────────────────────────────
    left, right = st.columns([1.25, 1], gap="medium")
    with left:
        T.section("Metric theo distribution", "Cùng một trục 0–1 để so sánh trực tiếp.")
        C.show(C.metrics_by_distribution(per_dist, D.GATE_FAITHFULNESS))
    with right:
        T.section("Failure clusters", "Số câu mà metric đó là điểm yếu nhất.")
        matrix = (pa.clusters or {}).get("matrix") or (
            D.cluster_matrix(rows)["matrix"] if rows else {}
        )
        if matrix:
            C.show(C.failure_heatmap(matrix))
        else:
            T.empty_state("Chưa có cluster", "Implement <code>cluster_analysis()</code> (Task 4).")

    clusters = pa.clusters or (D.cluster_matrix(rows) if rows else {})
    if clusters:
        dom_dist = clusters.get("dominant_failure_distribution", "—")
        dom_metric = clusters.get("dominant_failure_metric", "—")
        diag, fix = D.DIAGNOSTIC_TREE.get(dom_metric, ("—", "—"))
        T.note(
            f"Distribution <b>{T.DIST_LABEL.get(dom_dist, dom_dist)}</b> có nhiều failure nhất, "
            f"metric yếu chủ đạo là <b>{T.METRIC_LABEL.get(dom_metric, dom_metric)}</b> "
            f"→ chẩn đoán: {diag}. Hướng sửa: {fix}."
            + (f" <br><i>{clusters['insight']}</i>" if clusters.get("insight") else "")
        )

    with st.expander("Bảng số — metric × distribution"):
        st.dataframe(
            [
                {
                    "Distribution": T.DIST_LABEL.get(d, d),
                    "Số câu": v.get("count", 0),
                    **{T.METRIC_LABEL[m]: round(v.get(m, 0), 4) for m in T.METRICS},
                    "Avg": round(v.get("avg_score", 0), 4),
                }
                for d, v in per_dist.items()
            ],
            hide_index=True,
            **T.stretch(),
        )

    # ── Từng câu hỏi ─────────────────────────────────────────────────────────
    if rows:
        T.section("Điểm từng câu hỏi", "Mỗi điểm là một câu; hover để xem nội dung.")
        C.show(C.question_dots(rows, D.GATE_FAITHFULNESS))

    # ── Bottom 10 ────────────────────────────────────────────────────────────
    T.section("Bottom 10", "Mười câu yếu nhất kèm chẩn đoán từ diagnostic tree.")
    bottom = D.bottom_10_rows(rows) if rows else pa.bottom10
    if bottom:
        st.dataframe(
            [
                {
                    "#": b.get("rank"),
                    "Q": b.get("question_id"),
                    "Distribution": T.DIST_LABEL.get(b.get("distribution"), b.get("distribution")),
                    "Câu hỏi": b.get("question", ""),
                    "Avg": round(float(b.get("avg_score", 0)), 4),
                    "Metric yếu nhất": T.METRIC_LABEL.get(b.get("worst_metric"), b.get("worst_metric")),
                    "Chẩn đoán": b.get("diagnosis")
                    or D.DIAGNOSTIC_TREE.get(b.get("worst_metric"), ("", ""))[0],
                    "Hướng sửa": b.get("suggested_fix")
                    or D.DIAGNOSTIC_TREE.get(b.get("worst_metric"), ("", ""))[1],
                }
                for b in bottom
            ],
            hide_index=True,
            **T.stretch(),
        )
    else:
        T.empty_state("Chưa có bottom 10", "Implement <code>bottom_10()</code> (Task 3).")

    # ── Soi một câu cụ thể ───────────────────────────────────────────────────
    if rows:
        T.section("Soi một câu", "Answer, contexts đã retrieve và ground truth cạnh nhau.")
        options = sorted(rows, key=lambda r: r["avg_score"])
        picked_q = st.selectbox(
            "Câu hỏi",
            options=range(len(options)),
            format_func=lambda i: f"Q{options[i]['question_id']} · "
            f"{options[i]['avg_score']:.3f} · {options[i]['question'][:64]}",
            label_visibility="collapsed",
        )
        row = options[picked_q]
        mcols = st.columns(4, gap="small")
        for col, metric in zip(mcols, T.METRICS):
            color, label = T.score_status(row[metric], D.GATE_FAITHFULNESS)
            with col:
                T.kpi(T.METRIC_LABEL[metric], f"{row[metric]:.3f}",
                      status=color, status_label=label, meter=row[metric])
        a, b = st.columns(2, gap="medium")
        with a:
            st.markdown('<div class="l24-kpi-label">Pipeline answer</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="l24-text">{T.esc(row["answer"]) or "—"}</div>',
                unsafe_allow_html=True,
            )
        with b:
            st.markdown('<div class="l24-kpi-label">Ground truth</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="l24-text">{T.esc(row["ground_truth"]) or "—"}</div>',
                unsafe_allow_html=True,
            )
        if row["contexts"]:
            with st.expander(f'Contexts đã retrieve ({len(row["contexts"])})'):
                for i, ctx in enumerate(row["contexts"], 1):
                    st.markdown(
                        f'<div class="l24-kpi-label">chunk {i}</div>'
                        f'<div class="l24-text" style="margin-bottom:.6rem">{T.esc(ctx)}</div>',
                        unsafe_allow_html=True,
                    )
