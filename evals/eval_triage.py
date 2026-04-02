"""
Node 1 Eval — Triage Router Accuracy Measurement

Compares Claude's classifications against human-labeled ground truth.
Produces: accuracy, per-type precision/recall, and a confusion matrix.

Usage:
    python evals/eval_triage.py

Prerequisites:
    1. Run triage router: data/triage_full_results.json must exist
    2. Human labels: evals/ground_truth_feb2026.json must be filled in
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def run_eval():
    # Load data
    predictions_path = "data/triage_full_results.json"
    ground_truth_path = "evals/ground_truth_feb2026.json"

    if not Path(predictions_path).exists():
        print("❌ Missing predictions. Run the triage router first.")
        return
    if not Path(ground_truth_path).exists():
        print("❌ Missing ground truth. Create evals/ground_truth_feb2026.json")
        return

    predictions = load_json(predictions_path)
    ground_truth = load_json(ground_truth_path)

    # Check for empty labels
    unlabeled = [g for g in ground_truth if not g.get("ground_truth")]
    if unlabeled:
        print(f"❌ {len(unlabeled)} pages have no ground_truth label.")
        print(f"   Open evals/ground_truth_feb2026.json and fill in all labels.")
        print(f"   Valid types: invoice, invoice_list, bank_statement, homeowner_ledger,")
        print(f"   homeowner_aging, balance_sheet, income_statement, general_ledger,")
        print(f"   bank_account_list, insurance_compliance, boilerplate")
        return

    # Build lookup
    gt_by_page = {g["page_number"]: g["ground_truth"] for g in ground_truth}
    pred_by_page = {p["page_number"]: p["page_type"] for p in predictions}

    # Compare
    correct = 0
    wrong = []
    all_types = set()

    for page_num in sorted(gt_by_page.keys()):
        expected = gt_by_page[page_num]
        predicted = pred_by_page.get(page_num, "MISSING")
        all_types.add(expected)
        all_types.add(predicted)

        if expected == predicted:
            correct += 1
        else:
            wrong.append({
                "page": page_num,
                "expected": expected,
                "predicted": predicted,
            })

    total = len(gt_by_page)
    accuracy = correct / total

    # ── Results ──
    print("=" * 70)
    print("📊 Node 1 Triage Router — Eval Results")
    print(f"   Document: Briarwyck Monthly Financials Feb 2026 (53 pages)")
    print("=" * 70)

    print(f"\n🎯 Overall Accuracy: {correct}/{total} = {accuracy:.1%}")

    if wrong:
        print(f"\n❌ Misclassified Pages ({len(wrong)}):")
        print(f"   {'Page':>4s}  {'Expected':<25s}  {'Predicted':<25s}")
        print(f"   {'----':>4s}  {'--------':<25s}  {'---------':<25s}")
        for w in wrong:
            print(f"   {w['page']:4d}  {w['expected']:<25s}  {w['predicted']:<25s}")
    else:
        print("\n✅ Zero misclassifications!")

    # ── Per-type precision & recall ──
    print(f"\n📋 Per-Type Metrics:")
    print(f"   {'Type':<25s}  {'Precision':>9s}  {'Recall':>9s}  {'Count':>5s}")
    print(f"   {'-'*25}  {'-'*9}  {'-'*9}  {'-'*5}")

    for ptype in sorted(all_types):
        if ptype == "MISSING":
            continue
        true_positives = sum(
            1 for p in gt_by_page
            if gt_by_page[p] == ptype and pred_by_page.get(p) == ptype
        )
        predicted_as = sum(1 for p in pred_by_page if pred_by_page[p] == ptype)
        actually_is = sum(1 for p in gt_by_page if gt_by_page[p] == ptype)

        precision = true_positives / predicted_as if predicted_as > 0 else 0
        recall = true_positives / actually_is if actually_is > 0 else 0

        print(f"   {ptype:<25s}  {precision:>8.0%}  {recall:>8.0%}  {actually_is:>5d}")

    # ── Confusion Matrix ──
    types_list = sorted(all_types - {"MISSING"})
    print(f"\n🔀 Confusion Matrix (rows=actual, cols=predicted):")
    header = "   " + f"{'':>15s}" + "".join(f"{t[:8]:>10s}" for t in types_list)
    print(header)

    for actual in types_list:
        row = f"   {actual[:15]:>15s}"
        for predicted in types_list:
            count = sum(
                1 for p in gt_by_page
                if gt_by_page[p] == actual and pred_by_page.get(p) == predicted
            )
            cell = f"{count:>10d}" if count > 0 else f"{'·':>10s}"
            row += cell
        print(row)

    # ── Save results ──
    eval_result = {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "misclassifications": wrong,
    }
    output_path = "evals/eval_triage_results.json"
    with open(output_path, "w") as f:
        json.dump(eval_result, f, indent=2)
    print(f"\n💾 Results saved to {output_path}")

    print("\n" + "=" * 70)
    if accuracy >= 0.95:
        print("✅ PASS — Ready to proceed to Node 2")
    elif accuracy >= 0.85:
        print("⚠️  MARGINAL — Fix misclassifications before Node 2")
    else:
        print("❌ FAIL — Rewrite triage prompt and re-run before Node 2")
    print("=" * 70)


if __name__ == "__main__":
    run_eval()
