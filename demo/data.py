"""Lớp truy cập dữ liệu cho demo app.

Nguyên tắc: demo KHÔNG tự tính điểm. Mọi số liệu thật đến từ một trong ba nguồn,
theo thứ tự ưu tiên:

    1. "live"   — vừa chạy `src/phase_*.py` ngay trong app (lưu ở session_state)
    2. "report" — đọc từ `reports/*.json` do phase script sinh ra
    3. "sample" — số liệu MẪU trong `demo/sample.py`, chỉ để xem layout

Nguồn nào đang dùng luôn được hiển thị trên UI để không nhầm lẫn.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from demo import sample as _sample  # noqa: E402
from demo.theme import DISTRIBUTIONS, METRICS  # noqa: E402

# ── Source tag ───────────────────────────────────────────────────────────────

SOURCE_LABEL = {
    "live": "Live run",
    "report": "reports/",
    "sim": "Mô phỏng",
    "sample": "Dữ liệu MẪU",
    "none": "Chưa có dữ liệu",
}


@dataclass
class Source:
    kind: str = "none"          # live | report | sample | none
    detail: str = ""            # ví dụ: "reports/ragas_50q.json"
    partial: bool = False       # chỉ có số tổng hợp, không có từng câu

    @property
    def is_real(self) -> bool:
        return self.kind in ("live", "report")

    @property
    def label(self) -> str:
        base = SOURCE_LABEL.get(self.kind, self.kind)
        return f"{base} · {self.detail}" if self.detail else base


# ── File IO ──────────────────────────────────────────────────────────────────


def path(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


@st.cache_data(show_spinner=False)
def _read_json(abs_path: str, _mtime: float) -> Any:
    with open(abs_path, encoding="utf-8") as f:
        return json.load(f)


def read_json(*parts: str) -> Any | None:
    """Đọc JSON, trả None nếu không tồn tại. mtime nằm trong cache key."""
    p = path(*parts)
    if not os.path.exists(p):
        return None
    try:
        return _read_json(p, os.path.getmtime(p))
    except (json.JSONDecodeError, OSError):
        return None


def write_text(rel_path: str, content: str) -> str:
    p = path(rel_path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


# ── Static datasets ──────────────────────────────────────────────────────────


def test_set() -> list[dict]:
    return read_json("test_set_50q.json") or []


def answers() -> list[dict]:
    return read_json("answers_50q.json") or []


def human_labels() -> list[dict]:
    return read_json("human_labels_10q.json") or []


def adversarial_set() -> list[dict]:
    return read_json("adversarial_set_20.json") or []


def corpus_files() -> list[str]:
    d = path("data")
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.lower().endswith((".md", ".pdf")))


DATASETS = [
    ("test_set_50q.json", "Test set", "50 câu · 3 distributions"),
    ("answers_50q.json", "Answers", "output pipeline Day 18"),
    ("human_labels_10q.json", "Human labels", "10 nhãn cho Cohen κ"),
    ("adversarial_set_20.json", "Adversarial set", "20 input tấn công"),
]


def dataset_status() -> list[dict]:
    out = []
    for fname, label, hint in DATASETS:
        p = path(fname)
        exists = os.path.exists(p)
        data = read_json(fname) if exists else None
        out.append(
            {
                "file": fname,
                "label": label,
                "hint": hint,
                "exists": exists,
                "count": len(data) if isinstance(data, list) else 0,
            }
        )
    return out


# ── Environment / implementation probe ───────────────────────────────────────

_PHASE_FILES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "A": (
        "src/phase_a_ragas.py",
        [
            ("group_by_distribution", "Task 1 · group_by_distribution"),
            ("run_ragas_50q", "Task 2 · run_ragas_50q"),
            ("bottom_10", "Task 3 · bottom_10"),
            ("cluster_analysis", "Task 4 · cluster_analysis"),
        ],
    ),
    "B": (
        "src/phase_b_judge.py",
        [
            ("pairwise_judge", "Task 5 · pairwise_judge"),
            ("swap_and_average", "Task 6 · swap_and_average"),
            ("cohen_kappa", "Task 7 · cohen_kappa"),
            ("bias_report", "Task 8 · bias_report"),
        ],
    ),
    "C": (
        "src/phase_c_guard.py",
        [
            ("pii_scan", "Task 9a · pii_scan"),
            ("check_input_rail", "Task 9b · check_input_rail"),
            ("run_adversarial_suite", "Task 10 · run_adversarial_suite"),
            ("check_output_rail", "Task 11 · check_output_rail"),
            ("measure_p95_latency", "Task 12 · measure_p95_latency"),
        ],
    ),
}


@st.cache_data(show_spinner=False)
def _scan_functions(abs_path: str, _mtime: float) -> tuple[dict[str, bool], str]:
    """{tên hàm: đã implement?} — parse AST, không import, không gọi hàm.

    Tiêu chí "đã implement" giống checklist của lab: không còn `# TODO` trong thân hàm.
    """
    try:
        with open(abs_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except FileNotFoundError:
        return {}, "chưa có file"
    except (OSError, SyntaxError) as exc:
        return {}, f"{type(exc).__name__}: {exc}"

    found: dict[str, bool] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            segment = ast.get_source_segment(source, node) or ""
            found[node.name] = "# TODO" not in segment
    return found, ""


def task_status() -> list[dict]:
    """Trạng thái 13 task, đọc lại mỗi khi file source đổi (mtime trong cache key)."""
    rows: list[dict] = []
    for phase, (rel_path, tasks) in _PHASE_FILES.items():
        abs_path = path(rel_path)
        mtime = os.path.getmtime(abs_path) if os.path.exists(abs_path) else 0.0
        found, error = _scan_functions(abs_path, mtime)
        for fn_name, label in tasks:
            rows.append(
                {
                    "phase": phase,
                    "task": label,
                    "file": rel_path,
                    "done": found.get(fn_name, False),
                    "error": error or ("" if fn_name in found else "không tìm thấy hàm"),
                }
            )
    return rows


def tasks_done(phase: str) -> tuple[int, int]:
    rows = [r for r in task_status() if r["phase"] == phase]
    return sum(1 for r in rows if r["done"]), len(rows)


@st.cache_data(show_spinner=False)
def env_status() -> list[dict]:
    def has(mod: str) -> bool:
        try:
            return importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            return False

    key = ""
    try:
        from config import OPENAI_API_KEY

        key = OPENAI_API_KEY or ""
    except Exception:
        pass

    return [
        {"name": "OPENAI_API_KEY", "ok": bool(key), "hint": "…" + key[-4:] if key else "chưa set trong .env"},
        {"name": "presidio-analyzer", "ok": has("presidio_analyzer"), "hint": "PII engine (Task 9a)"},
        {"name": "nemoguardrails", "ok": has("nemoguardrails"), "hint": "input/output rails (9b, 11)"},
        {"name": "ragas", "ok": has("ragas"), "hint": "4 metrics (Task 2)"},
        {"name": "plotly", "ok": has("plotly"), "hint": "charts cho demo"},
    ]


# ── Phase A ──────────────────────────────────────────────────────────────────


@dataclass
class PhaseA:
    rows: list[dict] = field(default_factory=list)   # từng câu hỏi (có thể rỗng)
    per_dist: dict = field(default_factory=dict)     # distribution → {metric: score}
    overall: dict = field(default_factory=dict)      # metric → score
    clusters: dict = field(default_factory=dict)
    bottom10: list[dict] = field(default_factory=list)
    source: Source = field(default_factory=Source)

    @property
    def has_data(self) -> bool:
        return bool(self.per_dist or self.rows)


def _aggregate(rows: list[dict]) -> tuple[dict, dict]:
    per_dist: dict[str, dict] = {}
    for dist in DISTRIBUTIONS:
        subset = [r for r in rows if r["distribution"] == dist]
        if not subset:
            continue
        agg = {m: sum(r[m] for r in subset) / len(subset) for m in METRICS}
        agg["avg_score"] = sum(agg[m] for m in METRICS) / len(METRICS)
        agg["count"] = len(subset)
        per_dist[dist] = agg
    overall = (
        {m: sum(r[m] for r in rows) / len(rows) for m in METRICS} if rows else {}
    )
    if overall:
        overall["avg_score"] = sum(overall[m] for m in METRICS) / len(METRICS)
    return per_dist, overall


def _cluster_matrix(rows: list[dict]) -> dict:
    matrix = {m: {d: 0 for d in DISTRIBUTIONS} for m in METRICS}
    for r in rows:
        matrix[r["worst_metric"]][r["distribution"]] += 1
    dominant_dist = max(DISTRIBUTIONS, key=lambda d: sum(matrix[m][d] for m in METRICS))
    dominant_metric = max(METRICS, key=lambda m: sum(matrix[m].values()))
    return {
        "matrix": matrix,
        "dominant_failure_distribution": dominant_dist,
        "dominant_failure_metric": dominant_metric,
    }


cluster_matrix = _cluster_matrix  # alias công khai cho các view


def normalize_ragas_rows(raw: list[Any]) -> list[dict]:
    """Chuẩn hoá `RagasResult` (dataclass) hoặc dict về một schema dict duy nhất."""
    rows = []
    for item in raw:
        get = (lambda k, d=None: getattr(item, k, d)) if not isinstance(item, dict) else item.get
        row = {
            "question_id": get("question_id") or get("id") or 0,
            "distribution": get("distribution") or "factual",
            "question": get("question") or "",
            "answer": get("answer") or "",
            "contexts": get("contexts") or [],
            "ground_truth": get("ground_truth") or "",
        }
        for m in METRICS:
            try:
                row[m] = float(get(m) or 0.0)
            except (TypeError, ValueError):
                row[m] = 0.0
        row["avg_score"] = sum(row[m] for m in METRICS) / 4
        row["worst_metric"] = min(METRICS, key=lambda m: row[m])
        rows.append(row)
    return rows


def phase_a(use_sample: bool) -> PhaseA:
    # 1. live
    live = st.session_state.get("phase_a_rows")
    if live:
        rows = normalize_ragas_rows(live)
        per_dist, overall = _aggregate(rows)
        return PhaseA(rows, per_dist, overall, _cluster_matrix(rows),
                      bottom_10_rows(rows), Source("live", "src/phase_a_ragas.py"))

    # 2. report
    rep = read_json("reports", "ragas_50q.json")
    if isinstance(rep, dict) and rep.get("per_distribution"):
        per_dist = {d: dict(v) for d, v in rep["per_distribution"].items()}
        n = sum(v.get("count", 0) for v in per_dist.values()) or 1
        overall = {
            m: sum(v.get(m, 0) * v.get("count", 0) for v in per_dist.values()) / n
            for m in METRICS
        }
        overall["avg_score"] = sum(overall[m] for m in METRICS) / len(METRICS)
        return PhaseA(
            rows=[],
            per_dist=per_dist,
            overall=overall,
            clusters=rep.get("failure_clusters", {}) or {},
            bottom10=rep.get("bottom_10", []) or [],
            source=Source("report", "reports/ragas_50q.json", partial=True),
        )

    # 3. sample
    if use_sample:
        rows = _sample.ragas_rows(answers() or test_set())
        per_dist, overall = _aggregate(rows)
        return PhaseA(rows, per_dist, overall, _cluster_matrix(rows),
                      bottom_10_rows(rows), Source("sample"))

    return PhaseA()


DIAGNOSTIC_TREE = {
    "faithfulness": ("LLM hallucinating", "Siết system prompt, giảm temperature"),
    "context_recall": ("Thiếu chunk liên quan", "Cải thiện chunking hoặc thêm BM25"),
    "context_precision": ("Quá nhiều chunk nhiễu", "Thêm reranking hoặc metadata filter"),
    "answer_relevancy": ("Câu trả lời lệch câu hỏi", "Cải thiện prompt template"),
}


def bottom_10_rows(rows: list[dict], n: int = 10) -> list[dict]:
    out = []
    for i, r in enumerate(sorted(rows, key=lambda x: x["avg_score"])[:n]):
        diag, fix = DIAGNOSTIC_TREE[r["worst_metric"]]
        out.append(
            {
                "rank": i + 1,
                "question_id": r["question_id"],
                "distribution": r["distribution"],
                "question": r["question"],
                "avg_score": round(r["avg_score"], 4),
                "worst_metric": r["worst_metric"],
                "diagnosis": diag,
                "suggested_fix": fix,
            }
        )
    return out


def run_phase_a() -> tuple[int, str]:
    """Gọi thật `run_ragas_50q()` trên answers_50q.json. → (số row, lỗi)."""
    try:
        mod = importlib.import_module("src.phase_a_ragas")
        data = answers()
        if not data:
            return 0, "Chưa có answers_50q.json — chạy `python setup_answers.py` trước."
        results = mod.run_ragas_50q(data)
        if not results:
            return 0, "`run_ragas_50q()` trả về rỗng — Task 2 chưa implement."
        st.session_state["phase_a_rows"] = results
        return len(results), ""
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


# ── Phase B ──────────────────────────────────────────────────────────────────


@dataclass
class PhaseB:
    rows: list[dict] = field(default_factory=list)   # từng cặp đã judge
    kappa: float | None = None
    bias: dict = field(default_factory=dict)
    source: Source = field(default_factory=Source)

    @property
    def has_data(self) -> bool:
        return bool(self.rows) or self.kappa is not None


def normalize_judge_rows(raw: list[Any]) -> list[dict]:
    rows = []
    for item in raw:
        get = (lambda k, d=None: getattr(item, k, d)) if not isinstance(item, dict) else item.get
        rows.append(
            {
                "question": get("question") or "",
                "answer_a": get("answer_a") or "",
                "answer_b": get("answer_b") or "",
                "winner_pass1": get("winner_pass1") or "tie",
                "winner_pass2": get("winner_pass2") or "tie",
                "final_winner": get("final_winner") or "tie",
                "reasoning_pass1": get("reasoning_pass1") or "",
                "reasoning_pass2": get("reasoning_pass2") or "",
                "position_consistent": bool(get("position_consistent", True)),
                "judge_label": get("judge_label"),
                "human_label": get("human_label"),
                "question_id": get("question_id"),
            }
        )
    return rows


def phase_b(use_sample: bool) -> PhaseB:
    live = st.session_state.get("phase_b_rows")
    if live:
        rows = normalize_judge_rows(live)
        return PhaseB(
            rows,
            st.session_state.get("phase_b_kappa"),
            st.session_state.get("phase_b_bias", {}) or {},
            Source("live", "src/phase_b_judge.py"),
        )

    rep = read_json("reports", "judge_results.json")
    if isinstance(rep, dict) and (rep.get("results") or rep.get("kappa") is not None):
        return PhaseB(
            normalize_judge_rows(rep.get("results", []) or []),
            rep.get("kappa"),
            rep.get("bias_report", {}) or rep.get("bias", {}) or {},
            Source("report", "reports/judge_results.json"),
        )

    if use_sample:
        rows, kappa, bias = _sample.judge(human_labels(), test_set())
        return PhaseB(rows, kappa, bias, Source("sample"))

    return PhaseB()


def run_phase_b(pairs: list[dict], persist: bool = True) -> tuple[list[dict], str]:
    """Chạy swap_and_average trên các cặp answer, rồi κ + bias report.

    persist=False dùng cho pairwise arena: không ghi đè kết quả 10 cặp đang có.
    """
    try:
        mod = importlib.import_module("src.phase_b_judge")
        results = [mod.swap_and_average(p["question"], p["answer_a"], p["answer_b"]) for p in pairs]
        if not any(getattr(r, "reasoning_pass1", "") for r in results):
            return [], "Judge trả về rỗng — Task 5/6 chưa implement (hoặc thiếu API key)."
        rows = normalize_judge_rows(results)
        for row, p in zip(rows, pairs):
            row["question_id"] = p.get("question_id")
            row["human_label"] = p.get("human_label")
            # A = answer của pipeline, B = ground truth → A thắng/tie ⇒ judge cho nhãn 1
            row["judge_label"] = 1 if row["final_winner"] in ("A", "tie") else 0
        if not persist:
            return rows, ""
        labels = [r["judge_label"] for r in rows if r.get("human_label") is not None]
        humans = [r["human_label"] for r in rows if r.get("human_label") is not None]
        st.session_state["phase_b_rows"] = rows
        st.session_state["phase_b_kappa"] = mod.cohen_kappa(labels, humans) if labels else None
        st.session_state["phase_b_bias"] = mod.bias_report(results)
        return rows, ""
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


# ── Phase C ──────────────────────────────────────────────────────────────────


@dataclass
class PhaseC:
    rows: list[dict] = field(default_factory=list)   # 20 adversarial results
    latency: dict = field(default_factory=dict)
    source: Source = field(default_factory=Source)

    @property
    def has_data(self) -> bool:
        return bool(self.rows) or bool(self.latency)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.rows if r.get("passed"))


def phase_c(use_sample: bool) -> PhaseC:
    live_rows = st.session_state.get("phase_c_rows")
    live_lat = st.session_state.get("phase_c_latency")
    if live_rows or live_lat:
        simulated = bool(st.session_state.get("phase_c_simulated"))
        source = (
            Source("sim", "demo/simulate.py — regex, không phải Presidio/NeMo")
            if simulated
            else Source("live", "src/phase_c_guard.py")
        )
        return PhaseC(live_rows or [], live_lat or {}, source)

    rep = read_json("reports", "guard_results.json")
    if isinstance(rep, dict) and (rep.get("adversarial") or rep.get("latency")):
        return PhaseC(
            rep.get("adversarial", []) or rep.get("results", []) or [],
            rep.get("latency", {}) or {},
            Source("report", "reports/guard_results.json"),
        )

    if use_sample:
        rows, latency = _sample.guard(adversarial_set())
        return PhaseC(rows, latency, Source("sample"))

    return PhaseC()


def run_phase_c_sim() -> tuple[int, str]:
    """Chạy suite bằng guard mô phỏng trong `demo/simulate.py` (không cần cài gì)."""
    from demo import simulate

    items = adversarial_set()
    if not items:
        return 0, "Không đọc được adversarial_set_20.json."
    st.session_state["phase_c_rows"] = simulate.run_suite(items)
    st.session_state["phase_c_latency"] = simulate.measure_latency(
        [i["input"] for i in items], GATE_LATENCY_MS
    )
    st.session_state["phase_c_simulated"] = True
    return len(items), ""


def run_phase_c() -> tuple[int, str]:
    """Chạy adversarial suite + đo P95 latency bằng code thật của Phase C."""
    try:
        mod = importlib.import_module("src.phase_c_guard")
        items = adversarial_set()
        if not items:
            return 0, "Không đọc được adversarial_set_20.json."
        rows = mod.run_adversarial_suite(items)
        if not rows:
            return 0, "`run_adversarial_suite()` trả về rỗng — Task 10 chưa implement."
        latency = mod.measure_p95_latency([i["input"] for i in items[:10]], n_runs=10)
        st.session_state["phase_c_rows"] = rows
        st.session_state["phase_c_latency"] = latency
        st.session_state["phase_c_simulated"] = False
        return len(rows), ""
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def run_pii_scan(text: str) -> tuple[dict, str]:
    """Gọi `pii_scan()` thật (Presidio). Trả (kết quả, lỗi)."""
    try:
        mod = importlib.import_module("src.phase_c_guard")
        engine = st.session_state.get("presidio_engine")
        if engine is None:
            engine = mod.setup_presidio()
            st.session_state["presidio_engine"] = engine
        return mod.pii_scan(text, *engine), ""
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def run_input_rail(text: str) -> tuple[dict, str]:
    """Gọi `check_input_rail()` thật (NeMo, async)."""
    import asyncio

    try:
        mod = importlib.import_module("src.phase_c_guard")
        rails = st.session_state.get("nemo_rails")
        if rails is None:
            rails = mod.setup_nemo_rails()
            st.session_state["nemo_rails"] = rails
        return asyncio.run(mod.check_input_rail(text, rails)), ""
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


# ── CI gates ─────────────────────────────────────────────────────────────────

GATE_FAITHFULNESS = 0.75
GATE_ADVERSARIAL = 0.90
GATE_LATENCY_MS = 500
GATE_KAPPA = 0.60
