#!/usr/bin/env python3
"""
Re-analysis of fluency data controlling for response length.
Only compares short responses (≤5 tokens) to remove the length confound.
"""

import json
import glob
import os

def load_results(path):
    with open(path) as f:
        return json.load(f)

def analyze_short_only(data, max_tokens=5):
    model = data["model"]
    results = data["results"]

    # Filter to short responses only
    short = [r for r in results if r["timing"]["eval_tokens"] <= max_tokens and r["timing"]["tokens_per_sec"] > 0]
    correct = [r for r in short if r["is_correct"]]
    wrong = [r for r in short if not r["is_correct"]]

    print(f"\n{'='*50}")
    print(f"{model} — Short responses only (≤{max_tokens} tokens)")
    print(f"{'='*50}")
    print(f"Total short: {len(short)} | Correct: {len(correct)} | Wrong: {len(wrong)}")

    if len(correct) < 2 or len(wrong) < 2:
        print("Too few in one category.")
        return

    avg_c = sum(r["timing"]["tokens_per_sec"] for r in correct) / len(correct)
    avg_w = sum(r["timing"]["tokens_per_sec"] for r in wrong) / len(wrong)

    avg_tok_c = sum(r["timing"]["eval_tokens"] for r in correct) / len(correct)
    avg_tok_w = sum(r["timing"]["eval_tokens"] for r in wrong) / len(wrong)

    avg_ms_c = sum(r["timing"]["eval_ms"] for r in correct) / len(correct)
    avg_ms_w = sum(r["timing"]["eval_ms"] for r in wrong) / len(wrong)

    print(f"\n  Correct:  {avg_c:.1f} tok/s  (avg {avg_tok_c:.1f} tokens, {avg_ms_c:.1f}ms)")
    print(f"  Wrong:    {avg_w:.1f} tok/s  (avg {avg_tok_w:.1f} tokens, {avg_ms_w:.1f}ms)")
    print(f"  Delta:    {avg_w - avg_c:+.1f} tok/s")

    if avg_w > avg_c:
        print(f"  → Wrong STILL faster even controlling for length")
    else:
        print(f"  → Effect disappears when controlling for length")

    # Also check eval_ms per token
    ms_per_tok_c = avg_ms_c / avg_tok_c if avg_tok_c > 0 else 0
    ms_per_tok_w = avg_ms_w / avg_tok_w if avg_tok_w > 0 else 0
    print(f"\n  ms/token correct: {ms_per_tok_c:.1f}")
    print(f"  ms/token wrong:   {ms_per_tok_w:.1f}")
    print(f"  Delta:            {ms_per_tok_w - ms_per_tok_c:+.1f} ms/token")

    # Show individual data points
    print(f"\n  Individual short responses:")
    for r in short:
        mark = "✓" if r["is_correct"] else "✗"
        print(f"    {mark} {r['timing']['tokens_per_sec']:5.1f} tok/s | "
              f"{r['timing']['eval_tokens']}tok {r['timing']['eval_ms']:6.1f}ms | "
              f"{r['question'][:45]}")


def main():
    result_dir = os.path.join(os.path.dirname(__file__), "results")
    for path in sorted(glob.glob(os.path.join(result_dir, "fluency_*.json"))):
        data = load_results(path)
        analyze_short_only(data, max_tokens=5)
    print()

if __name__ == "__main__":
    main()
