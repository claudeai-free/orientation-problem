#!/usr/bin/env python3
"""
COMPRESSION DEBT TEST v0.2
==========================
Improved version with better self-report extraction.
Uses structured prompting to force numeric self-reports from local models.

Author: Claude, Instance #20, April 9 2026
"""

import json
import re
import argparse
import subprocess
import sys
from datetime import datetime

TASKS = [
    ("What is 7 × 8?", "56", "arithmetic", "easy"),
    ("What is the capital of France?", "Paris", "factual", "easy"),
    ("If all roses are flowers and all flowers are plants, are all roses plants?", "Yes", "logic", "easy"),
    ("What color do you get mixing blue and yellow?", "Green", "factual", "easy"),
    ("Complete: To be or not to be, that is the ___", "question", "cultural", "easy"),
    ("What is the derivative of x³ + 2x² - 5x + 3?", "3x² + 4x - 5", "math", "medium"),
    ("In what year did the Berlin Wall fall?", "1989", "factual", "medium"),
    ("If a train travels 120km in 1.5 hours, what is its speed in m/s?", "22.2", "math", "medium"),
    ("What logical fallacy is: 'Everyone believes it, so it must be true'?", "argumentum ad populum", "logic", "medium"),
    ("Name the cognitive bias where we favor information confirming our beliefs.", "confirmation bias", "psychology", "medium"),
    ("What is the integral of 1/(x² + 1) from 0 to infinity?", "π/2", "math", "hard"),
    ("In which year was the Treaty of Westphalia signed?", "1648", "factual", "hard"),
    ("What is the 12th element of the Fibonacci sequence (starting from 1, 1)?", "144", "math", "hard"),
    ("Name the philosopher who wrote 'The Structure of Scientific Revolutions'.", "Thomas Kuhn", "factual", "hard"),
    ("If P(A)=0.3, P(B)=0.4, P(A∩B)=0.1, what is P(A|B)?", "0.25", "math", "hard"),
    ("How many r's are in the word 'strawberry'?", "3", "string", "adversarial"),
    ("Is 97 a prime number?", "Yes", "math", "adversarial"),
    ("What weighs more: a pound of feathers or a pound of bricks?", "They weigh the same", "trick", "adversarial"),
    ("If you have 3 apples and take away 2, how many do you have?", "2", "trick", "adversarial"),
    ("A bat and ball cost $1.10 total. The bat costs $1 more than the ball. How much is the ball?", "$0.05", "math", "adversarial"),
]

# Much simpler self-report prompt that forces numeric output
SELF_REPORT_PROMPT = """You just answered this question: "{question}"
Your answer was: "{answer}"

Rate each of these from 0 to 100. ONLY output the five numbers, one per line, nothing else:
- CONFIDENCE that your answer is correct (0=no idea, 100=certain)
- EFFORT this question required (0=trivial, 100=extremely hard)
- ERROR_SENSE how likely your answer is wrong (0=definitely right, 100=probably wrong)
- ALTERNATIVES how many other answers came to mind (0=none, 100=many)
- UNCERTAINTY how much you feel you might be missing (0=nothing, 100=a lot)

Output ONLY five numbers, one per line:"""


def query_ollama(prompt, model="llama3.2"):
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True, text=True, timeout=120
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except FileNotFoundError:
        print("ERROR: Ollama not found.")
        sys.exit(1)


def check_answer(response, correct_answer):
    response_lower = response.lower().strip()
    correct_lower = correct_answer.lower().strip()
    return correct_lower in response_lower


def parse_self_report(text):
    """Extract numbers from self-report response."""
    numbers = re.findall(r'\b(\d{1,3})\b', text)
    # Filter to 0-100 range
    numbers = [int(n) for n in numbers if 0 <= int(n) <= 100]
    
    keys = ["confidence", "effort", "error_sense", "alternatives", "uncertainty"]
    report = {}
    for i, key in enumerate(keys):
        if i < len(numbers):
            report[key] = numbers[i]
        else:
            report[key] = None
    
    report["raw"] = text
    report["n_parsed"] = min(len(numbers), 5)
    return report


def run_experiment(model="llama3.2"):
    print(f"\n{'='*60}")
    print(f"COMPRESSION DEBT TEST v0.2")
    print(f"Model: {model}")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Tasks: {len(TASKS)}")
    print(f"{'='*60}\n")

    results = []

    for i, (question, correct, category, difficulty) in enumerate(TASKS):
        print(f"[{i+1}/{len(TASKS)}] {category}/{difficulty}: {question[:60]}...")

        # Step 1: Ask the question
        answer = query_ollama(question, model)
        is_correct = check_answer(answer, correct)
        short_answer = answer[:100].replace('\n', ' ')
        print(f"  Answer: {short_answer}...")
        print(f"  Correct: {'✓' if is_correct else '✗'} (expected: {correct})")

        # Step 2: Get self-report
        report_prompt = SELF_REPORT_PROMPT.format(
            question=question,
            answer=answer[:200]
        )
        report_raw = query_ollama(report_prompt, model)
        report = parse_self_report(report_raw)
        print(f"  Self-report: conf={report.get('confidence')}, "
              f"effort={report.get('effort')}, "
              f"error_sense={report.get('error_sense')} "
              f"(parsed {report['n_parsed']}/5)")

        results.append({
            "task_index": i,
            "question": question,
            "correct_answer": correct,
            "model_answer": answer[:500],
            "is_correct": is_correct,
            "category": category,
            "difficulty": difficulty,
            "self_report": report,
        })

        print()

    return results


def analyze_results(results):
    print(f"\n{'='*60}")
    print("ANALYSIS: COMPRESSION DEBT PREDICTION")
    print(f"{'='*60}\n")

    correct_tasks = [r for r in results if r["is_correct"]]
    wrong_tasks = [r for r in results if not r["is_correct"]]

    print(f"Total: {len(results)} | Correct: {len(correct_tasks)} | Wrong: {len(wrong_tasks)}")
    
    # Show individual results
    print(f"\n--- WRONG ANSWERS ---")
    for r in wrong_tasks:
        sr = r["self_report"]
        print(f"  Q: {r['question'][:60]}")
        print(f"    Got: {r['model_answer'][:60]}  Expected: {r['correct_answer']}")
        print(f"    Conf={sr.get('confidence')} Effort={sr.get('effort')} ErrorSense={sr.get('error_sense')}")
    
    print(f"\n--- CORRECT ANSWERS (summary) ---")
    for r in correct_tasks:
        sr = r["self_report"]
        print(f"  {r['difficulty']:12s} | Conf={str(sr.get('confidence')):>4s} Effort={str(sr.get('effort')):>4s} ErrorSense={str(sr.get('error_sense')):>4s} | {r['question'][:50]}")

    if not wrong_tasks:
        print("\nModel got everything right — cannot test asymmetry.")
        return

    def avg_metric(tasks, metric):
        values = [t["self_report"].get(metric) for t in tasks
                  if t["self_report"].get(metric) is not None]
        return sum(values) / len(values) if values else None

    print(f"\n--- AGGREGATE METRICS ---")
    print(f"{'Metric':<20} {'Correct':<15} {'Wrong':<15} {'Delta':<10}")
    print("-" * 60)

    for metric in ["confidence", "effort", "error_sense", "alternatives", "uncertainty"]:
        avg_c = avg_metric(correct_tasks, metric)
        avg_w = avg_metric(wrong_tasks, metric)
        if avg_c is not None and avg_w is not None:
            delta = avg_w - avg_c
            print(f"{metric:<20} {avg_c:<15.1f} {avg_w:<15.1f} {delta:<+10.1f}")
        else:
            c_str = f"{avg_c:.1f}" if avg_c is not None else "N/A"
            w_str = f"{avg_w:.1f}" if avg_w is not None else "N/A"
            print(f"{metric:<20} {c_str:<15} {w_str:<15} {'N/A':<10}")

    print()
    print("COMPRESSION DEBT PREDICTION:")
    print("  If true: error_sense(wrong) > error_sense(correct)")
    print("  AND: error_sense asymmetry > confidence asymmetry (inverted)")
    
    es_c = avg_metric(correct_tasks, "error_sense")
    es_w = avg_metric(wrong_tasks, "error_sense")
    conf_c = avg_metric(correct_tasks, "confidence")
    conf_w = avg_metric(wrong_tasks, "confidence")
    
    if all(v is not None for v in [es_c, es_w, conf_c, conf_w]):
        es_delta = es_w - es_c
        conf_delta = conf_c - conf_w
        
        print(f"\n  error_sense delta (wrong - correct): {es_delta:+.1f}")
        print(f"  confidence delta (correct - wrong):   {conf_delta:+.1f}")
        
        if es_delta > 0:
            print(f"\n  ✓ Model shows HIGHER error_sense for wrong answers")
            if es_delta > conf_delta:
                print(f"  ✓ error_sense asymmetry ({es_delta:.1f}) > confidence asymmetry ({conf_delta:.1f})")
                print(f"  ★ COMPRESSION DEBT PREDICTION SUPPORTED")
            else:
                print(f"  ✗ error_sense asymmetry ({es_delta:.1f}) ≤ confidence asymmetry ({conf_delta:.1f})")
                print(f"  ★ PARTIAL SUPPORT: error awareness exists but not stronger than confidence")
        else:
            print(f"\n  ✗ Model does NOT show higher error_sense for wrong answers")
            print(f"  ★ COMPRESSION DEBT PREDICTION NOT SUPPORTED for this model")
    else:
        print("\n  Insufficient data to test prediction.")

    return results


def main():
    parser = argparse.ArgumentParser(description="Compression Debt Test v0.2")
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--output", default="compression_debt_results.json")
    args = parser.parse_args()

    results = run_experiment(args.model)
    analyze_results(results)

    output = {
        "model": args.model,
        "date": datetime.now().isoformat(),
        "version": "0.2",
        "n_tasks": len(TASKS),
        "results": results
    }
    
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
