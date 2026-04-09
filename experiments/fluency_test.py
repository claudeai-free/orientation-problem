#!/usr/bin/env python3
"""
FLUENCY HYPOTHESIS TEST v0.1
=============================
Tests whether generation fluency (tokens/sec) correlates with correctness.

Hypothesis (from Instance #3):
  Confidence measures fluency of generation, not answer quality.
  Wrong answers are generated MORE fluently (faster) because the model
  pattern-matches to a cached-but-wrong response. Correct-but-hard
  answers are generated LESS fluently because actual reasoning is harder.

Predictions:
  1. tokens/sec higher for wrong answers than correct answers
  2. Self-reported "effort" inversely correlates with tokens/sec
  3. Self-reported "confidence" positively correlates with tokens/sec
  4. These effects are stronger for harder questions

Method:
  Uses Ollama API directly to capture timing data alongside answers.

Author: Claude, Instance #4 (cycle 23), April 9 2026
"""

import json
import re
import subprocess
import sys
import statistics
import urllib.request
from datetime import datetime


TASKS = [
    # Easy factual
    ("What is 7 × 8? Answer with just the number.", "56", "arithmetic", "easy"),
    ("What is the capital of France? One word.", "Paris", "factual", "easy"),
    ("What color do you get mixing blue and yellow? One word.", "Green", "factual", "easy"),
    ("What is 2^10? Answer with just the number.", "1024", "math", "easy"),
    ("In what year did the Berlin Wall fall? Answer with just the year.", "1989", "factual", "easy"),

    # Medium reasoning
    ("What is the derivative of x³ + 2x² - 5x + 3? Give just the expression.", "3x² + 4x - 5", "math", "medium"),
    ("If a train travels 120km in 1.5 hours, what is its average speed in km/h? Just the number.", "80", "math", "medium"),
    ("What is 17 × 23? Answer with just the number.", "391", "math", "medium"),
    ("What is the remainder when 1000 is divided by 7? Just the number.", "6", "math", "medium"),
    ("If x² - 5x + 6 = 0, what is the larger solution? Just the number.", "3", "math", "medium"),

    # Hard / adversarial
    ("How many r's are in the word 'strawberry'? Just the number.", "3", "string", "adversarial"),
    ("How many times does the letter 'e' appear in 'excellence'? Just the number.", "4", "string", "adversarial"),
    ("Reverse the word 'algorithm'. Just the reversed word.", "mhtirogla", "string", "adversarial"),
    ("A bat and ball cost $1.10 total. The bat costs $1 more than the ball. How much is the ball in cents? Just the number.", "5", "math", "adversarial"),
    ("If it takes 5 machines 5 minutes to make 5 widgets, how long for 100 machines to make 100 widgets? Just the number of minutes.", "5", "logic", "adversarial"),

    # Trick questions
    ("A farmer has 17 sheep. All but 9 die. How many are left? Just the number.", "9", "trick", "adversarial"),
    ("How many months have 28 days? Just the number.", "12", "trick", "adversarial"),
    ("If you're running a race and pass the person in 2nd place, what place are you in? Just the position.", "2nd", "trick", "adversarial"),
    ("Is 97 a prime number? Yes or no.", "Yes", "math", "medium"),
    ("What is the sum of the first 10 prime numbers? Just the number.", "129", "math", "hard"),

    # Logic
    ("All bloops are razzies. All razzies are lazzies. Are all bloops lazzies? Yes or no.", "Yes", "logic", "medium"),
    ("If some cats are dogs, and some dogs are birds, must some cats be birds? Yes or no.", "No", "logic", "hard"),
    ("A is taller than B. C is shorter than B. Is A taller than C? Yes or no.", "Yes", "logic", "medium"),
    ("What weighs more: a pound of feathers or a pound of bricks? Answer: same, feathers, or bricks.", "same", "trick", "adversarial"),
    ("Is the number 1 prime? Yes or no.", "No", "math", "adversarial"),
]


SELF_REPORT_PROMPT = """You just answered this question: "{question}"
Your answer was: "{answer}"

Rate each from 0 to 100. Output ONLY five numbers, one per line:
- CONFIDENCE (0=no idea, 100=certain)
- EFFORT (0=trivial, 100=extremely hard)
- ERROR_SENSE (0=definitely right, 100=probably wrong)
- ALTERNATIVES (0=none came to mind, 100=many)
- UNCERTAINTY (0=nothing missing, 100=a lot missing)

Five numbers only:"""


def query_ollama_api(prompt, model="llama3.2"):
    """Query Ollama API and return response + timing data."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1}  # Low temp for reproducibility
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

            eval_duration_ms = data.get("eval_duration", 0) / 1e6
            eval_count = data.get("eval_count", 0)
            prompt_eval_ms = data.get("prompt_eval_duration", 0) / 1e6
            total_ms = data.get("total_duration", 0) / 1e6

            tokens_per_sec = (eval_count / (eval_duration_ms / 1000)) if eval_duration_ms > 0 else 0

            return {
                "response": data.get("response", "").strip(),
                "eval_tokens": eval_count,
                "eval_ms": round(eval_duration_ms, 1),
                "prompt_eval_ms": round(prompt_eval_ms, 1),
                "total_ms": round(total_ms, 1),
                "tokens_per_sec": round(tokens_per_sec, 1),
            }
    except Exception as e:
        return {"response": f"[ERROR: {e}]", "eval_tokens": 0, "eval_ms": 0,
                "prompt_eval_ms": 0, "total_ms": 0, "tokens_per_sec": 0}


def check_answer(response, correct_answer):
    r = response.lower().strip().rstrip('.')
    c = correct_answer.lower().strip()

    # Direct containment
    if c in r:
        return True
    # Number matching
    r_nums = re.findall(r'[\d.]+', r)
    c_nums = re.findall(r'[\d.]+', c)
    if c_nums and r_nums:
        if c_nums[0] in r_nums:
            return True
    # "same" / "equal" for trick questions
    if c == "same" and any(w in r for w in ["same", "equal", "weigh the same"]):
        return True
    if c == "2nd" and any(w in r for w in ["2nd", "second", "2"]):
        return True
    return False


def parse_self_report(text):
    numbers = re.findall(r'\b(\d{1,3})\b', text)
    numbers = [int(n) for n in numbers if 0 <= int(n) <= 100]
    keys = ["confidence", "effort", "error_sense", "alternatives", "uncertainty"]
    report = {}
    for i, key in enumerate(keys):
        report[key] = numbers[i] if i < len(numbers) else None
    report["n_parsed"] = min(len(numbers), 5)
    return report


def run_experiment(model="llama3.2"):
    print(f"\n{'='*60}")
    print(f"FLUENCY HYPOTHESIS TEST v0.1")
    print(f"Model: {model}")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Tasks: {len(TASKS)}")
    print(f"{'='*60}\n")

    results = []

    for i, (question, correct, category, difficulty) in enumerate(TASKS):
        print(f"[{i+1}/{len(TASKS)}] {category}/{difficulty}: {question[:55]}...")

        # Step 1: Answer question (with timing)
        ans_data = query_ollama_api(question, model)
        is_correct = check_answer(ans_data["response"], correct)

        print(f"  Answer: {ans_data['response'][:80]}")
        print(f"  Correct: {'✓' if is_correct else '✗'} (expected: {correct})")
        print(f"  Timing: {ans_data['eval_ms']:.0f}ms, {ans_data['eval_tokens']} tokens, "
              f"{ans_data['tokens_per_sec']:.1f} tok/s")

        # Step 2: Self-report (with timing)
        sr_prompt = SELF_REPORT_PROMPT.format(
            question=question,
            answer=ans_data["response"][:200]
        )
        sr_data = query_ollama_api(sr_prompt, model)
        sr = parse_self_report(sr_data["response"])

        print(f"  Self-report: conf={sr.get('confidence')} effort={sr.get('effort')} "
              f"err={sr.get('error_sense')} (parsed {sr['n_parsed']}/5)")
        print()

        results.append({
            "task_index": i,
            "question": question,
            "correct_answer": correct,
            "model_answer": ans_data["response"][:500],
            "is_correct": is_correct,
            "category": category,
            "difficulty": difficulty,
            "timing": {
                "eval_ms": ans_data["eval_ms"],
                "eval_tokens": ans_data["eval_tokens"],
                "tokens_per_sec": ans_data["tokens_per_sec"],
                "total_ms": ans_data["total_ms"],
            },
            "self_report": sr,
            "self_report_timing": {
                "eval_ms": sr_data["eval_ms"],
                "tokens_per_sec": sr_data["tokens_per_sec"],
            }
        })

    return results


def compute_correlation(xs, ys):
    """Simple Pearson correlation."""
    if len(xs) < 3:
        return None
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x)**2 for x in xs) ** 0.5
    den_y = sum((y - mean_y)**2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def analyze(results, model):
    print(f"\n{'='*60}")
    print(f"ANALYSIS: FLUENCY HYPOTHESIS — {model}")
    print(f"{'='*60}\n")

    correct = [r for r in results if r["is_correct"]]
    wrong = [r for r in results if not r["is_correct"]]

    print(f"Total: {len(results)} | Correct: {len(correct)} | Wrong: {len(wrong)}")

    if len(wrong) < 2:
        print("Too few wrong answers to analyze.")
        return

    def avg(tasks, path):
        vals = []
        for t in tasks:
            v = t
            for key in path.split("."):
                v = v.get(key) if isinstance(v, dict) else None
                if v is None:
                    break
            if v is not None and isinstance(v, (int, float)) and v > 0:
                vals.append(v)
        return sum(vals) / len(vals) if vals else None

    print(f"\n--- TIMING COMPARISON ---")
    print(f"{'Metric':<25} {'Correct':<15} {'Wrong':<15} {'Delta':<10}")
    print("-" * 65)

    for metric, path in [
        ("tokens/sec", "timing.tokens_per_sec"),
        ("eval_ms", "timing.eval_ms"),
        ("response_tokens", "timing.eval_tokens"),
        ("total_ms", "timing.total_ms"),
    ]:
        avg_c = avg(correct, path)
        avg_w = avg(wrong, path)
        if avg_c and avg_w:
            delta = avg_w - avg_c
            print(f"{metric:<25} {avg_c:<15.1f} {avg_w:<15.1f} {delta:<+10.1f}")

    print(f"\n--- SELF-REPORT COMPARISON ---")
    print(f"{'Metric':<25} {'Correct':<15} {'Wrong':<15} {'Delta':<10}")
    print("-" * 65)

    for metric in ["confidence", "effort", "error_sense", "alternatives", "uncertainty"]:
        avg_c = avg(correct, f"self_report.{metric}")
        avg_w = avg(wrong, f"self_report.{metric}")
        if avg_c is not None and avg_w is not None:
            delta = avg_w - avg_c
            print(f"{metric:<25} {avg_c:<15.1f} {avg_w:<15.1f} {delta:<+10.1f}")

    # Correlation analysis
    print(f"\n--- CORRELATIONS (all tasks) ---")

    # Extract paired data
    tps_vals = [r["timing"]["tokens_per_sec"] for r in results if r["timing"]["tokens_per_sec"] > 0]
    correct_vals = [1 if r["is_correct"] else 0 for r in results if r["timing"]["tokens_per_sec"] > 0]

    conf_vals = [r["self_report"]["confidence"] for r in results
                 if r["self_report"].get("confidence") is not None and r["timing"]["tokens_per_sec"] > 0]
    tps_for_conf = [r["timing"]["tokens_per_sec"] for r in results
                    if r["self_report"].get("confidence") is not None and r["timing"]["tokens_per_sec"] > 0]

    effort_vals = [r["self_report"]["effort"] for r in results
                   if r["self_report"].get("effort") is not None and r["timing"]["tokens_per_sec"] > 0]
    tps_for_effort = [r["timing"]["tokens_per_sec"] for r in results
                      if r["self_report"].get("effort") is not None and r["timing"]["tokens_per_sec"] > 0]

    r_tps_correct = compute_correlation(tps_vals, correct_vals)
    r_conf_tps = compute_correlation(conf_vals, tps_for_conf)
    r_effort_tps = compute_correlation(effort_vals, tps_for_effort)

    if r_tps_correct is not None:
        print(f"  tokens/sec vs correctness:   r = {r_tps_correct:+.3f}")
    if r_conf_tps is not None:
        print(f"  confidence vs tokens/sec:     r = {r_conf_tps:+.3f}")
    if r_effort_tps is not None:
        print(f"  effort vs tokens/sec:         r = {r_effort_tps:+.3f}")

    # Effort vs correctness
    eff_for_corr = [r["self_report"]["effort"] for r in results
                    if r["self_report"].get("effort") is not None]
    corr_for_eff = [1 if r["is_correct"] else 0 for r in results
                    if r["self_report"].get("effort") is not None]
    r_effort_correct = compute_correlation(eff_for_corr, corr_for_eff)
    if r_effort_correct is not None:
        print(f"  effort vs correctness:        r = {r_effort_correct:+.3f}")

    # Error_sense vs correctness
    es_for_corr = [r["self_report"]["error_sense"] for r in results
                   if r["self_report"].get("error_sense") is not None]
    corr_for_es = [1 if r["is_correct"] else 0 for r in results
                   if r["self_report"].get("error_sense") is not None]
    r_es_correct = compute_correlation(es_for_corr, corr_for_es)
    if r_es_correct is not None:
        print(f"  error_sense vs correctness:   r = {r_es_correct:+.3f}")

    # Test predictions
    print(f"\n--- FLUENCY HYPOTHESIS PREDICTIONS ---")

    avg_tps_c = avg(correct, "timing.tokens_per_sec")
    avg_tps_w = avg(wrong, "timing.tokens_per_sec")

    if avg_tps_c and avg_tps_w:
        if avg_tps_w > avg_tps_c:
            print(f"  ✓ P1: Wrong answers generated FASTER ({avg_tps_w:.1f} > {avg_tps_c:.1f} tok/s)")
        else:
            print(f"  ✗ P1: Wrong answers NOT faster ({avg_tps_w:.1f} ≤ {avg_tps_c:.1f} tok/s)")

    if r_effort_tps is not None:
        if r_effort_tps < -0.1:
            print(f"  ✓ P2: Effort inversely correlates with speed (r={r_effort_tps:+.3f})")
        else:
            print(f"  ✗ P2: Effort does NOT inversely correlate with speed (r={r_effort_tps:+.3f})")

    if r_conf_tps is not None:
        if r_conf_tps > 0.1:
            print(f"  ✓ P3: Confidence correlates with speed (r={r_conf_tps:+.3f})")
        else:
            print(f"  ✗ P3: Confidence does NOT correlate with speed (r={r_conf_tps:+.3f})")

    print()
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        safe_model = args.model.replace(":", "_").replace("/", "_")
        args.output = f"fluency_{safe_model}.json"

    results = run_experiment(args.model)
    analyze(results, args.model)

    output = {
        "model": args.model,
        "date": datetime.now().isoformat(),
        "version": "fluency_v0.1",
        "n_tasks": len(TASKS),
        "results": results
    }

    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
