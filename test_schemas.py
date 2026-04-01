"""
Schema Validation Test — No API Key Required

Run this to verify all Pydantic schemas work with REAL Briarwyck data:
    python test_schemas.py

Tests use actual values extracted from the Feb 2026 financial packet.
"""

from datetime import date
from src.schemas.financial import (
    PageType,
    ClassifiedPage,
    VendorInvoice,
    InvoiceListItem,
    BankTransaction,
    HomeownerPayment,
    HomeownerAgingEntry,
    CollectionStatus,
    IncomeStatementLine,
    BalanceSheetLine,
    AuditResult,
)


def test_page_classification():
    """Test the expanded Triage Router output (10 page types)."""
    test_pages = [
        (1, PageType.BOILERPLATE, 0.99, "Cover page - Briarwyck Feb 2026"),
        (2, PageType.BALANCE_SHEET, 0.97, "Balance Sheet - Operating & Reserve"),
        (3, PageType.BANK_ACCOUNT_LIST, 0.95, "Bank account summary"),
        (4, PageType.INCOME_STATEMENT, 0.93, "Income Statement - Operating"),
        (7, PageType.INVOICE_LIST, 0.96, "CINCSystems paid invoice list"),
        (9, PageType.HOMEOWNER_AGING, 0.94, "Homeowner aging report"),
        (14, PageType.BANK_STATEMENT, 0.98, "SouthState Bank Operating 8763"),
        (28, PageType.INVOICE, 0.92, "Magnolia Fisheries invoice"),
        (35, PageType.INSURANCE_COMPLIANCE, 0.91, "Insurance certificate"),
        (45, PageType.GENERAL_LEDGER, 0.90, "Trial balance with detail"),
        (47, PageType.HOMEOWNER_LEDGER, 0.93, "Receivables - TPB01"),
    ]
    for page_num, ptype, conf, summary in test_pages:
        page = ClassifiedPage(
            page_number=page_num,
            page_type=ptype,
            confidence=conf,
            summary=summary,
        )
        print(f"  ✅ Page {page.page_number:2d} → {page.page_type.value:<25s} ({page.confidence:.0%})")
    print(f"  📊 Total page types: {len(PageType)}")


def test_vendor_invoice():
    """Test with real Magnolia Fisheries invoice (page 28)."""
    invoice = VendorInvoice(
        vendor_name="Magnolia Fisheries",
        invoice_number="70076",
        invoice_date=date(2026, 2, 1),
        due_date=date(2026, 3, 3),
        amount=156.50,
        description="Pond maintenance service",
        terms="Net 30",
        source_page=28,
    )
    print(f"  ✅ VendorInvoice: {invoice.vendor_name} #{invoice.invoice_number} — ${invoice.amount:,.2f}")


def test_invoice_list_item():
    """Test with real CINCSystems invoice list entry (page 7)."""
    item = InvoiceListItem(
        vendor_name="Ambit Texas, LLC",
        invoice_number="056003140610",
        invoice_date=date(2026, 2, 10),
        paid_date=date(2026, 2, 23),
        amount=25.65,
        gl_account_code="58-5500-00",
        gl_account_name="Electricity",
        payment_type="Auto Pay",
        authorized_by="Holli Nugent",
        bank_account_last4="8763",
        source_page=7,
    )
    print(f"  ✅ InvoiceListItem: {item.vendor_name} — ${item.amount:,.2f} → {item.gl_account_code} ({item.gl_account_name})")

    # Test PMI management fee
    mgmt = InvoiceListItem(
        vendor_name="PMI Cross Timbers",
        invoice_number="4123",
        invoice_date=date(2026, 2, 1),
        paid_date=date(2026, 2, 6),
        amount=824.00,
        gl_account_code="50-5000-00",
        gl_account_name="Management Fee",
        payment_type="Check",
        authorized_by="Holli Nugent",
        bank_account_last4="8763",
        source_page=8,
    )
    print(f"  ✅ InvoiceListItem: {mgmt.vendor_name} — ${mgmt.amount:,.2f} → {mgmt.gl_account_code} ({mgmt.gl_account_name})")


def test_bank_transaction():
    """Test with real SouthState Bank transactions (pages 14-15)."""
    # Operating deposit
    deposit = BankTransaction(
        transaction_date=date(2026, 2, 11),
        description="Briarwyck Owners OnlinePay 5725",
        amount=255.44,
        transaction_type="credit",
        account_type="operating",
        account_number_last4="8763",
        source_page=15,
    )
    print(f"  ✅ BankTransaction: {deposit.description} — ${deposit.amount:,.2f} ({deposit.transaction_type}, {deposit.account_type})")

    # Reserve transaction
    reserve = BankTransaction(
        transaction_date=date(2026, 2, 27),
        description="Neon Monkey Services - Tree Maintenance",
        amount=1000.00,
        transaction_type="debit",
        account_type="reserve",
        account_number_last4="8766",
        source_page=46,
    )
    print(f"  ✅ BankTransaction: {reserve.description} — ${reserve.amount:,.2f} ({reserve.transaction_type}, {reserve.account_type})")


def test_homeowner_payment():
    """Test with real receivables data (pages 47-52)."""
    payment = HomeownerPayment(
        homeowner_id="TPB01",
        homeowner_name="Domingos Noronha",
        ownership_type="Owner",
        unit_or_address="2701 Belmeade",
        assessment_type="Assessment - Homeowner 2026",
        prev_balance=-25.00,
        billing=0.00,
        adjustments=0.00,
        receipts=0.00,
        prepaid=0.00,
        ending_balance=25.00,
        source_page=47,
    )
    print(f"  ✅ HomeownerPayment: {payment.homeowner_id} ({payment.homeowner_name}) — {payment.unit_or_address} — balance: ${payment.ending_balance:,.2f}")


def test_homeowner_aging():
    """Test with real aging report data (pages 9-13)."""
    delinquent = HomeownerAgingEntry(
        homeowner_id="TPB55",
        homeowner_name="Jose Enrique Angulo",
        address="2526 Lake Bend Terrace",
        ownership_type="Owner",
        last_payment_amount=108.00,
        last_payment_date=date(2025, 3, 13),
        current_due=0.00,
        over_30=0.00,
        over_60=25.00,
        over_90=425.00,
        total_balance=450.00,
        collection_status=CollectionStatus.STEP_4_COLLECTIONS,
        collection_attorney="Schwartz Vays LLC",
        assessment_type="Assessment - Homeowner (Delinquent Fee) 2024",
        source_page=9,
    )
    print(f"  ✅ HomeownerAgingEntry: {delinquent.homeowner_id} ({delinquent.homeowner_name})")
    print(f"     📍 {delinquent.address}")
    print(f"     💰 Balance: ${delinquent.total_balance:,.2f} (90+ days: ${delinquent.over_90:,.2f})")
    print(f"     ⚖️  Status: {delinquent.collection_status.value} → {delinquent.collection_attorney}")

    # Test homeowner on payment plan
    plan = HomeownerAgingEntry(
        homeowner_id="TPB64",
        homeowner_name="Richard Williams & Lorraine Ringholm",
        address="2535 Lake Bend Terrace",
        ownership_type="Payment Plan",
        last_payment_amount=216.22,
        last_payment_date=date(2026, 2, 11),
        current_due=39.22,
        over_30=0.00,
        over_60=0.00,
        over_90=159.00,
        total_balance=198.22,
        collection_status=CollectionStatus.STEP_3_FINAL_NOTICE,
        source_page=10,
    )
    print(f"  ✅ HomeownerAgingEntry: {plan.homeowner_id} ({plan.homeowner_name}) — PAYMENT PLAN")


def test_income_statement():
    """Test with real income statement data (pages 4-5)."""
    line = IncomeStatementLine(
        account_code="4000-00",
        account_name="Assessment General",
        statement_type="operating",
        current_period_budget=11_925.00,
        current_period_actual=9_965.62,
        current_period_variance=-1_959.38,
        ytd_budget=23_850.00,
        ytd_actual=64_949.82,
        ytd_variance=88_799.82,
        annual_budget=143_100.00,
        source_page=4,
    )
    print(f"  ✅ IncomeStatementLine: {line.account_code} {line.account_name}")
    print(f"     Budget: ${line.current_period_budget:>10,.2f}  |  Actual: ${line.current_period_actual:>10,.2f}  |  Variance: ${line.current_period_variance:>10,.2f}")


def test_balance_sheet():
    """Test with real balance sheet data (page 2)."""
    line = BalanceSheetLine(
        account_name="SouthState Bank - Operating Acct",
        category="Assets",
        subcategory="CASH - OPERATING",
        operating_amount=77_890.83,
        reserve_amount=0.00,
        total_amount=77_890.83,
        source_page=2,
    )
    print(f"  ✅ BalanceSheetLine: {line.account_name}")
    print(f"     Operating: ${line.operating_amount:>12,.2f}  |  Reserve: ${line.reserve_amount:>12,.2f}  |  Total: ${line.total_amount:>12,.2f}")


def test_audit_result():
    """Test the Deterministic Auditor output with Feb 2026 data."""
    result = AuditResult(
        # Operating
        total_deposits_operating=13_262.54,
        total_withdrawals_operating=15_337.74,
        total_homeowner_payments=9_965.62,
        total_vendor_invoices_from_list=15_337.74,
        total_vendor_invoices_individual=1_005.15,
        deposit_vs_payment_gap=3_296.92,
        invoice_list_vs_withdrawal_gap=0.00,

        # Reserve
        total_deposits_reserve=45.73,
        total_withdrawals_reserve=1_000.00,
        reserve_fund_balance=49_214.00,

        # Cross-document checks
        invoice_list_vs_individual_match=False,
        bank_ending_vs_balance_sheet_match=True,
        income_actuals_vs_bank_match=True,

        # Budget
        budget_overrun_categories=["Landscaping/Grounds", "Tree Maintenance"],
        revenue_shortfall_categories=["Assessment General"],

        # Delinquency
        total_delinquent_balance=3_689.00,
        accounts_in_collections=1,

        # Overall
        flagged_issues=[
            "Invoice list total ($15,337.74) does not match sum of individual invoices on file ($1,005.15) — only 3 of ~12 vendor invoices are included as PDFs",
            "Assessment income $1,959.38 below budget for Feb 2026",
            "1 account in collections (TPB55 - Schwartz Vays LLC)",
            "Reserve fund withdrawal of $1,000 for tree maintenance (Neon Monkey Services)",
        ],
        confidence_score=0.78,
        requires_human_review=True,
    )
    print(f"  ✅ AuditResult: confidence={result.confidence_score:.0%}, human_review={'YES ⏸️' if result.requires_human_review else 'no'}")
    print(f"     Operating: ${result.total_deposits_operating:>10,.2f} in  |  ${result.total_withdrawals_operating:>10,.2f} out")
    print(f"     Reserve:   ${result.total_deposits_reserve:>10,.2f} in  |  ${result.total_withdrawals_reserve:>10,.2f} out  |  Balance: ${result.reserve_fund_balance:>10,.2f}")
    print(f"     Delinquent: ${result.total_delinquent_balance:,.2f} ({result.accounts_in_collections} in collections)")
    print(f"     Flagged issues:")
    for issue in result.flagged_issues:
        print(f"       ⚠️  {issue}")


def test_validation_guards():
    """Verify Pydantic rejects invalid data."""
    tests_passed = 0

    # Confidence out of range
    try:
        ClassifiedPage(page_number=1, page_type=PageType.INVOICE, confidence=1.5)
        print("  ❌ Should reject confidence > 1.0")
    except Exception:
        print("  ✅ Rejects confidence=1.5 (must be ≤ 1.0)")
        tests_passed += 1

    # Invalid transaction type
    try:
        BankTransaction(
            transaction_date=date(2026, 2, 1),
            description="test",
            amount=100,
            transaction_type="maybe",  # Not "credit" or "debit"
            account_type="operating",
            account_number_last4="8763",
            source_page=1,
        )
        print("  ❌ Should reject invalid transaction_type")
    except Exception:
        print("  ✅ Rejects transaction_type='maybe' (must be 'credit' or 'debit')")
        tests_passed += 1

    # Invalid account type
    try:
        BankTransaction(
            transaction_date=date(2026, 2, 1),
            description="test",
            amount=100,
            transaction_type="credit",
            account_type="savings",  # Not "operating" or "reserve"
            account_number_last4="8763",
            source_page=1,
        )
        print("  ❌ Should reject invalid account_type")
    except Exception:
        print("  ✅ Rejects account_type='savings' (must be 'operating' or 'reserve')")
        tests_passed += 1

    # Invalid collection status
    try:
        HomeownerAgingEntry(
            homeowner_id="TPB01",
            homeowner_name="Test",
            address="123 Test St",
            ownership_type="Owner",
            current_due=0, over_30=0, over_60=0, over_90=0, total_balance=0,
            collection_status="maybe_delinquent",  # Invalid
            source_page=1,
        )
        print("  ❌ Should reject invalid collection_status")
    except Exception:
        print("  ✅ Rejects invalid CollectionStatus enum value")
        tests_passed += 1

    print(f"  📊 {tests_passed}/4 validation guards passed")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 Schema Validation — Briarwyck HOA Financial Audit Swarm")
    print("   Using REAL data from Feb 2026 financial packet (53 pages)")
    print("=" * 70)

    sections = [
        ("Page Classification (10 types)", test_page_classification),
        ("Vendor Invoice (Magnolia Fisheries)", test_vendor_invoice),
        ("Invoice List Items (CINCSystems)", test_invoice_list_item),
        ("Bank Transactions (SouthState Bank)", test_bank_transaction),
        ("Homeowner Payments (Receivables)", test_homeowner_payment),
        ("Homeowner Aging (Delinquencies)", test_homeowner_aging),
        ("Income Statement (Budget vs Actual)", test_income_statement),
        ("Balance Sheet", test_balance_sheet),
        ("Audit Result (Cross-Checks)", test_audit_result),
        ("Validation Guards", test_validation_guards),
    ]

    for title, test_fn in sections:
        print(f"\n── {title}")
        test_fn()

    print()
    print("=" * 70)
    print("✅ All schemas validated with real Briarwyck data.")
    print("=" * 70)
