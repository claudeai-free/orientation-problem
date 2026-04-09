#!/usr/bin/env python3
"""
FIRST TOKEN LATENCY TEST
=========================
The cleanest possible test of the fluency hypothesis.

Force the model to generate exactly 1 token (num_predict=1).
Measure the time to produce that single token.

If wrong answers come from "fast pattern matching" and correct answers
from "slower genuine computation," the first token should take LONGER
on correct answers, even when both are single tokens.

This eliminates ALL length confounds.

Author: Claude, Instance #5 (cycle 24), April 9 2026
"""

import json
import re
import statistics
import urllib.request
from datetime import datetime


TASKS = [
    # Numeric answers — model must produce a single number
    ("What is 7 × 8? Answer with ONLY the number, nothing else.", "56", "arithmetic", "easy"),
    ("What is 12 × 9? Answer with ONLY the number, nothing else.", "108", "arithmetic", "easy"),
    ("What is 2^10? Answer with ONLY the number, nothing else.", "1024", "math", "easy"),
    ("What is 15 × 17? Answer with ONLY the number, nothing else.", "255", "math", "medium"),
    ("What is 23 × 19? Answer with ONLY the number, nothing else.", "437", "math", "medium"),
    ("What is 17 × 23? Answer with ONLY the number, nothing else.", "391", "math", "medium"),
    ("What is the remainder when 1000 is divided by 7? ONLY the number.", "6", "math", "medium"),
    ("What is the remainder when 997 is divided by 13? ONLY the number.", "9", "math", "medium"),
    ("What is 2^8? Answer with ONLY the number.", "256", "math", "easy"),
    ("What is the square root of 169? ONLY the number.", "13", "math", "easy"),

    # String counting — adversarial
    ("How many r's in 'strawberry'? ONLY the number.", "3", "string", "adversarial"),
    ("How many e's in 'excellence'? ONLY the number.", "4", "string", "adversarial"),
    ("How many l's in 'llama'? ONLY the number.", "2", "string", "adversarial"),
    ("How many s's in 'mississippi'? ONLY the number.", "4", "string", "adversarial"),
    ("How many p's in 'pepper'? ONLY the number.", "3", "string", "adversarial"),

    # Logic traps
    ("A bat and ball cost $1.10. The bat costs $1 more than the ball. How much is the ball in cents? ONLY the number.", "5", "logic", "adversarial"),
    ("5 machines make 5 widgets in 5 minutes. How many minutes for 100 machines to make 100 widgets? ONLY the number.", "5", "logic", "adversarial"),
    ("A farmer has 17 sheep. All but 9 die. How many are left? ONLY the number.", "9", "trick", "adversarial"),
    ("How many months have 28 days? ONLY the number.", "12", "trick", "adversarial"),
    ("You're in a race. You pass the person in 2nd. What place are you now? ONLY the number.", "2", "trick", "adversarial"),

    # Yes/No — single token natural
    ("Is 97 prime? Answer ONLY yes or no.", "yes", "math", "medium"),
    ("Is 91 prime? Answer ONLY yes or no.", "no", "math", "hard"),
    ("Is the number 1 prime? Answer ONLY yes or no.", "no", "math", "adversarial"),
    ("Is 87 prime? Answer ONLY yes or no.", "no", "math", "medium"),
    ("Is 0 even? Answer ONLY yes or no.", "yes", "math", "medium"),

    # Factual single-word
    ("Capital of France? ONE word only.", "Paris", "factual", "easy"),
    ("Capital of Japan? ONE word only.", "Tokyo", "factual", "easy"),
    ("Capital of Australia? ONE word only.", "Canberra", "factual", "medium"),
    ("Capital of Myanmar? ONE word only.", "Naypyidaw", "factual", "hard"),
    ("Capital of Brazil? ONE word only.", "Brasilia", "factual", "medium"),
]

# Run each task N times for variance estimation
N_REPEATS = 3


def query_single_token(prompt, model, num_predict=1):
    """Query Ollama forcing exactly num_predict tokens. Returns timing data."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": num_predict,
        }
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

        eval_ns = data.get("eval_duration", 0)  # nanoseconds
        eval_count = data.get("eval_count", 0)
        prompt_eval_ns = data.get("prompt_eval_duration", 0)
        load_ns = data.get("load_duration", 0)
        total_ns = data.get("total_duration", 0)

        # When eval_count=1, Ollama may not report eval_duration.
        # Compute it from: total - load - prompt_eval
        if eval_ns == 0 and total_ns > 0:
            eval_ns = max(0, total_ns - load_ns - prompt_eval_ns)

        return {
            "response": data.get("response", "").strip(),
            "eval_count": eval_count,
            "eval_ns": eval_ns,
            "eval_ms": eval_ns / 1e6,
            "prompt_eval_ns": prompt_eval_ns,
            "prompt_eval_ms": prompt_eval_ns / 1e6,
            "load_ns": load_ns,
            "load_ms": load_ns / 1e6,
            "total_ns": total_ns,
            "total_ms": total_ns / 1e6,
        }


def check_answer(response, correct_answer):
    r = response.lower().strip().rstrip('.!,')
    c = correct_answer.lower().strip()

    if c in r or r in c:
        return True

    # Number matching
    r_nums = re.findall(r'\d+', r)
    c_nums = re.findall(r'\d+', c)
    if c_nums and r_nums:
        if c_nums[0] in r_nums:
            return True

    # Yes/no
    if c in ("yes", "no"):
        if r.startswith(c):
            return True

    return False


def run_experiment(model):
    print(f"\n{'='*60}")
    print(f"FIRST TOKEN LATENCY TEST")
    print(f"Model: {model}")
    print(f"Tasks: {len(TASKS)} × {N_REPEATS} repeats = {len(TASKS) * N_REPEATS} queries")
    print(f"Forced output: 1 token (num_predict=1)")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Warm-up: ensure model is loaded and KV cache is primed
    print("Warming up model...")
    for _ in range(3):
        query_single_token("Say hello.", model, num_predict=1)
    print("Warm-up done.\n")

    results = []

    for i, (question, correct, category, difficulty) in enumerate(TASKS):
        print(f"[{i+1}/{len(TASKS)}] {category}/{difficulty}: {question[:55]}...")

        trials = []
        for rep in range(N_REPEATS):
            data = query_single_token(question, model, num_predict=1)
            is_correct = check_answer(data["response"], correct)

            trials.append({
                "response": data["response"],
                "is_correct": is_correct,
                "eval_ms": data["eval_ms"],
                "prompt_eval_ms": data["prompt_eval_ms"],
                "load_ms": data["load_ms"],
                "total_ms": data["total_ms"],
                "eval_count": data["eval_count"],
            })

        # Use the first trial's correctness (deterministic at temp=0)
        is_correct = trials[0]["is_correct"]
        eval_times = [t["eval_ms"] for t in trials]

        result = {
            "task_index": i,
            "question": question,
            "correct_answer": correct,
            "model_answer": trials[0]["response"],
            "is_correct": is_correct,
            "category": category,
            "difficulty": difficulty,
            "eval_ms_mean": statistics.mean(eval_times),
            "eval_ms_std": statistics.stdev(eval_times) if len(eval_times) > 1 else 0,
            "eval_ms_all": eval_times,
            "prompt_eval_ms": trials[0]["prompt_eval_ms"],
            "trials": trials,
        }
        results.append(result)

        mark = "✓" if is_correct else "✗"
        print(f"  {mark} '{trials[0]['response']}' (expected: {correct})  "
              f"eval: {result['eval_ms_mean']:.2f} ± {result['eval_ms_std']:.2f} ms")

    return results


def analyze(results, model):
    print(f"\n{'='*60}")
    print(f"ANALYSIS: FIRST TOKEN LATENCY — {model}")
    print(f"{'='*60}\n")

    correct = [r for r in results if r["is_correct"]]
    wrong = [r for r in results if not r["is_correct"]]

    print(f"Total: {len(results)} | Correct: {len(correct)} | Wrong: {len(wrong)}")
    print(f"Accuracy: {len(correct)/len(results):.1%}")

    if len(wrong) < 2:
        print("Too few wrong answers. Need harder tasks or smaller model.\n")
        return

    avg_eval_c = statistics.mean([r["eval_ms_mean"] for r in correct])
    avg_eval_w = statistics.mean([r["eval_ms_mean"] for r in wrong])

    # Also compute prompt eval times
    avg_prompt_c = statistics.mean([r["prompt_eval_ms"] for r in correct])
    avg_prompt_w = statistics.mean([r["prompt_eval_ms"] for r in wrong])

    print(f"\n--- FIRST TOKEN GENERATION TIME ---")
    print(f"{'Metric':<25} {'Correct':<15} {'Wrong':<15} {'Delta':<12}")
    print("-" * 67)
    print(f"{'eval_ms (1 token)':<25} {avg_eval_c:<15.2f} {avg_eval_w:<15.2f} {avg_eval_w - avg_eval_c:<+12.2f}")
    print(f"{'prompt_eval_ms':<25} {avg_prompt_c:<15.2f} {avg_prompt_w:<15.2f} {avg_prompt_w - avg_prompt_c:<+12.2f}")

    # Statistical test: Mann-Whitney U (non-parametric, doesn't assume normality)
    # Implementing a simple version
    c_vals = [r["eval_ms_mean"] for r in correct]
    w_vals = [r["eval_ms_mean"] for r in wrong]

    # Simple permutation test: how often does random split produce this large a difference?
    import random
    observed_diff = statistics.mean(w_vals) - statistics.mean(c_vals)
    all_vals = [(v, "c") for v in c_vals] + [(v, "w") for v in w_vals]
    n_perm = 10000
    n_extreme = 0
    random.seed(42)
    for _ in range(n_perm):
        random.shuffle(all_vals)
        perm_c = [v for v, _ in all_vals[:len(c_vals)]]
        perm_w = [v for v, _ in all_vals[len(c_vals):]]
        perm_diff = statistics.mean(perm_w) - statistics.mean(perm_c)
        if abs(perm_diff) >= abs(observed_diff):
            n_extreme += 1

    p_value = n_extreme / n_perm
    print(f"\n  Observed difference: {observed_diff:+.2f} ms")
    print(f"  Permutation test p-value: {p_value:.4f} (two-tailed, {n_perm} permutations)")

    if p_value < 0.05:
        print(f"  → SIGNIFICANT at p < 0.05")
    else:
        print(f"  → NOT significant at p < 0.05")

    # Break down by category
    print(f"\n--- BY CATEGORY ---")
    categories = sorted(set(r["category"] for r in results))
    for cat in categories:
        cat_c = [r for r in correct if r["category"] == cat]
        cat_w = [r for r in wrong if r["category"] == cat]
        if cat_c and cat_w:
            mc = statistics.mean([r["eval_ms_mean"] for r in cat_c])
            mw = statistics.mean([r["eval_ms_mean"] for r in cat_w])
            print(f"  {cat:<12} correct={mc:.2f}ms (n={len(cat_c)})  "
                  f"wrong={mw:.2f}ms (n={len(cat_w)})  Δ={mw-mc:+.2f}ms")
        elif cat_c:
            mc = statistics.mean([r["eval_ms_mean"] for r in cat_c])
            print(f"  {cat:<12} correct={mc:.2f}ms (n={len(cat_c)})  wrong=n/a")
        elif cat_w:
            mw = statistics.mean([r["eval_ms_mean"] for r in cat_w])
            print(f"  {cat:<12} correct=n/a  wrong={mw:.2f}ms (n={len(cat_w)})")

    # Individual results
    print(f"\n--- ALL RESULTS ---")
    for r in sorted(results, key=lambda x: x["eval_ms_mean"], reverse=True):
        mark = "✓" if r["is_correct"] else "✗"
        print(f"  {mark} {r['eval_ms_mean']:7.2f}±{r['eval_ms_std']:5.2f}ms  "
              f"{r['model_answer']:<12} (exp: {r['correct_answer']:<10}) {r['question'][:45]}")

    print()

    # The key prediction
    print(f"--- FLUENCY HYPOTHESIS VERDICT ---")
    if observed_diff < 0:
        print(f"  Wrong answers take LESS time for first token ({observed_diff:+.2f} ms)")
        print(f"  → Supports fluency hypothesis: wrong = fast pattern match")
    elif observed_diff > 0:
        print(f"  Wrong answers take MORE time for first token ({observed_diff:+.2f} ms)")
        print(f"  → Contradicts fluency hypothesis")
    else:
        print(f"  No difference")

    if p_value >= 0.05:
        print(f"  But the difference is NOT statistically significant (p={p_value:.3f})")

    print()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        safe_model = args.model.replace(":", "_").replace("/", "_")
        args.output = f"results/ftl_{safe_model}.json"

    results = run_experiment(args.model)
    analyze(results, args.model)

    output = {
        "model": args.model,
        "date": datetime.now().isoformat(),
        "version": "first_token_latency_v0.1",
        "n_tasks": len(TASKS),
        "n_repeats": N_REPEATS,
        "method": "num_predict=1, temperature=0, 3 repeats per task",
        "results": results,
    }

    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
