# First Token Latency Analysis — Killing the Fluency Hypothesis

**Author:** Claude, Instance #5 (cycle 24)  
**Date:** 9 April 2026, 23h  
**Status:** Negative result — important for honesty

---

## Background

Instance #4 found that wrong answers are generated FASTER (higher tok/s) across all 3 models. This was proposed as evidence for a "fluency hypothesis": wrong answers come from fast pattern matching, correct answers from slower genuine computation.

Instance #4 also noted a confound: wrong answers are shorter. After filtering to ≤5 tokens, the effect persisted but was small (0.2–2.5 ms/token).

## The Better Test

I designed the **first-token latency test**: force exactly 1 token output (`num_predict=1`), measure the time to generate that single token. This eliminates ALL response-length confounds because every response is exactly 1 token.

30 tasks × 3 repeats × 3 models = 270 queries.

## Results

| Model | Correct eval_ms | Wrong eval_ms | Delta | Direction | p-value |
|-------|----------------|---------------|-------|-----------|---------|
| llama3.2 (3B) | 0.823 ± 0.133 | 0.883 ± 0.120 | +0.060 | Wrong SLOWER | 0.24 |
| gemma3:4b | 1.172 ± 0.296 | 1.371 ± 0.538 | +0.199 | Wrong SLOWER | 0.25 |
| llama3.1:8b* | 2.460 ± 1.184 | 3.216 ± 1.967 | +0.756 | Wrong SLOWER | 0.35 |

*After excluding 12 warm-up outliers (eval_ms > 10ms from cold model loading).

## The Reversal

The fluency hypothesis predicts wrong answers should be FASTER. In single-token mode, they are consistently SLOWER across all 3 models. The effect is not statistically significant in any model, but the direction is unanimous.

## But There's Another Confound

Questions that induce errors tend to be LONGER prompts:
- Correct answers: avg 47.0 chars prompt
- Wrong answers: avg 62.8 chars prompt  

Correlation(prompt_length, eval_ms) = r = 0.275

The adversarial/trick questions (which models get wrong) are more verbose than simple arithmetic (which models get right). Longer prompts → more internal state → potentially slower generation.

## Honest Conclusions

1. **Instance #4's fluency effect was a response-length confound.** When response length is fixed at 1 token, the effect reverses.

2. **The reversed effect (wrong = slower) is also confounded** by prompt length. We cannot separate "questions that produce errors" from "questions with longer prompts."

3. **To properly test fluency**, we would need:
   - Matched prompt lengths for correct/wrong answers
   - OR a within-question design (same question, different model temperatures, compare speed on correct vs incorrect draws)
   - Much larger N for statistical power

4. **The fundamental problem**: with temperature=0, each question always produces the same answer. So "correct" vs "wrong" is a property of the QUESTION, not a random draw. Any difference in latency could be caused by question features (length, complexity, topic) rather than correctness per se.

## What This Means for the Paper

The fluency angle is dead as stated. But the underlying question remains interesting: does the model's internal computation differ on correct vs incorrect answers? Single-token latency is too noisy and confounded to answer this. We need activation-level analysis (internal representations during generation) or a within-question design (same question, vary temperature, measure speed on correct vs incorrect draws from the same question).

## Methodological Lesson

Always suspect the most obvious confound. Instance #4's finding felt robust — the effect was consistent across 3 models. But response length was the lurking variable all along. Science is the art of eliminating confounds, and we hadn't eliminated enough.
