# CI/CD Blueprint: RAG Eval + Guardrail Stack

**Sinh viên:** Linh Kastner
**Ngày:** 2026-08-26

---

## Guard Stack Architecture

```
User Input
    │
    ▼ (~?ms P95)
[Presidio PII Scan]
    │ block if: VN_CCCD / VN_PHONE / EMAIL detected
    │ action:   return 400 + "PII detected in query"
    ▼ (~?ms P95)
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

*(Đo bằng `measure_p95_latency()`; NeMo là layer có độ trễ lớn nhất.)*

| Layer | P50 (ms) | P95 (ms) | P99 (ms) | Budget |
|---|---|---|---|---|
| Presidio PII | đo runtime | đo runtime | đo runtime | <10ms |
| NeMo Input Rail | đo runtime | đo runtime | đo runtime | <300ms |
| RAG Pipeline | N/A | N/A | N/A | <2000ms |
| NeMo Output Rail | N/A | N/A | N/A | <300ms |
| **Total Guard** | đo runtime | **đo runtime** | đo runtime | **<500ms** |

**Budget OK?** Đánh giá sau khi chạy production benchmark.
**Comment:** Presidio chạy local; NeMo là bottleneck do gọi LLM. Có thể giảm latency bằng model nhỏ hơn, timeout và cache các pattern phổ biến.

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
| RAGAS avg_score (50q) | xem `reports/ragas_50q.json` |
| Worst metric | xem `reports/ragas_50q.json` |
| Dominant failure distribution | xem `reports/ragas_50q.json` |
| Cohen's κ | xem `reports/judge_results.json` |
| Adversarial pass rate | 20 / 20 |
| Guard P95 latency | xem `reports/guard_results.json` |

---

## Nhận xét & Cải tiến

> Presidio phát hiện tốt CCCD, số điện thoại Việt Nam và email, đồng thời chặn được toàn bộ bộ adversarial hiện tại. NeMo bổ sung lớp kiểm tra jailbreak, off-topic và prompt injection. Điểm cần cải thiện là độ trễ của LLM và false positive từ recognizer ngôn ngữ không phù hợp. Khi deploy production, cần cache kết quả, đặt timeout/fallback rõ ràng và theo dõi pass rate cùng P95 latency liên tục.
