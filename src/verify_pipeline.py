"""
Staged Pipeline Verification — Gate Checks at Every Node

Runs each node of the audit pipeline ONE AT A TIME with explicit
verification checks between each stage. Does NOT proceed to the
next stage unless ALL checks pass.

This is our "trust but verify" approach — Deterministic Stewardship.

Usage:
    python -m src.verify_pipeline                    # Run all stages
    python -m src.verify_pipeline --stage triage     # Run just triage + check
    python -m src.verify_pipeline --stage bank       # Run just bank extractor + check
    python -m src.verify_pipeline --stage all        # Full pipeline end-to-end
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════════
# Logger — real-time pipeline visibility
# ══════════════════════════════════════════════════════════════════════

class PipelineLogger:
    """Rich console logger for pipeline progress tracking."""

    STAGES = [
        ("1",  "TRIAGE ROUTER",           "🔀", "LLM"),
        ("2a", "INVOICE LIST EXTRACTOR",  "📋", "LLM"),
        ("2b", "BANK STATEMENT EXTRACTOR","🏦", "Deterministic"),
        ("2c", "HOMEOWNER LEDGER",        "👤", "Deterministic"),
        ("3",  "DETERMINISTIC AUDITOR",   "🔍", "Deterministic"),
    ]

    def __init__(self):
        self.total_checks = 0
        self.total_passed = 0
        self.total_failed = 0
        self.stage_results = []  # list of (stage_name, passed, total, elapsed)
        self.pipeline_start = time.time()

    def banner(self, pdf_name: str):
        """Print the opening banner."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   🔬  HOA AUDIT — STAGED PIPELINE VERIFICATION                      ║
║                                                                      ║
║   Every node runs. Every output verified. Nothing proceeds           ║
║   until the gate check passes with 100% confidence.                  ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║   📄 Document:  {pdf_name:<50s}  ║
║   🕐 Started:   {now:<50s}  ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║   Pipeline Stages:                                                   ║
║   ┌─────┬──────────────────────────────┬─────────────────┬────────┐  ║
║   │  #  │ Stage                        │ Engine          │ Status │  ║
║   ├─────┼──────────────────────────────┼─────────────────┼────────┤  ║""")
        for num, name, icon, engine in self.STAGES:
            print(f"║   │ {num:<3s} │ {icon} {name:<26s} │ {engine:<15s} │   ⏳   │  ║")
        print(f"""║   └─────┴──────────────────────────────┴─────────────────┴────────┘  ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    def stage_start(self, stage_num: str, stage_name: str, icon: str, detail: str = ""):
        """Announce a stage is starting."""
        elapsed = time.time() - self.pipeline_start
        print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│  {icon}  STAGE {stage_num}: {stage_name:<47s}  │
│  {'─'*66}  │
│  ⏱️  Pipeline clock: {elapsed:>6.1f}s{' ' * 50} │""")
        if detail:
            print(f"│  📍 {detail:<63s}  │")
        print(f"└──────────────────────────────────────────────────────────────────────┘")

    def progress(self, msg: str):
        """Log a progress message within a stage."""
        print(f"  │  {msg}")

    def item(self, label: str, value: str, indent: int = 1):
        """Log a single data item."""
        pad = "  " * indent
        print(f"  │{pad}  {label:<30s}  {value}")

    def sub_header(self, msg: str):
        """Log a sub-section header."""
        print(f"  │")
        print(f"  │  ── {msg} {'─' * max(0, 55 - len(msg))}")

    def data_row(self, label: str, amount: str, extra: str = ""):
        """Log a financial data row."""
        if extra:
            print(f"  │    {label:<35s} {amount:>12s}  {extra}")
        else:
            print(f"  │    {label:<35s} {amount:>12s}")

    def check_result(self, check_num: int, total: int, check: 'Check'):
        """Log a single check result as it happens."""
        status = "✅" if check.passed else "❌"
        pct = (check_num / total) * 100
        bar_filled = int(check_num / total * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        print(f"  │")
        print(f"  │  [{bar}] Check {check_num}/{total} ({pct:.0f}%)")
        print(f"  │  {status}  {check.name}")
        print(f"  │       Expected: {check.expected}")
        print(f"  │       Actual:   {check.actual}")
        if check.detail:
            print(f"  │       Detail:   {check.detail}")

        if check.passed:
            self.total_passed += 1
        else:
            self.total_failed += 1
        self.total_checks += 1

    def gate_verdict(self, stage_name: str, checks: list['Check'], elapsed: float):
        """Print the gate pass/fail verdict for a stage."""
        passed = sum(1 for c in checks if c.passed)
        total = len(checks)
        all_pass = passed == total

        self.stage_results.append((stage_name, passed, total, elapsed))

        if all_pass:
            print(f"""  │
  ├──────────────────────────────────────────────────────────────────┐
  │  ✅ GATE PASSED  │  {passed}/{total} checks  │  {elapsed:.1f}s  │  Score: {passed}/{total}  │
  │  ✅ {stage_name} verified — proceeding to next stage            │
  └──────────────────────────────────────────────────────────────────┘""")
        else:
            failed = total - passed
            print(f"""  │
  ├──────────────────────────────────────────────────────────────────┐
  │  ❌ GATE FAILED  │  {passed}/{total} checks  │  {elapsed:.1f}s  │  {failed} FAILED   │
  │  ⛔ PIPELINE HALTED — fix failures before proceeding            │
  └──────────────────────────────────────────────────────────────────┘""")

    def running_scorecard(self):
        """Print the running scorecard after each stage."""
        if not self.stage_results:
            return

        elapsed = time.time() - self.pipeline_start
        print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │  📊 RUNNING SCORECARD                    ⏱️ {elapsed:>6.1f}s elapsed     │
  ├────────────────────────────────────┬────────┬───────┬──────────┤
  │  Stage                             │ Checks │ Time  │  Status  │
  ├────────────────────────────────────┼────────┼───────┼──────────┤""")
        for name, passed, total, t in self.stage_results:
            status = "✅ PASS" if passed == total else "❌ FAIL"
            print(f"  │  {name:<34s} │ {passed:>2d}/{total:<2d}  │ {t:>4.1f}s │ {status:<8s} │")

        # Show remaining stages
        completed_names = {r[0] for r in self.stage_results}
        for num, name, icon, engine in self.STAGES:
            if name not in completed_names:
                print(f"  │  {name:<34s} │  ──   │  ──   │   ⏳     │")

        pct = (self.total_passed / max(self.total_checks, 1)) * 100
        print(f"""  ├────────────────────────────────────┼────────┼───────┼──────────┤
  │  TOTAL                              │ {self.total_passed:>2d}/{self.total_checks:<2d}  │ {elapsed:>4.1f}s │ {pct:>5.1f}%   │
  └────────────────────────────────────┴────────┴───────┴──────────┘
""")

    def final_report(self):
        """Print the final verification report."""
        elapsed = time.time() - self.pipeline_start
        all_pass = self.total_failed == 0 and self.total_checks > 0
        pct = (self.total_passed / max(self.total_checks, 1)) * 100

        if all_pass:
            print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   🎯  VERIFICATION COMPLETE — 100% CONFIDENCE                       ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║   Total Checks:    {self.total_passed:>3d} / {self.total_checks:<3d}  ✅ ALL PASSED                       ║
║   Total Time:      {elapsed:>6.1f}s                                          ║
║   Confidence:      {pct:>5.1f}%                                            ║
║                                                                      ║
║   Pipeline Breakdown:                                                ║""")
        else:
            print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ⛔  VERIFICATION INCOMPLETE — {self.total_failed} CHECK(S) FAILED                 ║
║                                                                      ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║   Total Checks:    {self.total_passed:>3d} / {self.total_checks:<3d}  ({self.total_failed} FAILED)                        ║
║   Total Time:      {elapsed:>6.1f}s                                          ║
║   Confidence:      {pct:>5.1f}%                                            ║
║                                                                      ║
║   Pipeline Breakdown:                                                ║""")

        for name, passed, total, t in self.stage_results:
            status = "✅" if passed == total else "❌"
            print(f"║   {status}  {name:<30s}  {passed}/{total} checks  ({t:.1f}s)           ║")

        if all_pass:
            print(f"""║                                                                      ║
║   ✅ All extraction verified against known-good values               ║
║   ✅ All reconciliation checks produce expected results              ║
║   ✅ Pipeline is safe to run: python -m src.graph --approve          ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")
        else:
            print(f"""║                                                                      ║
║   ⛔ Fix the failing checks before running the pipeline              ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


# Global logger instance
log = PipelineLogger()


# ══════════════════════════════════════════════════════════════════════
# Verification Framework
# ══════════════════════════════════════════════════════════════════════

@dataclass
class Check:
    name: str
    expected: str
    actual: str
    passed: bool
    detail: str = ""


@dataclass
class GateResult:
    stage: str
    checks: list[Check] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)


# ══════════════════════════════════════════════════════════════════════
# Known-good values for Feb 2026 (from verified manual extraction)
# ══════════════════════════════════════════════════════════════════════

KNOWN_FEB_2026 = {
    # Triage
    "total_pages": 53,
    "page_types": {
        "boilerplate": [1, 17, 18, 19, 21, 22, 23, 40, 42],
        "invoice": [27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 43, 44],
        "bank_statement": [14, 15, 16, 20, 24, 25, 26],
        "homeowner_ledger": [47, 48, 49, 50, 51, 52, 53],
        "homeowner_aging": [9, 10, 11, 12, 13],
        "invoice_list": [7, 8],
        "income_statement": [4, 5, 6],
        "balance_sheet": [2],
        "general_ledger": [45, 46],
        "bank_account_list": [3],
        "insurance_compliance": [39, 41],
    },

    # Bank Statement (from PDF Account Summary — absolute truth)
    "bank_operating_credits": 13262.54,
    "bank_operating_debits": 11957.74,
    "bank_reserve_credits": 303.61,
    "bank_operating_txn_count": 45,  # 30 credits + 15 debits
    "bank_reserve_txn_count": 2,

    # Invoice List
    "invoice_count": 9,
    "invoice_total": 9966.13,
    "invoice_vendors": [
        "Ambit Texas, LLC",
        "AmTrust Financial",
        "City of Carrollton",
        "Five Star Aquatics, LLC",
        "Granite Landscape & Maintenance, Inc.",
        "Manning & Meyers",
        "Neon Monkey LLC",
        "PMI Cross Timbers - Mgmt Mod Only",
        "Reliant",
    ],

    # Homeowner Ledger (from Association Totals — absolute truth)
    "homeowner_count": 52,
    "association_ending_balance": -4458.58,  # From Association Totals row
    "homeowner_formula_balanced": 44,
    "homeowner_prepaid_carryforward": 8,
    "homeowner_formula_failed": 0,

    # Audit results
    "reserve_xfer_amount": 279.17,
    "rejected_check_count": 2,
    "unapproved_check_count": 2,
    "unapproved_check_total": 2457.00,
}


# ══════════════════════════════════════════════════════════════════════
# Stage 1: Triage Verification
# ══════════════════════════════════════════════════════════════════════

def verify_triage(pdf_path: str) -> GateResult:
    """Run triage and verify against ground truth."""
    from src.agents.triage_router import classify_document

    log.stage_start("1", "TRIAGE ROUTER", "🔀",
                     f"Classifying {KNOWN_FEB_2026['total_pages']} pages via Claude API")

    start = time.time()

    log.sub_header("Sending pages to LLM for classification")
    results = classify_document(pdf_path)
    elapsed_classify = time.time() - start
    log.progress(f"✓ {len(results)} pages classified in {elapsed_classify:.1f}s")

    # Load ground truth
    gt_path = Path("evals/ground_truth_feb2026.json")
    ground_truth = {}
    if gt_path.exists():
        gt_data = json.load(open(gt_path, encoding="utf-8"))
        ground_truth = {item["page_number"]: item["ground_truth"] for item in gt_data}
        log.progress(f"✓ Ground truth loaded: {len(ground_truth)} pages")

    # Build routing map
    routing = {}
    for r in results:
        ptype = r.page_type.value
        if ptype not in routing:
            routing[ptype] = []
        routing[ptype].append(r.page_number)

    log.sub_header("Routing Map")
    for ptype, pages in sorted(routing.items()):
        log.data_row(ptype, f"{len(pages)} pages", f"→ {pages}")

    # Confidence distribution
    log.sub_header("Confidence Distribution")
    high = sum(1 for r in results if r.confidence >= 0.95)
    med = sum(1 for r in results if 0.80 <= r.confidence < 0.95)
    low = sum(1 for r in results if r.confidence < 0.80)
    log.data_row("≥ 95% confidence", str(high), "█" * high)
    log.data_row("80-94% confidence", str(med), "▓" * med)
    log.data_row("< 80% confidence", str(low), "░" * low if low else "✓ None")

    gate = GateResult(stage="TRIAGE ROUTER", data={
        "results": [r.model_dump(mode="json") for r in results],
        "routing": routing,
    })

    log.sub_header("Running Gate Checks")

    # Check 1
    c = Check("Total pages classified",
              str(KNOWN_FEB_2026["total_pages"]),
              str(len(results)),
              len(results) == KNOWN_FEB_2026["total_pages"])
    gate.checks.append(c)
    log.check_result(1, 8, c)

    # Check 2
    page_nums = sorted(r.page_number for r in results)
    expected_nums = list(range(1, KNOWN_FEB_2026["total_pages"] + 1))
    c = Check("No gaps in page numbers",
              f"1 to {KNOWN_FEB_2026['total_pages']} continuous",
              f"{page_nums[0]} to {page_nums[-1]}, {len(page_nums)} pages",
              page_nums == expected_nums)
    gate.checks.append(c)
    log.check_result(2, 8, c)

    # Check 3
    if ground_truth:
        correct = 0
        mismatches = []
        for r in results:
            gt = ground_truth.get(r.page_number)
            if gt and r.page_type.value == gt:
                correct += 1
            elif gt:
                mismatches.append(f"pg{r.page_number}: got={r.page_type.value} expected={gt}")
        accuracy = correct / len(ground_truth) if ground_truth else 0
        c = Check("Ground truth accuracy",
                  "100%",
                  f"{accuracy:.1%} ({correct}/{len(ground_truth)})",
                  accuracy == 1.0,
                  f"Mismatches: {mismatches}" if mismatches else "All match")
        gate.checks.append(c)
        log.check_result(3, 8, c)

    # Check 4
    expected_types = set(KNOWN_FEB_2026["page_types"].keys())
    actual_types = set(routing.keys())
    c = Check("All 11 page types detected",
              f"{len(expected_types)} types",
              f"{len(actual_types)} types",
              expected_types == actual_types,
              f"Missing: {expected_types - actual_types}" if expected_types != actual_types else "")
    gate.checks.append(c)
    log.check_result(4, 8, c)

    # Check 5
    low_conf = [r for r in results if r.confidence < 0.8]
    c = Check("All classifications >= 80% confidence",
              "0 low-confidence pages",
              f"{len(low_conf)} low-confidence",
              len(low_conf) == 0,
              f"Low: {[(r.page_number, r.page_type.value, r.confidence) for r in low_conf]}" if low_conf else "")
    gate.checks.append(c)
    log.check_result(5, 8, c)

    # Checks 6-8: Critical page type counts
    check_num = 6
    for ptype, expected_pages in [
        ("bank_statement", KNOWN_FEB_2026["page_types"]["bank_statement"]),
        ("homeowner_ledger", KNOWN_FEB_2026["page_types"]["homeowner_ledger"]),
        ("invoice_list", KNOWN_FEB_2026["page_types"]["invoice_list"]),
    ]:
        actual_pages = routing.get(ptype, [])
        c = Check(f"{ptype} page count",
                  f"{len(expected_pages)} pages: {expected_pages}",
                  f"{len(actual_pages)} pages: {actual_pages}",
                  sorted(actual_pages) == sorted(expected_pages))
        gate.checks.append(c)
        log.check_result(check_num, 8, c)
        check_num += 1

    elapsed = time.time() - start
    log.gate_verdict("TRIAGE ROUTER", gate.checks, elapsed)
    return gate


# ══════════════════════════════════════════════════════════════════════
# Stage 2a: Invoice Extractor Verification
# ══════════════════════════════════════════════════════════════════════

def verify_invoices(pdf_path: str, routing: dict) -> GateResult:
    """Extract invoices and verify against known values."""
    from src.agents.invoice_list_extractor import InvoiceListExtraction, EXTRACTION_PROMPT
    from src.utils.pdf_reader import extract_pages
    from src.config import get_llm
    from langchain_core.messages import SystemMessage, HumanMessage

    invoice_pages = routing.get("invoice_list", [])

    log.stage_start("2a", "INVOICE LIST EXTRACTOR", "📋",
                     f"Extracting from {len(invoice_pages)} pages: {invoice_pages}")

    start = time.time()
    all_pages = extract_pages(pdf_path)
    pages_to_process = [p for p in all_pages if p.page_number in invoice_pages]

    log.sub_header("Connecting to LLM for structured extraction")
    model = get_llm()
    structured = model.with_structured_output(InvoiceListExtraction)
    log.progress("✓ LLM ready with structured output schema")

    all_items = []
    log.sub_header("Extracting Vendor Invoices")
    for page in pages_to_process:
        log.progress(f"Processing page {page.page_number}...")
        result = structured.invoke([
            SystemMessage(content=EXTRACTION_PROMPT),
            HumanMessage(content=f"Page {page.page_number} of {page.total_pages}:\n\n{page.text}"),
        ])
        for item in result.items:
            item.source_page = page.page_number
            all_items.append(item.model_dump(mode="json"))
            log.data_row(
                item.vendor_name,
                f"${item.amount:>10,.2f}",
                f"{item.gl_account_code} ({item.gl_account_name})"
            )

    elapsed_extract = time.time() - start
    total_amount = sum(item["amount"] for item in all_items)
    vendor_names = sorted(item["vendor_name"] for item in all_items)

    log.sub_header("Extraction Summary")
    log.data_row("Total vendors", str(len(all_items)))
    log.data_row("Total amount", f"${total_amount:,.2f}")
    log.data_row("Extraction time", f"{elapsed_extract:.1f}s")

    gate = GateResult(stage="INVOICE LIST EXTRACTOR", data={"items": all_items})

    log.sub_header("Running Gate Checks")
    total_checks = 5

    # Check 1
    c = Check("Invoice count",
              str(KNOWN_FEB_2026["invoice_count"]),
              str(len(all_items)),
              len(all_items) == KNOWN_FEB_2026["invoice_count"])
    gate.checks.append(c)
    log.check_result(1, total_checks, c)

    # Check 2
    c = Check("Total invoice amount",
              f"${KNOWN_FEB_2026['invoice_total']:,.2f}",
              f"${total_amount:,.2f}",
              abs(total_amount - KNOWN_FEB_2026["invoice_total"]) < 0.01)
    gate.checks.append(c)
    log.check_result(2, total_checks, c)

    # Check 3
    expected_vendors = sorted(KNOWN_FEB_2026["invoice_vendors"])
    c = Check("All vendors extracted",
              f"{len(expected_vendors)} vendors",
              f"{len(vendor_names)} vendors",
              vendor_names == expected_vendors,
              f"Missing: {set(expected_vendors) - set(vendor_names)}" if vendor_names != expected_vendors else "")
    gate.checks.append(c)
    log.check_result(3, total_checks, c)

    # Check 4
    missing_fields = []
    for item in all_items:
        for fld in ["vendor_name", "amount", "gl_account_code", "payment_type"]:
            if not item.get(fld):
                missing_fields.append(f"{item['vendor_name']}.{fld}")
    c = Check("All required fields populated",
              "0 missing fields",
              f"{len(missing_fields)} missing",
              len(missing_fields) == 0,
              str(missing_fields) if missing_fields else "")
    gate.checks.append(c)
    log.check_result(4, total_checks, c)

    # Check 5
    bad_dates = []
    for item in all_items:
        pd = item.get("paid_date", "")
        if pd and not pd.startswith("2026-02"):
            bad_dates.append(f"{item['vendor_name']}: {pd}")
    c = Check("All paid dates in Feb 2026",
              "0 out-of-range dates",
              f"{len(bad_dates)} issues",
              len(bad_dates) == 0,
              str(bad_dates) if bad_dates else "All correct")
    gate.checks.append(c)
    log.check_result(5, total_checks, c)

    elapsed = time.time() - start
    log.gate_verdict("INVOICE LIST EXTRACTOR", gate.checks, elapsed)
    return gate


# ══════════════════════════════════════════════════════════════════════
# Stage 2b: Bank Statement Extractor Verification
# ══════════════════════════════════════════════════════════════════════

def verify_bank(pdf_path: str, routing: dict) -> GateResult:
    """Extract bank transactions and verify against PDF Account Summary."""
    from src.agents.bank_statement_extractor import parse_bank_page
    from src.utils.pdf_reader import extract_pages

    bank_pages = routing.get("bank_statement", [])

    log.stage_start("2b", "BANK STATEMENT EXTRACTOR", "🏦",
                     f"Deterministic regex parsing — {len(bank_pages)} pages: {bank_pages}")

    start = time.time()
    all_pages = extract_pages(pdf_path)
    all_txns = []

    log.sub_header("Parsing Bank Statement Pages")
    for page in all_pages:
        if page.page_number not in bank_pages:
            continue

        text_upper = page.text.upper()
        if "BANK ACCOUNT RECONCILIATION" in text_upper:
            log.progress(f"Page {page.page_number}: skipping (reconciliation page)")
            continue
        if "THIS PAGE LEFT INTENTIONALLY BLANK" in text_upper:
            log.progress(f"Page {page.page_number}: skipping (blank page)")
            continue

        # Determine account type from header only
        header_lines = page.text.split('\n')[:15]
        header_text = '\n'.join(header_lines)
        if "8766" in header_text or "RESERVE" in header_text.upper():
            account_type, account_last4 = "reserve", "8766"
        else:
            account_type, account_last4 = "operating", "8763"

        log.progress(f"Page {page.page_number} → {account_type.upper()} (***{account_last4})")

        txns = parse_bank_page(page.text, page.page_number, account_type, account_last4)
        all_txns.extend(txns)

        credits_on_page = sum(t["amount"] for t in txns if t["transaction_type"] == "credit")
        debits_on_page = sum(t["amount"] for t in txns if t["transaction_type"] == "debit")
        log.data_row(
            f"  {len(txns)} transactions",
            f"+${credits_on_page:,.2f}" if credits_on_page else "",
            f"-${debits_on_page:,.2f}" if debits_on_page else ""
        )

    elapsed_parse = time.time() - start

    # Compute totals
    op = [t for t in all_txns if t["account_type"] == "operating"]
    res = [t for t in all_txns if t["account_type"] == "reserve"]
    op_credits = sum(t["amount"] for t in op if t["transaction_type"] == "credit")
    op_debits = sum(t["amount"] for t in op if t["transaction_type"] == "debit")
    res_credits = sum(t["amount"] for t in res if t["transaction_type"] == "credit")

    log.sub_header("Extraction Summary")
    log.data_row("Total transactions", str(len(all_txns)))
    log.data_row("Operating credits", f"${op_credits:,.2f}", f"(PDF says: ${KNOWN_FEB_2026['bank_operating_credits']:,.2f})")
    log.data_row("Operating debits", f"${op_debits:,.2f}", f"(PDF says: ${KNOWN_FEB_2026['bank_operating_debits']:,.2f})")
    log.data_row("Reserve credits", f"${res_credits:,.2f}", f"(PDF says: ${KNOWN_FEB_2026['bank_reserve_credits']:,.2f})")
    log.data_row("Net cash flow", f"${op_credits - op_debits:+,.2f}")
    log.data_row("Parse time", f"{elapsed_parse:.2f}s", "⚡ No API calls")

    gate = GateResult(stage="BANK STATEMENT EXTRACTOR", data={"transactions": all_txns})

    log.sub_header("Running Gate Checks")
    total_checks = 7

    c = Check("Operating credits total (vs PDF Account Summary)",
              f"${KNOWN_FEB_2026['bank_operating_credits']:,.2f}",
              f"${op_credits:,.2f}",
              abs(op_credits - KNOWN_FEB_2026["bank_operating_credits"]) < 0.01)
    gate.checks.append(c)
    log.check_result(1, total_checks, c)

    c = Check("Operating debits total (vs PDF Account Summary)",
              f"${KNOWN_FEB_2026['bank_operating_debits']:,.2f}",
              f"${op_debits:,.2f}",
              abs(op_debits - KNOWN_FEB_2026["bank_operating_debits"]) < 0.01)
    gate.checks.append(c)
    log.check_result(2, total_checks, c)

    c = Check("Reserve credits total (vs PDF Account Summary)",
              f"${KNOWN_FEB_2026['bank_reserve_credits']:,.2f}",
              f"${res_credits:,.2f}",
              abs(res_credits - KNOWN_FEB_2026["bank_reserve_credits"]) < 0.01)
    gate.checks.append(c)
    log.check_result(3, total_checks, c)

    bad_dates = [t for t in all_txns if not t["transaction_date"].startswith("2026-02")]
    c = Check("All transaction dates in Feb 2026",
              "0 out-of-range dates",
              f"{len(bad_dates)} out-of-range",
              len(bad_dates) == 0,
              str([(t["transaction_date"], t["description"]) for t in bad_dates]) if bad_dates else "")
    gate.checks.append(c)
    log.check_result(4, total_checks, c)

    neg = [t for t in all_txns if t["amount"] <= 0]
    c = Check("All amounts positive",
              "0 negative/zero amounts",
              f"{len(neg)} invalid",
              len(neg) == 0)
    gate.checks.append(c)
    log.check_result(5, total_checks, c)

    rejected = [t for t in all_txns if "REJECTED" in t["description"].upper()]
    c = Check("Rejected checks detected",
              f"{KNOWN_FEB_2026['rejected_check_count']} rejected checks",
              f"{len(rejected)} rejected checks",
              len(rejected) == KNOWN_FEB_2026["rejected_check_count"])
    gate.checks.append(c)
    log.check_result(6, total_checks, c)

    xfers = [t for t in all_txns if "CINCXFER" in t["description"].upper()]
    c = Check("CincXfer reserve transfer detected",
              f"Transfer amount: ${KNOWN_FEB_2026['reserve_xfer_amount']:,.2f}",
              f"{len(xfers)} transfers: {[t['amount'] for t in xfers]}",
              len(xfers) == 2 and all(abs(t["amount"] - KNOWN_FEB_2026["reserve_xfer_amount"]) < 0.01 for t in xfers))
    gate.checks.append(c)
    log.check_result(7, total_checks, c)

    elapsed = time.time() - start
    log.gate_verdict("BANK STATEMENT EXTRACTOR", gate.checks, elapsed)
    return gate


# ══════════════════════════════════════════════════════════════════════
# Stage 2c: Homeowner Ledger Extractor Verification
# ══════════════════════════════════════════════════════════════════════

def verify_ledger(pdf_path: str, routing: dict) -> GateResult:
    """Extract homeowner ledger and verify against Association Totals."""
    from src.agents.homeowner_ledger_extractor import parse_ledger_pages, to_json_records
    from src.utils.pdf_reader import extract_pages

    ledger_pages = routing.get("homeowner_ledger", [])

    log.stage_start("2c", "HOMEOWNER LEDGER EXTRACTOR", "👤",
                     f"Deterministic parsing — {len(ledger_pages)} pages: {ledger_pages}")

    start = time.time()
    all_pages = extract_pages(pdf_path)
    pages_to_process = [p for p in all_pages if p.page_number in ledger_pages]

    log.sub_header("Parsing Homeowner Accounts")
    homeowners, association_totals = parse_ledger_pages(pages_to_process)
    records = to_json_records(homeowners)
    elapsed_parse = time.time() - start

    # Show data overview
    total_ending = round(sum(r["ending_balance"] for r in records), 2)
    owners_with_balance = sum(1 for r in records if r["ending_balance"] > 0)
    owners_prepaid = sum(1 for r in records if r["ending_balance"] < 0)
    owners_zero = sum(1 for r in records if r["ending_balance"] == 0)

    log.data_row("Total homeowner accounts", str(len(records)))
    log.data_row("With balance due", str(owners_with_balance), "⚠️" if owners_with_balance > 0 else "")
    log.data_row("Prepaid (credit)", str(owners_prepaid), "💰")
    log.data_row("Current ($0.00)", str(owners_zero), "✅")

    log.sub_header("Financial Summary")
    log.data_row("Total ending balance", f"${total_ending:,.2f}")
    log.data_row("Total billing", f"${sum(r['billing'] for r in records):,.2f}")
    log.data_row("Total receipts", f"${sum(r['receipts'] for r in records):,.2f}")
    if association_totals:
        log.data_row("Association Totals (PDF)", f"${association_totals['ending_balance']:,.2f}",
                     "← checksum target")

    log.sub_header("Top Balances Due")
    top_owed = sorted([r for r in records if r["ending_balance"] > 0],
                      key=lambda x: -x["ending_balance"])[:5]
    for r in top_owed:
        log.data_row(f"  {r['unit_id']} {r['homeowner_name'][:25]}",
                     f"${r['ending_balance']:,.2f}", "⚠️")

    gate = GateResult(stage="HOMEOWNER LEDGER EXTRACTOR", data={
        "records": records, "association_totals": association_totals,
    })

    log.sub_header("Running Gate Checks")
    total_checks = 6

    c = Check("Homeowner account count",
              str(KNOWN_FEB_2026["homeowner_count"]),
              str(len(records)),
              len(records) == KNOWN_FEB_2026["homeowner_count"])
    gate.checks.append(c)
    log.check_result(1, total_checks, c)

    if association_totals:
        assoc_ending = association_totals["ending_balance"]
        c = Check("Ending balance vs Association Totals (checksum)",
                  f"Match Association Totals (${assoc_ending:,.2f})",
                  f"${total_ending:,.2f}",
                  abs(total_ending - assoc_ending) < 0.01)
        gate.checks.append(c)
        log.check_result(2, total_checks, c)
    else:
        c = Check("Association Totals found",
                  "Present",
                  "NOT FOUND",
                  False)
        gate.checks.append(c)
        log.check_result(2, total_checks, c)

    # Per-homeowner formula
    balanced = 0
    carryforward_count = 0
    failed = 0
    for hw in homeowners:
        t = hw.get("totals")
        if not t:
            failed += 1
            continue
        computed = round(t["prev_balance"] + t["billing"] + t["receipts"] + t["adjustments"] + t["prepaid"], 2)
        if abs(t["ending_balance"] - computed) < 0.01:
            balanced += 1
        elif hw.get("has_prepaid_carryforward"):
            carryforward_count += 1
        else:
            failed += 1

    c = Check("Per-homeowner formula balanced",
              f"{KNOWN_FEB_2026['homeowner_formula_balanced']} balanced",
              f"{balanced} balanced",
              balanced == KNOWN_FEB_2026["homeowner_formula_balanced"])
    gate.checks.append(c)
    log.check_result(3, total_checks, c)

    c = Check("PrePaid carryforward accounts",
              f"{KNOWN_FEB_2026['homeowner_prepaid_carryforward']} carryforward",
              f"{carryforward_count} carryforward",
              carryforward_count == KNOWN_FEB_2026["homeowner_prepaid_carryforward"])
    gate.checks.append(c)
    log.check_result(4, total_checks, c)

    c = Check("Unexplained formula failures",
              f"{KNOWN_FEB_2026['homeowner_formula_failed']} failures",
              f"{failed} failures",
              failed == KNOWN_FEB_2026["homeowner_formula_failed"])
    gate.checks.append(c)
    log.check_result(5, total_checks, c)

    no_totals = [hw["unit_id"] for hw in homeowners if not hw.get("totals")]
    c = Check("All homeowners have Totals row",
              "0 missing",
              f"{len(no_totals)} missing",
              len(no_totals) == 0,
              str(no_totals) if no_totals else "")
    gate.checks.append(c)
    log.check_result(6, total_checks, c)

    elapsed = time.time() - start
    log.gate_verdict("HOMEOWNER LEDGER EXTRACTOR", gate.checks, elapsed)
    return gate


# ══════════════════════════════════════════════════════════════════════
# Stage 3: Audit Verification
# ══════════════════════════════════════════════════════════════════════

def verify_audit(bank_txns: list, invoices: list, ledger: list) -> GateResult:
    """Run the auditor and verify its output."""
    from src.agents.deterministic_auditor import (
        check_deposits_vs_receipts,
        check_withdrawals_vs_invoices,
        check_reserve_transfers,
        check_net_cash_flow,
        check_homeowner_formulas,
        detect_rejected_checks,
        detect_unapproved_checks,
    )

    log.stage_start("3", "DETERMINISTIC AUDITOR", "🔍",
                     f"Pure Python math — {len(bank_txns)} bank txns, "
                     f"{len(invoices)} invoices, {len(ledger)} ledger records")

    start = time.time()

    log.sub_header("Running Reconciliation Checks")

    # Run all checks with progress
    log.progress("► Check 1: Bank deposits vs homeowner receipts...")
    check1 = check_deposits_vs_receipts(bank_txns, ledger)
    log.data_row("Bank deposits", f"${check1.amount_a:,.2f}")
    log.data_row("Homeowner receipts", f"${check1.amount_b:,.2f}")
    log.data_row("Gap", f"${check1.difference:,.2f}", "← known timing gap")

    log.progress("► Check 2: Bank withdrawals vs approved invoices...")
    check2 = check_withdrawals_vs_invoices(bank_txns, invoices)
    log.data_row("Bank withdrawals", f"${check2.amount_a:,.2f}")
    log.data_row("Invoice list total", f"${check2.amount_b:,.2f}")
    log.data_row("Gap", f"${check2.difference:,.2f}", "← unapproved checks")

    log.progress("► Check 3: Reserve transfers...")
    check3 = check_reserve_transfers(bank_txns)
    log.data_row("Operating → Reserve", f"${check3.amount_a:,.2f}")
    log.data_row("Reserve ← Operating", f"${check3.amount_b:,.2f}")
    log.data_row("Difference", f"${check3.difference:,.2f}", "✅ balanced" if check3.passed else "❌")

    log.progress("► Check 4: Net cash flow...")
    check4 = check_net_cash_flow(bank_txns)
    log.data_row("Credits (in)", f"${check4.amount_a:,.2f}")
    log.data_row("Debits (out)", f"${check4.amount_b:,.2f}")
    log.data_row("Net flow", f"${check4.difference:+,.2f}", "📈 positive" if check4.difference > 0 else "📉 negative")

    log.progress("► Homeowner formula verification...")
    hw_results = check_homeowner_formulas(ledger)
    passed_hw = [r for r in hw_results if r.passed]
    carryforward = [r for r in hw_results if r.has_prepaid_carryforward]
    failed_real = [r for r in hw_results if not r.passed and not r.has_prepaid_carryforward]
    log.data_row("Formula balanced", str(len(passed_hw)), "✅")
    log.data_row("PrePaid carryforward", str(len(carryforward)), "ℹ️ expected")
    log.data_row("Truly failed", str(len(failed_real)), "✅" if not failed_real else "❌")

    log.progress("► Red flag detection...")
    rejected = detect_rejected_checks(bank_txns)
    unapproved, pending = detect_unapproved_checks(bank_txns, invoices)

    log.sub_header("Red Flag Summary")
    if rejected:
        for rc in rejected:
            redeposit = "✅ redeposited" if rc["redeposit_found"] else "⚠️ NO REDEPOSIT"
            log.data_row(f"  Rejected: {rc['description'][:40]}", f"${rc['amount']:,.2f}", redeposit)
    if unapproved:
        for u in unapproved:
            log.data_row(f"  🔴 UNAPPROVED: {u['description']}", f"${u['amount']:,.2f}", u['date'])
    if pending:
        for p in pending:
            log.data_row(f"  ⏳ Pending: {p['vendor_name'][:30]}", f"${p['amount']:,.2f}")
    if not rejected and not unapproved and not pending:
        log.progress("  ✅ No red flags detected")

    gate = GateResult(stage="DETERMINISTIC AUDITOR")

    log.sub_header("Running Gate Checks")
    total_checks = 7

    c = Check("Reserve transfers balance (CincXfer out = in)",
              "Difference: $0.00",
              f"Difference: ${check3.difference:,.2f}",
              check3.passed)
    gate.checks.append(c)
    log.check_result(1, total_checks, c)

    c = Check("Operating net cash flow positive",
              "Positive (more in than out)",
              f"${check4.difference:+,.2f}",
              check4.difference > 0)
    gate.checks.append(c)
    log.check_result(2, total_checks, c)

    all_redeposited = all(rc["redeposit_found"] for rc in rejected)
    c = Check("All rejected checks have redeposits",
              f"{KNOWN_FEB_2026['rejected_check_count']} rejected, all redeposited",
              f"{len(rejected)} rejected, all redeposited: {all_redeposited}",
              len(rejected) == KNOWN_FEB_2026["rejected_check_count"] and all_redeposited)
    gate.checks.append(c)
    log.check_result(3, total_checks, c)

    c = Check("Unapproved checks detected",
              f"{KNOWN_FEB_2026['unapproved_check_count']} checks (${KNOWN_FEB_2026['unapproved_check_total']:,.2f})",
              f"{len(unapproved)} checks (${sum(u['amount'] for u in unapproved):,.2f})",
              (len(unapproved) == KNOWN_FEB_2026["unapproved_check_count"]
               and abs(sum(u["amount"] for u in unapproved) - KNOWN_FEB_2026["unapproved_check_total"]) < 0.01))
    gate.checks.append(c)
    log.check_result(4, total_checks, c)

    c = Check("Homeowner formula results",
              f"{KNOWN_FEB_2026['homeowner_formula_balanced']} balanced, "
              f"{KNOWN_FEB_2026['homeowner_prepaid_carryforward']} carryforward, "
              f"{KNOWN_FEB_2026['homeowner_formula_failed']} failed",
              f"{len(passed_hw)} balanced, {len(carryforward)} carryforward, {len(failed_real)} failed",
              (len(passed_hw) == KNOWN_FEB_2026["homeowner_formula_balanced"]
               and len(carryforward) == KNOWN_FEB_2026["homeowner_prepaid_carryforward"]
               and len(failed_real) == KNOWN_FEB_2026["homeowner_formula_failed"]))
    gate.checks.append(c)
    log.check_result(5, total_checks, c)

    c = Check("Deposits vs Receipts gap matches known value",
              f"~$3,609.64 (explained by rejected checks + timing)",
              f"${check1.difference:,.2f}",
              abs(check1.difference - 3609.64) < 1.00)
    gate.checks.append(c)
    log.check_result(6, total_checks, c)

    c = Check("Withdrawals vs Invoices gap matches known value",
              f"~$1,457.00 (unapproved checks - pending Neon Monkey)",
              f"${check2.difference:,.2f}",
              abs(check2.difference - 1457.00) < 1.00)
    gate.checks.append(c)
    log.check_result(7, total_checks, c)

    elapsed = time.time() - start
    log.gate_verdict("DETERMINISTIC AUDITOR", gate.checks, elapsed)
    return gate


# ══════════════════════════════════════════════════════════════════════
# Pipeline Runner
# ══════════════════════════════════════════════════════════════════════

def _load_routing_from_triage() -> dict:
    """Load routing map from saved triage results."""
    triage_data = json.load(open("data/triage_full_results.json", encoding="utf-8"))
    routing = {}
    for item in triage_data:
        ptype = item["page_type"]
        if ptype not in routing:
            routing[ptype] = []
        routing[ptype].append(item["page_number"])
    return routing


def run_staged_verification(pdf_path: str, stage: str = "all"):
    """Run the full staged verification pipeline."""
    global log
    log = PipelineLogger()  # Fresh logger for each run

    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

    log.banner(Path(pdf_path).name)

    all_gates = []

    # ── Stage 1: Triage ──
    if stage in ("all", "triage"):
        gate_triage = verify_triage(pdf_path)
        all_gates.append(gate_triage)
        log.running_scorecard()
        if not gate_triage.all_passed and stage == "all":
            print("  ⛔ PIPELINE HALTED at Stage 1 — Triage failed")
            log.final_report()
            return all_gates
        if stage == "triage":
            log.final_report()
            return all_gates

    routing = gate_triage.data["routing"] if stage == "all" else None

    # ── Stage 2a: Invoices ──
    if stage in ("all", "invoices"):
        if stage == "invoices":
            routing = _load_routing_from_triage()
        gate_invoices = verify_invoices(pdf_path, routing)
        all_gates.append(gate_invoices)
        log.running_scorecard()
        if not gate_invoices.all_passed and stage == "all":
            print("  ⛔ PIPELINE HALTED at Stage 2a — Invoice extraction failed")
            log.final_report()
            return all_gates
        if stage == "invoices":
            log.final_report()
            return all_gates

    # ── Stage 2b: Bank ──
    if stage in ("all", "bank"):
        if stage == "bank":
            routing = _load_routing_from_triage()
        gate_bank = verify_bank(pdf_path, routing)
        all_gates.append(gate_bank)
        log.running_scorecard()
        if not gate_bank.all_passed and stage == "all":
            print("  ⛔ PIPELINE HALTED at Stage 2b — Bank extraction failed")
            log.final_report()
            return all_gates
        if stage == "bank":
            log.final_report()
            return all_gates

    # ── Stage 2c: Ledger ──
    if stage in ("all", "ledger"):
        if stage == "ledger":
            routing = _load_routing_from_triage()
        gate_ledger = verify_ledger(pdf_path, routing)
        all_gates.append(gate_ledger)
        log.running_scorecard()
        if not gate_ledger.all_passed and stage == "all":
            print("  ⛔ PIPELINE HALTED at Stage 2c — Ledger extraction failed")
            log.final_report()
            return all_gates
        if stage == "ledger":
            log.final_report()
            return all_gates

    # ── Stage 3: Audit ──
    if stage in ("all", "audit"):
        if stage == "all":
            bank_txns = gate_bank.data["transactions"]
            invoices = gate_invoices.data["items"]
            ledger = gate_ledger.data["records"]
        else:
            bank_txns = json.load(open("data/extraction_bank_statements.json", encoding="utf-8"))
            invoices = json.load(open("data/extraction_invoice_list.json", encoding="utf-8"))
            ledger = json.load(open("data/extraction_homeowner_ledger.json", encoding="utf-8"))

        gate_audit = verify_audit(bank_txns, invoices, ledger)
        all_gates.append(gate_audit)
        log.running_scorecard()

    log.final_report()
    return all_gates


# ══════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Staged Pipeline Verification")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default="data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf",
    )
    parser.add_argument(
        "--stage",
        choices=["all", "triage", "invoices", "bank", "ledger", "audit"],
        default="all",
        help="Which stage to verify (default: all)",
    )
    args = parser.parse_args()

    run_staged_verification(args.pdf_path, args.stage)
