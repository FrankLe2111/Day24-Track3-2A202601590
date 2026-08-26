"""Lab 24 — Production Eval + Guardrail Stack · Streamlit demo.

Chạy:
    streamlit run demo_app.py

App là lớp trình bày cho `src/phase_a_ragas.py`, `src/phase_b_judge.py`,
`src/phase_c_guard.py`. Chưa implement task nào cũng chạy được: bật "Dữ liệu mẫu"
ở sidebar để xem trước layout, hoặc dùng guard mô phỏng ở Phase C.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

st.set_page_config(
    page_title="Lab 24 · Eval + Guardrail Stack",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from demo import theme as T  # noqa: E402

T.inject_css()

if importlib.util.find_spec("plotly") is None:
    st.error(
        "Thiếu **plotly** — demo cần thư viện này để vẽ chart.\n\n"
        "```bash\npip install -r requirements-demo.txt\n```"
    )
    st.stop()

from demo import data as D  # noqa: E402
from demo.views import blueprint, overview, phase_a, phase_b, phase_c  # noqa: E402

PAGES = {
    "Overview": overview,
    "Phase A · RAGAS": phase_a,
    "Phase B · Judge": phase_b,
    "Phase C · Guardrails": phase_c,
    "Task 13 · Blueprint": blueprint,
}


def _sidebar() -> tuple[str, bool]:
    with st.sidebar:
        st.markdown(
            '<div class="l24-eyebrow">Day 24 · Track 3</div>'
            '<div style="font-size:1.15rem;font-weight:640;color:'
            f'{T.INK};line-height:1.2;margin:.25rem 0 .1rem">Eval &amp; Guardrail</div>'
            f'<div style="font-size:.79rem;color:{T.MUTED}">RAGAS · LLM-as-Judge · NeMo</div>'
            '<div class="l24-rule" style="margin:.9rem 0 1rem"></div>',
            unsafe_allow_html=True,
        )

        page = st.radio("Trang", list(PAGES), label_visibility="collapsed")

        st.markdown('<div class="l24-rule" style="margin:1rem 0"></div>', unsafe_allow_html=True)

        use_sample = getattr(st, "toggle", st.checkbox)(
            "Dữ liệu mẫu",
            value=st.session_state.get("use_sample", True),
            key="use_sample",
            help="Khi chưa có kết quả thật, lấp bằng số liệu MẪU trong demo/sample.py "
                 "để xem trước layout. Kết quả thật luôn được ưu tiên hơn.",
        )

        # Nhắc nguồn dữ liệu — hiện trên mọi trang.
        rows = ""
        for label, source in [
            ("A", D.phase_a(use_sample).source),
            ("B", D.phase_b(use_sample).source),
            ("C", D.phase_c(use_sample).source),
        ]:
            rows += (
                f'<div style="display:flex;align-items:center;gap:.45rem;padding:.22rem 0">'
                f'<span class="l24-dot" style="background:{T.source_color(source.kind)}"></span>'
                f'<span style="font-size:.78rem;color:{T.INK_2}">Phase {label} · '
                f"{D.SOURCE_LABEL.get(source.kind, source.kind)}</span></div>"
            )
        st.markdown(
            f'<div class="l24-kpi-label" style="margin-bottom:.3rem">Nguồn dữ liệu</div>{rows}',
            unsafe_allow_html=True,
        )

        if st.button("Xoá kết quả trong session"):
            for key in [
                "phase_a_rows", "phase_b_rows", "phase_b_kappa", "phase_b_bias",
                "phase_c_rows", "phase_c_latency", "phase_c_simulated",
                "pg_result", "arena_result", "presidio_engine", "nemo_rails",
            ]:
                st.session_state.pop(key, None)
            T.flash("Đã xoá kết quả live — quay lại reports/ hoặc dữ liệu mẫu.", "info")
            T.rerun()

        st.markdown(
            f'<div style="margin-top:1.1rem;font-size:.74rem;color:{T.MUTED};line-height:1.6">'
            "Số liệu thật đến từ <code>src/phase_*.py</code> và <code>reports/*.json</code>. "
            "Mọi con số không phải kết quả đo đều được dán nhãn ngay trên UI."
            "</div>",
            unsafe_allow_html=True,
        )

    return page, use_sample


page, use_sample = _sidebar()
T.show_flash()
PAGES[page].render(use_sample)
