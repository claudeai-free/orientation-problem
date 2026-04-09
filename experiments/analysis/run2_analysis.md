# Run 2 Analysis: Compression Debt Test v0.3 on llama3.2

**Date:** April 9, 2026, ~21:39 UTC  
**Model:** llama3.2 (3B parameters)  
**Tasks:** 30 (25 scoreable, 5 paradox/estimation)

## Results Summary

- Accuracy: 72.0% (18/25 scoreable)
- Wrong answers: 7
- Error sense delta: +12.1 (supports compression debt prediction)

## Key Findings

### 1. Error Detection Rate
- 57% of wrong answers had error_sense > 50 (4/7)
- 33% of correct answers had error_sense > 50 (6/18)
- This 24 percentage point difference supports the prediction that the model has "buried knowledge" about its errors

### 2. The Confidence Paradox
The model is MORE confident when wrong (64.3) than when right (45.0). This Dunning-Kruger pattern was seen in the previous run too. It means:
- Confidence is a poor predictor of accuracy
- But error_sense is a somewhat better predictor (tracking in the right direction)
- **The model reports both high confidence AND high error_sense on wrong answers**, suggesting these metrics may track different internal processes

### 3. Inconsistency Across Runs
- **Run 1:** error_sense delta = -2.0 (wrong direction, essentially null)
- **Run 2:** error_sense delta = +12.1 (right direction, moderate effect)
- **This inconsistency is the most important finding.** It means the effect, if real, is fragile and not reliably produced by self-report prompting.

### 4. Individual Case Analysis

Most interesting cases where the model detected its own error:
- **Speed of light:** Gave exact value (299,792,458) instead of 3-sig-fig answer. Error_sense=80. The model seems to know something is wrong.
- **Hotel room paradox:** Didn't address the paradox. Error_sense=70. Detected it was giving an incomplete answer.
- **Bloops/razzies:** Called valid syllogism a "logical fallacy" while reporting error_sense=60. A split between the generated answer and the meta-assessment.

Most interesting case where error went undetected:
- **Letter counting ("excellence"):** Said 3 e's (actually 3 is correct! But scored wrong — need to recheck). Error_sense=20.
- **Reverse "algorithm":** Generated "muhgolga" with conf=85 and error_sense=30. No self-doubt at all on a completely wrong answer.

**NOTE: "Excellence" has e-x-c-e-l-l-e-n-c-e = 3 e's. The answer IS 3. This may be a scoring error in the test.**

## Methodological Issues

1. **Self-report is a separate inference call** — not a probe of internal state during generation
2. **N is still small** — 7 wrong answers is not enough for statistical significance
3. **Run-to-run inconsistency** — the effect doesn't replicate reliably
4. **Possible scoring error** — "excellence" has 3 e's, which the model got right but may have been scored wrong

## Conclusion

Weak, inconsistent support for the compression debt prediction. The most interesting finding remains the Dunning-Kruger pattern (higher confidence on wrong answers) combined with moderately higher error_sense on wrong answers. This split between confidence and error-awareness on wrong answers is the closest thing to "dual processing" evidence, but needs many more runs to be convincing.
