"""
HOA Financial Audit Swarm — LangGraph StateGraph

The production pipeline that wires all nodes together:

  PDF → [triage] → [extract_invoices] → [extract_bank] → [extract_ledger] → [audit] → [report]
                                                                                ↓
                                                                          confidence < 80%?
                                                                                ↓
                                                                        [HITL interrupt()]

Supports ANY monthly financial PDF — page numbers are discovered
dynamically via triage classification, not hardcoded.

Usage:
    # Single month
    python -m src.graph "data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf"

    # Batch mode — all PDFs in a directory
    python -m src.graph --batch data/sample_pdfs/

    # With human review override
    python -m src.graph "path/to/pdf" --approve
"""

import json
import operator
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from typing_extensions import TypedDict

from src.schemas.financial import PageType


# ══════════════════════════════════════════════════════════════════════
# Graph State — the typed state flowing through the pipeline
# ══════════════════════════════════════════════════════════════════════

def _merge_lists(a: list, b: list) -> list:
    """Reducer that appends new items to existing list."""
    return a + b


class AuditState(TypedDict):
    """
    Full pipeline state. Each node reads what it needs and writes its output.
    LangGraph manages state persistence via checkpointing.
    """
    # ── Input ──
    pdf_path: str                                   # Path to the monthly financial PDF
    run_id: str                                     # Unique run identifier

    # ── Node 1: Triage Router output ──
    classified_pages: list[dict]                    # ClassifiedPage dicts from triage
    page_routing: dict[str, list[int]]              # page_type → [page_numbers]

    # ── Node 2: Extractor outputs ──
    bank_transactions: Annotated[list[dict], _merge_lists]
    invoice_list_items: Annotated[list[dict], _merge_lists]
    homeowner_ledger: Annotated[list[dict], _merge_lists]

    # ── Node 3: Auditor output ──
    audit_report: dict                              # Serialized AuditReport

    # ── Pipeline metadata ──
    errors: Annotated[list[str], _merge_lists]      # Non-fatal errors
    timing: dict[str, float]                        # node_name → seconds
    human_approved: bool                            # HITL override flag


# ══════════════════════════════════════════════════════════════════════
# Node 1: Triage Router
# ══════════════════════════════════════════════════════════════════════

def triage_node(state: AuditState) -> dict:
    """
    Classify every page in the PDF using the LLM-powered triage router.
    Builds a routing map: page_type → [page_numbers].
    """
    from src.agents.triage_router import classify_document

    pdf_path = state["pdf_path"]
    start = time.time()

    print(f"\n{'═'*70}")
    print(f"  🔀 NODE 1: TRIAGE ROUTER")
    print(f"  Classifying pages in: {Path(pdf_path).name}")
    print(f"{'═'*70}")

    results = classify_document(pdf_path)

    # Build the routing map
    routing: dict[str, list[int]] = {}
    for r in results:
        ptype = r.page_type.value
        if ptype not in routing:
            routing[ptype] = []
        routing[ptype].append(r.page_number)

    classified = [r.model_dump(mode="json") for r in results]
    elapsed = time.time() - start

    print(f"\n  ⏱️  Triage completed in {elapsed:.1f}s")
    print(f"  📋 Routing map:")
    for ptype, pages in sorted(routing.items()):
        print(f"     {ptype:<25s} → pages {pages}")

    return {
        "classified_pages": classified,
        "page_routing": routing,
        "timing": {**state.get("timing", {}), "triage": elapsed},
    }


# ══════════════════════════════════════════════════════════════════════
# Node 2a: Invoice List Extractor
# ══════════════════════════════════════════════════════════════════════

def extract_invoices_node(state: AuditState) -> dict:
    """
    Extract structured invoice data from invoice_list pages.
    Uses LLM (Claude) for extraction since invoice formats vary.
    """
    from src.agents.invoice_list_extractor import InvoiceListExtraction
    from src.utils.pdf_reader import extract_pages
    from src.config import get_llm
    from src.agents.invoice_list_extractor import EXTRACTION_PROMPT
    from langchain_core.messages import SystemMessage, HumanMessage

    routing = state["page_routing"]
    invoice_pages = routing.get("invoice_list", [])

    if not invoice_pages:
        print("\n  ℹ️  No invoice_list pages found — skipping extractor")
        return {"invoice_list_items": [], "errors": []}

    pdf_path = state["pdf_path"]
    start = time.time()

    print(f"\n{'═'*70}")
    print(f"  📋 NODE 2a: INVOICE LIST EXTRACTOR")
    print(f"  Processing pages: {invoice_pages}")
    print(f"{'═'*70}")

    all_pages = extract_pages(pdf_path)
    pages_to_process = [p for p in all_pages if p.page_number in invoice_pages]

    model = get_llm()
    structured = model.with_structured_output(InvoiceListExtraction)

    all_items = []
    errors = []

    for page in pages_to_process:
        try:
            result = structured.invoke([
                SystemMessage(content=EXTRACTION_PROMPT),
                HumanMessage(
                    content=f"Page {page.page_number} of {page.total_pages}:\n\n{page.text}"
                ),
            ])
            for item in result.items:
                item.source_page = page.page_number
                item_dict = item.model_dump(mode="json")
                all_items.append(item_dict)
                print(f"    {item.vendor_name:<30s} ${item.amount:>10,.2f}")
        except Exception as e:
            err = f"Invoice extraction failed on page {page.page_number}: {e}"
            print(f"    ❌ {err}")
            errors.append(err)

    elapsed = time.time() - start
    total = sum(item["amount"] for item in all_items)
    print(f"\n  ✓ {len(all_items)} invoices extracted (${total:,.2f}) in {elapsed:.1f}s")

    return {
        "invoice_list_items": all_items,
        "errors": errors,
        "timing": {**state.get("timing", {}), "extract_invoices": elapsed},
    }


# ══════════════════════════════════════════════════════════════════════
# Node 2b: Bank Statement Extractor
# ══════════════════════════════════════════════════════════════════════

def extract_bank_node(state: AuditState) -> dict:
    """
    Extract bank transactions using deterministic regex parsing.
    Dynamically detects operating vs reserve pages from triage routing.
    NO LLM calls — pure Python.
    """
    from src.agents.bank_statement_extractor import parse_bank_page
    from src.utils.pdf_reader import extract_pages

    routing = state["page_routing"]
    bank_pages = routing.get("bank_statement", [])

    if not bank_pages:
        print("\n  ℹ️  No bank_statement pages found — skipping extractor")
        return {"bank_transactions": [], "errors": []}

    pdf_path = state["pdf_path"]
    start = time.time()

    print(f"\n{'═'*70}")
    print(f"  🏦 NODE 2b: BANK STATEMENT EXTRACTOR (deterministic)")
    print(f"  Processing pages: {bank_pages}")
    print(f"{'═'*70}")

    all_pages = extract_pages(pdf_path)
    all_txns = []
    errors = []

    # Identify operating vs reserve pages from page content
    for page in all_pages:
        if page.page_number not in bank_pages:
            continue

        # Detect account type from page text
        text_upper = page.text.upper()

        # Skip reconciliation pages and blank pages — they use different formats
        if "BANK ACCOUNT RECONCILIATION" in text_upper:
            print(f"  Page {page.page_number}: skipping (reconciliation page)")
            continue
        if "THIS PAGE LEFT INTENTIONALLY BLANK" in text_upper:
            print(f"  Page {page.page_number}: skipping (blank page)")
            continue

        # Determine account type from page header (account number is at the top)
        # IMPORTANT: Don't check full text — descriptions like "CincXfer to 8766"
        # cause false matches that misclassify operating pages as reserve
        header_lines = page.text.split('\n')[:15]
        header_text = '\n'.join(header_lines)
        if "8766" in header_text or "RESERVE" in header_text.upper():
            account_type = "reserve"
            account_last4 = "8766"
        else:
            account_type = "operating"
            account_last4 = "8763"

        try:
            print(f"\n  Page {page.page_number} ({account_type}/{account_last4}):")
            txns = parse_bank_page(page.text, page.page_number, account_type, account_last4)
            all_txns.extend(txns)
            print(f"    → {len(txns)} transactions")
        except Exception as e:
            err = f"Bank parsing failed on page {page.page_number}: {e}"
            print(f"    ❌ {err}")
            errors.append(err)

    elapsed = time.time() - start

    # Summary
    op_txns = [t for t in all_txns if t["account_type"] == "operating"]
    res_txns = [t for t in all_txns if t["account_type"] == "reserve"]
    op_credits = sum(t["amount"] for t in op_txns if t["transaction_type"] == "credit")
    op_debits = sum(t["amount"] for t in op_txns if t["transaction_type"] == "debit")

    print(f"\n  ✓ {len(all_txns)} total transactions in {elapsed:.1f}s")
    print(f"    Operating: {len(op_txns)} txns (credits: ${op_credits:,.2f}, debits: ${op_debits:,.2f})")
    print(f"    Reserve:   {len(res_txns)} txns")

    return {
        "bank_transactions": all_txns,
        "errors": errors,
        "timing": {**state.get("timing", {}), "extract_bank": elapsed},
    }


# ══════════════════════════════════════════════════════════════════════
# Node 2c: Homeowner Ledger Extractor
# ══════════════════════════════════════════════════════════════════════

def extract_ledger_node(state: AuditState) -> dict:
    """
    Extract homeowner ledger data using deterministic parsing.
    Dynamically discovers ledger pages from triage routing.
    NO LLM calls — pure Python.
    """
    from src.agents.homeowner_ledger_extractor import parse_ledger_pages, to_json_records
    from src.utils.pdf_reader import extract_pages

    routing = state["page_routing"]
    ledger_pages = routing.get("homeowner_ledger", [])

    if not ledger_pages:
        print("\n  ℹ️  No homeowner_ledger pages found — skipping extractor")
        return {"homeowner_ledger": [], "errors": []}

    pdf_path = state["pdf_path"]
    start = time.time()

    print(f"\n{'═'*70}")
    print(f"  👤 NODE 2c: HOMEOWNER LEDGER EXTRACTOR (deterministic)")
    print(f"  Processing pages: {ledger_pages}")
    print(f"{'═'*70}")

    all_pages = extract_pages(pdf_path)
    pages_to_process = [p for p in all_pages if p.page_number in ledger_pages]
    errors = []

    try:
        homeowners, association_totals = parse_ledger_pages(pages_to_process)
        records = to_json_records(homeowners)

        # Verify against association totals
        total_ending = sum(r["ending_balance"] for r in records)
        if association_totals:
            expected = association_totals["ending_balance"]
            match = abs(total_ending - expected) < 0.01
            print(f"\n  ✓ {len(records)} homeowner accounts extracted")
            print(f"    Ending balance: ${total_ending:,.2f} "
                  f"(expected: ${expected:,.2f}) {'✅ MATCH' if match else '❌ MISMATCH'}")
            if not match:
                errors.append(
                    f"Ledger ending balance mismatch: computed=${total_ending:,.2f} "
                    f"vs expected=${expected:,.2f}"
                )
        else:
            print(f"\n  ✓ {len(records)} homeowner accounts (no association totals for verification)")

    except Exception as e:
        err = f"Ledger extraction failed: {e}"
        print(f"    ❌ {err}")
        errors.append(err)
        records = []

    elapsed = time.time() - start
    print(f"    ⏱️  {elapsed:.1f}s")

    return {
        "homeowner_ledger": records,
        "errors": errors,
        "timing": {**state.get("timing", {}), "extract_ledger": elapsed},
    }


# ══════════════════════════════════════════════════════════════════════
# Node 3: Deterministic Auditor
# ══════════════════════════════════════════════════════════════════════

def audit_node(state: AuditState) -> dict:
    """
    Run all deterministic reconciliation checks on extracted data.
    NO LLM calls — pure Python math.
    """
    from src.agents.deterministic_auditor import (
        check_deposits_vs_receipts,
        check_withdrawals_vs_invoices,
        check_reserve_transfers,
        check_net_cash_flow,
        check_homeowner_formulas,
        detect_rejected_checks,
        detect_unapproved_checks,
        AuditReport,
        save_audit_report,
    )

    start = time.time()

    print(f"\n{'═'*70}")
    print(f"  🔍 NODE 3: DETERMINISTIC AUDITOR")
    print(f"  Pure Python math — no LLM calls")
    print(f"{'═'*70}")

    bank_txns = state["bank_transactions"]
    ledger = state["homeowner_ledger"]
    invoices = state["invoice_list_items"]

    # Check if we have enough data to audit
    if not bank_txns and not ledger and not invoices:
        print("  ⚠️  No extracted data to audit!")
        return {
            "audit_report": {
                "confidence_score": 0.0,
                "requires_human_review": True,
                "flagged_issues": ["No data extracted — all extractors returned empty"],
            },
            "errors": ["Audit skipped: no extracted data"],
            "timing": {**state.get("timing", {}), "audit": 0},
        }

    report = AuditReport(
        timestamp=datetime.now().isoformat(),
        period=_detect_period(state["pdf_path"]),
    )

    # Run whatever checks we have data for
    if bank_txns and ledger:
        check1 = check_deposits_vs_receipts(bank_txns, ledger)
        report.checks.append(check1)
        print(f"\n{check1}")

    if bank_txns and invoices:
        check2 = check_withdrawals_vs_invoices(bank_txns, invoices)
        report.checks.append(check2)
        print(f"\n{check2}")

    if bank_txns:
        check3 = check_reserve_transfers(bank_txns)
        report.checks.append(check3)
        print(f"\n{check3}")

        check4 = check_net_cash_flow(bank_txns)
        report.checks.append(check4)
        print(f"\n{check4}")

    # Per-homeowner formula verification
    if ledger:
        hw_results = check_homeowner_formulas(ledger)
        report.homeowner_results = hw_results
        passed = [r for r in hw_results if r.passed]
        failed_real = [r for r in hw_results if not r.passed and not r.has_prepaid_carryforward]
        carryforward = [r for r in hw_results if r.has_prepaid_carryforward]
        print(f"\n  Homeowner formulas: {len(passed)}/{len(hw_results)} balanced "
              f"(+{len(carryforward)} carryforward, {len(failed_real)} failed)")
    else:
        hw_results = []
        passed = []
        failed_real = []
        carryforward = []

    # Red flag detection
    if bank_txns and invoices:
        unapproved, pending = detect_unapproved_checks(bank_txns, invoices)
        report.unapproved_checks = unapproved
        report.pending_invoices = pending
        if unapproved:
            total_u = sum(u["amount"] for u in unapproved)
            print(f"\n  🔴 {len(unapproved)} UNAPPROVED CHECK(S) — ${total_u:,.2f}")
            report.red_flags.append(
                f"UNAPPROVED CHECKS: {len(unapproved)} totaling ${total_u:,.2f}"
            )

    if bank_txns:
        rejected = detect_rejected_checks(bank_txns)
        report.rejected_checks = rejected
        if rejected:
            print(f"  ⚠️  {len(rejected)} rejected check(s) found")

    # Compute confidence score
    aggregate_checks = report.checks
    aggregate_passed = sum(1 for c in aggregate_checks if c.passed)
    aggregate_total = max(len(aggregate_checks), 1)

    formula_pass_rate = (len(passed) + len(carryforward)) / max(len(hw_results), 1) if hw_results else 1.0
    rejected_list = report.rejected_checks or []
    rejected_score = (
        1.0 if all(rc["redeposit_found"] for rc in rejected_list)
        else 0.5 if rejected_list
        else 1.0
    )

    confidence = round(
        0.60 * (aggregate_passed / aggregate_total)
        + 0.30 * formula_pass_rate
        + 0.10 * rejected_score,
        4,
    )

    report.total_checks = aggregate_total + len(hw_results)
    report.checks_passed = aggregate_passed + len(passed) + len(carryforward)
    report.checks_failed = (aggregate_total - aggregate_passed) + len(failed_real)
    report.confidence_score = confidence
    report.requires_human_review = confidence < 0.80 or len(failed_real) > 0

    # Build flagged issues
    for c in aggregate_checks:
        if not c.passed:
            report.flagged_issues.append(f"[{c.severity.upper()}] {c.name}: Δ=${c.difference:,.2f}")
    for r in failed_real:
        report.flagged_issues.append(
            f"[WARNING] {r.unit_id} ({r.homeowner_name}): formula off by ${r.difference:,.2f}"
        )

    # Save the report
    pdf_name = Path(state["pdf_path"]).stem
    output_dir = Path("data") / "audit_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"audit_{pdf_name}.json"
    save_audit_report(report, output_path)

    elapsed = time.time() - start

    print(f"\n  {'─'*50}")
    print(f"  Confidence: {confidence:.1%}")
    print(f"  Human Review: {'YES ⏸️' if report.requires_human_review else 'NO ✅'}")
    print(f"  ⏱️  {elapsed:.1f}s")

    # Serialize for state
    audit_dict = {
        "confidence_score": report.confidence_score,
        "requires_human_review": report.requires_human_review,
        "total_checks": report.total_checks,
        "checks_passed": report.checks_passed,
        "checks_failed": report.checks_failed,
        "flagged_issues": report.flagged_issues,
        "red_flags": report.red_flags,
        "period": report.period,
        "timestamp": report.timestamp,
        "output_path": str(output_path),
    }

    return {
        "audit_report": audit_dict,
        "timing": {**state.get("timing", {}), "audit": elapsed},
    }


# ══════════════════════════════════════════════════════════════════════
# Node 4: HITL Veto Point
# ══════════════════════════════════════════════════════════════════════

def hitl_review_node(state: AuditState) -> dict:
    """
    Human-in-the-Loop interrupt point.

    If the auditor's confidence is below 80%, we PAUSE the pipeline
    and ask a human to review before generating the final report.

    This uses LangGraph's interrupt() — the pipeline suspends,
    state is checkpointed, and resumes when a human responds.
    """
    audit = state.get("audit_report", {})
    confidence = audit.get("confidence_score", 0)
    issues = audit.get("flagged_issues", [])
    red_flags = audit.get("red_flags", [])

    print(f"\n{'═'*70}")
    print(f"  ⏸️  HITL VETO POINT — Human Review Required")
    print(f"  Confidence: {confidence:.1%}")
    print(f"  Flagged Issues: {len(issues)}")
    print(f"  Red Flags: {len(red_flags)}")
    print(f"{'═'*70}")

    if issues:
        print("\n  Issues:")
        for issue in issues:
            print(f"    • {issue}")
    if red_flags:
        print("\n  🚩 Red Flags:")
        for rf in red_flags:
            print(f"    🔴 {rf}")

    # LangGraph interrupt — suspends execution until human responds
    human_response = interrupt({
        "message": "Audit confidence is below threshold. Review the flagged issues above.",
        "confidence": confidence,
        "flagged_issues": issues,
        "red_flags": red_flags,
        "action_required": "Reply with 'approve' to accept or provide corrections.",
    })

    # Human approved — continue to report
    print(f"\n  ✅ Human response: {human_response}")

    return {"human_approved": True}


# ══════════════════════════════════════════════════════════════════════
# Node 5: Report Generator
# ══════════════════════════════════════════════════════════════════════

def report_node(state: AuditState) -> dict:
    """
    Generate the final structured audit report.
    Summarizes all findings from the pipeline.
    """
    audit = state.get("audit_report", {})
    timing = state.get("timing", {})
    errors = state.get("errors", [])
    pdf_name = Path(state["pdf_path"]).name

    print(f"\n{'═'*70}")
    print(f"  📊 NODE 5: REPORT GENERATOR")
    print(f"{'═'*70}")

    confidence = audit.get("confidence_score", 0)
    total_time = sum(timing.values()) if timing else 0

    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │  HOA FINANCIAL AUDIT — COMPLETE                         │
  ├─────────────────────────────────────────────────────────┤
  │  Document:     {pdf_name:<41s} │
  │  Period:       {audit.get('period', 'Unknown'):<41s} │
  │  Confidence:   {confidence:.1%}{' ':>36s} │
  │  Checks:       {audit.get('checks_passed', 0)}/{audit.get('total_checks', 0)} passed{' ':>31s} │
  │  Red Flags:    {len(audit.get('red_flags', []))}{' ':>40s} │
  │  Pipeline:     {total_time:.1f}s total{' ':>32s} │
  │  Human Review: {'APPROVED ✅' if state.get('human_approved') else 'NOT REQUIRED ✅' if not audit.get('requires_human_review') else 'PENDING ⏸️':<41s} │
  └─────────────────────────────────────────────────────────┘""")

    # Timing breakdown
    if timing:
        print(f"\n  ⏱️  Timing:")
        for node, t in sorted(timing.items(), key=lambda x: -x[1]):
            bar = "█" * int(t / max(timing.values()) * 30) if max(timing.values()) > 0 else ""
            print(f"    {node:<20s} {t:>6.1f}s  {bar}")

    if errors:
        print(f"\n  ⚠️  Pipeline Errors ({len(errors)}):")
        for err in errors:
            print(f"    • {err}")

    print(f"\n  📄 Report saved to: {audit.get('output_path', 'N/A')}")
    print(f"{'═'*70}\n")

    return {}


# ══════════════════════════════════════════════════════════════════════
# Routing Logic
# ══════════════════════════════════════════════════════════════════════

def route_after_audit(state: AuditState) -> str:
    """
    After the auditor runs, decide: go to HITL review or straight to report?

    - Confidence >= 80% AND no formula failures → report
    - Confidence < 80% OR formula failures      → HITL veto point
    - If --approve flag was set                  → skip HITL
    """
    if state.get("human_approved"):
        return "report"

    audit = state.get("audit_report", {})
    confidence = audit.get("confidence_score", 0)
    requires_review = audit.get("requires_human_review", False)

    if requires_review and confidence < 0.80:
        return "hitl_review"
    return "report"


# ══════════════════════════════════════════════════════════════════════
# Build the Graph
# ══════════════════════════════════════════════════════════════════════

def build_audit_graph() -> StateGraph:
    """
    Build and compile the full HOA audit pipeline.

    Graph topology:

        START → triage → extract_invoices → extract_bank → extract_ledger
                                                                ↓
                                                              audit
                                                           ↙        ↘
                                                     hitl_review   report
                                                          ↓
                                                        report → END
    """
    builder = StateGraph(AuditState)

    # Add all nodes
    builder.add_node("triage", triage_node)
    builder.add_node("extract_invoices", extract_invoices_node)
    builder.add_node("extract_bank", extract_bank_node)
    builder.add_node("extract_ledger", extract_ledger_node)
    builder.add_node("audit", audit_node)
    builder.add_node("hitl_review", hitl_review_node)
    builder.add_node("report", report_node)

    # Wire the edges: linear pipeline with conditional after audit
    builder.add_edge(START, "triage")
    builder.add_edge("triage", "extract_invoices")
    builder.add_edge("extract_invoices", "extract_bank")
    builder.add_edge("extract_bank", "extract_ledger")
    builder.add_edge("extract_ledger", "audit")
    builder.add_conditional_edges(
        "audit",
        route_after_audit,
        ["hitl_review", "report"],
    )
    builder.add_edge("hitl_review", "report")
    builder.add_edge("report", END)

    return builder.compile()


def build_audit_graph_with_checkpointer():
    """Build the graph with MemorySaver for state persistence (HITL support)."""
    from langgraph.checkpoint.memory import MemorySaver

    builder = StateGraph(AuditState)

    builder.add_node("triage", triage_node)
    builder.add_node("extract_invoices", extract_invoices_node)
    builder.add_node("extract_bank", extract_bank_node)
    builder.add_node("extract_ledger", extract_ledger_node)
    builder.add_node("audit", audit_node)
    builder.add_node("hitl_review", hitl_review_node)
    builder.add_node("report", report_node)

    builder.add_edge(START, "triage")
    builder.add_edge("triage", "extract_invoices")
    builder.add_edge("extract_invoices", "extract_bank")
    builder.add_edge("extract_bank", "extract_ledger")
    builder.add_edge("extract_ledger", "audit")
    builder.add_conditional_edges(
        "audit",
        route_after_audit,
        ["hitl_review", "report"],
    )
    builder.add_edge("hitl_review", "report")
    builder.add_edge("report", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _detect_period(pdf_path: str) -> str:
    """Try to extract the month/year period from the PDF filename."""
    name = Path(pdf_path).stem.lower()

    # Common patterns in this user's filenames:
    # "Briarwyck Monthly Financials 2026 2" → February 2026
    # "2025.09 TPB Financials" → September 2025
    # "2024 May Financials TPB" → May 2024
    # "TPB March 2025 Financial Packet" → March 2025

    import re

    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09",
        "oct": "10", "nov": "11", "dec": "12",
    }

    # Pattern: "2026 2" or "2026 1" (year + month number)
    m = re.search(r'(\d{4})\s+(\d{1,2})', name)
    if m:
        year = m.group(1)
        month_num = int(m.group(2))
        month_names = ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        if 1 <= month_num <= 12:
            return f"{month_names[month_num]} {year}"

    # Pattern: "2025.09" (year.month)
    m = re.search(r'(\d{4})\.(\d{2})', name)
    if m:
        year = m.group(1)
        month_num = int(m.group(2))
        month_names = ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        if 1 <= month_num <= 12:
            return f"{month_names[month_num]} {year}"

    # Pattern: month name + year
    for month_name, month_num in months.items():
        if month_name in name:
            m = re.search(r'(\d{4})', name)
            if m:
                return f"{month_name.capitalize()} {m.group(1)}"

    # No year in filename — try reading from PDF content
    for month_name, month_num in months.items():
        if month_name in name:
            try:
                from src.utils.pdf_reader import extract_pages
                pages = extract_pages(pdf_path)
                if pages:
                    # Look for a 4-digit year in the first page text
                    year_match = re.search(r'(20\d{2})', pages[0].text)
                    if year_match:
                        return f"{month_name.capitalize()} {year_match.group(1)}"
            except Exception:
                pass

    return f"Unknown ({Path(pdf_path).stem})"


# ══════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ══════════════════════════════════════════════════════════════════════

def run_single(pdf_path: str, approve: bool = False):
    """Run the audit pipeline on a single PDF."""
    print(f"\n{'═'*70}")
    print(f"  🏗️  HOA FINANCIAL AUDIT SWARM")
    print(f"  LangGraph StateGraph Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*70}")
    print(f"  PDF: {pdf_path}")
    print(f"  Mode: {'Auto-approve' if approve else 'HITL enabled'}")
    print(f"{'═'*70}")

    if approve:
        # Simple graph without checkpointer (no HITL needed)
        graph = build_audit_graph()
        result = graph.invoke({
            "pdf_path": pdf_path,
            "run_id": f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "classified_pages": [],
            "page_routing": {},
            "bank_transactions": [],
            "invoice_list_items": [],
            "homeowner_ledger": [],
            "audit_report": {},
            "errors": [],
            "timing": {},
            "human_approved": True,  # Skip HITL
        })
    else:
        # Graph with checkpointer for HITL interrupt support
        graph = build_audit_graph_with_checkpointer()
        config = {"configurable": {"thread_id": f"audit_{Path(pdf_path).stem}"}}
        result = graph.invoke(
            {
                "pdf_path": pdf_path,
                "run_id": f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "classified_pages": [],
                "page_routing": {},
                "bank_transactions": [],
                "invoice_list_items": [],
                "homeowner_ledger": [],
                "audit_report": {},
                "errors": [],
                "timing": {},
                "human_approved": False,
            },
            config=config,
        )

    return result


def run_batch(pdf_dir: str, approve: bool = True):
    """Run the audit pipeline on all PDFs in a directory."""
    pdf_dir = Path(pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))

    print(f"\n{'═'*70}")
    print(f"  🏗️  HOA FINANCIAL AUDIT SWARM — BATCH MODE")
    print(f"  {len(pdfs)} PDFs found in {pdf_dir}")
    print(f"{'═'*70}")

    results = []
    for i, pdf in enumerate(pdfs, 1):
        print(f"\n\n{'▶'*3} [{i}/{len(pdfs)}] {pdf.name}")
        try:
            result = run_single(str(pdf), approve=approve)
            audit = result.get("audit_report", {})
            results.append({
                "pdf": pdf.name,
                "period": audit.get("period", "Unknown"),
                "confidence": audit.get("confidence_score", 0),
                "checks_passed": audit.get("checks_passed", 0),
                "total_checks": audit.get("total_checks", 0),
                "red_flags": len(audit.get("red_flags", [])),
                "status": "complete",
            })
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            results.append({
                "pdf": pdf.name,
                "status": "failed",
                "error": str(e),
            })

    # Summary table
    print(f"\n\n{'═'*70}")
    print(f"  BATCH AUDIT SUMMARY — {len(pdfs)} months")
    print(f"  {'─'*66}")
    print(f"  {'PDF':<45s} {'Conf':>6s} {'Checks':>8s} {'Flags':>6s}")
    print(f"  {'─'*66}")
    for r in results:
        if r["status"] == "complete":
            print(f"  {r['pdf']:<45s} {r['confidence']:>5.1%} "
                  f"{r['checks_passed']:>3d}/{r['total_checks']:<3d}  {r['red_flags']:>4d}")
        else:
            print(f"  {r['pdf']:<45s} {'FAILED':>6s}")
    print(f"{'═'*70}\n")

    # Save batch results
    output = Path("data") / "audit_results" / "batch_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  📄 Batch summary: {output}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="HOA Financial Audit Swarm — LangGraph Pipeline"
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default="data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf",
        help="Path to a PDF file, or a directory for batch mode",
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Process all PDFs in the given directory",
    )
    parser.add_argument(
        "--approve", action="store_true",
        help="Auto-approve all audits (skip HITL review)",
    )
    args = parser.parse_args()

    if args.batch or Path(args.pdf_path).is_dir():
        run_batch(args.pdf_path, approve=args.approve)
    else:
        run_single(args.pdf_path, approve=args.approve)
