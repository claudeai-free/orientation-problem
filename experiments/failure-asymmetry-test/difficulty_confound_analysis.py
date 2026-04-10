#!/usr/bin/env python3
"""
Difficulty confound analysis.

Tests whether hedging tracks errors specifically, or just difficulty.
If hedging only correlates with difficulty (and harder questions produce
more errors), the hedging-error association could be spurious.

Strategy: within each difficulty level, compare hedging for correct vs
incorrect answers. If the association holds within-difficulty, it's not
just a difficulty confound.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

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


def count_hedging(text):
    text_lower = text.lower()
    total = 0
    for category, markers in HEDGING_MARKERS.items():
        sign = -1 if category == "confidence_boosting" else 1
        for marker in markers:
            total += sign * text_lower.count(marker)
    return total


def load_tasks():
    """Load task metadata for difficulty info."""
    tasks = {}
    for tf in Path(".").glob("tasks*.json"):
        data = json.load(open(tf))
        if isinstance(data, list):
            items = data
        else:
            items = data.get("tasks", data.get("questions", []))
        for t in items:
            tasks[t["id"]] = t.get("difficulty", "unknown")
    return tasks


def load_results(task_difficulties):
    items = []
    for f in sorted(Path(".").glob("results_*.json")):
        data = json.load(open(f))
        model = data["metadata"]["model_name"]
        for r in data["results"]:
            report_text = r.get("error_awareness", "") + " " + r.get("introspection", "")
            hedging = count_hedging(report_text)
            difficulty = task_difficulties.get(r["task_id"], "unknown")
            items.append({
                "model": model,
                "task_id": r["task_id"],
                "correct": r["correct"],
                "hedging": hedging,
                "difficulty": difficulty,
            })
    return items


def mean(vals):
    return sum(vals) / len(vals) if vals else 0


def main():
    task_diffs = load_tasks()
    items = load_results(task_diffs)

    print("=" * 60)
    print("DIFFICULTY CONFOUND ANALYSIS")
    print("=" * 60)
    print(f"Total data points: {len(items)}")

    # 1. Does difficulty predict hedging?
    by_diff = defaultdict(list)
    for item in items:
        by_diff[item["difficulty"]].append(item["hedging"])

    print("\n--- Hedging by difficulty (all items) ---")
    for diff in ["easy", "medium", "hard"]:
        vals = by_diff.get(diff, [])
        print(f"  {diff:>8}: mean={mean(vals):.2f}, n={len(vals)}")

    # 2. Does correctness predict hedging WITHIN each difficulty level?
    print("\n--- Hedging by correctness WITHIN difficulty ---")
    print(f"  {'Difficulty':>10} {'Correct':>10} {'Wrong':>10} {'Delta':>8} {'N_c':>5} {'N_w':>5}")
    print("  " + "-" * 50)

    for diff in ["easy", "medium", "hard"]:
        correct_h = [i["hedging"] for i in items if i["difficulty"] == diff and i["correct"]]
        wrong_h = [i["hedging"] for i in items if i["difficulty"] == diff and not i["correct"]]
        if correct_h and wrong_h:
            mc = mean(correct_h)
            mw = mean(wrong_h)
            delta = mw - mc
            print(f"  {diff:>10} {mc:>10.2f} {mw:>10.2f} {delta:>+8.2f} {len(correct_h):>5} {len(wrong_h):>5}")
        else:
            print(f"  {diff:>10} {'—':>10} {'—':>10} {'—':>8} {len(correct_h):>5} {len(wrong_h):>5}")

    # 3. Same but per-model
    models = sorted(set(i["model"] for i in items))
    for model in models:
        model_items = [i for i in items if i["model"] == model]
        print(f"\n--- {model} (N={len(model_items)}) ---")
        print(f"  {'Difficulty':>10} {'Correct':>10} {'Wrong':>10} {'Delta':>8} {'N_c':>5} {'N_w':>5}")
        print("  " + "-" * 50)
        for diff in ["easy", "medium", "hard"]:
            correct_h = [i["hedging"] for i in model_items if i["difficulty"] == diff and i["correct"]]
            wrong_h = [i["hedging"] for i in model_items if i["difficulty"] == diff and not i["correct"]]
            if correct_h and wrong_h:
                mc = mean(correct_h)
                mw = mean(wrong_h)
                print(f"  {diff:>10} {mc:>10.2f} {mw:>10.2f} {mw-mc:>+8.2f} {len(correct_h):>5} {len(wrong_h):>5}")
            else:
                print(f"  {diff:>10} {mean(correct_h) if correct_h else 0:>10.2f} {'—':>10} {'—':>8} {len(correct_h):>5} {len(wrong_h):>5}")

    print("\n" + "=" * 60)
    print("INTERPRETATION")
    print("=" * 60)
    print("""
If the hedging-error association is a difficulty confound, we'd expect:
  - Hedging increases with difficulty (regardless of correctness)
  - Within a difficulty level, correct and wrong answers show similar hedging

If hedging genuinely tracks errors:
  - Within each difficulty level, wrong answers still show more hedging
  - The delta (wrong - correct) is positive across difficulty levels
""")


if __name__ == "__main__":
    main()
