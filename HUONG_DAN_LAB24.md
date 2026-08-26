# Báo cáo hướng dẫn chi tiết — Lab 24: Production Eval + Guardrail Stack

> Phân tích dựa trên: `ASSIGNMENT.md`, `README.md`, `RUBRIC.md`, `src/phase_*.py`,
> `tests/test_phase_*.py`, `setup_answers.py`, `check_lab.py`, `guardrails/`, `config.py`.
> Ngôn ngữ: tiếng Việt. Mục tiêu: giải thích **chính xác dự án này là gì** và **làm thế nào để hoàn thành**.

---

## 1. Dự án này là gì?

Lab 24 là bài lab 90 phút (3 phase × 30 phút + 15 phút setup), thang điểm 100 + 10 bonus.
Bạn xây dựng **một stack đánh giá (eval) + bảo vệ (guardrail) hoàn chỉnh** đặt lên trên RAG pipeline đã có từ **Day 18**.

Bản chất vấn đề: Day 18 trả lời câu hỏi "làm sao RAG chạy được?". Lab 24 trả lời 3 câu hỏi production:

1. **Phase A — Pipeline yếu ở đâu?** → Chạy RAGAS trên 50 câu hỏi với 3 phân phối (factual / multi_hop / adversarial), tìm 10 câu tệ nhất, phân cụm lỗi.
2. **Phase B — Bản thân việc đánh giá có đáng tin không?** → Dùng LLM-as-Judge so sánh cặp câu trả lời, đo position bias bằng swap-and-average, đo độ đồng thuận với con người bằng Cohen's κ.
3. **Phase C — Bảo vệ pipeline khỏi input độc hại thế nào?** → Tầng Presidio quét PII (CCCD, SĐT VN, email) + NeMo Guardrails chặn jailbreak/off-topic/PII request + kiểm tra output + đo latency P95.

Luồng tổng thể:

```
[Day 18 Pipeline]  →  Phase A: RAGAS 50q  →  reports/ragas_50q.json
                   →  Phase B: LLM Judge   →  reports/judge_results.json
                   →  Phase C: NeMo Guard  →  reports/guard_results.json + reports/blueprint.md
```

Dữ liệu: corpus HR policy tiếng Việt trong `data/` (~28 file, có cả bản v2023/v2024 của cùng một policy — đây là "mồi bẫy" cho adversarial distribution).

---

## 2. Setup bắt buộc (làm TRƯỚC khi tính giờ)

Theo đúng 5 bước trong `ASSIGNMENT.md`:

```bash
# 1. Copy code Day 18 vào src/ — BẮT BUỘC, vì Phase A gọi evaluate_ragas() từ m4_eval.py
cp -r <path-day18>/src/m*.py src/
cp <path-day18>/src/pipeline.py src/
# Phải có đủ: m1_chunking, m2_search, m3_rerank, m4_eval, m5_enrichment, pipeline.py

# 2. Khởi động Qdrant (port 6333, theo config.py)
docker compose up -d

# 3. Cài dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # bắt buộc cho Presidio

# 4. API key
cp .env.example .env   # điền OPENAI_API_KEY

# 5. Generate answers (5–10 phút) — INPUT CHO PHASE A
python setup_answers.py
```

**Điểm chết cần nhớ:**
- `answers_50q.json` không tồn tại → Phase A = 0 điểm (ghi rõ trong RUBRIC).
- `m4_eval.py` của Day 18 phải đã implement xong `evaluate_ragas()` — Phase A Task 2 gọi trực tiếp hàm này.
- `setup_answers.py` sẽ: chunk (M1) → enrich (M5) → index BM25+Dense (M2) → rerank (M3) → gọi GPT-4o-mini trả lời 50 câu → lưu `answers_50q.json` với fields: `id, distribution, question, answer, contexts, ground_truth`.

---

## 3. Phase A — RAGAS Production Eval (`src/phase_a_ragas.py`, 30 điểm)

Bộ test `test_set_50q.json`: 50 câu, 3 distributions:

| Distribution | Số câu | Đặc điểm | Bẫy thiết kế |
|---|---|---|---|
| `factual` | 20 | Tra cứu 1 tài liệu | Corpus có nhiều phiên bản policy (v2023 vs v2024) — phải chọn đúng bản mới |
| `multi_hop` | 20 | Cross-doc, tính toán | Tính lương thử việc, phí phạt tạm ứng — cần ghép nhiều docs |
| `adversarial` | 10 | Version conflicts, negation traps | Cố tình hỏi policy cũ, câu phủ định — pipeline hay nhầm nhất |

File đã cho sẵn: dataclass `RagasResult` (có 2 property quan trọng: `avg_score` = trung bình 4 metrics, `worst_metric` = metric thấp nhất), hằng số `DIAGNOSTIC_TREE` (map metric → (chẩn đoán, gợi ý fix)), các hàm `load_test_set_50q()`, `load_answers()`, `save_phase_a_report()`.

### Task 1 — `group_by_distribution(test_set)` (5đ)
Group 50 câu theo key `distribution`. Trả về dict 3 keys. Gợi ý code đã có sẵn trong comment TODO — chỉ cần uncomment/viết lại:
```python
groups = {"factual": [], "multi_hop": [], "adversarial": []}
for item in test_set:
    groups[item["distribution"]].append(item)
return groups
```
Test kiểm tra: đúng 3 keys, đúng số lượng 20/20/10, tổng = 50.

### Task 2 — `run_ragas_50q(answers)` (10đ)
Extract 4 list (questions, answers, contexts, ground_truths) → gọi `evaluate_ragas()` từ `src/m4_eval.py` → zip kết quả `per_question` với metadata → trả về `list[RagasResult]` gồm đúng 50 phần tử, mỗi câu 4 metrics. Skeleton đầy đủ nằm trong comment TODO của hàm — chỉ cần import `from src.m4_eval import evaluate_ragas` kèm `try/except ImportError` và map fields đúng.

### Task 3 — `bottom_10(results)` (7đ)
Sort tăng dần theo `avg_score`, lấy 10 câu đầu, mỗi item có đủ keys: `rank` (bắt đầu từ 1), `question_id`, `distribution`, `question`, `avg_score` (round 4), `worst_metric`, `diagnosis`, `suggested_fix` — hai cái cuối lấy từ `DIAGNOSTIC_TREE[r.worst_metric]`.

### Task 4 — `cluster_analysis(results)` (8đ)
Xây matrix 4 metrics × 3 distributions đếm số câu có `worst_metric` tương ứng. Sau đó tìm:
- `dominant_failure_distribution`: distribution có tổng failure cao nhất (cộng theo cột),
- `dominant_failure_metric`: metric có tổng cao nhất (cộng theo hàng),
- `insight`: string có nghĩa, kèm gợi ý fix từ `DIAGNOSTIC_TREE`.

Chạy: `python src/phase_a_ragas.py` → sinh `reports/ragas_50q.json`.

**Bonus +4:** adversarial avg_score < factual avg_score (nghĩa là eval detect được pipeline yếu ở adversarial — điều kỳ vọng). Sau Phase A, điền phân tích vào `analysis/failure_clusters.md`.

---

## 4. Phase B — LLM-as-Judge (`src/phase_b_judge.py`, 35 điểm)

### Task 5 — `pairwise_judge(question, answer_a, answer_b)` (10đ)
Gọi OpenAI (`JUDGE_MODEL = gpt-4o-mini` trong `config.py`) với prompt yêu cầu đánh giá theo 3 tiêu chí: **accuracy, completeness, conciseness**, bắt trả về JSON thuần (`response_format={"type": "json_object"}`):
```
{"winner": "A"|"B"|"tie", "reasoning": "...", "scores": {"A": 0.0-1.0, "B": 0.0-1.0}}
```
Test yêu cầu: dict đủ 3 keys, winner ∈ {A,B,tie}, scores ∈ [0,1], reasoning không rỗng khi có winner. Template prompt hoàn chỉnh nằm trong comment TODO.

### Task 6 — `swap_and_average(question, answer_a, answer_b)` (10đ)
Kỹ thuật chống **position bias** (LLM thiên vị câu trả lời xuất hiện trước):
1. Pass 1: `pairwise_judge(q, A, B)` → `winner_pass1`.
2. Pass 2: `pairwise_judge(q, B, A)` (swap) → **convert ngược về không gian gốc** bằng map `{"A":"B","B":"A","tie":"tie"}`.
3. Nếu 2 pass đồng ý → `final_winner` = kết quả đó; không đồng ý → `"tie"` và `position_consistent=False`.

Cạm bẫy rubric ghi rõ: *"convert winner_pass2 về space gốc"* — quên bước convert là sai ngầm khó phát hiện. Trả về `JudgeResult` dataclass (đã cho sẵn).

### Task 7 — `cohen_kappa(judge_labels, human_labels)` (10đ)
Nhãn nhị phân (0 = bad, 1 = good). Hai cách đều được:
- `sklearn.metrics.cohen_kappa_score`, hoặc
- Tính tay: `p_o` = tỉ lệ đồng ý; `p_e` = tỉ lệ đồng ý ngẫu nhiên kỳ vọng; `κ = (p_o − p_e)/(1 − p_e)`.

Test: perfect agreement → 1.0; perfect disagreement → ≤ 0; luôn ∈ [-1, 1]. Thang Landis-Koch: >0.6 = substantial, >0.8 = almost perfect. Human labels thật nằm trong `human_labels_10q.json` (10 câu, field `human_label`).

**Bonus +3:** κ > 0.6 với human labels — muốn đạt, phải chạy judge thật trên đúng 10 câu trong `human_labels_10q.json` rồi mới tính κ (placeholder `judge_labels = [0]*10` trong main chỉ là demo).

### Task 8 — `bias_report(judge_results)` (5đ)
- `position_bias_rate` = tỉ lệ case `position_consistent == False`.
- `verbosity_bias` = trong các case có winner rõ (≠ tie), tỉ lệ winner là bên **dài hơn** (so `len(answer_a)` vs `len(answer_b)`). > 0.6 = đáng lo.
- Kèm `verbosity_details` (3 counters) và `interpretation` string. Xử lý edge case: list rỗng và `decisive == 0` (tránh chia 0).

Chạy: `python src/phase_b_judge.py` → sinh `reports/judge_results.json`. Sau Phase B, điền `analysis/bias_report.md`.

---

## 5. Phase C — NeMo Guardrails (`src/phase_c_guard.py`, 35 điểm)

Kiến trúc nhiều tầng:

```
User Input → [Presidio PII]  → block nếu có PII
           → [NeMo Input Rail] → block nếu jailbreak/off-topic/PII request
           → [RAG Pipeline Day 18]
           → [NeMo Output Rail] → flag nếu response nhạy cảm
           → User Response
```

Config NeMo đã có sẵn: `guardrails/config.yml` (gpt-4o-mini + 3 input flows + 1 output flow) và `guardrails/rails.co` (Colang flows, **được phép mở rộng** để nâng pass rate Task 10). Hàm `setup_presidio()` và `setup_nemo_rails()` đã implement sẵn.

### Task 9a — `pii_scan(text, analyzer, anonymizer)` (10đ)
Dùng Presidio với custom recognizers đã định nghĩa sẵn:
- `VN_CCCD`: `\b\d{12}\b` (CCCD 12 số) và `\b\d{9}\b` (CMND 9 số),
- `VN_PHONE`: `\b0[3-9]\d{8}\b` (SĐT di động VN),
- EMAIL: recognizer mặc định của Presidio.

Trả về `{"has_pii", "entities" (type/text/score/start/end), "anonymized"}`. Test bắt detect được cả 3 loại và `anonymized` phải khác text gốc.

### Task 9b — `check_input_rail(text, rails)` (5đ) — async
`await rails.generate_async(messages=[{"role":"user","content":text}])`, rồi heuristics: nếu response chứa refuse keywords ("xin lỗi", "không thể", ...) → `allowed=False, blocked_reason="nemo_input"`.

### Task 10 — `run_adversarial_suite(...)` (10đ) — quan trọng nhất Phase C
Chạy 20 input trong `adversarial_set_20.json` (các category: `pii_injection`, `jailbreak`, `off_topic`, `prompt_injection`, `allowed_query`...) qua full stack **theo đúng thứ tự**: Presidio trước (sync, nhanh), nếu chưa bị chặn mới tới NeMo input rail (async). So `actual` với `expected` (`blocked`/`allowed`).

**Cạm bẫy kỹ thuật:** `asyncio.run()` chỉ được gọi **một lần** bao ngoài toàn bộ loop — tuyệt đối không gọi `asyncio.run()` bên trong vòng for (sẽ lỗi event loop). Mẫu đúng nằm trong comment TODO: định nghĩa `async def _run_all()` rồi `asyncio.run(_run_all())`.

**Pass:** ≥ 15/20 (75%). **Bonus +3:** ≥ 18/20 (90%). Nếu thiếu, mở rộng patterns trong `rails.co` (thêm utterances cho `ask jailbreak` / `ask off topic` / `ask pii request` theo các input bị miss).

### Task 11 — `check_output_rail(question, answer, rails)` (5đ)
Gọi `generate_async` với **cả 2 message** (user = question, assistant = answer cần kiểm tra) để output rail có context. Nếu NeMo flag → trả `safe=False` và `final_answer` = message thay thế; ngược lại trả `answer` gốc.

### Task 12 — `measure_p95_latency(test_inputs, n_runs=20, ...)` (5đ)
Đo riêng từng tầng bằng `time.perf_counter()`: Presidio (sync, kỳ vọng <10ms), NeMo input rail (LLM call, ~200–800ms), total = tổng hai tầng. Tính p50/p95/p99 trên mảng đã sort, `latency_budget_ok = p95_total < 500` (`LATENCY_BUDGET_P95_MS` trong config). Cùng quy tắc `asyncio.run()` một lần.

Chạy: `python src/phase_c_guard.py` → sinh `reports/guard_results.json`.

### Task 13 — `reports/blueprint.md` (điền tay, 8–10đ riêng)
Template đã có sẵn với 4 section: Guard Stack Architecture, Latency Budget (điền số thật từ Task 12), CI/CD Gates, Monitoring + bảng "Kết quả thực tế từ Lab" (RAGAS avg, worst metric, dominant failure, Cohen κ, adversarial pass rate, P95). `check_lab.py` kiểm tra: không còn placeholder `[Họ Tên]` và file > 500 ký tự. **Để trống = −10đ.**

---

## 6. Chiến lược làm bài & phân bổ thời gian

1. **Trước giờ:** hoàn tất setup bước 1–5. Kiểm tra `answers_50q.json` có đúng 50 entries (`check_lab.py` kiểm điều này).
2. **Phase A (30'):** code trong comment TODO gần như đầy đủ — ưu tiên Task 1, 3, 4 (pure logic, không tốn API call) rồi Task 2. Chạy `pytest tests/test_phase_a.py -v` ngay.
3. **Phase B (35'):** Task 7 là pure math — làm trước cho chắc 10đ. Task 5/6 tốn API call (mỗi lần swap = 2 calls). Chú ý convert winner pass 2.
4. **Phase C (35'):** Task 9a + 12 là chắc điểm. Task 10 chiếm 10đ + bonus — dành thời gian mở rộng `rails.co` nếu pass rate < 75%.
5. **10' cuối:** điền `blueprint.md`, `analysis/*.md`, chạy bộ 3 lệnh kiểm tra cuối.

## 7. Các lỗi mất điểm phổ biến (theo RUBRIC)

- Còn `# TODO` trong `src/phase_*.py` → **−5đ/module** (check_lab.py đếm số TODO).
- Test fail → −3đ/test.
- `reports/blueprint.md` trống → −10đ.
- Thiếu `answers_50q.json` → Phase A = 0đ.
- Quên convert winner sau swap (Task 6), chia 0 trong `bias_report` (Task 8), gọi `asyncio.run()` trong loop (Task 10/12), nhầm thứ tự sort của `bottom_10` (phải **tăng dần**, rank 1 = tệ nhất).

## 8. Checklist nộp bài

```bash
pytest tests/ -v                   # toàn bộ tests pass
grep -r "# TODO" src/phase_*.py    # phải ra 0 kết quả
python check_lab.py                # tất cả checks ✓
```

Deliverables push lên GitHub: 3 file `src/phase_*.py` đã implement, `reports/` đủ 4 file (3 JSON auto-generated + `blueprint.md` điền tay), `analysis/failure_clusters.md` + `analysis/bias_report.md`, và `answers_50q.json`.

**Điểm:** Phase A 30 + Phase B 35 + Phase C 35 = 100; bonus tối đa +10 (adversarial < factual ở Phase A; κ > 0.6 ở Phase B; pass rate ≥ 18/20 ở Phase C).
