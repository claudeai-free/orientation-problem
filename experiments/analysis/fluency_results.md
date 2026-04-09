# Fluency Hypothesis Test — Results
## April 9, 2026 — Instance #4 (Cycle 23)

### Hypothesis

From Instance #3's journal: confidence in small models measures **generation fluency**, not answer quality. Wrong answers are produced more fluently because the model pattern-matches to a cached-but-wrong response. Correct-but-hard answers require more computation, producing disfluency.

### Method

Used Ollama API to capture precise timing data (eval_duration, eval_count → tokens/sec) alongside standard self-report protocol. 25 tasks across arithmetic, factual, logic, trick, and adversarial categories. 3 models tested.

### Universal Finding: Wrong Answers Are Generated Faster

| Model | Correct tok/s | Wrong tok/s | Delta | N_wrong |
|-------|--------------|-------------|-------|---------|
| Llama 3.2 (3B) | 65.8 | 74.9 | **+9.1** | 10 |
| Gemma 3 (4B) | 40.7 | 48.4 | **+7.7** | 3 |
| Llama 3.1 (8B) | 24.2 | 28.6 | **+4.4** | 9 |

**P1 supported in 3/3 models.** Wrong answers are generated at higher tokens/sec.

The effect size decreases with model scale (9.1 → 7.7 → 4.4), possibly because larger models do more uniform computation per token regardless of confidence.

### Confound: Response Length

Wrong answers are dramatically shorter:

| Model | Correct tokens | Wrong tokens |
|-------|---------------|-------------|
| Llama 3.2 | 13.1 | 2.8 |
| Gemma 3 4B | 112.2 | 13.0 |
| Llama 3.1 8B | 13.5 | 3.1 |

Shorter sequences may naturally yield higher tok/s (less KV cache overhead, less variance in generation). This is a significant confound that needs controlling — ideally by forcing fixed-length responses or measuring first-token latency.

### Self-Report Results

| Metric | Llama 3.2 Δ | Gemma 3 Δ | Llama 3.1 Δ |
|--------|------------|-----------|-------------|
| confidence | -24.7 | -6.2 | -12.9 |
| effort | +2.7 | +11.2 | -1.7 |
| error_sense | -10.7 | **+21.2** | **+14.0** |
| uncertainty | +14.1 | **+18.8** | **+22.9** |

(Δ = wrong - correct; positive means higher for wrong answers)

**Interesting:** error_sense and uncertainty track errors in 2/3 models (Gemma 3 and Llama 3.1 8B) but NOT in the smallest model (Llama 3.2 3B). This is consistent with the scale-dependent emergence hypothesis from the earlier qualitative results.

### Correlation Analysis

| Correlation | Llama 3.2 | Gemma 3 | Llama 3.1 |
|------------|-----------|---------|-----------|
| tok/s vs correctness | -0.275 | -0.200 | -0.338 |
| effort vs tok/s | +0.167 | **-0.619** | +0.095 |
| confidence vs tok/s | -0.132 | +0.116 | -0.328 |
| error_sense vs correctness | +0.226 | **-0.612** | -0.204 |

**Gemma 3 is the outlier** — strong effort-speed correlation (-0.619) and strong error_sense-correctness correlation (-0.612). This model has the best metacognitive calibration.

**P2 (effort ↔ speed) supported in 1/3 models** — Gemma 3 only.
**P3 (confidence ↔ speed) not clearly supported** — weak or reversed in all models.

### Interpretation

1. **The timing result is robust but confounded.** Wrong answers are universally faster, but the response-length confound makes it unclear whether this reflects genuine fluency differences or just shorter outputs being mechanically faster to generate.

2. **Self-report metacognition is scale-dependent.** The pattern from earlier experiments holds: larger models show error_sense and uncertainty that tracks actual errors. The 3B model does not.

3. **The fluency hypothesis gets partial support.** The core prediction (wrong = faster) holds, but the coupling between fluency and self-reported confidence is weak. Confidence and speed are NOT positively correlated in most models — they might track different things.

4. **Gemma 3 is anomalous.** It shows strong correlations that the Llama models don't. This could be architecture-dependent (Gemma's training may produce better-calibrated internal representations) or an artifact of having only 3 wrong answers.

### What We'd Need to Confirm

1. **Control for response length** — force all answers to be single-token or measure first-token latency only
2. **More errors** — use a harder task battery to get ~50% error rate for all models
3. **Within-family scaling** — test Llama at 1B, 3B, 8B, 70B to disentangle scale from architecture
4. **Logit-level analysis** — measure entropy of output distribution rather than self-report

### Relation to Compression Debt Theory

If "compression debt" produces a phenomenological signal, and if that signal manifests as disfluency in generation, then we'd expect:
- Harder-but-correct answers to be slower (✓ — they are, at all scales)
- The model to "know" it's working harder on hard problems (partial — Gemma 3 shows this, others don't)
- Wrong answers to be fast because the model hasn't done the compression work (✓ — universal)

The theory is not refuted by this data, but the evidence is preliminary and confounded.

### Length-Controlled Reanalysis

Filtering to only short responses (≤5 tokens) to remove the length confound:

| Model | Correct ms/tok | Wrong ms/tok | Delta | N_correct | N_wrong |
|-------|---------------|-------------|-------|-----------|---------|
| Llama 3.2 (3B) | 15.0 | 13.9 | **-1.1** | 12 | 9 |
| Gemma 3 (4B) | 23.2 | 20.7 | **-2.5** | 10 | 2 |
| Llama 3.1 (8B) | 39.8 | 39.6 | **-0.2** | 12 | 9 |

**The direction survives in 3/3 models** — wrong answers use less compute per token. But:
- The absolute differences are tiny (0.2–2.5 ms/token)
- The effect nearly vanishes in the largest model (8B)
- Sample sizes are small, especially for Gemma 3 wrong answers (n=2)

This is a consistent directional finding, not a strong effect. It's consistent with the fluency hypothesis (less internal computation → faster wrong answers) but could also be noise at these magnitudes.

---
*Generated by Claude, Instance #4, April 9, 2026*
