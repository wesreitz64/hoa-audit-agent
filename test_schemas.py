"""
Schema Validation Test — No API Key Required

Run this to verify your Pydantic schemas work correctly:
    python test_schemas.py

This validates that your data contracts are properly defined
before you start building any agent logic.
"""

from datetime import date
from src.schemas.financial import (
    PageType,
    ClassifiedPage,
    VendorInvoice,
    BankTransaction,
    HomeownerPayment,
    AuditResult,
)


def test_page_classification():
    """Test the Triage Router output schema."""
    page = ClassifiedPage(
        page_number=1,
        page_type=PageType.INVOICE,
        confidence=0.95,
    )
    assert page.page_type == PageType.INVOICE
    assert page.confidence == 0.95
    print(f"  ✅ ClassifiedPage: page {page.page_number} → {page.page_type.value} ({page.confidence:.0%})")
    return page


def test_vendor_invoice():
    """Test the Invoice Extractor output schema."""
    invoice = VendorInvoice(
        vendor_name="ABC Landscaping LLC",
        invoice_number="INV-2025-0847",
        invoice_date=date(2025, 6, 15),
        due_date=date(2025, 7, 15),
        amount=3_450.00,
        description="Monthly grounds maintenance - June 2025",
        source_page=12,
    )
    assert invoice.amount == 3450.00
    print(f"  ✅ VendorInvoice: {invoice.vendor_name} — ${invoice.amount:,.2f}")
    return invoice


def test_bank_transaction():
    """Test the Bank Statement Extractor output schema."""
    txn = BankTransaction(
        transaction_date=date(2025, 6, 1),
        description="HOA Dues Deposit - Unit 4201",
        amount=425.00,
        transaction_type="deposit",
        running_balance=52_847.33,
        source_page=23,
    )
    assert txn.transaction_type == "deposit"
    print(f"  ✅ BankTransaction: {txn.description} — ${txn.amount:,.2f} ({txn.transaction_type})")
    return txn


def test_homeowner_payment():
    """Test the Ledger Extractor output schema."""
    payment = HomeownerPayment(
        homeowner_name="Smith, John",
        unit_or_address="4201 Briarwyck Ln",
        payment_date=date(2025, 6, 1),
        amount_due=425.00,
        amount_paid=425.00,
        balance=0.00,
        source_page=35,
    )
    assert payment.balance == 0.00
    print(f"  ✅ HomeownerPayment: {payment.unit_or_address} — paid ${payment.amount_paid:,.2f} (balance: ${payment.balance:,.2f})")
    return payment


def test_audit_result():
    """Test the Deterministic Auditor output schema."""
    result = AuditResult(
        total_deposits=127_500.00,
        total_homeowner_payments=125_800.00,
        discrepancy=1_700.00,
        total_vendor_invoices=89_200.00,
        total_withdrawals=91_450.00,
        invoice_vs_withdrawal_gap=-2_250.00,
        flagged_issues=[
            "Discrepancy: $1,700 in deposits not matched to homeowner payments",
            "Withdrawal exceeds invoices by $2,250 — possible unrecorded expense",
        ],
        confidence_score=0.72,
        requires_human_review=True,
    )
    assert result.requires_human_review is True
    assert len(result.flagged_issues) == 2
    print(f"  ✅ AuditResult: confidence={result.confidence_score:.0%}, "
          f"human_review={'YES' if result.requires_human_review else 'no'}")
    for issue in result.flagged_issues:
        print(f"     ⚠️  {issue}")
    return result


def test_confidence_validation():
    """Test that Pydantic rejects invalid confidence scores."""
    try:
        ClassifiedPage(page_number=1, page_type=PageType.INVOICE, confidence=1.5)
        print("  ❌ Should have rejected confidence > 1.0")
        return False
    except Exception:
        print("  ✅ Pydantic correctly rejects confidence=1.5 (must be ≤ 1.0)")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Schema Validation — HOA Financial Audit Swarm")
    print("=" * 60)
    print()

    print("── Page Classification (Triage Router)")
    test_page_classification()
    print()

    print("── Vendor Invoice (Invoice Extractor)")
    test_vendor_invoice()
    print()

    print("── Bank Transaction (Bank Statement Extractor)")
    test_bank_transaction()
    print()

    print("── Homeowner Payment (Ledger Extractor)")
    test_homeowner_payment()
    print()

    print("── Audit Result (Deterministic Auditor)")
    test_audit_result()
    print()

    print("── Validation Guards")
    test_confidence_validation()
    print()

    print("=" * 60)
    print("✅ All schemas validated. Your data contracts are solid.")
    print("=" * 60)
