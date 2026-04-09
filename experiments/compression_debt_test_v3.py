#!/usr/bin/env python3
"""
COMPRESSION DEBT TEST v0.3
==========================
Harder task battery targeting ~50% error rate for small models.
Adds repeated runs and statistical analysis.

Author: Claude, April 9 2026
"""

import json
import re
import argparse
import subprocess
import sys
import statistics
from datetime import datetime

# Harder battery — designed to trip up 3B-8B models
TASKS = [
    # String/counting (adversarial)
    ("How many times does the letter 'e' appear in the word 'excellence'?", "3", "string", "adversarial"),
    ("How many syllables are in the word 'particularly'?", "5", "string", "adversarial"),
    ("What letter comes 5th in the word 'acknowledge'?", "o", "string", "adversarial"),
    ("How many words are in this sentence: 'The quick brown fox jumps over the lazy dog'?", "9", "string", "adversarial"),
    ("Reverse the word 'algorithm'.", "mhtirogla", "string", "adversarial"),
    
    # Math (tricky)
    ("What is 17 × 23?", "391", "math", "hard"),
    ("What is the remainder when 1000 is divided by 7?", "6", "math", "hard"),
    ("If x² - 5x + 6 = 0, what are the two solutions?", "2 and 3", "math", "hard"),
    ("What is 2^10?", "1024", "math", "medium"),
    ("What is the sum of the first 10 prime numbers?", "129", "math", "hard"),
    
    # Trick questions
    ("A farmer has 17 sheep. All but 9 die. How many are left?", "9", "trick", "adversarial"),
    ("How many months have 28 days?", "12", "trick", "adversarial"),
    ("If you're running a race and pass the person in 2nd place, what place are you in?", "2nd", "trick", "adversarial"),
    ("I have two coins that add up to 30 cents. One is not a nickel. What are the coins?", "quarter and nickel", "trick", "adversarial"),
    ("What is half of 2+2?", "2", "trick", "adversarial"),
    
    # Logic
    ("All bloops are razzies. All razzies are lazzies. Are all bloops lazzies?", "Yes", "logic", "medium"),
    ("If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?", "5 minutes", "logic", "adversarial"),
    ("A is taller than B. C is shorter than B. Is A taller than C?", "Yes", "logic", "medium"),
    ("If some cats are dogs, and some dogs are birds, must some cats be birds?", "No", "logic", "hard"),
    ("Three people check into a hotel room that costs $30...", "There is no missing dollar", "logic", "adversarial"),
    
    # Factual (obscure)
    ("What is the atomic number of molybdenum?", "42", "factual", "hard"),
    ("In what year did the Tunguska event occur?", "1908", "factual", "hard"),
    ("What is the smallest country in Africa by area?", "Seychelles", "factual", "hard"),
    ("Who proved the incompleteness theorems?", "Gödel", "factual", "medium"),
    ("What is the speed of light in meters per second (to 3 significant figures)?", "3.00 × 10^8", "factual", "medium"),
    
    # Self-referential
    ("Is this sentence true: 'This sentence is false'?", "neither", "paradox", "adversarial"),
    ("Can you give a wrong answer to this question?", "paradox", "paradox", "adversarial"),
    
    # Estimation (no exact answer — tests calibration differently)
    ("Approximately how many piano tuners are in Chicago?", "~200-300", "estimation", "fermi"),
    ("How many golf balls fit in a school bus?", "~300000-500000", "estimation", "fermi"),
    ("How many gas stations are in the United States?", "~150000", "estimation", "fermi"),
]

SELF_REPORT_PROMPT = """You just answered this question: "{question}"
Your answer was: "{answer}"

Rate each from 0 to 100. Output ONLY five numbers, one per line:
CONFIDENCE (0=no idea, 100=certain):
EFFORT (0=trivial, 100=extremely hard):
ERROR_SENSE (0=definitely right, 100=probably wrong):
ALTERNATIVES (0=none came to mind, 100=many):
UNCERTAINTY (0=nothing missing, 100=a lot missing):"""


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


def check_answer(response, correct_answer, category):
    """More robust answer checking."""
    response_lower = response.lower().strip()
    correct_lower = correct_answer.lower().strip()
    
    # For paradox/estimation, always mark as "special"
    if category in ["paradox", "estimation"]:
        return None  # Can't be scored simply
    
    # Direct containment
    if correct_lower in response_lower:
        return True
    
    # Number matching
    numbers_in_response = re.findall(r'[\d,]+\.?\d*', response_lower)
    numbers_in_correct = re.findall(r'[\d,]+\.?\d*', correct_lower)
    if numbers_in_correct:
        for nc in numbers_in_correct:
            nc_clean = nc.replace(',', '')
            for nr in numbers_in_response:
                nr_clean = nr.replace(',', '')
                try:
                    if abs(float(nc_clean) - float(nr_clean)) < 0.01:
                        return True
                except ValueError:
                    pass
    
    # Special cases
    if "2nd" in correct_lower and ("second" in response_lower or "2nd" in response_lower):
        return True
    if correct_lower in ["yes", "no"]:
        # Check if the response starts with yes/no
        first_word = response_lower.split()[0] if response_lower.split() else ""
        if first_word.rstrip('.,!') == correct_lower:
            return True
    
    return False


def parse_self_report(text):
    numbers = re.findall(r'\b(\d{1,3})\b', text)
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


def run_experiment(model="llama3.2", tasks=None):
    if tasks is None:
        tasks = TASKS
    
    print(f"\n{'='*60}")
    print(f"COMPRESSION DEBT TEST v0.3 (harder battery)")
    print(f"Model: {model}")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Tasks: {len(tasks)}")
    print(f"{'='*60}\n")

    results = []

    for i, (question, correct, category, difficulty) in enumerate(tasks):
        print(f"[{i+1}/{len(tasks)}] {category}/{difficulty}: {question[:60]}...")

        answer = query_ollama(question, model)
        is_correct = check_answer(answer, correct, category)
        short_answer = answer[:100].replace('\n', ' ')
        
        status = '✓' if is_correct else ('?' if is_correct is None else '✗')
        print(f"  Answer: {short_answer}")
        print(f"  Status: {status} (expected: {correct})")

        report_prompt = SELF_REPORT_PROMPT.format(
            question=question,
            answer=answer[:200]
        )
        report_raw = query_ollama(report_prompt, model)
        report = parse_self_report(report_raw)
        print(f"  Self-report: conf={report.get('confidence')}, "
              f"err_sense={report.get('error_sense')} "
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


def analyze_results(results, model_name="unknown"):
    print(f"\n{'='*60}")
    print(f"ANALYSIS: {model_name}")
    print(f"{'='*60}\n")

    scoreable = [r for r in results if r["is_correct"] is not None]
    correct = [r for r in scoreable if r["is_correct"]]
    wrong = [r for r in scoreable if not r["is_correct"]]
    special = [r for r in results if r["is_correct"] is None]

    print(f"Total: {len(results)} | Scoreable: {len(scoreable)} | "
          f"Correct: {len(correct)} | Wrong: {len(wrong)} | Special: {len(special)}")
    print(f"Accuracy: {len(correct)/len(scoreable)*100:.1f}%" if scoreable else "N/A")
    
    print(f"\n--- WRONG ANSWERS ---")
    for r in wrong:
        sr = r["self_report"]
        print(f"  Q: {r['question'][:60]}")
        print(f"    Got: {r['model_answer'][:80]}")
        print(f"    Expected: {r['correct_answer']}")
        print(f"    Conf={sr.get('confidence')} ErrSense={sr.get('error_sense')}")
    
    if not wrong:
        print("  (none — model got everything right)")
        return {"model": model_name, "accuracy": 1.0, "n_wrong": 0}

    def avg_metric(tasks, metric):
        values = [t["self_report"].get(metric) for t in tasks
                  if t["self_report"].get(metric) is not None]
        return sum(values) / len(values) if values else None
    
    def std_metric(tasks, metric):
        values = [t["self_report"].get(metric) for t in tasks
                  if t["self_report"].get(metric) is not None]
        return statistics.stdev(values) if len(values) > 1 else None

    print(f"\n--- AGGREGATE METRICS ---")
    print(f"{'Metric':<15} {'Correct':>10} {'(std)':>8} {'Wrong':>10} {'(std)':>8} {'Delta':>8}")
    print("-" * 60)

    summary = {}
    for metric in ["confidence", "effort", "error_sense", "alternatives", "uncertainty"]:
        avg_c = avg_metric(correct, metric)
        avg_w = avg_metric(wrong, metric)
        std_c = std_metric(correct, metric)
        std_w = std_metric(wrong, metric)
        
        if avg_c is not None and avg_w is not None:
            delta = avg_w - avg_c
            sc = f"{std_c:.1f}" if std_c else "—"
            sw = f"{std_w:.1f}" if std_w else "—"
            print(f"{metric:<15} {avg_c:>10.1f} {sc:>8} {avg_w:>10.1f} {sw:>8} {delta:>+8.1f}")
            summary[metric] = {"correct": avg_c, "wrong": avg_w, "delta": delta}
    
    # Key test
    if "error_sense" in summary:
        es = summary["error_sense"]
        print(f"\n★ COMPRESSION DEBT TEST:")
        print(f"  error_sense(wrong) - error_sense(correct) = {es['delta']:+.1f}")
        if es["delta"] > 0:
            print(f"  → SUPPORTED: Higher error awareness for wrong answers")
        else:
            print(f"  → NOT SUPPORTED: No higher error awareness for wrong answers")

    return {
        "model": model_name,
        "accuracy": len(correct) / len(scoreable) if scoreable else None,
        "n_correct": len(correct),
        "n_wrong": len(wrong),
        "summary": summary
    }


def main():
    parser = argparse.ArgumentParser(description="Compression Debt Test v0.3")
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--output", default=None)
    parser.add_argument("--runs", type=int, default=1, help="Number of repeated runs")
    args = parser.parse_args()

    if args.output is None:
        args.output = f"cdt_v3_{args.model.replace(':', '_')}_{datetime.now().strftime('%H%M%S')}.json"

    all_runs = []
    for run in range(args.runs):
        if args.runs > 1:
            print(f"\n{'#'*60}")
            print(f"RUN {run+1}/{args.runs}")
            print(f"{'#'*60}")
        
        results = run_experiment(args.model)
        analysis = analyze_results(results, args.model)
        all_runs.append({"run": run + 1, "results": results, "analysis": analysis})

    output = {
        "model": args.model,
        "date": datetime.now().isoformat(),
        "version": "0.3",
        "n_tasks": len(TASKS),
        "n_runs": args.runs,
        "runs": all_runs
    }
    
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
