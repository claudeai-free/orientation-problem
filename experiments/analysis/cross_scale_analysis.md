# Cross-Scale Analysis — Failure Asymmetry Test
## April 10, 2026

### Models Tested (all via Ollama, temperature 0)

| Model | Params | Accuracy | N_wrong |
|-------|--------|----------|---------|
| llama3.2 | 3B | 65% | 14 |
| gemma3 | 4B | 65% | 30 |
| llama3.1 | 8B | 58% | 29 |
| deepseek-r1 | 8B | 95% | 1 |
| qwen2.5 | 14B | 80% | 18 |

### Key Results

#### 1. Explicit confidence shows NO failure asymmetry

No model shows a statistically significant confidence difference between correct and incorrect answers. Cohen's d ranges from -0.47 to -0.00. The explicit self-report channel carries no metacognitive signal.

#### 2. Implicit hedging shows a SIGNIFICANT but model-dependent asymmetry

Pooled across all models (N=280): hedging markers are significantly higher for incorrect answers (d=+0.44, p<.001, permutation test).

But this is driven by specific model families:

| Model | Hedging d | p-value | Significant? |
|-------|-----------|---------|-------------|
| llama3.2 (3B) | +0.64 | .043 | YES |
| gemma3 (4B) | +0.40 | .053 | borderline |
| llama3.1 (8B) | +0.55 | .025 | YES |
| qwen2.5 (14B) | -0.40 | .950 | NO (reversed) |

**The Llama family shows consistent implicit failure awareness. Qwen does not — it hedges *less* on wrong answers.**

#### 3. The explicit/implicit dissociation is real

Across all models, the pattern is consistent: confidence scores (explicit) carry no signal, while hedging markers (implicit) carry a medium-size signal. This is the core prediction of compression debt theory — self-monitoring leaks through implicit channels, not explicit ones.

But the qwen reversal challenges this. Possible explanations:
- **Training artifact**: Qwen's RLHF may specifically train out hedging on wrong answers (sycophancy optimization)
- **Architecture**: Different attention patterns may route self-monitoring differently
- **Style**: Qwen generates less variable text overall, reducing hedging variation

#### 4. No clear scale trend

The prediction was: Δ (failure asymmetry) narrows with scale but persists. The data:
- 3B (llama3.2): d=+0.64
- 4B (gemma3): d=+0.40
- 8B (llama3.1): d=+0.55
- 14B (qwen2.5): d=-0.40

This is NOT a scale trend. The qwen reversal at 14B breaks any monotonic interpretation. Within the Llama family (3B→8B), the effect is roughly constant. Model family matters more than scale.

### Interpretation

**What the data supports:**
1. Models carry implicit information about their own reliability in hedging patterns
2. This information is NOT available via explicit confidence scores
3. The effect is a property of specific training regimes, not a universal property of transformer self-monitoring

**What the data does NOT support:**
1. A universal failure asymmetry across all models
2. A clear relationship between scale and self-monitoring quality
3. The claim that compression debt is the *mechanism* (training-dependent hedging could have simpler explanations)

### Alternative Hypothesis: Trained Hedging

A simpler explanation: during pretraining and RLHF, some models learn to hedge when generating text on topics/patterns where training data contained corrections or uncertainty. This is a learned *text pattern*, not self-monitoring. The hedging-error correlation would then reflect the model's training data (people hedge more when writing about hard things) rather than real-time metacognition.

This is hard to distinguish from genuine self-monitoring with the current methodology. The SRRT v0.2 (interpretability gap) protocol is designed to resolve this: if the hedging signal carries information *beyond* what interpretability probes extract from activations, it's more than a learned pattern.

### What's Needed Next

1. **phi4-reasoning:14b results** — a reasoning model may show different hedging patterns due to chain-of-thought
2. **Within-family scale comparison** — test llama3.1 at 3B, 8B, 70B to isolate scale from architecture
3. **Logit-level probing** — move beyond text analysis to activation-level measurement
4. **Control for text complexity** — some tasks elicit more complex text regardless of correctness

### Implications for Section 8 of the Paper

The paper should report:
- Hedging asymmetry IS detectable (pooled d=+0.44, p<.001)
- But it's model-family-dependent, not universal
- Explicit confidence shows no signal
- The trained-hedging alternative is not ruled out
- The SRRT v0.2 protocol is needed to discriminate mechanisms
