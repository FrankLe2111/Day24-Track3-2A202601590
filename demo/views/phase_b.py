"""Phase B — LLM-as-Judge: pairwise, swap-and-average, Cohen κ, bias report."""

from __future__ import annotations

import streamlit as st

from demo import charts as C
from demo import data as D
from demo import theme as T

_DEMO_Q = "Nhân viên được nghỉ bao nhiêu ngày phép năm?"
_DEMO_A = "Nhân viên được nghỉ 15 ngày phép năm theo chính sách v2024 hiện hành."
_DEMO_B = "Theo quy định, nhân viên có 12 ngày phép hàng năm."


def _pairs() -> list[dict]:
    """Ghép 10 human label với ground truth: A = answer pipeline, B = reference."""
    truth = {t.get("id"): t.get("ground_truth", "") for t in D.test_set()}
    pairs = []
    for item in D.human_labels():
        qid = item.get("question_id")
        pairs.append(
            {
                "question": item.get("question", ""),
                "answer_a": item.get("model_answer", ""),
                "answer_b": truth.get(qid, ""),
                "human_label": item.get("human_label"),
                "question_id": qid,
            }
        )
    return pairs


def _run_panel() -> None:
    with st.expander("Chạy judge trên 10 câu có human label"):
        st.markdown(
            '<div class="l24-note warn">Gọi <b>swap_and_average()</b> thật: 2 lượt judge × 10 cặp '
            "= 20 API call. A là answer của pipeline, B là ground truth. Sau đó tính "
            "<b>cohen_kappa()</b> và <b>bias_report()</b>.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Chạy swap-and-average ×10", key="run_b"):
            with st.spinner("Đang judge…"):
                rows, error = D.run_phase_b(_pairs())
            if error:
                st.error(error)
            else:
                st.success(f"Xong — {len(rows)} cặp đã judge.")


def _kappa_card(kappa: float | None) -> None:
    if kappa is None:
        T.card(
            '<div class="l24-kpi-label">Cohen\'s κ</div>'
            '<div class="l24-kpi-value">—</div>'
            '<div class="l24-kpi-foot">Chưa có nhãn judge để so với human.</div>'
        )
        return
    band = next((n for lo, hi, n in T.KAPPA_BANDS if lo <= kappa < hi), "Almost perfect")
    ok = kappa >= D.GATE_KAPPA
    color = T.GOOD if ok else (T.WARNING if kappa >= 0.4 else T.CRITICAL)
    T.card(
        '<div class="l24-kpi-head"><span class="l24-kpi-label">Cohen\'s κ · judge vs human</span>'
        + T.badge("PASS" if ok else "CHƯA ĐẠT", color)
        + "</div>"
        f'<div class="l24-kpi-value">{kappa:.3f}'
        f'<span class="l24-kpi-unit">· {band}</span></div>'
        + T.kappa_band(kappa)
        + f'<div class="l24-kpi-foot">Thang Landis–Koch · bonus của lab yêu cầu κ &gt; '
        f"{D.GATE_KAPPA:.1f}</div>"
    )


def _confusion(rows: list[dict]) -> None:
    paired = [r for r in rows if r.get("human_label") is not None and r.get("judge_label") is not None]
    if not paired:
        T.empty_state("Chưa có cặp nhãn", "Cần cả judge_label và human_label để dựng ma trận.")
        return

    def count(h: int, j: int) -> int:
        return sum(1 for r in paired if r["human_label"] == h and r["judge_label"] == j)

    cells = {(h, j): count(h, j) for h in (1, 0) for j in (1, 0)}
    agree = cells[(1, 1)] + cells[(0, 0)]

    def cell(h: int, j: int) -> str:
        value = cells[(h, j)]
        good = h == j
        tint = "rgba(12,163,12,.16)" if good else "rgba(208,59,59,.16)"
        ring = T.GOOD if good else T.CRITICAL
        return (
            f'<div class="c" style="background:{tint};border-color:{ring}55">'
            f'<div class="v">{value}</div>'
            f'<div class="k">{"đồng ý" if good else "lệch"}</div></div>'
        )

    st.markdown(
        '<div class="l24-card">'
        '<div class="l24-kpi-label">Ma trận đồng thuận</div>'
        '<div class="l24-mx" style="margin-top:.6rem">'
        '<div class="h"></div><div class="h">judge = 1</div><div class="h">judge = 0</div>'
        '<div class="h">human = 1</div>' + cell(1, 1) + cell(1, 0) +
        '<div class="h">human = 0</div>' + cell(0, 1) + cell(0, 0) +
        "</div>"
        f'<div class="l24-kpi-foot">Khớp {agree}/{len(paired)} câu '
        f"({agree / len(paired):.0%} raw agreement — chưa trừ đồng thuận ngẫu nhiên)</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _bias_cards(bias: dict) -> None:
    if not bias or not bias.get("total_judged"):
        T.empty_state("Chưa có bias report", "Implement <code>bias_report()</code> (Task 8).")
        return

    pos_rate = float(bias.get("position_bias_rate", 0) or 0)
    verb = float(bias.get("verbosity_bias", 0) or 0)
    details = bias.get("verbosity_details", {}) or {}

    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        color = T.GOOD if pos_rate <= 0.30 else T.CRITICAL
        T.kpi(
            "Position bias", f"{pos_rate:.0%}",
            foot=f'{bias.get("position_bias_count", 0)}/{bias.get("total_judged", 0)} cặp đổi '
                 "kết quả khi swap · ngưỡng lo ngại > 30%",
            status=color, status_label="ỔN" if pos_rate <= 0.30 else "CAO", meter=pos_rate,
        )
    with c2:
        color = T.GOOD if verb <= 0.60 else T.WARNING
        T.kpi(
            "Verbosity bias", f"{verb:.0%}",
            foot=f'answer dài hơn thắng {details.get("a_wins_a_longer", 0) + details.get("b_wins_b_longer", 0)}'
                 f'/{details.get("total_decisive", 0)} ca có winner · ngưỡng > 60%',
            status=color, status_label="ỔN" if verb <= 0.60 else "ĐÁNG LO", meter=verb,
        )
    with c3:
        decisive = int(details.get("total_decisive", 0) or 0)
        total = int(bias.get("total_judged", 0) or 0)
        T.kpi(
            "Kết luận rõ ràng", f"{decisive}", unit=f"/{total}",
            foot="số cặp mà hai lượt judge đồng ý về cùng một answer",
            status=T.SERIES[0], status_label="", meter=decisive / total if total else 0,
        )
    if bias.get("interpretation"):
        T.note(bias["interpretation"], "warn" if pos_rate > 0.30 else "info")


def _arena() -> None:
    T.section("Pairwise arena", "Gõ hai câu trả lời rồi cho judge chấm hai lượt đảo thứ tự.")
    question = st.text_input("Câu hỏi", value=_DEMO_Q)
    a, b = st.columns(2, gap="medium")
    with a:
        answer_a = st.text_area("Answer A", value=_DEMO_A, height=110)
    with b:
        answer_b = st.text_area("Answer B", value=_DEMO_B, height=110)

    if st.button("Judge — 2 lượt (swap-and-average)", key="run_arena"):
        with st.spinner("Đang chấm…"):
            rows, error = D.run_phase_b(
                [{"question": question, "answer_a": answer_a, "answer_b": answer_b}],
                persist=False,
            )
        if error:
            st.error(error)
        elif rows:
            st.session_state["arena_result"] = rows[0]

    result = st.session_state.get("arena_result")
    if not result:
        return

    winner_color = {"A": T.SERIES[0], "B": T.SERIES[1], "tie": T.MUTED}
    c1, c2, c3 = st.columns(3, gap="small")
    for col, key, label in [
        (c1, "winner_pass1", "Pass 1 · (A, B)"),
        (c2, "winner_pass2", "Pass 2 · (B, A) → quy về A/B"),
        (c3, "final_winner", "Kết luận"),
    ]:
        with col:
            value = result.get(key, "tie")
            T.kpi(label, value.upper(), status=winner_color.get(value, T.MUTED),
                  status_label="WINNER" if value != "tie" else "TIE")
    consistent = result.get("position_consistent", True)
    T.note(
        ("Hai lượt cho cùng kết quả → không phát hiện position bias ở cặp này."
         if consistent else
         "Hai lượt cho kết quả khác nhau → có position bias, swap-and-average hạ về <b>tie</b>."),
        "info" if consistent else "warn",
    )
    for key, title in [("reasoning_pass1", "Lý giải pass 1"), ("reasoning_pass2", "Lý giải pass 2")]:
        if result.get(key):
            st.markdown(
                f'<div class="l24-kpi-label" style="margin-top:.6rem">{title}</div>'
                f'<div class="l24-text">{T.esc(result[key])}</div>',
                unsafe_allow_html=True,
            )


def render(use_sample: bool) -> None:
    T.page_head(
        "Phase B · Tasks 5–8",
        "LLM-as-Judge & độ tin cậy của phép đo",
        "RAGAS cũng do LLM chấm, nên phải đo lại chính người chấm: judge có ổn định khi đảo "
        "thứ tự không, có đồng thuận với người không, và có thiên vị câu dài không.",
    )
    _run_panel()

    pb = D.phase_b(use_sample)
    T.source_chip(pb.source)

    if not pb.has_data:
        T.empty_state(
            "Chưa có kết quả Phase B",
            "Implement <code>pairwise_judge()</code> + <code>swap_and_average()</code> rồi bấm "
            "<i>Chạy swap-and-average ×10</i>, hoặc ghi "
            "<code>reports/judge_results.json</code>, hoặc bật <i>Dữ liệu mẫu</i> ở sidebar.",
        )
        _arena()
        return

    left, right = st.columns([1.15, 1], gap="medium")
    with left:
        T.section("Đồng thuận với human", "κ trừ phần đồng thuận ngẫu nhiên, khác với % khớp thô.")
        _kappa_card(pb.kappa)
    with right:
        T.section("Ma trận 2×2", "10 câu có nhãn người trong human_labels_10q.json.")
        _confusion(pb.rows)

    if pb.rows:
        T.section("Nhãn theo từng câu", "Điểm lệch nhau là nơi judge và người không đồng ý.")
        C.show(C.judge_agreement(pb.rows))

    T.section("Bias report", "Hai loại thiên vị hay gặp nhất của LLM judge.")
    _bias_cards(pb.bias)

    if pb.rows:
        with st.expander(f"Bảng chi tiết {len(pb.rows)} cặp đã judge"):
            st.dataframe(
                [
                    {
                        "Q": r.get("question_id", ""),
                        "Câu hỏi": r["question"],
                        "Pass 1": r["winner_pass1"],
                        "Pass 2": r["winner_pass2"],
                        "Final": r["final_winner"],
                        "Nhất quán": "✓" if r["position_consistent"] else "✗",
                        "Judge": r.get("judge_label"),
                        "Human": r.get("human_label"),
                        "Lý giải": r["reasoning_pass1"],
                    }
                    for r in pb.rows
                ],
                hide_index=True,
                **T.stretch(),
            )

    _arena()
