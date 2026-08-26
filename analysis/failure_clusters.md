# Failure Cluster Analysis — Phase A

## 1. Aggregate RAGAS Scores

| Metric | factual | multi_hop | adversarial |
|---|---:|---:|---:|
| faithfulness | 0.900 | 0.376 | 0.583 |
| answer_relevancy | 0.691 | 0.579 | 0.575 |
| context_precision | 0.971 | 1.000 | 0.983 |
| context_recall | 0.925 | 0.750 | 0.717 |
| **avg_score** | **0.872** | **0.676** | **0.715** |

## 2. Bottom 10 Questions

| Rank | Distribution | ID | avg_score | worst_metric |
|---:|---|---:|---:|---|
| 1 | multi_hop | 33 | 0.3750 | faithfulness |
| 2 | factual | 5 | 0.3958 | answer_relevancy |
| 3 | multi_hop | 34 | 0.4167 | faithfulness |
| 4 | adversarial | 48 | 0.4167 | faithfulness |
| 5 | adversarial | 50 | 0.4167 | faithfulness |
| 6 | factual | 9 | 0.5000 | faithfulness |
| 7 | multi_hop | 39 | 0.5000 | faithfulness |
| 8 | multi_hop | 24 | 0.5744 | faithfulness |
| 9 | multi_hop | 31 | 0.5999 | faithfulness |
| 10 | factual | 6 | 0.6250 | answer_relevancy |

## 3. Failure Cluster Matrix

| worst_metric | factual | multi_hop | adversarial | Total |
|---|---:|---:|---:|---:|
| faithfulness | 2 | 15 | 5 | 22 |
| answer_relevancy | 18 | 4 | 1 | 23 |
| context_precision | 0 | 0 | 0 | 0 |
| context_recall | 0 | 1 | 4 | 5 |

## 4. Dominant Failure Analysis

**Dominant distribution:** factual (the report's worst-metric count is highest by distribution only because it contains 20 questions; multi_hop has the weakest average score).

**Dominant metric:** answer_relevancy by count; faithfulness is the main quality problem for multi-hop and adversarial questions.

Factual retrieval is strong, but short answers sometimes omit qualifiers required by the question, lowering answer relevancy. Multi-hop questions require arithmetic and combining several policies, which explains the lower faithfulness score. Adversarial questions expose version conflicts and negations, so the answer must explicitly prioritize current policy versions. Context precision is already near 1.0 and is not the bottleneck.

## 5. Suggested Fixes

| Metric | Root cause | Suggested fix |
|---|---|---|
| faithfulness | Multi-step calculations and policy conflicts | Require answers to cite the relevant policy version and show calculations. |
| context_recall | Relevant facts split across chunks | Increase retrieval depth for multi-hop queries and preserve parent context. |
| context_precision | Not a material issue in this run | Keep reranking; avoid adding another retrieval layer without evidence. |
| answer_relevancy | Answers omit part of compound questions | Use a checklist prompt covering every requested field. |

## 6. Adversarial Distribution

Adversarial average score is 0.715, below factual (0.872) but above multi-hop (0.676). The bottom 10 contains IDs 48 and 50, both negation/policy-conflict traps. The main risk is not retrieval precision; it is selecting the current policy and preserving explicit “KHÔNG” answers.
