# Demo Streamlit — Lab 24 Eval + Guardrail Stack

Một dashboard cho toàn bộ lab: RAGAS 50 câu, LLM-as-Judge, guard stack, và blueprint
Task 13. **Chạy được ngay cả khi chưa implement task nào** — chỗ nào chưa có số thật thì
UI nói rõ là chưa có.

```bash
pip install -r requirements-demo.txt      # streamlit + plotly
streamlit run demo_app.py                 # → http://localhost:8501
```

---

## Ba nguồn dữ liệu, ưu tiên từ trên xuống

| Nguồn | Ở đâu ra | Nhãn trên UI |
|---|---|---|
| **Live run** | bấm nút "Chạy…" trong app → gọi thẳng `src/phase_*.py` | `Live run` |
| **Report** | `reports/ragas_50q.json`, `judge_results.json`, `guard_results.json` | `reports/` |
| **Mô phỏng** | `demo/simulate.py` — regex thay cho Presidio/NeMo, chỉ ở Phase C | `Mô phỏng` |
| **Dữ liệu MẪU** | `demo/sample.py` — số synthetic để xem trước layout | `Dữ liệu MẪU` |

Kết quả thật luôn thắng dữ liệu mẫu. Nguồn hiện hành hiện ở sidebar và đầu mỗi trang,
nên không thể nhìn số mẫu mà tưởng là số đo.

> Tắt "Dữ liệu mẫu" ở sidebar nếu muốn thấy đúng trạng thái trống của từng phase.

---

## Các trang

**Overview** — 4 CI gate (faithfulness, adversarial pass rate, guard P95, Cohen κ),
sơ đồ guard stack kèm latency thực đo, trạng thái 4 dataset, và tiến độ 13 task đọc
trực tiếp từ source (`# TODO` còn hay hết).

**Phase A · RAGAS** — 4 metric × 3 distribution trên một trục 0–1, ma trận failure
cluster (metric yếu nhất × distribution), điểm từng câu với ngưỡng 0.75, bottom 10 kèm
chẩn đoán từ diagnostic tree, và panel soi từng câu (answer / contexts / ground truth).

**Phase B · Judge** — Cohen κ trên thang Landis–Koch, ma trận đồng thuận 2×2 với 10 nhãn
người, position bias + verbosity bias, và *pairwise arena*: gõ hai câu trả lời rồi chấm
hai lượt đảo thứ tự để thấy swap-and-average hoạt động.

**Phase C · Guardrails** — playground gõ input và xem nó đi qua từng lớp (lớp nào chặn,
vì sao, mất bao nhiêu ms, PII được tô và anonymize), adversarial suite 20 ca với các ca
lệch kỳ vọng tách riêng, và P95 latency so với budget 500 ms.

**Task 13 · Blueprint** — điền blueprint từ số đo hiện có, tải về hoặc ghi vào
`reports/blueprint.md`. Phần nhận xét và tên sinh viên để trống — app không viết hộ.
Nếu số đang là mẫu/mô phỏng, file sinh ra có cảnh báo ngay đầu file.

---

## Chạy code thật từ trong app

| Nút | Gọi hàm | Cần gì |
|---|---|---|
| Chạy RAGAS 50 câu | `run_ragas_50q()` | Task 2 + `answers_50q.json` + API key (5–10 phút) |
| Chạy swap-and-average ×10 | `swap_and_average()`, `cohen_kappa()`, `bias_report()` | Task 5–8 + API key (20 call) |
| Chạy suite — code thật | `run_adversarial_suite()`, `measure_p95_latency()` | Task 10, 12 + presidio + nemo |
| Chạy suite — mô phỏng | `demo/simulate.py` | không cần gì |
| Chạy qua guard stack | `pii_scan()`, `check_input_rail()` | Task 9a/9b (hoặc chọn mode mô phỏng) |

Kết quả live nằm trong session; "Xoá kết quả trong session" ở sidebar đưa về
`reports/` hoặc dữ liệu mẫu.

---

## Shape của `reports/*.json`

`reports/ragas_50q.json` do `save_phase_a_report()` của lab sinh ra — app đọc được luôn
(chỉ có số tổng hợp, nên các chart theo từng câu sẽ trống; muốn đầy thì chạy live).

Hai file còn lại bạn tự ghi. App đọc theo shape này:

```jsonc
// reports/judge_results.json
{
  "kappa": 0.62,
  "bias_report": { /* nguyên dict từ bias_report() */ },
  "results": [ /* list JudgeResult, thêm judge_label + human_label nếu muốn vẽ ma trận 2×2 */ ]
}

// reports/guard_results.json
{
  "adversarial": [ /* nguyên list từ run_adversarial_suite() */ ],
  "latency":     { /* nguyên dict từ measure_p95_latency() */ }
}
```

---

## Cấu trúc code

```
demo_app.py              entry point: page config, sidebar, routing
demo/
  theme.py               palette + CSS + component (kpi, badge, gate, empty state)
  data.py                đọc dataset, chọn nguồn, gọi src/phase_*.py
  charts.py              chart builder (plotly, một template dark dùng chung)
  sample.py              số liệu MẪU — deterministic, không random
  simulate.py            guard mô phỏng bằng regex (không phải Presidio/NeMo)
  views/                 một file cho mỗi trang
.streamlit/config.toml   theme khớp palette
```

Đổi màu: sửa khối `Tokens` trong `demo/theme.py` và `[theme]` trong
`.streamlit/config.toml`. Thêm chart: viết builder trong `demo/charts.py` rồi
`C.show(fig)` trong view.

Quy ước màu: categorical đi theo *entity* (mỗi distribution một hue cố định, filter không
đổi màu), sequential dùng một hue blue cho magnitude, status good/critical chỉ dùng cho
pass/fail và luôn kèm nhãn chữ để không phụ thuộc vào màu.
