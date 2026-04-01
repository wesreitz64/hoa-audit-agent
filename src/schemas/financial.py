"""
HOA Financial Audit Swarm — Core Data Schemas

These Pydantic models define the CONTRACTS that every agent in the swarm
must conform to. Define these FIRST, before writing any agent logic.

The philosophy: if the data doesn't match the schema, the extraction FAILED.
No hallucinated numbers. No fuzzy outputs. Deterministic stewardship.
"""

from pydantic import BaseModel, Field
from datetime import date
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# Page Classification (Node 1: Triage Router)
# ──────────────────────────────────────────────────────────────────────

class PageType(str, Enum):
    """Classification of page types found in HOA financial documents."""
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    HOMEOWNER_LEDGER = "homeowner_ledger"
    BALANCE_SHEET = "balance_sheet"
    BOILERPLATE = "boilerplate"


class ClassifiedPage(BaseModel):
    """Output of the Triage Router — one per page in the PDF."""
    page_number: int
    page_type: PageType
    confidence: float = Field(ge=0.0, le=1.0)


# ──────────────────────────────────────────────────────────────────────
# Extraction Schemas (Nodes 2a, 2b, 2c)
# ──────────────────────────────────────────────────────────────────────

class VendorInvoice(BaseModel):
    """Extracted from invoice pages — vendor bills to the HOA."""
    vendor_name: str
    invoice_number: Optional[str] = None
    invoice_date: date
    due_date: Optional[date] = None
    amount: float = Field(description="Total invoice amount in USD")
    description: str
    source_page: int = Field(description="Page number in original PDF")


class BankTransaction(BaseModel):
    """Extracted from bank statement pages — deposits and withdrawals."""
    transaction_date: date
    description: str
    amount: float
    transaction_type: str = Field(description="deposit or withdrawal")
    running_balance: Optional[float] = None
    source_page: int


class HomeownerPayment(BaseModel):
    """Extracted from ledger pages — individual HOA dues payments."""
    homeowner_name: Optional[str] = None
    unit_or_address: str
    payment_date: date
    amount_due: float
    amount_paid: float
    balance: float
    source_page: int


# ──────────────────────────────────────────────────────────────────────
# Audit Result (Node 3: Deterministic Auditor)
# ──────────────────────────────────────────────────────────────────────

class AuditResult(BaseModel):
    """
    Output of the Deterministic Auditor — pure Python math, NOT LLM math.
    
    Key cross-checks:
    - Bank_Deposits should ≈ Homeowner_Payments
    - Vendor_Invoices should ≈ Bank_Withdrawals
    - Any discrepancy → flagged for human review
    """
    total_deposits: float
    total_homeowner_payments: float
    discrepancy: float = Field(
        description="deposits - payments, should be ~0"
    )
    total_vendor_invoices: float
    total_withdrawals: float
    invoice_vs_withdrawal_gap: float
    flagged_issues: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool
