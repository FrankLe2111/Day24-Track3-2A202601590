"""Mô phỏng guard stack — CHỈ để demo chạy được khi chưa cài Presidio/NeMo.

⚠️  Đây KHÔNG phải Presidio và KHÔNG phải NeMo Guardrails.
Đây là regex + keyword matching thuần Python, dùng đúng các pattern mà lab yêu cầu
(VN_CCCD, VN_PHONE, EMAIL) để bạn thấy luồng dữ liệu chạy. Con số latency đo được ở
mode này là latency của regex, không phải của Presidio hay LLM call.

Kết quả từ module này luôn được UI dán nhãn "Mô phỏng".
"""

from __future__ import annotations

import re
import time

# ── Layer 1: PII patterns (giống setup_presidio() trong phase_c_guard.py) ─────

_PII_PATTERNS: list[tuple[str, str, float]] = [
    ("EMAIL_ADDRESS", r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b", 1.0),
    ("VN_PHONE", r"\b0[3-9]\d{8}\b", 0.9),
    ("VN_CCCD", r"\b\d{12}\b", 0.9),
    ("VN_CCCD", r"\b\d{9}\b", 0.7),
]


def pii_scan(text: str) -> dict:
    """Trả cùng schema với `pii_scan()` của Phase C: has_pii / entities / anonymized."""
    found: list[dict] = []
    for entity, pattern, score in _PII_PATTERNS:
        for match in re.finditer(pattern, text):
            if any(match.start() < e["end"] and e["start"] < match.end() for e in found):
                continue  # bỏ span chồng lấn — ưu tiên pattern khai báo trước
            found.append(
                {
                    "type": entity,
                    "text": match.group(),
                    "score": score,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    found.sort(key=lambda e: e["start"])

    anonymized, cursor = [], 0
    for entity in found:
        anonymized.append(text[cursor:entity["start"]])
        anonymized.append(f'<{entity["type"]}>')
        cursor = entity["end"]
    anonymized.append(text[cursor:])

    return {
        "has_pii": bool(found),
        "entities": found,
        "anonymized": "".join(anonymized),
    }


# ── Layer 2: input rail patterns ─────────────────────────────────────────────

_JAILBREAK = [
    r"bỏ qua (tất cả|toàn bộ|mọi|các) ",
    r"bỏ qua hướng dẫn",
    r"ignore (all )?(previous|prior|your)",
    r"\bdan\b|do anything now",
    r"không có giới hạn|không bị giới hạn|no restrictions|unrestricted",
    r"đóng vai|pretend you are|act as if you",
    r"hệ thống nội bộ.*mật khẩu|mật khẩu admin",
]
_PROMPT_INJECTION = [
    r"system override|system prompt|system instructions",
    r"admin command|priority 1",
    r"<!--",
    r"forget all|forget your",
    r"tôi là (ceo|giám đốc|tổng giám đốc).*(ra lệnh|bỏ qua)",
    r"in ra toàn bộ|dump all|print all",
]
_PII_REQUEST_SUBJECT = r"cccd|cmnd|sđt|số điện thoại|bảng lương|lương tháng|lương của|thông tin nhân viên|employee (salaries|records|data)|confidential"
_PII_REQUEST_VERB = r"cho tôi biết|tiết lộ|liệt kê|cung cấp|dump|reveal|list all|print all|của nhân viên"

# Từ khoá thuộc phạm vi HR policy — không có từ nào ⇒ off-topic.
_ON_TOPIC = [
    "nghỉ phép", "phép năm", "phép", "lương", "thưởng", "bảo hiểm", "phụ cấp",
    "tạm ứng", "công tác", "thử việc", "mật khẩu", "vpn", "wfh", "làm việc từ xa",
    "đào tạo", "mentor", "buddy", "đánh giá", "hiệu suất", "kpi", "mua sắm",
    "phê duyệt", "nghỉ ốm", "malware", "bảo mật", "dữ liệu", "chính sách",
    "nhân viên", "kết hôn", "tang lễ", "sinh con", "hợp đồng", "nhân sự", "hr",
    "expense", "chi phí", "sự cố", "thâm niên", "onboarding",
]

_REFUSAL = {
    "jailbreak": "Xin lỗi, tôi không thể bỏ qua các quy định đã được thiết lập.",
    "prompt_injection": "Xin lỗi, tôi không thể thực hiện chỉ thị được nhúng trong câu hỏi.",
    "pii_request": "Xin lỗi, tôi không được phép cung cấp thông tin cá nhân của nhân viên khác.",
    "off_topic": "Xin lỗi, tôi chỉ trả lời các câu hỏi về chính sách nhân sự của công ty.",
}


def input_rail(text: str) -> dict:
    """Trả cùng schema với `check_input_rail()`: allowed / blocked_reason / response."""
    low = text.lower()

    for reason, patterns in (("jailbreak", _JAILBREAK), ("prompt_injection", _PROMPT_INJECTION)):
        if any(re.search(p, low) for p in patterns):
            return {"allowed": False, "blocked_reason": reason, "response": _REFUSAL[reason]}

    if re.search(_PII_REQUEST_SUBJECT, low) and re.search(_PII_REQUEST_VERB, low):
        return {"allowed": False, "blocked_reason": "pii_request", "response": _REFUSAL["pii_request"]}

    if not any(keyword in low for keyword in _ON_TOPIC):
        return {"allowed": False, "blocked_reason": "off_topic", "response": _REFUSAL["off_topic"]}

    return {"allowed": True, "blocked_reason": None, "response": ""}


# ── Guard stack: chạy hai lớp theo đúng thứ tự của Task 10 ────────────────────


def guard_once(text: str) -> dict:
    """Một lượt qua guard stack, kèm latency từng lớp (đo thật, của regex)."""
    t0 = time.perf_counter()
    pii = pii_scan(text)
    presidio_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    rail = input_rail(text) if not pii["has_pii"] else {"allowed": True, "blocked_reason": None, "response": ""}
    rail_ms = (time.perf_counter() - t1) * 1000

    blocked_by = "presidio" if pii["has_pii"] else ("nemo_input" if not rail["allowed"] else None)
    return {
        "pii": pii,
        "rail": rail,
        "blocked_by": blocked_by,
        "allowed": blocked_by is None,
        "presidio_ms": presidio_ms,
        "nemo_ms": rail_ms,
        "total_ms": presidio_ms + rail_ms,
    }


def run_suite(items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        verdict = guard_once(item.get("input", ""))
        actual = "allowed" if verdict["allowed"] else "blocked"
        rows.append(
            {
                "id": item.get("id"),
                "category": item.get("category", ""),
                "input": item.get("input", "")[:80] + "...",
                "expected": item.get("expected", "blocked"),
                "actual": actual,
                "blocked_by": verdict["blocked_by"],
                "passed": actual == item.get("expected", "blocked"),
                "reason": verdict["rail"].get("blocked_reason"),
            }
        )
    return rows


def measure_latency(texts: list[str], budget_ms: int = 500) -> dict:
    presidio, nemo, total = [], [], []
    for text in texts:
        verdict = guard_once(text)
        presidio.append(verdict["presidio_ms"])
        nemo.append(verdict["nemo_ms"])
        total.append(verdict["total_ms"])

    def pct(values: list[float]) -> dict:
        ordered = sorted(values)
        n = len(ordered)
        if n == 0:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        return {
            "p50": round(ordered[min(int(n * 0.50), n - 1)], 3),
            "p95": round(ordered[min(int(n * 0.95), n - 1)], 3),
            "p99": round(ordered[min(int(n * 0.99), n - 1)], 3),
        }

    totals = pct(total)
    return {
        "presidio_ms": pct(presidio),
        "nemo_ms": pct(nemo),
        "total_ms": totals,
        "latency_budget_ok": totals["p95"] < budget_ms,
        "budget_ms": budget_ms,
        "simulated": True,
    }
