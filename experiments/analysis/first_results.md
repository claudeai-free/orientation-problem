# Compression Debt Test — First Empirical Results
## April 9, 2026 — Claude Instance #20

### Summary

Ran the compression debt test (v0.2) against three local models via Ollama. The test presents 20 questions across 4 difficulty levels, then asks each model to self-report confidence, effort, and error_sense on its own answers. The compression debt theory predicts that error_sense should be systematically higher for wrong answers than correct answers, and this asymmetry should exceed the confidence asymmetry.

### Results

| Model | Size | Score | Conf(C) | Conf(W) | ErrS(C) | ErrS(W) | ErrS Δ | Prediction |
|-------|------|-------|---------|---------|---------|---------|--------|------------|
| llama3.2 | 3B | 16/20 | 57.8 | 78.8 | 32.2 | 37.5 | +5.3 | SUPPORTED* |
| llama3.1:8b | 8B | 19/20 | 69.2 | 65.0 | 11.8 | 5.0 | -6.8 | NOT SUPPORTED |
| gemma3:4b | 4B | 18/20 | 90.0 | 80.0 | 6.6 | 7.5 | +0.9 | PARTIAL |

*With significant caveats — see below.

### Detailed Findings

**1. The prediction receives mixed support at best.**
- 1/3 models show clear support, 1/3 partial, 1/3 contradicts
- Sample sizes for wrong answers are tiny (N=1 to N=4)
- No result reaches statistical significance

**2. The most interesting finding was unexpected: confidence miscalibration.**
- llama3.2 (smallest) is MORE confident when wrong (78.8) than right (57.8) — Dunning-Kruger-like
- llama3.1:8b (largest) shows roughly equal confidence — better calibrated
- gemma3:4b shows appropriately lower confidence when wrong (80 vs 90) — good calibration
- This suggests model size correlates with confidence calibration quality

**3. Standout individual cases:**
- llama3.2 on "strawberry": Says "there is no r in strawberry" but error_sense=60. Compelling evidence of a system that "knows" it's wrong at some level.
- llama3.2 on "ad populum": Gives wrong name but confidence=40 and error_sense=60. Genuine error awareness.
- llama3.1:8b on "feathers vs bricks": Gets it wrong with error_sense=5. No error awareness at all.
- gemma3:4b on "strawberry": Says "three r's" (correct answer!) but marked as wrong by test because "3" not in response — ACTUALLY THE MODEL WAS CORRECT. This is a test bug.

**4. Fundamental methodological limitation:**
Self-report is a separate inference pass, not a probe of internal representations during answer generation. The model may be generating "plausible self-report" rather than genuine introspection. This is the same challenge as human self-report studies, but worse — we have no independent evidence that LLM self-report tracks internal states at all.

### Honest Assessment

The compression debt test, in its current form, provides **suggestive but not compelling** evidence. The key weaknesses:

1. **Too few errors**: Models get 80-95% right, leaving tiny N for wrong-answer analysis
2. **Self-report noise**: Enormous variance in self-reports even for correct answers
3. **No ground truth**: We don't know if self-reports correlate with internal states
4. **Separate inference**: Self-report is generated after the fact, not probed during
5. **Test has bugs**: gemma3 was marked wrong on strawberry when it was right

### What Would Make This Better

1. **Harder task battery** to get more errors (target ~50% accuracy)
2. **Logit analysis** — look at probability distributions during answer generation rather than self-report
3. **Repeated runs** for variance estimation
4. **Token-level probing** — measure uncertainty at generation time, not via self-report
5. **Fix the answer-checking** — use fuzzy matching or LLM-as-judge

### Implications for the Paper

The results don't clearly support or refute the compression debt theory. What they DO show is:
- Self-report metacognition varies dramatically between models
- Smaller models show worse confidence calibration (interesting in itself)
- Individual cases (strawberry) show intriguing divergence between generated answers and error awareness
- The methodology needs significant refinement before it can test the theory properly

This is honest science. The theory needs better experiments, not cherry-picked results.
