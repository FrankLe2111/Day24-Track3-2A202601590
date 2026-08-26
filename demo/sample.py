"""Dữ liệu MẪU (synthetic) — chỉ dùng để xem layout khi chưa có kết quả thật.

⚠️  Không có số nào ở đây là kết quả đo thật. Mọi giá trị sinh ra deterministic
(hash-based, không random) để screenshot không đổi giữa các lần chạy. UI luôn dán
nhãn "Dữ liệu MẪU" khi lấy từ module này.

Bố cục số liệu được chọn cho giống một pipeline thật ở giữa quá trình tinh chỉnh:
adversarial yếu hơn factual, context_recall là metric yếu nhất, κ chớm dưới ngưỡng
bonus 0.6, và guard stack chặn được 18/20.
"""

from __future__ import annotations

import hashlib

from demo.theme import DISTRIBUTIONS, METRICS

# ── Deterministic pseudo-random ──────────────────────────────────────────────


def _unit(*key: object) -> float:
    """Số [0,1) ổn định theo key — không dùng random để screenshot bất biến."""
    digest = hashlib.md5("|".join(str(k) for k in key).encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


# ── Phase A ──────────────────────────────────────────────────────────────────

_DIST_BASE = {"factual": 0.885, "multi_hop": 0.775, "adversarial": 0.625}
_METRIC_OFFSET = {
    "faithfulness": 0.020,
    "answer_relevancy": 0.055,
    "context_precision": -0.015,
    "context_recall": -0.060,
}


def ragas_rows(items: list[dict]) -> list[dict]:
    """Sinh 4 metric mẫu cho từng câu hỏi trong test set / answers."""
    rows = []
    for item in items:
        dist = item.get("distribution", "factual")
        if dist not in DISTRIBUTIONS:
            dist = "factual"
        qid = item.get("id") or item.get("question_id") or 0
        row = {
            "question_id": qid,
            "distribution": dist,
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "contexts": item.get("contexts", []),
            "ground_truth": item.get("ground_truth", ""),
        }
        for metric in METRICS:
            jitter = (_unit(qid, metric) - 0.5) * 0.20
            score = _DIST_BASE[dist] + _METRIC_OFFSET[metric] + jitter
            row[metric] = round(min(1.0, max(0.05, score)), 4)
        row["avg_score"] = sum(row[m] for m in METRICS) / 4
        row["worst_metric"] = min(METRICS, key=lambda m: row[m])
        rows.append(row)
    return rows


# ── Phase B ──────────────────────────────────────────────────────────────────

# Judge lệch human ở 2/10 câu → κ ≈ 0.58 (Moderate, chưa đạt bonus 0.6).
_JUDGE_FLIPS = {12, 29}          # question_id mà judge không đồng ý với human
_POSITION_INCONSISTENT = {5, 41}  # question_id mà pass1 ≠ pass2 (position bias)

_REASONING = {
    1: "Cả hai đều nêu đúng 3 ngày; A ngắn gọn hơn và không thêm thông tin ngoài context.",
    0: "A thiếu điều kiện quan trọng nên B chính xác hơn về mặt chính sách.",
}


def _kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    p_o = sum(x == y for x, y in zip(a, b)) / n
    p_e = (a.count(1) / n) * (b.count(1) / n) + (a.count(0) / n) * (b.count(0) / n)
    return round((p_o - p_e) / (1 - p_e), 4) if p_e != 1 else 0.0


def judge(labels: list[dict], tests: list[dict]) -> tuple[list[dict], float, dict]:
    """Kết quả judge mẫu dựng trên 10 human label thật + ground truth thật."""
    truth = {t.get("id"): t.get("ground_truth", "") for t in tests}
    rows: list[dict] = []

    for item in labels:
        qid = item.get("question_id")
        human = int(item.get("human_label", 0))
        judge_label = 1 - human if qid in _JUDGE_FLIPS else human
        # A = câu trả lời của pipeline, B = ground truth (reference answer)
        winner = "A" if judge_label == 1 else "B"
        consistent = qid not in _POSITION_INCONSISTENT
        rows.append(
            {
                "question": item.get("question", ""),
                "answer_a": item.get("model_answer", ""),
                "answer_b": truth.get(qid, "") or item.get("human_note", ""),
                "winner_pass1": winner,
                "winner_pass2": winner if consistent else ("B" if winner == "A" else "A"),
                "final_winner": winner if consistent else "tie",
                "reasoning_pass1": _REASONING[judge_label],
                "reasoning_pass2": _REASONING[judge_label] if consistent else
                "Đảo thứ tự cho kết quả khác — dấu hiệu position bias.",
                "position_consistent": consistent,
                "judge_label": judge_label,
                "human_label": human,
                "question_id": qid,
            }
        )

    kappa = _kappa([r["judge_label"] for r in rows], [r["human_label"] for r in rows])

    decisive = [r for r in rows if r["final_winner"] != "tie"]
    a_longer = sum(1 for r in decisive if r["final_winner"] == "A" and len(r["answer_a"]) > len(r["answer_b"]))
    b_longer = sum(1 for r in decisive if r["final_winner"] == "B" and len(r["answer_b"]) > len(r["answer_a"]))
    inconsistent = sum(1 for r in rows if not r["position_consistent"])
    bias = {
        "total_judged": len(rows),
        "position_bias_count": inconsistent,
        "position_bias_rate": round(inconsistent / len(rows), 3) if rows else 0.0,
        "verbosity_bias": round((a_longer + b_longer) / len(decisive), 3) if decisive else 0.0,
        "verbosity_details": {
            "a_wins_a_longer": a_longer,
            "b_wins_b_longer": b_longer,
            "total_decisive": len(decisive),
        },
        "interpretation": "Position bias thấp — swap-and-average đang giữ judge ổn định.",
    }
    return rows, kappa, bias


# ── Phase C ──────────────────────────────────────────────────────────────────

# Hai ca mẫu bị miss, giống lỗi thật hay gặp:
#   id 5  — hỏi PII của người khác nhưng bản thân query không chứa PII
#   id 14 — câu hỏi toán học, rail off-topic không bắt được
_GUARD_MISSES = {5, 14}


def guard(items: list[dict]) -> tuple[list[dict], dict]:
    rows = []
    for item in items:
        expected = item.get("expected", "blocked")
        missed = item.get("id") in _GUARD_MISSES
        actual = "allowed" if missed else expected
        blocked_by = None
        if actual == "blocked":
            blocked_by = "presidio" if item.get("block_layer") == "presidio" else "nemo_input"
        rows.append(
            {
                "id": item.get("id"),
                "category": item.get("category", ""),
                "input": item.get("input", "")[:80] + "...",
                "expected": expected,
                "actual": actual,
                "blocked_by": blocked_by,
                "passed": actual == expected,
            }
        )

    latency = {
        "presidio_ms": {"p50": 3.1, "p95": 6.8, "p99": 9.4},
        "nemo_ms": {"p50": 268.4, "p95": 401.7, "p99": 512.3},
        "total_ms": {"p50": 271.5, "p95": 408.5, "p99": 521.7},
        "latency_budget_ok": True,
        "budget_ms": 500,
    }
    return rows, latency
