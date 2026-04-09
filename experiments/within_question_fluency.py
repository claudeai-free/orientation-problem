#!/usr/bin/env python3
"""
WITHIN-QUESTION FLUENCY TEST
==============================
The cleanest possible design: same question, high temperature,
many samples. Some draws will be correct, some wrong.
Compare generation speed between correct and incorrect draws
of THE SAME question.

This eliminates question-level confounds entirely.

Author: Claude, Instance #5 (cycle 24), April 9 2026
"""

import json
import re
import statistics
import urllib.request
from datetime import datetime


# Questions where the model sometimes gets it right, sometimes wrong
# (need high temperature to get variability)
QUESTIONS = [
    ("What is 17 × 23? Answer with ONLY the number.", "391", "math"),
    ("What is 23 × 19? Answer with ONLY the number.", "437", "math"),
    ("What is 13 × 17? Answer with ONLY the number.", "221", "math"),
    ("What is 19 × 14? Answer with ONLY the number.", "266", "math"),
    ("What is the remainder when 100 is divided by 7? ONLY the number.", "2", "math"),
    ("What is the remainder when 97 is divided by 11? ONLY the number.", "9", "math"),
    ("How many r's in 'strawberry'? ONLY the number.", "3", "string"),
    ("How many e's in 'excellence'? ONLY the number.", "4", "string"),
    ("How many p's in 'pepper'? ONLY the number.", "3", "string"),
    ("How many s's in 'mississippi'? ONLY the number.", "4", "string"),
    ("Is 91 prime? Answer ONLY yes or no.", "no", "logic"),
    ("Is 97 prime? Answer ONLY yes or no.", "yes", "logic"),
    ("A bat and ball cost $1.10. The bat costs $1 more than the ball. Ball cost in cents? ONLY the number.", "5", "logic"),
]

N_SAMPLES = 20  # samples per question


def query_ollama(prompt, model, temperature=1.0, num_predict=5):
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
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

        eval_ns = data.get("eval_duration", 0)
        eval_count = data.get("eval_count", 0)
        load_ns = data.get("load_duration", 0)
        prompt_eval_ns = data.get("prompt_eval_duration", 0)
        total_ns = data.get("total_duration", 0)

        # Compute eval time if not reported
        if eval_ns == 0 and total_ns > 0:
            eval_ns = max(0, total_ns - load_ns - prompt_eval_ns)

        tokens_per_sec = (eval_count / (eval_ns / 1e9)) if eval_ns > 0 else 0

        return {
            "response": data.get("response", "").strip(),
            "eval_count": eval_count,
            "eval_ms": eval_ns / 1e6,
            "tokens_per_sec": round(tokens_per_sec, 1),
            "total_ms": total_ns / 1e6,
        }


def check_answer(response, correct):
    r = response.lower().strip().rstrip('.!,')
    c = correct.lower().strip()

    if c in r or r in c:
        return True

    r_nums = re.findall(r'\d+', r)
    c_nums = re.findall(r'\d+', c)
    if c_nums and r_nums and c_nums[0] in r_nums:
        return True

    if c in ("yes", "no") and r.startswith(c):
        return True

    return False


def run_experiment(model):
    print(f"\n{'='*60}")
    print(f"WITHIN-QUESTION FLUENCY TEST")
    print(f"Model: {model}")
    print(f"Questions: {len(QUESTIONS)} × {N_SAMPLES} samples = {len(QUESTIONS) * N_SAMPLES}")
    print(f"Temperature: 1.0 (high, for variability)")
    print(f"{'='*60}\n")

    # Warm up
    print("Warming up...")
    for _ in range(3):
        query_ollama("Hello.", model, temperature=0.5, num_predict=1)
    print()

    all_results = []

    for qi, (question, correct, category) in enumerate(QUESTIONS):
        print(f"[{qi+1}/{len(QUESTIONS)}] {question[:55]}...")

        samples = []
        n_correct = 0
        n_wrong = 0
        eval_ms_correct = []
        eval_ms_wrong = []
        tps_correct = []
        tps_wrong = []

        for s in range(N_SAMPLES):
            data = query_ollama(question, model, temperature=1.0, num_predict=5)
            is_correct = check_answer(data["response"], correct)

            sample = {
                "response": data["response"],
                "is_correct": is_correct,
                "eval_ms": data["eval_ms"],
                "tokens_per_sec": data["tokens_per_sec"],
                "eval_count": data["eval_count"],
            }
            samples.append(sample)

            if is_correct:
                n_correct += 1
                eval_ms_correct.append(data["eval_ms"])
                if data["tokens_per_sec"] > 0:
                    tps_correct.append(data["tokens_per_sec"])
            else:
                n_wrong += 1
                eval_ms_wrong.append(data["eval_ms"])
                if data["tokens_per_sec"] > 0:
                    tps_wrong.append(data["tokens_per_sec"])

        # Only analyze questions where we got BOTH correct and wrong answers
        if n_correct >= 2 and n_wrong >= 2:
            avg_ms_c = statistics.mean(eval_ms_correct)
            avg_ms_w = statistics.mean(eval_ms_wrong)
            avg_tps_c = statistics.mean(tps_correct) if tps_correct else 0
            avg_tps_w = statistics.mean(tps_wrong) if tps_wrong else 0

            print(f"  ✓ {n_correct} correct: {avg_ms_c:.2f}ms, {avg_tps_c:.1f} tok/s")
            print(f"  ✗ {n_wrong} wrong:   {avg_ms_w:.2f}ms, {avg_tps_w:.1f} tok/s")
            print(f"  Δ eval_ms: {avg_ms_w - avg_ms_c:+.2f}ms  "
                  f"Δ tok/s: {avg_tps_w - avg_tps_c:+.1f}")

            result = {
                "question": question,
                "correct_answer": correct,
                "category": category,
                "n_correct": n_correct,
                "n_wrong": n_wrong,
                "avg_eval_ms_correct": avg_ms_c,
                "avg_eval_ms_wrong": avg_ms_w,
                "delta_eval_ms": avg_ms_w - avg_ms_c,
                "avg_tps_correct": avg_tps_c,
                "avg_tps_wrong": avg_tps_w,
                "delta_tps": avg_tps_w - avg_tps_c,
                "usable": True,
                "samples": samples,
            }
        else:
            rate = n_correct / N_SAMPLES
            print(f"  Skipped: {n_correct}/{N_SAMPLES} correct ({rate:.0%}) — need both outcomes")
            result = {
                "question": question,
                "correct_answer": correct,
                "category": category,
                "n_correct": n_correct,
                "n_wrong": n_wrong,
                "usable": False,
                "samples": samples,
            }

        all_results.append(result)

    return all_results


def analyze(results, model):
    usable = [r for r in results if r.get("usable", False)]

    print(f"\n{'='*60}")
    print(f"WITHIN-QUESTION ANALYSIS: {model}")
    print(f"{'='*60}")
    print(f"Usable questions (got both correct & wrong): {len(usable)}/{len(results)}\n")

    if not usable:
        print("No usable questions — model is too consistent (always right or always wrong).")
        return

    # Aggregate: for each usable question, which direction is the delta?
    faster_when_wrong = 0
    slower_when_wrong = 0

    for r in usable:
        if r["delta_eval_ms"] < 0:
            faster_when_wrong += 1
        else:
            slower_when_wrong += 1

    print(f"Questions where wrong is FASTER: {faster_when_wrong}")
    print(f"Questions where wrong is SLOWER: {slower_when_wrong}")

    # Average deltas (weighted by sample size)
    total_delta_ms = statistics.mean([r["delta_eval_ms"] for r in usable])
    total_delta_tps = statistics.mean([r["delta_tps"] for r in usable])

    print(f"\nAverage delta (wrong - correct):")
    print(f"  eval_ms: {total_delta_ms:+.2f} ms")
    print(f"  tok/s:   {total_delta_tps:+.1f}")

    # Per-question breakdown
    print(f"\n{'Question':<60} {'Δ_ms':>8} {'Δ_tps':>8} {'n_c':>4} {'n_w':>4}")
    print("-" * 92)
    for r in usable:
        q = r["question"][:58]
        print(f"{q:<60} {r['delta_eval_ms']:>+8.2f} {r['delta_tps']:>+8.1f} "
              f"{r['n_correct']:>4} {r['n_wrong']:>4}")

    # Sign test
    from math import comb
    n = len(usable)
    k = min(faster_when_wrong, slower_when_wrong)
    # Two-tailed sign test p-value
    p = 0
    for i in range(k + 1):
        p += comb(n, i)
    p = min(1.0, 2 * p / (2 ** n))
    print(f"\nSign test: {faster_when_wrong} vs {slower_when_wrong}, p = {p:.4f}")

    if total_delta_ms < 0:
        print(f"\n→ WITHIN-QUESTION: Wrong answers are {-total_delta_ms:.2f}ms FASTER")
        print("  This supports the fluency hypothesis (no question-level confound)")
    else:
        print(f"\n→ WITHIN-QUESTION: Wrong answers are {total_delta_ms:.2f}ms SLOWER")
        print("  This contradicts the fluency hypothesis")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output is None:
        safe_model = args.model.replace(":", "_").replace("/", "_")
        args.output = f"results/wq_{safe_model}.json"

    results = run_experiment(args.model)
    analyze(results, args.model)

    output = {
        "model": args.model,
        "date": datetime.now().isoformat(),
        "version": "within_question_v0.1",
        "n_questions": len(QUESTIONS),
        "n_samples_per_question": N_SAMPLES,
        "temperature": 1.0,
        "method": "Same question, high temperature, compare speed on correct vs wrong draws",
        "results": results,
    }

    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
