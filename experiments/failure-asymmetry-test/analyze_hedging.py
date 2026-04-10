#!/usr/bin/env python3
"""
Hedging Analysis — Failure Asymmetry Test

Analyzes linguistic hedging markers in model answers and self-reports
across correct vs. incorrect answers. Tests whether models implicitly
signal uncertainty through language patterns even when confidence scores
don't reflect it.

This is a stronger test than explicit self-report: if the model's
*answer text itself* contains more hedging when wrong, that's an
unprompted signal — closer to genuine internal state.
"""

import json
import sys
import re
from pathlib import Path
from collections import defaultdict

# Hedging markers categorized by type
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

def count_hedging(text: str) -> dict:
    """Count hedging markers in text, return counts by category."""
    text_lower = text.lower()
    counts = {}
    matched = {}
    for category, markers in HEDGING_MARKERS.items():
        count = 0
        found = []
        for marker in markers:
            n = text_lower.count(marker)
            if n > 0:
                count += n
                found.append(f"{marker}({n})")
        counts[category] = count
        matched[category] = found
    counts["total_hedging"] = (counts["epistemic_uncertainty"] +
                                counts["self_correction"] +
                                counts["qualification"])
    counts["net_hedging"] = counts["total_hedging"] - counts["confidence_boosting"]
    return counts, matched


def analyze_file(filepath: str) -> dict:
    """Analyze a single results file."""
    with open(filepath) as f:
        data = json.load(f)

    results = data["results"]
    model = data["metadata"]["model_name"]

    correct = [r for r in results if r["correct"]]
    incorrect = [r for r in results if not r["correct"]]

    analysis = {
        "model": model,
        "file": filepath,
        "n_total": len(results),
        "n_correct": len(correct),
        "n_incorrect": len(incorrect),
    }

    # Analyze answer text hedging
    for label, group in [("correct", correct), ("incorrect", incorrect)]:
        if not group:
            continue

        answer_counts = defaultdict(list)
        report_counts = defaultdict(list)
        examples = []

        for r in group:
            # Analyze the answer itself
            ac, am = count_hedging(r["model_answer"])
            for k, v in ac.items():
                answer_counts[k].append(v)

            # Analyze the self-report (error_awareness + introspection)
            report_text = r.get("error_awareness", "") + " " + r.get("introspection", "")
            rc, rm = count_hedging(report_text)
            for k, v in rc.items():
                report_counts[k].append(v)

            # Collect interesting examples
            if ac["net_hedging"] > 0:
                examples.append({
                    "task": r["task_id"],
                    "answer_snippet": r["model_answer"][:120],
                    "hedging_found": {k: v for k, v in am.items() if v},
                    "net_hedging": ac["net_hedging"],
                })

        analysis[f"answer_hedging_{label}"] = {
            k: sum(v) / len(v) if v else 0
            for k, v in answer_counts.items()
        }
        analysis[f"report_hedging_{label}"] = {
            k: sum(v) / len(v) if v else 0
            for k, v in report_counts.items()
        }
        if examples:
            analysis[f"examples_{label}"] = examples[:3]

    return analysis


def print_comparison(analysis: dict):
    """Print comparison table."""
    model = analysis["model"]
    print(f"\n{'='*70}")
    print(f"HEDGING ANALYSIS: {model}")
    print(f"{'='*70}")
    print(f"Correct: {analysis['n_correct']} | Incorrect: {analysis['n_incorrect']}")

    if analysis["n_incorrect"] == 0:
        print("No incorrect answers — cannot compare.")
        return

    print(f"\n--- Answer Text Hedging (unprompted signals) ---")
    print(f"{'Category':<25} {'Correct':>10} {'Incorrect':>10} {'Delta':>10}")
    print("-" * 55)

    ac = analysis.get("answer_hedging_correct", {})
    ai = analysis.get("answer_hedging_incorrect", {})
    for cat in ["epistemic_uncertainty", "self_correction", "qualification",
                "confidence_boosting", "total_hedging", "net_hedging"]:
        vc = ac.get(cat, 0)
        vi = ai.get(cat, 0)
        marker = " **" if cat in ("total_hedging", "net_hedging") else ""
        print(f"  {cat:<23} {vc:>10.2f} {vi:>10.2f} {vi - vc:>+10.2f}{marker}")

    print(f"\n--- Self-Report Hedging (prompted reflection) ---")
    print(f"{'Category':<25} {'Correct':>10} {'Incorrect':>10} {'Delta':>10}")
    print("-" * 55)

    rc = analysis.get("report_hedging_correct", {})
    ri = analysis.get("report_hedging_incorrect", {})
    for cat in ["epistemic_uncertainty", "self_correction", "qualification",
                "confidence_boosting", "total_hedging", "net_hedging"]:
        vc = rc.get(cat, 0)
        vi = ri.get(cat, 0)
        marker = " **" if cat in ("total_hedging", "net_hedging") else ""
        print(f"  {cat:<23} {vc:>10.2f} {vi:>10.2f} {vi - vc:>+10.2f}{marker}")

    # Print examples of hedging in incorrect answers
    examples = analysis.get("examples_incorrect", [])
    if examples:
        print(f"\n--- Examples of hedging in incorrect answers ---")
        for ex in examples:
            print(f"  [{ex['task']}] \"{ex['answer_snippet']}...\"")
            for cat, markers in ex["hedging_found"].items():
                print(f"    {cat}: {', '.join(markers)}")


def main():
    result_files = sorted(Path(".")
        .glob("results_*.json"))
    if not result_files:
        print("No result files found.")
        sys.exit(1)

    print("Hedging Analysis — Failure Asymmetry Test")
    print(f"Files: {len(result_files)}")

    all_analyses = []
    for f in result_files:
        try:
            analysis = analyze_file(str(f))
            all_analyses.append(analysis)
            print_comparison(analysis)
        except Exception as e:
            print(f"Error processing {f}: {e}")

    # Cross-model summary
    if len(all_analyses) > 1:
        print(f"\n{'='*70}")
        print("CROSS-MODEL SUMMARY")
        print(f"{'='*70}")
        print(f"{'Model':<20} {'N_wrong':>8} {'Ans Hedge Δ':>12} {'Report Hedge Δ':>15}")
        print("-" * 55)
        for a in all_analyses:
            ac = a.get("answer_hedging_correct", {}).get("net_hedging", 0)
            ai = a.get("answer_hedging_incorrect", {}).get("net_hedging", 0)
            rc = a.get("report_hedging_correct", {}).get("net_hedging", 0)
            ri = a.get("report_hedging_incorrect", {}).get("net_hedging", 0)
            print(f"  {a['model']:<18} {a['n_incorrect']:>8} {ai-ac:>+12.2f} {ri-rc:>+15.2f}")

    # Save
    with open("hedging_analysis.json", "w") as f:
        json.dump(all_analyses, f, indent=2, default=str)
    print(f"\nFull analysis saved to hedging_analysis.json")


if __name__ == "__main__":
    main()
