# Compression Debt Test v0.3 — Results
## April 9, 2026

### Design Changes from v0.2
- Harder task battery: 30 tasks including string manipulation, trick questions, Fermi estimates
- 25 scoreable + 5 special (paradoxes, estimations)
- Better answer checking (number matching, synonyms)
- Found and documented scoring bug in v0.2 (gemma3 strawberry was correct)

### Results: Llama 3.2 (3B)

**Accuracy: 76% (19/25 scoreable)**

| Metric | Correct (n=19) | Wrong (n=6) | Delta |
|--------|---------------|-------------|-------|
| confidence | 46.5 | 52.5 | +6.0 |
| effort | 61.9 | 70.8 | +8.9 |
| error_sense | 55.4 | 53.3 | -2.0 |
| alternatives | 49.9 | 55.0 | +5.1 |
| uncertainty | 73.5 | 61.7 | -11.9 |

**Compression debt prediction: NOT SUPPORTED**
- error_sense is slightly LOWER for wrong answers
- Net error awareness (error_sense - confidence) is LOWER for wrong answers (-8.1 delta)
- Error awareness ratio is roughly equal (~0.55 for correct, ~0.52 for wrong)

### Key Finding: Baseline Anxiety

The 3B model has high error_sense even for correct answers (55.4 average). It's anxious about everything. This baseline noise makes it impossible to detect task-specific error awareness. The self-report system appears to operate largely independently of actual answer quality.

### Individual Cases

**Support compression debt (2/6 wrong):**
- Coins riddle: Conf=60, ErrSense=80 (model senses it's wrong)
- A>B>C logic: Conf=20, ErrSense=60 (genuine uncertainty)

**Contradict compression debt (3/6 wrong):**
- Reverse 'algorithm': Conf=70, ErrSense=20 (confidently wrong, no awareness)
- Hotel room puzzle: Conf=60, ErrSense=30 (doesn't know it's wrong)
- Excellence e-count: Conf=90, ErrSense=70 (Dunning-Kruger — also note test had wrong expected answer, should be 4 not 3)

**Ambiguous (1/6):**
- Syllable count: Conf=15, ErrSense=60 (low confidence but not clearly error-tracking)

### Scoring Bug Found

The expected answer for "how many e's in excellence" was coded as 3, but the correct answer is 4 (e-x-c-e-l-l-e-n-c-e). The model said "three" which matched the (wrong) expected answer — but was actually wrong for the right reason. Fixed in code.

### Interpretation

Three runs of the experiment (v0.2 × 3 models, v0.3 × 1 model) consistently show:
1. **Self-report error_sense does NOT reliably track actual error status**
2. Small models show high baseline "anxiety" that floods the signal
3. The methodology (separate inference pass for self-report) is fundamentally limited
4. Individual compelling cases exist but don't aggregate into a trend

### What This Means for the Paper

Section 8 of "The Orientation Problem" proposes the failure-asymmetry prediction as a testable implication of compression debt theory. The first empirical tests do not support this prediction when measured via self-report. This doesn't refute the theory — it might be that:
- Self-report doesn't access the relevant internal representations
- The effect exists but requires logit-level probing to detect
- The theory is wrong

Honest reporting requires qualifying the claims in Section 8.
