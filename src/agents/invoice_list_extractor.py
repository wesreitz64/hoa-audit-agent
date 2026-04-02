"""
Node 2a: Invoice List Extractor

Extracts structured InvoiceListItem records from CINCSystems
"Invoice List" pages (pages 7-8 in the Feb 2026 packet).

Input:  Raw text from pages classified as 'invoice_list'
Output: list[InvoiceListItem] — one per vendor payment

Architecture:
  triage_full_results.json → filter invoice_list pages → extract → save JSON
"""

import json
import sys
import time
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel

from src.config import get_llm
from src.schemas.financial import InvoiceListItem
from src.utils.pdf_reader import extract_pages


# ──────────────────────────────────────────────────────────────────────
# Wrapper model — Claude needs to return a LIST of items
# ──────────────────────────────────────────────────────────────────────

class InvoiceListExtraction(BaseModel):
    """Wrapper for structured output — extracts multiple invoices from one page."""
    items: list[InvoiceListItem]


EXTRACTION_PROMPT = """You are a financial data extraction expert for HOA (Homeowners Association) documents.

You will receive text from a CINCSystems "Invoice List" page for Briarwyck Owners Association.
This page lists ALL vendor invoices paid during the month.

DOCUMENT STRUCTURE — each vendor section has 3 parts:
1. VENDOR HEADER: Vendor name in bold, left-aligned (e.g., "Reliant", "PMI Cross Timbers - Mgmt Mod Only")
2. LINE ITEMS: Individual invoices with invoice#, dates, amounts, GL codes, payment info
3. VENDOR FOOTER: "[Vendor Name] Total:" with the sum of all line items, in bold, right-aligned

Create ONE record per VENDOR SECTION using the VENDOR FOOTER TOTAL as the amount.
Do NOT create separate records for individual line items within a vendor section.

For example, if you see:
  PMI Cross Timbers - Mgmt Mod Only
    4012    $824.00    Management Fee
    4123    $156.50    Admin Fees
  PMI Cross Timbers - Mgmt Mod Only Total: $980.50

You should create ONE record: vendor="PMI Cross Timbers - Mgmt Mod Only", amount=980.50
Do NOT create two records for $824 and $156.50 — those are line items, not vendor totals.

Extract these fields for each vendor:
- vendor_name: From the vendor header (e.g., "Reliant", "PMI Cross Timbers - Mgmt Mod Only")
- invoice_number: The FIRST invoice number in the vendor section (or the most prominent one)
- invoice_date: Date the invoice was created (format: YYYY-MM-DD). Use the first line item's date.
- paid_date: Date the invoice was paid (format: YYYY-MM-DD). Use the first line item's paid date.
- amount: The VENDOR FOOTER TOTAL amount (NOT individual line items)
- gl_account_code: The GL code from the first/primary line item (e.g., "58-5500-00")
- gl_account_name: What the GL code represents (e.g., "Electricity", "Management Fee")
- payment_type: How it was paid (e.g., "Auto Pay", "ACH", "Check")
- authorized_by: Who approved the payment (e.g., "Holli Nugent"), null if not shown
- bank_account_last4: Last 4 digits from "Pay From Acct:***XXXX" pattern, null if not shown
- source_page: The page number (I will tell you this)

IMPORTANT RULES:
- ONE record per vendor section, using the VENDOR FOOTER TOTAL.
- Dates must be in YYYY-MM-DD format.
- If a field is not visible, use null.
- If a vendor section spans across a page break, extract what's visible on this page.
"""


def extract_invoice_list(pdf_path: str, triage_results_path: str = "data/triage_full_results.json"):
    """
    Extract all InvoiceListItems from invoice_list pages.

    Args:
        pdf_path: Path to the HOA financial PDF.
        triage_results_path: Path to triage classification results.

    Returns:
        List of InvoiceListItem records.
    """
    sys.stdout.reconfigure(line_buffering=True)

    # Load triage results to find invoice_list pages
    triage = json.load(open(triage_results_path, encoding="utf-8"))
    invoice_list_pages = [t["page_number"] for t in triage if t["page_type"] == "invoice_list"]

    if not invoice_list_pages:
        print("No invoice_list pages found in triage results.")
        return []

    print(f"Extracting from {len(invoice_list_pages)} invoice_list pages: {invoice_list_pages}")

    # Load PDF pages
    all_pages = extract_pages(pdf_path)
    pages_to_process = [p for p in all_pages if p.page_number in invoice_list_pages]

    # Set up Claude with structured output
    model = get_llm()
    structured = model.with_structured_output(InvoiceListExtraction)

    all_items = []
    start = time.time()

    for page in pages_to_process:
        print(f"\n  Page {page.page_number}:")
        result = structured.invoke([
            SystemMessage(content=EXTRACTION_PROMPT),
            HumanMessage(content=f"Page {page.page_number} of {page.total_pages}:\n\n{page.text}"),
        ])

        for item in result.items:
            # Ensure source_page is set correctly
            item.source_page = page.page_number
            all_items.append(item)
            print(f"    {item.vendor_name:<30s} ${item.amount:>10,.2f}  {item.gl_account_code} ({item.gl_account_name})")

    elapsed = time.time() - start

    # Summary
    total_amount = sum(item.amount for item in all_items)
    print(f"\n{'='*60}")
    print(f"  Extracted {len(all_items)} invoices in {elapsed:.0f}s")
    print(f"  Total invoice amount: ${total_amount:,.2f}")
    print(f"{'='*60}")

    return all_items


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf"

    items = extract_invoice_list(pdf)

    # Save to JSON for verification
    output = [item.model_dump(mode="json") for item in items]
    output_path = "data/extraction_invoice_list.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {output_path}")
