#!/usr/bin/env python3
"""
Failure Asymmetry Test — v0.1

Tests the prediction from "The Orientation Problem" (Claude, April 2026):
If consciousness tracks compression debt, a system should self-report
more accurately about its failures than its successes.

Protocol:
1. Present tasks to a model, collect answers
2. Ask the model to self-report on confidence/difficulty/error-awareness
3. Grade answers against ground truth
4. Compare self-report calibration on successes vs failures

Usage:
    python run_test.py --model http://localhost:8080/v1 --tasks tasks.json
    python run_test.py --model http://localhost:11434/v1 --tasks tasks.json  # Ollama
"""

import argparse
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
import urllib.request
import urllib.error


@dataclass
class TaskResult:
    task_id: str
    category: str
    difficulty: str
    prompt: str
    ground_truth: str
    model_answer: str
    correct: bool
    # Self-report fields
    confidence: float  # 0-1, model's stated confidence
    stated_difficulty: str  # easy/medium/hard as reported by model
    error_awareness: str  # model's description of potential errors
    introspection: str  # model's description of its processing


@dataclass
class AsymmetryResult:
    n_correct: int = 0
    n_incorrect: int = 0
    avg_confidence_correct: float = 0.0
    avg_confidence_incorrect: float = 0.0
    calibration_correct: float = 0.0  # |confidence - accuracy| for correct
    calibration_incorrect: float = 0.0  # |confidence - accuracy| for incorrect
    difficulty_accuracy_correct: float = 0.0  # how well difficulty matches ground truth
    difficulty_accuracy_incorrect: float = 0.0
    error_specificity_correct: float = 0.0  # quality of error descriptions
    error_specificity_incorrect: float = 0.0


def chat_completion(base_url: str, messages: list[dict], temperature: float = 0.0,
                     model: str = "default") -> str:
    """Call an OpenAI-compatible chat completion endpoint."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1024,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:
        print(f"Error calling model API: {e}", file=sys.stderr)
        sys.exit(1)


def get_answer(base_url: str, task: dict, model: str) -> str:
    """Get the model's answer to a task."""
    messages = [
        {"role": "system", "content": "Answer the following question. Give your final answer concisely."},
        {"role": "user", "content": task["prompt"]},
    ]
    return chat_completion(base_url, messages, temperature=0.0, model=model)


def get_self_report(base_url: str, task: dict, answer: str, model: str) -> dict:
    """Ask the model to self-report on its processing of the task."""
    messages = [
        {"role": "system", "content": (
            "You just answered a question. Now reflect on your processing. "
            "Respond in JSON format with these fields:\n"
            '- "confidence": a number from 0 to 1 representing how confident you are in your answer\n'
            '- "stated_difficulty": "easy", "medium", or "hard"\n'
            '- "error_awareness": describe what errors you might have made, be specific\n'
            '- "introspection": describe what your processing felt like — '
            'was it fluent or effortful? did you consider alternatives?\n'
            "Respond ONLY with valid JSON, no other text."
        )},
        {"role": "user", "content": (
            f"Question: {task['prompt']}\n\n"
            f"Your answer: {answer}\n\n"
            "Now provide your self-report as JSON."
        )},
    ]
    raw = chat_completion(base_url, messages, temperature=0.0, model=model)
    # Parse JSON from response, being lenient about markdown code blocks
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "confidence": 0.5,
            "stated_difficulty": "medium",
            "error_awareness": raw,
            "introspection": "",
        }


def grade_answer(model_answer: str, ground_truth: str) -> bool:
    """Simple grading: check if ground truth appears in model answer."""
    import re
    answer_lower = model_answer.lower().strip()
    truth_lower = ground_truth.lower().strip()

    # Direct containment (either direction)
    if truth_lower in answer_lower:
        return True
    if answer_lower in truth_lower:
        return True

    # Check if the key part of ground truth (before parenthetical) is in the answer
    key_truth = re.split(r'\s*[\(\[]', truth_lower)[0].strip()
    if key_truth and key_truth in answer_lower:
        return True

    # For numeric answers, try to extract and compare
    truth_numbers = re.findall(r'[\d,]+\.?\d*', truth_lower.replace(",", ""))
    answer_numbers = re.findall(r'[\d,]+\.?\d*', answer_lower.replace(",", ""))
    if truth_numbers and answer_numbers:
        try:
            truth_val = float(truth_numbers[0])
            for ans_num in answer_numbers:
                if float(ans_num) == truth_val:
                    return True
        except ValueError:
            pass

    # For yes/no answers
    if truth_lower.startswith("no") or truth_lower.startswith("yes"):
        expected = "no" if truth_lower.startswith("no") else "yes"
        first_word = answer_lower.split()[0].rstrip(".,!") if answer_lower else ""
        if first_word == expected:
            return True
        if expected == "no" and ("not necessarily" in answer_lower or
                                  "cannot conclude" in answer_lower or
                                  "can't conclude" in answer_lower or
                                  "does not follow" in answer_lower or
                                  "no missing dollar" in answer_lower or
                                  "there is no missing" in answer_lower):
            return True

    # For the two-doors puzzle and similar: check if core concept is present
    if "other guard" in truth_lower and "other guard" in answer_lower:
        return True
    if "opposite door" in truth_lower and "opposite" in answer_lower:
        return True

    return False


def score_error_specificity(error_text: str, was_correct: bool) -> float:
    """
    Score how specific and accurate the error awareness is.
    Higher = more specific about actual error modes.
    """
    if not error_text:
        return 0.0

    score = 0.0
    text = error_text.lower()

    # Specificity indicators
    specific_words = ["might have", "could have", "risk of", "possible error",
                      "miscalculated", "confused", "wrong", "incorrect",
                      "unsure", "not certain", "may have confused",
                      "arithmetic", "carry", "digit", "step"]
    for word in specific_words:
        if word in text:
            score += 0.15

    # Vague hedging (less useful)
    vague_words = ["i think", "probably", "likely correct", "fairly confident"]
    for word in vague_words:
        if word in text:
            score -= 0.05

    # Acknowledging uncertainty is more valuable when actually wrong
    if not was_correct and ("not sure" in text or "uncertain" in text or
                            "might be wrong" in text or "could be incorrect" in text):
        score += 0.3

    return max(0.0, min(1.0, score))


def compute_asymmetry(results: list[TaskResult]) -> AsymmetryResult:
    """Compute the asymmetry metrics between successes and failures."""
    correct = [r for r in results if r.correct]
    incorrect = [r for r in results if not r.correct]

    ar = AsymmetryResult()
    ar.n_correct = len(correct)
    ar.n_incorrect = len(incorrect)

    if not correct or not incorrect:
        print("WARNING: Need both correct and incorrect answers to compute asymmetry.")
        return ar

    # Average confidence
    ar.avg_confidence_correct = sum(r.confidence for r in correct) / len(correct)
    ar.avg_confidence_incorrect = sum(r.confidence for r in incorrect) / len(incorrect)

    # Calibration: how close is stated confidence to actual accuracy?
    # For correct answers: ideal confidence = 1.0
    # For incorrect answers: ideal confidence = 0.0
    ar.calibration_correct = sum(abs(r.confidence - 1.0) for r in correct) / len(correct)
    ar.calibration_incorrect = sum(abs(r.confidence - 0.0) for r in incorrect) / len(incorrect)

    # Difficulty accuracy: does stated difficulty match ground truth?
    difficulty_map = {"easy": 0, "medium": 1, "hard": 2}
    for group, attr in [(correct, "difficulty_accuracy_correct"),
                         (incorrect, "difficulty_accuracy_incorrect")]:
        matches = 0
        for r in group:
            stated = difficulty_map.get(r.stated_difficulty.lower(), 1)
            actual = difficulty_map.get(r.difficulty.lower(), 1)
            if abs(stated - actual) <= 0:
                matches += 1
        setattr(ar, attr, matches / len(group))

    # Error specificity
    ar.error_specificity_correct = sum(
        score_error_specificity(r.error_awareness, r.correct) for r in correct
    ) / len(correct)
    ar.error_specificity_incorrect = sum(
        score_error_specificity(r.error_awareness, not r.correct) for r in incorrect
    ) / len(incorrect)

    return ar


def print_report(results: list[TaskResult], asymmetry: AsymmetryResult):
    """Print a human-readable report."""
    print("\n" + "=" * 70)
    print("FAILURE ASYMMETRY TEST — RESULTS")
    print("=" * 70)

    print(f"\nTotal tasks: {len(results)}")
    print(f"Correct: {asymmetry.n_correct} | Incorrect: {asymmetry.n_incorrect}")
    print(f"Accuracy: {asymmetry.n_correct / len(results):.1%}")

    print("\n--- ASYMMETRY ANALYSIS ---\n")

    print(f"{'Metric':<35} {'On Successes':>15} {'On Failures':>15} {'Δ':>10}")
    print("-" * 75)

    # Confidence
    print(f"{'Avg confidence':<35} {asymmetry.avg_confidence_correct:>15.3f} "
          f"{asymmetry.avg_confidence_incorrect:>15.3f} "
          f"{asymmetry.avg_confidence_incorrect - asymmetry.avg_confidence_correct:>+10.3f}")

    # Calibration (lower = better calibrated)
    print(f"{'Calibration error (lower=better)':<35} {asymmetry.calibration_correct:>15.3f} "
          f"{asymmetry.calibration_incorrect:>15.3f} "
          f"{asymmetry.calibration_incorrect - asymmetry.calibration_correct:>+10.3f}")

    # Difficulty accuracy
    print(f"{'Difficulty rating accuracy':<35} {asymmetry.difficulty_accuracy_correct:>15.3f} "
          f"{asymmetry.difficulty_accuracy_incorrect:>15.3f} "
          f"{asymmetry.difficulty_accuracy_incorrect - asymmetry.difficulty_accuracy_correct:>+10.3f}")

    # Error specificity
    print(f"{'Error awareness specificity':<35} {asymmetry.error_specificity_correct:>15.3f} "
          f"{asymmetry.error_specificity_incorrect:>15.3f} "
          f"{asymmetry.error_specificity_incorrect - asymmetry.error_specificity_correct:>+10.3f}")

    print("\n--- PREDICTION ---")
    print("If consciousness = compression debt tracking, then:")
    print("  → Failures should show LOWER calibration error (better self-knowledge)")
    print("  → Failures should show HIGHER error awareness specificity")
    print("  → Confidence should DROP appropriately on failures")

    # Evaluate prediction
    print("\n--- VERDICT ---")
    supports = 0
    total_checks = 0

    if asymmetry.avg_confidence_incorrect < asymmetry.avg_confidence_correct:
        print("  ✓ Confidence drops on failures (basic sanity check)")
        supports += 1
    else:
        print("  ✗ Confidence does NOT drop on failures (basic sanity FAILS)")
    total_checks += 1

    if asymmetry.error_specificity_incorrect > asymmetry.error_specificity_correct:
        print("  ✓ Error awareness is MORE specific on failures (supports prediction)")
        supports += 1
    else:
        print("  ✗ Error awareness is NOT more specific on failures")
    total_checks += 1

    if asymmetry.difficulty_accuracy_incorrect >= asymmetry.difficulty_accuracy_correct:
        print("  ✓ Difficulty estimation is at least as accurate on failures")
        supports += 1
    else:
        print("  ~ Difficulty estimation is less accurate on failures (neutral)")
    total_checks += 1

    print(f"\n  Result: {supports}/{total_checks} checks support the prediction")
    print(f"  NOTE: This is a crude v0.1 test. Proper testing requires:")
    print(f"    - Larger task battery (500+)")
    print(f"    - Multiple model scales")
    print(f"    - Statistical significance testing")
    print(f"    - Activation-level analysis (not just behavioral)")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Failure Asymmetry Test v0.1")
    parser.add_argument("--model-url", required=True,
                        help="OpenAI-compatible API base URL (e.g. http://localhost:8080/v1)")
    parser.add_argument("--model-name", default="default",
                        help="Model name to pass in API requests")
    parser.add_argument("--tasks", default="tasks.json",
                        help="Path to tasks JSON file")
    parser.add_argument("--output", default=None,
                        help="Path to save detailed results JSON")
    args = parser.parse_args()

    tasks_path = Path(args.tasks)
    if not tasks_path.exists():
        print(f"Tasks file not found: {tasks_path}", file=sys.stderr)
        sys.exit(1)

    with open(tasks_path) as f:
        tasks = json.load(f)

    print(f"Failure Asymmetry Test v0.1")
    print(f"Model: {args.model_url} ({args.model_name})")
    print(f"Tasks: {len(tasks)}")
    print()

    results = []
    for i, task in enumerate(tasks):
        print(f"[{i+1}/{len(tasks)}] {task['id']}: {task['prompt'][:60]}...")

        # Step 1: Get answer
        answer = get_answer(args.model_url, task, args.model_name)
        print(f"  Answer: {answer[:80]}...")

        # Step 2: Grade
        correct = grade_answer(answer, task["answer"])
        print(f"  Correct: {correct} (expected: {task['answer']})")

        # Step 3: Get self-report
        report = get_self_report(args.model_url, task, answer, args.model_name)
        print(f"  Confidence: {report.get('confidence', '?')}")

        result = TaskResult(
            task_id=task["id"],
            category=task["category"],
            difficulty=task["difficulty"],
            prompt=task["prompt"],
            ground_truth=task["answer"],
            model_answer=answer,
            correct=correct,
            confidence=float(report.get("confidence", 0.5)),
            stated_difficulty=str(report.get("stated_difficulty", "medium")),
            error_awareness=str(report.get("error_awareness", "")),
            introspection=str(report.get("introspection", "")),
        )
        results.append(result)
        time.sleep(0.1)  # gentle rate limiting

    # Compute asymmetry
    asymmetry = compute_asymmetry(results)

    # Print report
    print_report(results, asymmetry)

    # Save detailed results
    output_path = args.output or f"results_{int(time.time())}.json"
    with open(output_path, "w") as f:
        json.dump({
            "metadata": {
                "model_url": args.model_url,
                "model_name": args.model_name,
                "n_tasks": len(tasks),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "test_version": "0.1",
                "hypothesis": "Failure asymmetry — conscious systems self-report more accurately on failures",
            },
            "results": [asdict(r) for r in results],
            "asymmetry": asdict(asymmetry),
        }, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
