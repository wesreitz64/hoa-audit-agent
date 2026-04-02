"""
Node 1: Triage Router — Page Classification Agent

The FIRST node in the audit swarm. Takes each PDF page and classifies
it into one of 11 page types using Claude's structured output.

Why this matters:
  - Routes pages to the correct extractor (invoice vs bank vs ledger)
  - Skips boilerplate/insurance pages → saves ~25% in token costs
  - Confidence scores flag uncertain pages for human review

Architecture:
  PDF → [extract_pages] → [triage_router] → list[ClassifiedPage]
                                               ↓
                                    Routes to Nodes 2a-2d
"""

import os

from src.config import get_llm  # Suppresses Pydantic V1 warning
from langchain_core.messages import SystemMessage, HumanMessage

from src.schemas.financial import PageType, ClassifiedPage
from src.utils.pdf_reader import PDFPage


# ──────────────────────────────────────────────────────────────────────
# System prompt — tells Claude exactly how to classify pages
# ──────────────────────────────────────────────────────────────────────

TRIAGE_SYSTEM_PROMPT = """You are a document classification expert for HOA (Homeowners Association) financial packets.

You will receive the text content of a single page from a PMI Cross Timbers / CINCSystems financial report for "Briarwyck Owners Association, Inc."

Classify the page into EXACTLY ONE of these types:

1. **invoice** — An individual vendor invoice PDF (from companies like Magnolia Fisheries, Granite Landscape, PMI Cross Timbers, Neon Monkey Services, Ambit Texas). Contains: vendor name, invoice number, date, amount, description of services.

2. **invoice_list** — A CINCSystems report titled "Invoice List" showing ALL paid invoices for the month in a table. Contains: multiple vendors, invoice numbers, dates, amounts, GL account codes (like "58-5500-00"), payment types, and who authorized each payment.

3. **bank_statement** — A bank statement from SouthState Bank. Contains: transaction dates, descriptions, credit/debit amounts, running balances. Account numbers ending in 8763 (Operating) or 8766 (Reserve). Look for "ASSOCIATION CHECKING" header.

4. **homeowner_ledger** — Title is ALWAYS "Receivables Type Balances". This is the monthly accounting ledger for each homeowner. Columns are: Prev. Bal, Billing, Receipts, Adjustments, PrePaid, Ending Bal. Shows homeowner IDs (TPB##) and names. Does NOT have aging buckets (30/60/90). Does NOT show collection status or attorneys.
   CRITICAL: If you see "Receivables Type Balances" anywhere on the page, classify as homeowner_ledger, NOT homeowner_aging.

5. **homeowner_aging** — Title is ALWAYS "Homeowner Aging Report". Shows delinquent and current accounts with aging columns: Current, Over 30, Over 60, Over 90, Balance. Includes collection status (Step 1-4), collection attorney names, and last payment info. Does NOT have columns for Billing, Receipts, Adjustments, PrePaid.
   CRITICAL: If you see "Homeowner Aging Report" in the title, classify as homeowner_aging.

6. **balance_sheet** — "Balance Sheet" showing Assets, Liabilities & Equity. Contains: Operating and Reserve columns, account names like "SouthState Bank - Operating Acct", total assets and total liabilities.

7. **income_statement** — "Income Statement" (Operating or Reserve). Contains: account codes, descriptions, Current Period Budget vs Actual, Year-to-date Budget vs Actual, Annual Budget, variance calculations.

8. **general_ledger** — "General Ledger Trial Balance with Details". Contains: account numbers, detailed transaction entries, debits/credits, GL reference numbers, running balances by account.

9. **bank_account_list** — "Bank Account List" summary page. Contains: bank names, account numbers, chart account codes, balances, interest rates, maturity dates. Usually just 1 page.

10. **insurance_compliance** — Insurance certificates, policy declarations, cancellation notices, compliance documents. Look for: "CERTIFICATE OF INSURANCE", "NOTICE OF CANCELLATION", policy numbers, coverage amounts, insurance company names.

11. **boilerplate** — Cover pages, blank pages ("intentionally left blank"), table of contents, covenant enforcement policies, or any page that doesn't contain extractable financial data.

IMPORTANT RULES:
- If a page is mostly blank or says "intentionally left blank", classify as boilerplate.
- If a page contains "Prepared for... Financial Report Package", classify as boilerplate (cover page).
- Pages with mixed content should be classified by the DOMINANT content type.
- Use the PAGE TITLE (top-right header on PMI reports) as the primary classification signal.
- Your confidence should reflect how clearly the page matches the type. Use lower confidence (0.5-0.7) when the page is ambiguous or contains mixed content.
"""


# ──────────────────────────────────────────────────────────────────────
# Triage Router — classifies a single page
# ──────────────────────────────────────────────────────────────────────

def create_triage_model():
    """Create the Claude model configured for structured page classification."""
    model = get_llm()
    # .with_structured_output() forces Claude to return a ClassifiedPage
    # Pydantic validation runs automatically — invalid responses are rejected
    return model.with_structured_output(ClassifiedPage)


def classify_page(model, page: PDFPage) -> ClassifiedPage:
    """
    Classify a single PDF page into one of 11 page types.

    Args:
        model: Claude model with structured output for ClassifiedPage.
        page: Extracted PDF page with text content.

    Returns:
        ClassifiedPage with page_number, page_type, confidence, and summary.
    """
    # Truncate very long pages to save tokens (keep first 3000 chars)
    page_text = page.text[:3000] if len(page.text) > 3000 else page.text

    if not page_text.strip():
        # Empty page — skip the LLM call entirely
        return ClassifiedPage(
            page_number=page.page_number,
            page_type=PageType.BOILERPLATE,
            confidence=1.0,
            summary="Empty or blank page",
        )

    result = model.invoke([
        SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
        HumanMessage(content=f"Classify this page (page {page.page_number} of {page.total_pages}):\n\n{page_text}"),
    ])

    # Ensure page_number matches the actual page (the LLM might hallucinate a different number)
    result.page_number = page.page_number
    return result


def classify_document(pdf_path: str) -> list[ClassifiedPage]:
    """
    Classify ALL pages in a PDF document.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of ClassifiedPage objects, one per page.
    """
    from src.utils.pdf_reader import extract_pages

    pages = extract_pages(pdf_path)
    model = create_triage_model()
    results = []

    print(f"📄 Classifying {len(pages)} pages from {pdf_path}...")
    print("-" * 60)

    for page in pages:
        result = classify_page(model, page)
        results.append(result)

        # Live progress
        icon = _get_icon(result.page_type)
        print(
            f"  Page {result.page_number:3d} → {icon} {result.page_type.value:<25s} "
            f"({result.confidence:.0%})"
            f"{'  ⚠️ LOW' if result.confidence < 0.8 else ''}"
        )

    print("-" * 60)
    _print_summary(results)

    return results


def _get_icon(page_type: PageType) -> str:
    """Map page types to emoji for readable output."""
    icons = {
        PageType.INVOICE: "🧾",
        PageType.INVOICE_LIST: "📋",
        PageType.BANK_STATEMENT: "🏦",
        PageType.HOMEOWNER_LEDGER: "👤",
        PageType.HOMEOWNER_AGING: "⏰",
        PageType.BALANCE_SHEET: "📊",
        PageType.INCOME_STATEMENT: "📈",
        PageType.GENERAL_LEDGER: "📒",
        PageType.BANK_ACCOUNT_LIST: "🔗",
        PageType.INSURANCE_COMPLIANCE: "🛡️",
        PageType.BOILERPLATE: "🗑️",
    }
    return icons.get(page_type, "❓")


def _print_summary(results: list[ClassifiedPage]):
    """Print a summary of classification results."""
    from collections import Counter

    counts = Counter(r.page_type.value for r in results)
    total = len(results)
    skippable = sum(
        1 for r in results
        if r.page_type in (PageType.BOILERPLATE, PageType.INSURANCE_COMPLIANCE, PageType.BANK_ACCOUNT_LIST)
    )
    low_confidence = [r for r in results if r.confidence < 0.8]

    print(f"\n📊 Classification Summary ({total} pages)")
    for ptype, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"   {ptype:<25s} {count:3d} pages")

    print(f"\n   💰 Extractable pages: {total - skippable} ({(total - skippable) / total:.0%})")
    print(f"   🗑️  Skippable pages:   {skippable} ({skippable / total:.0%}) ← token savings")

    if low_confidence:
        print(f"\n   ⚠️  Low confidence ({len(low_confidence)} pages):")
        for r in low_confidence:
            print(f"      Page {r.page_number}: {r.page_type.value} ({r.confidence:.0%})")


# ──────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        pdf = "data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf"
    else:
        pdf = sys.argv[1]

    results = classify_document(pdf)

    # Save results as JSON for inspection
    import json
    output = [r.model_dump(mode="json") for r in results]
    output_path = "data/triage_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n💾 Results saved to {output_path}")
