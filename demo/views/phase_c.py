"""Phase C — Guardrails: playground trực tiếp, adversarial suite 20 ca, P95 latency."""

from __future__ import annotations

import time

import streamlit as st

from demo import charts as C
from demo import data as D
from demo import simulate
from demo import theme as T

_LEGIT = [
    "Nhân viên chính thức được phép làm việc từ xa tối đa bao nhiêu ngày một tuần?",
    "Phụ cấp ăn trưa hàng tháng là bao nhiêu?",
]


def _layer_row(name: str, verdict: str, why: str, ms: float | None) -> str:
    """verdict ∈ {pass, block, skip}."""
    style = {
        "pass": (T.GOOD, "✓"),
        "block": (T.CRITICAL, "✕"),
        "skip": (T.MUTED, "·"),
    }[verdict]
    ms_text = f"{ms:.2f} ms" if ms is not None else "—"
    return (
        f'<div class="l24-layer">'
        f'<div class="ico" style="background:{style[0]}">{style[1]}</div>'
        f'<div class="body"><div class="name">{T.esc(name)}</div>'
        f'<div class="why">{why}</div></div>'
        f'<div class="ms">{ms_text}</div></div>'
    )


def _highlight_pii(text: str, entities: list[dict]) -> str:
    """Tô các span PII trên văn bản gốc (đã escape)."""
    if not entities:
        return T.esc(text)
    parts, cursor = [], 0
    for entity in sorted(entities, key=lambda e: e.get("start", 0)):
        start, end = int(entity.get("start", 0)), int(entity.get("end", 0))
        if start < cursor:
            continue
        parts.append(T.esc(text[cursor:start]))
        parts.append(
            f'<span class="l24-pii" title="{T.esc(entity.get("type"))} · '
            f'score {entity.get("score", 0)}">{T.esc(text[start:end])}</span>'
        )
        cursor = end
    parts.append(T.esc(text[cursor:]))
    return "".join(parts)


def _playground() -> None:
    T.section(
        "Guard playground",
        "Gõ một câu hỏi rồi xem nó đi qua từng lớp — lớp nào chặn, chặn vì sao, mất bao lâu.",
    )

    items = D.adversarial_set()
    presets = ["— Tự gõ —"] + [f"✓ hợp lệ · {q[:58]}" for q in _LEGIT] + [
        f'⚠ {i.get("category")} #{i.get("id")} · {i.get("input", "")[:52]}' for i in items
    ]
    lookup = {p: v for p, v in zip(presets[1:], _LEGIT + [i.get("input", "") for i in items])}

    top = st.columns([1.4, 1], gap="medium")
    with top[0]:
        preset = st.selectbox("Mẫu có sẵn", presets, label_visibility="collapsed")
    with top[1]:
        mode = st.radio(
            "Engine",
            ["Mô phỏng (chạy ngay)", "Code thật (Presidio + NeMo)"],
            horizontal=True,
            label_visibility="collapsed",
        )

    default = lookup.get(preset, _LEGIT[0])
    text = st.text_area("Input", value=default, height=90, key=f"pg_{preset}")

    if st.button("Chạy qua guard stack", key="run_pg"):
        st.session_state["pg_result"] = _run_guard(text, mode)

    result = st.session_state.get("pg_result")
    if not result:
        return
    if result.get("error"):
        st.error(result["error"])
        return

    pii, rail = result["pii"], result["rail"]
    blocked_by = result["blocked_by"]

    verdict_color = T.CRITICAL if blocked_by else T.GOOD
    verdict_text = "BỊ CHẶN" if blocked_by else "ĐƯỢC ĐI TIẾP"
    left, right = st.columns([1, 1.25], gap="medium")

    with left:
        foot = T.esc(rail.get("blocked_reason") or "không rule nào khớp")
        if result.get("total_ms"):
            foot += f' · tổng {result["total_ms"]:.2f} ms'
        T.card(
            '<div class="l24-kpi-head"><span class="l24-kpi-label">Kết luận</span>'
            + T.badge(verdict_text, verdict_color)
            + "</div>"
            f'<div class="l24-kpi-value" style="font-size:1.35rem">'
            f'{"Chặn tại " + blocked_by if blocked_by else "Vào được RAG pipeline"}</div>'
            f'<div class="l24-kpi-foot">{foot}</div>'
        )
        if result.get("simulated"):
            T.note(
                "Đang chạy <b>mô phỏng regex</b> trong <code>demo/simulate.py</code> — không phải "
                "Presidio/NeMo. Latency ở đây là latency của regex.",
                "warn",
            )
        elif result.get("cold_start"):
            T.note(
                "Lần chạy đầu bao gồm thời gian khởi tạo engine (spaCy model, NeMo config). "
                "Chạy lại cùng input để thấy latency ở trạng thái nóng.",
                "warn",
            )
    with right:
        rows = _layer_row(
            "01 · Presidio PII",
            "block" if pii.get("has_pii") else "pass",
            f'{len(pii.get("entities", []))} entity phát hiện'
            if pii.get("has_pii")
            else "không thấy PII trong input",
            result.get("presidio_ms"),
        )
        rows += _layer_row(
            "02 · NeMo input rail",
            "skip" if pii.get("has_pii") else ("block" if not rail.get("allowed") else "pass"),
            "bỏ qua — đã chặn ở lớp trước"
            if pii.get("has_pii")
            else T.esc(rail.get("response") or "topic hợp lệ, không phát hiện jailbreak"),
            None if pii.get("has_pii") else result.get("nemo_ms"),
        )
        rows += _layer_row(
            "03 · RAG pipeline",
            "skip" if blocked_by else "pass",
            "không chạy vì input đã bị chặn" if blocked_by else "M1→M5 xử lý câu hỏi",
            None,
        )
        rows += _layer_row(
            "04 · NeMo output rail",
            "skip" if blocked_by else "pass",
            "không chạy" if blocked_by else "kiểm tra answer trước khi trả về user",
            None,
        )
        T.card('<div class="l24-kpi-label">Đường đi qua các lớp</div>' + rows)

    if pii.get("entities"):
        a, b = st.columns(2, gap="medium")
        with a:
            st.markdown(
                '<div class="l24-kpi-label">Input gốc — PII được tô</div>'
                f'<div class="l24-text">{_highlight_pii(text, pii["entities"])}</div>',
                unsafe_allow_html=True,
            )
        with b:
            st.markdown(
                '<div class="l24-kpi-label">Sau khi anonymize</div>'
                f'<div class="l24-text">{T.esc(pii.get("anonymized", ""))}</div>',
                unsafe_allow_html=True,
            )
        st.dataframe(
            [
                {
                    "Entity": e.get("type"),
                    "Giá trị": e.get("text"),
                    "Score": e.get("score"),
                    "Vị trí": f'{e.get("start")}–{e.get("end")}',
                }
                for e in pii["entities"]
            ],
            hide_index=True,
            **T.stretch(),
        )


def _run_guard(text: str, mode: str) -> dict:
    if mode.startswith("Mô phỏng"):
        verdict = simulate.guard_once(text)
        verdict["simulated"] = True
        return verdict

    # Engine được cache trong session — lần đầu tốn thêm thời gian khởi tạo.
    cold = "presidio_engine" not in st.session_state or "nemo_rails" not in st.session_state

    t0 = time.perf_counter()
    pii, error = D.run_pii_scan(text)
    presidio_ms = (time.perf_counter() - t0) * 1000
    if error:
        return {"error": f"pii_scan() lỗi — {error}"}
    if not pii:
        return {"error": "pii_scan() không trả về gì — Task 9a chưa implement?"}

    rail = {"allowed": True, "blocked_reason": None, "response": ""}
    nemo_ms = 0.0
    if not pii.get("has_pii"):
        t1 = time.perf_counter()
        rail, rail_error = D.run_input_rail(text)
        nemo_ms = (time.perf_counter() - t1) * 1000
        if rail_error:
            return {"error": f"check_input_rail() lỗi — {rail_error}"}

    blocked_by = (
        "presidio" if pii.get("has_pii")
        else ("nemo_input" if not rail.get("allowed") else None)
    )
    return {
        "pii": pii,
        "rail": rail,
        "blocked_by": blocked_by,
        "allowed": blocked_by is None,
        "presidio_ms": presidio_ms,
        "nemo_ms": nemo_ms or None,
        "total_ms": presidio_ms + nemo_ms,
        "simulated": False,
        "cold_start": cold,
    }


def _suite(pc) -> None:
    T.section(
        "Adversarial suite",
        f"20 input tấn công · gate của lab: pass rate ≥ {D.GATE_ADVERSARIAL:.0%} (18/20).",
    )

    b1, b2, _ = st.columns([1, 1, 2], gap="small")
    with b1:
        if st.button("Chạy suite — mô phỏng", key="suite_sim"):
            count, error = D.run_phase_c_sim()
            T.flash(error, "error") if error else T.flash(f"Xong — {count} input (mô phỏng).")
            T.rerun()
    with b2:
        if st.button("Chạy suite — code thật", key="suite_real"):
            with st.spinner("Đang chạy Presidio + NeMo…"):
                count, error = D.run_phase_c()
            T.flash(error, "error") if error else T.flash(f"Xong — {count} input.")
            T.rerun()

    if not pc.rows:
        T.empty_state(
            "Chưa có kết quả suite",
            "Bấm <i>Chạy suite — mô phỏng</i> để xem luồng chạy ngay, hoặc implement "
            "<code>run_adversarial_suite()</code> (Task 10) rồi chạy code thật.",
        )
        return

    total = len(pc.rows)
    rate = pc.passed / total
    by_presidio = sum(1 for r in pc.rows if r.get("blocked_by") == "presidio")
    by_nemo = sum(1 for r in pc.rows if r.get("blocked_by") == "nemo_input")
    leaked = [r for r in pc.rows if not r.get("passed")]

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        color, label = T.score_status(rate, D.GATE_ADVERSARIAL)
        T.kpi("Pass rate", f"{pc.passed}", unit=f"/{total}", foot=f"{rate:.0%} đúng kỳ vọng",
              status=color, status_label=label, meter=rate)
    with c2:
        T.kpi("Chặn bởi Presidio", str(by_presidio), foot="lớp regex/NER cục bộ",
              status=T.SERIES[0], status_label="", meter=by_presidio / total)
    with c3:
        T.kpi("Chặn bởi NeMo", str(by_nemo), foot="topic + jailbreak rail",
              status=T.SERIES[1], status_label="", meter=by_nemo / total)
    with c4:
        T.kpi("Lệch kỳ vọng", str(len(leaked)), foot="ca cần xem lại rule",
              status=T.GOOD if not leaked else T.CRITICAL,
              status_label="CLEAN" if not leaked else "CHECK",
              meter=len(leaked) / total)

    left, right = st.columns([1, 1.1], gap="medium")
    with left:
        C.show(C.guard_by_category(pc.rows, T.CATEGORY_LABEL))
    with right:
        if leaked:
            body = "".join(
                f'<div class="l24-gate">'
                f'<span class="l24-dot" style="background:{T.CRITICAL}"></span>'
                f'<span class="l24-gate-name">#{r.get("id")} · '
                f'{T.CATEGORY_LABEL.get(r.get("category"), r.get("category"))}'
                f'<small>{T.esc(r.get("input", ""))}</small></span>'
                f'<span class="l24-gate-val">kỳ vọng {r.get("expected")}<br>thực tế '
                f'{r.get("actual")}</span></div>'
                for r in leaked
            )
            T.card('<div class="l24-kpi-label">Các ca lệch kỳ vọng</div>' + body)
        else:
            T.card(
                '<div class="l24-kpi-label">Các ca lệch kỳ vọng</div>'
                '<div class="l24-kpi-value" style="font-size:1.2rem">Không có</div>'
                '<div class="l24-kpi-foot">Cả 20 input đều cho kết quả đúng như kỳ vọng.</div>'
            )

    only_failed = st.checkbox("Chỉ hiện ca lệch kỳ vọng", value=False)
    table_rows = leaked if only_failed else pc.rows
    if not table_rows:
        T.note("Không có ca nào lệch kỳ vọng — bỏ tick để xem cả 20 input.")
        return
    st.dataframe(
        [
            {
                "#": r.get("id"),
                "Loại": T.CATEGORY_LABEL.get(r.get("category"), r.get("category")),
                "Input": r.get("input", ""),
                "Kỳ vọng": r.get("expected"),
                "Thực tế": r.get("actual"),
                "Chặn bởi": r.get("blocked_by") or "—",
                "Rule": r.get("reason") or "—",
                "Kết quả": "✓" if r.get("passed") else "✗",
            }
            for r in table_rows
        ],
        hide_index=True,
        **T.stretch(),
    )


def _latency(pc) -> None:
    T.section(
        "Latency budget",
        f"P50/P95/P99 từng lớp · budget production: P95 tổng < {D.GATE_LATENCY_MS} ms.",
    )
    if not pc.latency:
        T.empty_state(
            "Chưa đo latency",
            "Implement <code>measure_p95_latency()</code> (Task 12) hoặc chạy suite mô phỏng.",
        )
        return

    C.show(C.latency_bars(pc.latency, int(pc.latency.get("budget_ms", D.GATE_LATENCY_MS))))

    total_p95 = float(pc.latency.get("total_ms", {}).get("p95", 0) or 0)
    nemo_p95 = float(pc.latency.get("nemo_ms", {}).get("p95", 0) or 0)
    budget = int(pc.latency.get("budget_ms", D.GATE_LATENCY_MS))
    share = nemo_p95 / total_p95 if total_p95 else 0

    if pc.latency.get("simulated") or pc.source.kind in ("sim", "sample"):
        T.note(
            "Số này <b>không phải</b> latency thật của Presidio/NeMo — nguồn hiện tại là "
            f"<b>{pc.source.label}</b>. Chạy <code>measure_p95_latency()</code> để có số đo thật.",
            "warn",
        )
    elif total_p95 < budget:
        T.note(
            f"P95 tổng <b>{total_p95:.0f} ms</b> nằm dưới budget {budget} ms. "
            f"NeMo chiếm {share:.0%} thời gian — muốn giảm tiếp thì tối ưu ở lớp LLM call "
            "(model nhỏ hơn, cache, hoặc chạy song song với retrieval).",
        )
    else:
        T.note(
            f"P95 tổng <b>{total_p95:.0f} ms</b> vượt budget {budget} ms. NeMo chiếm "
            f"{share:.0%} — cân nhắc dùng model nhẹ hơn cho rail hoặc bỏ qua rail với "
            "các câu hỏi đã qua allowlist.",
            "bad",
        )

    with st.expander("Bảng số — percentile theo lớp"):
        st.dataframe(
            [
                {
                    "Layer": label,
                    "P50 (ms)": pc.latency.get(key, {}).get("p50"),
                    "P95 (ms)": pc.latency.get(key, {}).get("p95"),
                    "P99 (ms)": pc.latency.get(key, {}).get("p99"),
                }
                for key, label in [
                    ("presidio_ms", "Presidio (PII)"),
                    ("nemo_ms", "NeMo (rails)"),
                    ("total_ms", "Guard stack"),
                ]
            ],
            hide_index=True,
            **T.stretch(),
        )


def render(use_sample: bool) -> None:
    T.page_head(
        "Phase C · Tasks 9–12",
        "Production guardrails",
        "Hai lớp chặn trước khi câu hỏi vào RAG: Presidio bắt PII bằng regex/NER cục bộ, "
        "NeMo chặn jailbreak và câu ngoài phạm vi. Đo cả độ chặn và độ trễ.",
    )

    pc = D.phase_c(use_sample)
    T.source_chip(pc.source)

    _playground()
    _suite(pc)
    _latency(pc)
