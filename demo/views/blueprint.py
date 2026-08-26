"""Trang Blueprint — điền CI/CD blueprint (Task 13) từ số đo hiện có.

Chỉ điền những ô có dữ liệu. Ô cần nhận xét của người thì để nguyên placeholder —
app không viết hộ phần đánh giá.
"""

from __future__ import annotations

import datetime as _dt
import os

import streamlit as st

from demo import data as D
from demo import theme as T

_BLUEPRINT_PATH = "reports/blueprint.md"


def _fmt(value, spec: str = "", fallback: str = "?") -> str:
    if value is None or value == "":
        return fallback
    try:
        return format(value, spec) if spec else str(value)
    except (TypeError, ValueError):
        return str(value)


def _build_markdown(pa, pb, pc) -> str:
    lat = pc.latency or {}
    presidio = lat.get("presidio_ms", {})
    nemo = lat.get("nemo_ms", {})
    total = lat.get("total_ms", {})
    budget = int(lat.get("budget_ms", D.GATE_LATENCY_MS))
    total_p95 = float(total.get("p95", 0) or 0)

    worst_metric = (
        min(T.METRICS, key=lambda m: pa.overall.get(m, 1.0)) if pa.overall else None
    )
    dominant = (pa.clusters or {}).get("dominant_failure_distribution")
    rate = f"{pc.passed} / {len(pc.rows)}" if pc.rows else "? / 20"

    sources = {"Phase A": pa.source, "Phase B": pb.source, "Phase C": pc.source}
    unreal = [name for name, s in sources.items() if not s.is_real]
    provenance = "\n".join(f"> - {name}: {s.label}" for name, s in sources.items())
    warning = (
        "\n> ⚠️ **CẢNH BÁO** — các số dưới đây KHÔNG phải kết quả đo thật "
        f"({', '.join(unreal)} chưa có dữ liệu thật). Không dùng bản này để nộp bài.\n"
        if unreal
        else ""
    )

    budget_yes = "[x]" if total_p95 and total_p95 < budget else "[ ]"
    budget_no = "[x]" if total_p95 and total_p95 >= budget else "[ ]"

    return f"""# CI/CD Blueprint: RAG Eval + Guardrail Stack

**Sinh viên:** [Họ Tên]
**Ngày:** {_dt.date.today():%d/%m/%Y}

> Sinh tự động bởi `demo_app.py` từ các nguồn:
{provenance}
{warning}
---

## Guard Stack Architecture

```
User Input
    │
    ▼ (~{_fmt(presidio.get("p95"), ".1f")}ms P95)
[Presidio PII Scan]
    │ block if: VN_CCCD / VN_PHONE / EMAIL detected
    │ action:   return 400 + "PII detected in query"
    ▼ (~{_fmt(nemo.get("p95"), ".0f")}ms P95)
[NeMo Input Rail]
    │ block if: off-topic / jailbreak / prompt injection
    │ action:   return 503 + refuse message
    ▼
[RAG Pipeline (Day 18)]
    │ M1 Chunk → M2 Search → M3 Rerank → GPT-4o-mini
    ▼
[NeMo Output Rail]
    │ flag if:  PII in response / sensitive content
    │ action:   replace with safe response
    ▼
User Response
```

---

## Latency Budget

*(Điền từ kết quả Task 12 — measure_p95_latency())*

| Layer | P50 (ms) | P95 (ms) | P99 (ms) | Budget |
|---|---|---|---|---|
| Presidio PII | {_fmt(presidio.get("p50"), ".2f")} | {_fmt(presidio.get("p95"), ".2f")} | {_fmt(presidio.get("p99"), ".2f")} | <10ms |
| NeMo Input Rail | {_fmt(nemo.get("p50"), ".1f")} | {_fmt(nemo.get("p95"), ".1f")} | {_fmt(nemo.get("p99"), ".1f")} | <300ms |
| RAG Pipeline | ? | ? | ? | <2000ms |
| NeMo Output Rail | ? | ? | ? | <300ms |
| **Total Guard** | {_fmt(total.get("p50"), ".1f")} | **{_fmt(total.get("p95"), ".1f")}** | {_fmt(total.get("p99"), ".1f")} | **<{budget}ms** |

**Budget OK?** {budget_yes} Yes / {budget_no} No
**Comment:** [Nếu vượt budget, layer nào là bottleneck và cách tối ưu?]

---

## CI/CD Gates (phải pass trước khi merge to main)

```yaml
# .github/workflows/rag_eval.yml
- name: RAGAS Quality Gate
  run: python src/phase_a_ragas.py
  env:
    MIN_FAITHFULNESS: 0.75
    MIN_AVG_SCORE: 0.65

- name: Guardrail Gate
  run: pytest tests/test_phase_c.py -k "test_adversarial_suite_pass_rate"
  # phải ≥ 15/20 (75%)

- name: Latency Gate
  run: python -c "from src.phase_c_guard import measure_p95_latency; ..."
  # P95 total < 500ms
```

---

## Monitoring Dashboard (production)

| Metric | Alert Threshold | Action |
|---|---|---|
| RAGAS faithfulness (daily sample) | < 0.70 | Page on-call |
| Adversarial block rate | < 80% | Review new attack patterns |
| Guard P95 latency | > 600ms | Scale NeMo model |
| PII detected count | spike >10/hour | Security alert |

---

## Kết quả thực tế từ Lab

| | Kết quả |
|---|---|
| RAGAS avg_score (50q) | {_fmt(pa.overall.get("avg_score"), ".4f")} |
| Faithfulness | {_fmt(pa.overall.get("faithfulness"), ".4f")} |
| Worst metric | {T.METRIC_LABEL.get(worst_metric, "?")} |
| Dominant failure distribution | {T.DIST_LABEL.get(dominant, "?")} |
| Cohen's κ | {_fmt(pb.kappa, ".4f")} |
| Adversarial pass rate | {rate} |
| Guard P95 latency | {_fmt(total.get("p95"), ".1f")} ms |

---

## Nhận xét & Cải tiến

> [Viết 3-5 câu về: điều gì hoạt động tốt, điều gì cần cải thiện,
>  nếu deploy production thực sự bạn sẽ thay đổi gì trong stack này?]
"""


def render(use_sample: bool) -> None:
    pa = D.phase_a(use_sample)
    pb = D.phase_b(use_sample)
    pc = D.phase_c(use_sample)

    T.page_head(
        "Task 13 · Deliverable",
        "CI/CD blueprint",
        "Gom số đo của ba phase thành bản blueprint để nộp. Phần nhận xét và tên sinh viên "
        "vẫn để trống — app không viết hộ.",
    )

    # ── Gate summary ─────────────────────────────────────────────────────────
    T.section("Trạng thái 4 gate", "Đọc từ nguồn dữ liệu đang chọn.")
    faith = pa.overall.get("faithfulness")
    rate = pc.passed / len(pc.rows) if pc.rows else None
    p95 = float((pc.latency or {}).get("total_ms", {}).get("p95", 0) or 0) or None

    gates = [
        ("RAGAS faithfulness", f"gate ≥ {D.GATE_FAITHFULNESS:.2f}", faith, "{:.3f}",
         (faith or 0) >= D.GATE_FAITHFULNESS),
        ("Adversarial pass rate", f"gate ≥ {D.GATE_ADVERSARIAL:.0%}", rate, "{:.0%}",
         (rate or 0) >= D.GATE_ADVERSARIAL),
        ("Guard P95 latency", f"budget < {D.GATE_LATENCY_MS} ms", p95, "{:.0f} ms",
         bool(p95) and p95 < D.GATE_LATENCY_MS),
        ("Cohen's κ (bonus)", f"bonus ≥ {D.GATE_KAPPA:.1f}", pb.kappa, "{:.3f}",
         (pb.kappa or 0) >= D.GATE_KAPPA),
    ]
    body = ""
    for name, hint, value, spec, ok in gates:
        if value is None:
            body += T.gate(name, hint, "—", T.MUTED, "N/A")
        else:
            body += T.gate(name, hint, spec.format(value), T.GOOD if ok else T.CRITICAL,
                           "PASS" if ok else "FAIL")
    T.card(body)

    unreal = [
        (label, s) for label, s in
        [("Phase A", pa.source), ("Phase B", pb.source), ("Phase C", pc.source)]
        if not s.is_real
    ]
    if unreal:
        T.note(
            "Chưa đủ số thật để nộp: "
            + ", ".join(f"<b>{label}</b> = {s.label}" for label, s in unreal)
            + ". Bản blueprint sinh ra sẽ có cảnh báo ở đầu file.",
            "warn",
        )

    # ── Generated markdown ───────────────────────────────────────────────────
    T.section("Bản blueprint", f"Cùng khung với <code>{_BLUEPRINT_PATH}</code> của lab.")
    markdown = _build_markdown(pa, pb, pc)

    tabs = st.tabs(["Xem trước", "Markdown thô"])
    with tabs[0]:
        st.markdown(markdown)
    with tabs[1]:
        st.code(markdown, language="markdown")

    # ── Ghi file ─────────────────────────────────────────────────────────────
    T.section("Xuất file", "Tải về, hoặc ghi thẳng vào reports/ (có xác nhận).")
    path = D.path(_BLUEPRINT_PATH)
    exists = os.path.exists(path)
    if exists:
        stamp = _dt.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d/%m/%Y %H:%M")
        st.markdown(
            f'<div class="l24-chip">File hiện tại · {os.path.getsize(path)} bytes · '
            f"sửa lần cuối {stamp}</div>",
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns([1, 2], gap="medium")
    with c1:
        st.download_button(
            "Tải blueprint.md", markdown, file_name="blueprint.md", mime="text/markdown"
        )
    with c2:
        confirm = st.checkbox(
            f"Cho phép ghi đè `{_BLUEPRINT_PATH}`"
            + (" (file đang có nội dung — sẽ mất bản cũ)" if exists else ""),
            value=False,
        )
        if st.button("Ghi vào reports/blueprint.md", disabled=not confirm, key="write_bp"):
            written = D.write_text(_BLUEPRINT_PATH, markdown)
            st.success(f"Đã ghi → {os.path.relpath(written, D.ROOT)}")
