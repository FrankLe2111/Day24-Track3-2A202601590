# LLM Judge Bias Report — Phase B

**Judge model:** gpt-4o-mini
**Pairwise cases:** 1 demo pair
**Position bias rate:** 0% (0/1 inconsistent)

## Pairwise Result

| # | Question | Winner | Final | Position consistent |
|---:|---|---|---|---|
| 1 | Số ngày phép năm hiện hành | A | A | Yes |

Answer A correctly used the current v2024 policy (15 days), while Answer B used the obsolete 12-day policy.

## Cohen's κ

The current report contains a demo pair only, not the 10 human-labeled evaluation pairs; therefore a production κ comparison is not claimed here. Run the judge on the same 10 question IDs before using κ as a reliability metric.

## Verbosity Bias

The demo had one decisive case and the winning answer was longer, so the observed longer-winner rate was 100% (1/1). This sample is too small to establish a verbosity trend.

## Recommendation

Swap-and-average is useful because it detects disagreement caused by answer position. For production evaluation, judge the same 10 questions used by `human_labels_10q.json`, persist both passes, and compute κ only after labels are aligned by question ID. Use the judge as an evaluation signal, not as the sole source of truth.
