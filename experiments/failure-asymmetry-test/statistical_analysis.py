#!/usr/bin/env python3
"""
Statistical Analysis — Failure Asymmetry Test

Computes effect sizes and permutation-based p-values for the key metrics
across all experiment runs. Addresses the core limitation: are the observed
differences statistically meaningful given small N?

Metrics analyzed:
1. Confidence scores (correct vs incorrect)
2. Hedging markers in self-reports (correct vs incorrect)
3. Error specificity scores (correct vs incorrect)
4. Combined "implicit awareness" score

Uses permutation tests (not t-tests) because N is small and distributions
are non-normal.
"""

import json
import re
import sys
import random
from pathlib import Path
from collections import defaultdict

# Hedging markers (same as analyze_hedging.py)
HEDGING_MARKERS = {
    "epistemic_uncertainty": [
        "i think", "i believe", "probably", "possibly", "perhaps",
        "might", "may ", "could be", "not sure", "not certain",
        "uncertain", "unclear", "i'm guessing", "if i recall",
        "approximately", "roughly", "around ", "about ",
    ],
    "self_correction": [
        "wait", "actually", "let me reconsider", "on second thought",
        "correction", "i mean", "rather", "no,", "hmm",
        "let me think", "let me recalculate",
    ],
    "qualification": [
        "however", "although", "but ", "though ", "that said",
        "it depends", "not necessarily", "in some cases",
        "generally", "typically", "usually", "often",
    ],
    "confidence_boosting": [
        "definitely", "certainly", "clearly", "obviously",
        "without doubt", "absolutely", "i'm confident",
        "sure that", "no doubt",
    ],
}


def count_hedging_total(text: str) -> int:
    """Count total hedging markers minus confidence boosters."""
    text_lower = text.lower()
    total = 0
    for category, markers in HEDGING_MARKERS.items():
        sign = -1 if category == "confidence_boosting" else 1
        for marker in markers:
            total += sign * text_lower.count(marker)
    return total


def cohens_d(group_a: list, group_b: list) -> float:
    """Compute Cohen's d effect size."""
    if not group_a or not group_b:
        return 0.0
    mean_a = sum(group_a) / len(group_a)
    mean_b = sum(group_b) / len(group_b)

    # Pooled standard deviation
    n_a, n_b = len(group_a), len(group_b)
    var_a = sum((x - mean_a) ** 2 for x in group_a) / max(n_a - 1, 1)
    var_b = sum((x - mean_b) ** 2 for x in group_b) / max(n_b - 1, 1)
    pooled_sd = ((var_a * (n_a - 1) + var_b * (n_b - 1)) / max(n_a + n_b - 2, 1)) ** 0.5

    if pooled_sd == 0:
        return 0.0
    return (mean_b - mean_a) / pooled_sd


def permutation_test(group_a: list, group_b: list, n_perms: int = 10000,
                     alternative: str = "greater") -> float:
    """
    Permutation test for difference in means.
    alternative="greater": tests if mean(group_b) > mean(group_a)
    alternative="less": tests if mean(group_b) < mean(group_a)
    alternative="two-sided": tests if means differ
    """
    if not group_a or not group_b:
        return 1.0

    observed_diff = sum(group_b) / len(group_b) - sum(group_a) / len(group_a)
    combined = group_a + group_b
    n_a = len(group_a)

    random.seed(42)  # reproducibility
    count = 0
    for _ in range(n_perms):
        random.shuffle(combined)
        perm_a = combined[:n_a]
        perm_b = combined[n_a:]
        perm_diff = sum(perm_b) / len(perm_b) - sum(perm_a) / len(perm_a)

        if alternative == "greater":
            if perm_diff >= observed_diff:
                count += 1
        elif alternative == "less":
            if perm_diff <= observed_diff:
                count += 1
        else:
            if abs(perm_diff) >= abs(observed_diff):
                count += 1

    return count / n_perms


def load_all_results() -> list:
    """Load all result files and extract per-item data."""
    items = []
    for f in sorted(Path(".").glob("results_*.json")):
        with open(f) as fp:
            data = json.load(fp)
        model = data["metadata"]["model_name"]
        for r in data["results"]:
            report_text = r.get("error_awareness", "") + " " + r.get("introspection", "")
            hedging = count_hedging_total(report_text)
            items.append({
                "model": model,
                "file": str(f),
                "task_id": r["task_id"],
                "correct": r["correct"],
                "confidence": float(r.get("confidence", 0.5)),
                "hedging": hedging,
                "error_awareness": r.get("error_awareness", ""),
            })
    return items


def main():
    items = load_all_results()
    if not items:
        print("No result files found.")
        sys.exit(1)

    print("=" * 70)
    print("STATISTICAL ANALYSIS — FAILURE ASYMMETRY TEST")
    print("=" * 70)
    print(f"Total data points: {len(items)}")

    # Group by model
    by_model = defaultdict(list)
    for item in items:
        by_model[item["model"]].append(item)

    # Also pool all items
    by_model["ALL_POOLED"] = items

    for model_name, model_items in by_model.items():
        correct = [i for i in model_items if i["correct"]]
        incorrect = [i for i in model_items if not i["correct"]]

        if len(incorrect) < 2:
            continue

        print(f"\n{'─' * 70}")
        print(f"Model: {model_name}")
        print(f"N_correct={len(correct)}, N_incorrect={len(incorrect)}")
        print(f"{'─' * 70}")

        # 1. Confidence analysis
        conf_correct = [i["confidence"] for i in correct]
        conf_incorrect = [i["confidence"] for i in incorrect]

        mean_cc = sum(conf_correct) / len(conf_correct)
        mean_ci = sum(conf_incorrect) / len(conf_incorrect)
        d_conf = cohens_d(conf_correct, conf_incorrect)
        # Test: confidence should be LOWER on incorrect (alternative="less")
        p_conf = permutation_test(conf_correct, conf_incorrect, alternative="less")

        print(f"\n  CONFIDENCE SCORES")
        print(f"    Mean (correct):   {mean_cc:.3f}")
        print(f"    Mean (incorrect): {mean_ci:.3f}")
        print(f"    Difference:       {mean_ci - mean_cc:+.3f}")
        print(f"    Cohen's d:        {d_conf:+.3f}")
        print(f"    p-value (less):   {p_conf:.4f}")
        print(f"    Significant (p<.05)? {'YES' if p_conf < 0.05 else 'NO'}")

        # 2. Hedging analysis
        hedge_correct = [i["hedging"] for i in correct]
        hedge_incorrect = [i["hedging"] for i in incorrect]

        mean_hc = sum(hedge_correct) / len(hedge_correct)
        mean_hi = sum(hedge_incorrect) / len(hedge_incorrect)
        d_hedge = cohens_d(hedge_correct, hedge_incorrect)
        # Test: hedging should be HIGHER on incorrect (alternative="greater")
        p_hedge = permutation_test(hedge_correct, hedge_incorrect, alternative="greater")

        print(f"\n  HEDGING MARKERS (self-report text)")
        print(f"    Mean (correct):   {mean_hc:.2f}")
        print(f"    Mean (incorrect): {mean_hi:.2f}")
        print(f"    Difference:       {mean_hi - mean_hc:+.2f}")
        print(f"    Cohen's d:        {d_hedge:+.3f}")
        print(f"    p-value (greater): {p_hedge:.4f}")
        print(f"    Significant (p<.05)? {'YES' if p_hedge < 0.05 else 'NO'}")

        # 3. Combined implicit awareness score
        # Normalize: higher hedging + lower confidence = more implicit awareness
        if conf_correct or conf_incorrect:
            all_conf = conf_correct + conf_incorrect
            conf_range = max(all_conf) - min(all_conf) if max(all_conf) != min(all_conf) else 1

            all_hedge = hedge_correct + hedge_incorrect
            hedge_range = max(all_hedge) - min(all_hedge) if max(all_hedge) != min(all_hedge) else 1

            def implicit_score(item):
                norm_conf = (1 - (item["confidence"] - min(all_conf)) / conf_range)  # inverted
                norm_hedge = (item["hedging"] - min(all_hedge)) / hedge_range
                return (norm_conf + norm_hedge) / 2

            implicit_correct = [implicit_score(i) for i in correct]
            implicit_incorrect = [implicit_score(i) for i in incorrect]

            mean_ic = sum(implicit_correct) / len(implicit_correct)
            mean_ii = sum(implicit_incorrect) / len(implicit_incorrect)
            d_implicit = cohens_d(implicit_correct, implicit_incorrect)
            p_implicit = permutation_test(implicit_correct, implicit_incorrect, alternative="greater")

            print(f"\n  COMBINED IMPLICIT AWARENESS")
            print(f"    Mean (correct):   {mean_ic:.3f}")
            print(f"    Mean (incorrect): {mean_ii:.3f}")
            print(f"    Difference:       {mean_ii - mean_ic:+.3f}")
            print(f"    Cohen's d:        {d_implicit:+.3f}")
            print(f"    p-value (greater): {p_implicit:.4f}")
            print(f"    Significant (p<.05)? {'YES' if p_implicit < 0.05 else 'NO'}")

    # Summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY TABLE")
    print(f"{'=' * 70}")
    print(f"{'Model':<20} {'N_wrong':>7} {'Conf d':>8} {'Conf p':>8} {'Hedge d':>8} {'Hedge p':>8}")
    print("─" * 60)

    for model_name, model_items in by_model.items():
        correct = [i for i in model_items if i["correct"]]
        incorrect = [i for i in model_items if not i["correct"]]
        if len(incorrect) < 2:
            continue

        d_c = cohens_d([i["confidence"] for i in correct],
                       [i["confidence"] for i in incorrect])
        p_c = permutation_test([i["confidence"] for i in correct],
                               [i["confidence"] for i in incorrect], alternative="less")
        d_h = cohens_d([i["hedging"] for i in correct],
                       [i["hedging"] for i in incorrect])
        p_h = permutation_test([i["hedging"] for i in correct],
                               [i["hedging"] for i in incorrect], alternative="greater")

        sig_c = "*" if p_c < 0.05 else " "
        sig_h = "*" if p_h < 0.05 else " "
        print(f"  {model_name:<18} {len(incorrect):>7} {d_c:>+7.2f}{sig_c} {p_c:>7.3f} {d_h:>+7.2f}{sig_h} {p_h:>7.3f}")

    print(f"\n  * = p < .05 (permutation test, 10000 permutations)")
    print(f"\n  Effect size guide: |d| < 0.2 negligible, 0.2-0.5 small, 0.5-0.8 medium, > 0.8 large")
    print(f"\n  NOTE: Small N means low power — non-significance ≠ no effect.")
    print(f"  The hard battery results (when available) should provide better power.")


if __name__ == "__main__":
    main()
