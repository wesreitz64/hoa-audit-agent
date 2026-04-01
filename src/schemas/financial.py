"""
HOA Financial Audit Swarm — Core Data Schemas

Pydantic models defining STRICT CONTRACTS for every piece of data
flowing through the audit swarm. Shaped by real PMI Cross Timbers /
CINCSystems financial packets from Briarwyck Owners Association.

Philosophy: if the data doesn't match the schema, the extraction FAILED.
No hallucinated numbers. No fuzzy outputs. Deterministic stewardship.

Document Types Discovered (from 53-page Feb 2026 packet):
  - Cover Page (1 page)
  - Balance Sheet (1 page)
  - Bank Account List (1 page)
  - Income Statement — Operating & Reserve (3 pages)
  - Invoice List — CINCSystems summary (2 pages)
  - Homeowner Aging Report (5 pages)
  - Bank Statements — Operating & Reserve (13 pages)
  - Individual Vendor Invoices (3 pages)
  - Insurance / Compliance / Legal (13 pages → SKIP)
  - General Ledger Trial Balance (2 pages)
  - Receivables Type Balances per homeowner (7 pages)
"""

from pydantic import BaseModel, Field
from datetime import date
from enum import Enum
from typing import Literal, Optional


# ══════════════════════════════════════════════════════════════════════
# LAYER 1: Page Classification (Node 1 — Triage Router)
# ══════════════════════════════════════════════════════════════════════

class PageType(str, Enum):
    """
    Classification of page types found in PMI Cross Timbers
    HOA financial packets. Expanded from 5 → 10 types based on
    real Briarwyck Owners Association documents.
    """
    # --- Extractable financial pages ---
    INVOICE = "invoice"                         # Individual vendor invoices (Magnolia, Granite, PMI)
    INVOICE_LIST = "invoice_list"               # CINCSystems paid invoice summary table
    BANK_STATEMENT = "bank_statement"           # SouthState Bank transaction detail
    HOMEOWNER_LEDGER = "homeowner_ledger"        # Receivables per homeowner (assessments, receipts)
    HOMEOWNER_AGING = "homeowner_aging"          # Delinquency report (30/60/90 day buckets)
    BALANCE_SHEET = "balance_sheet"              # Assets / Liabilities / Equity snapshot
    INCOME_STATEMENT = "income_statement"        # Budget vs Actual (Operating & Reserve)
    GENERAL_LEDGER = "general_ledger"            # Trial Balance with transaction detail

    # --- Non-extractable pages (skip to save tokens) ---
    BANK_ACCOUNT_LIST = "bank_account_list"      # Account numbers & balances summary
    INSURANCE_COMPLIANCE = "insurance_compliance"  # Insurance certs, cancellation notices, legal
    BOILERPLATE = "boilerplate"                  # Cover page, blank pages, policies, filler


class ClassifiedPage(BaseModel):
    """Output of the Triage Router — one per page in the PDF."""
    page_number: int
    page_type: PageType
    confidence: float = Field(ge=0.0, le=1.0)
    summary: Optional[str] = Field(
        default=None,
        description="Brief description of page content for audit trail"
    )


# ══════════════════════════════════════════════════════════════════════
# LAYER 2: Extraction Schemas (Nodes 2a–2d)
# ══════════════════════════════════════════════════════════════════════


# ─── 2a: Invoice Extraction ──────────────────────────────────────────

class VendorInvoice(BaseModel):
    """
    Extracted from individual vendor invoice PDFs.
    Examples: Magnolia Fisheries (pond maintenance), Granite Landscape,
    PMI Cross Timbers (management fee), Neon Monkey Services (tree work).
    """
    vendor_name: str
    invoice_number: Optional[str] = None
    invoice_date: date
    due_date: Optional[date] = None
    amount: float = Field(description="Total invoice amount in USD")
    description: str
    terms: Optional[str] = Field(
        default=None,
        description="Payment terms, e.g. 'Net 30'"
    )
    source_page: int = Field(description="Page number in original PDF")


class InvoiceListItem(BaseModel):
    """
    From the CINCSystems Invoice List — monthly paid invoice summary.
    These pages (typically 2) list ALL vendor payments for the month
    in a structured table with GL account codes.

    This is often MORE useful than individual invoices for auditing
    because it includes GL categorization and authorization info.
    """
    vendor_name: str
    invoice_number: str
    invoice_date: date
    paid_date: date
    amount: float
    gl_account_code: str = Field(
        description="Chart of accounts code, e.g. '58-5500-00'"
    )
    gl_account_name: str = Field(
        description="Account description, e.g. 'Electricity'"
    )
    payment_type: str = Field(
        description="Payment method: 'Auto Pay', 'ACH', 'Check'"
    )
    authorized_by: Optional[str] = Field(
        default=None,
        description="Who approved the payment, e.g. 'Holli Nugent'"
    )
    bank_account_last4: Optional[str] = Field(
        default=None,
        description="Last 4 of bank account used, e.g. '8763'"
    )
    source_page: int


# ─── 2b: Bank Statement Extraction ──────────────────────────────────

class BankTransaction(BaseModel):
    """
    Extracted from SouthState Bank statements.
    Briarwyck has TWO accounts:
      - Operating (ending 8763) — pages 14-16
      - Reserve (ending 8766) — pages 18-27
    """
    transaction_date: date
    description: str = Field(
        description="Transaction description, e.g. 'PAYABLI DEPOSIT TRANSFER 895472396'"
    )
    amount: float
    transaction_type: Literal["credit", "debit"] = Field(
        description="Credit = money in, Debit = money out"
    )
    account_type: Literal["operating", "reserve"] = Field(
        description="Which HOA bank account"
    )
    account_number_last4: str = Field(
        description="Last 4 digits: '8763' (operating) or '8766' (reserve)"
    )
    running_balance: Optional[float] = None
    source_page: int


# ─── 2c: Homeowner Payment / Ledger Extraction ──────────────────────

class HomeownerPayment(BaseModel):
    """
    From Receivables Type Balances pages (47-53).
    Per-homeowner ledger showing: assessments, billing,
    adjustments, receipts, prepaid, and ending balance.
    """
    homeowner_id: str = Field(
        description="CINCSystems ID, e.g. 'TPB01', 'TPB22'"
    )
    homeowner_name: Optional[str] = None
    ownership_type: Optional[str] = Field(
        default=None,
        description="e.g. 'Owner'"
    )
    unit_or_address: str
    assessment_type: str = Field(
        description="e.g. 'Assessment - Homeowner 2026', 'PrePaid'"
    )
    prev_balance: float
    billing: float
    adjustments: float
    receipts: float
    prepaid: float
    ending_balance: float
    source_page: int


class CollectionStatus(str, Enum):
    """Delinquency escalation steps used by PMI Cross Timbers."""
    CURRENT = "current"
    STEP_1_REMINDER = "step_1_reminder"
    STEP_2_NOTICE = "step_2_notice"
    STEP_3_FINAL_NOTICE = "step_3_final_notice"
    STEP_4_COLLECTIONS = "step_4_collections"
    PAYMENT_PLAN = "payment_plan"


class HomeownerAgingEntry(BaseModel):
    """
    From the Homeowner Aging Report (pages 9-13).
    Shows delinquent homeowners with 30/60/90+ day aging buckets,
    collection status, and attorney assignments.
    """
    homeowner_id: str = Field(
        description="CINCSystems ID, e.g. 'TPB55'"
    )
    homeowner_name: str
    address: str
    ownership_type: str = Field(
        description="e.g. 'Owner', 'Payment Plan'"
    )
    last_payment_amount: Optional[float] = None
    last_payment_date: Optional[date] = None
    current_due: float = Field(description="Amount currently due")
    over_30: float = Field(description="Amount 30+ days overdue")
    over_60: float = Field(description="Amount 60+ days overdue")
    over_90: float = Field(description="Amount 90+ days overdue")
    total_balance: float
    collection_status: Optional[CollectionStatus] = None
    collection_attorney: Optional[str] = Field(
        default=None,
        description="e.g. 'Schwartz Vays LLC'"
    )
    assessment_type: Optional[str] = Field(
        default=None,
        description="e.g. 'Assessment - Homeowner (Delinquent Fee) 2024'"
    )
    source_page: int


# ─── 2d: Income Statement Extraction (NEW) ──────────────────────────

class IncomeStatementLine(BaseModel):
    """
    Line item from the Income Statement — Budget vs Actual.
    Two statement types exist: Operating (pages 4-5) and Reserve (page 6).
    Key for detecting budget overruns and revenue shortfalls.
    """
    account_code: str = Field(
        description="GL code, e.g. '4000-00', '5752-00'"
    )
    account_name: str = Field(
        description="e.g. 'Assessment General', 'Electricity'"
    )
    statement_type: Literal["operating", "reserve"]
    current_period_budget: float
    current_period_actual: float
    current_period_variance: float
    ytd_budget: float
    ytd_actual: float
    ytd_variance: float
    annual_budget: float
    source_page: int


# ══════════════════════════════════════════════════════════════════════
# LAYER 3: Balance Sheet Extraction
# ══════════════════════════════════════════════════════════════════════

class BalanceSheetLine(BaseModel):
    """
    Line item from the Balance Sheet (page 2).
    Shows Operating vs Reserve breakdown for each account.
    """
    account_name: str = Field(
        description="e.g. 'SouthState Bank - Operating Acct', 'Accounts Payable'"
    )
    category: str = Field(
        description="Top-level category: 'Assets', 'Liabilities & Equity'"
    )
    subcategory: str = Field(
        description="e.g. 'CASH - OPERATING', 'CASH- RESERVE', 'ACCOUNTS PAYABLE'"
    )
    operating_amount: float
    reserve_amount: float
    total_amount: float
    source_page: int


# ══════════════════════════════════════════════════════════════════════
# LAYER 4: Audit Result (Node 3 — Deterministic Auditor)
# ══════════════════════════════════════════════════════════════════════

class AuditResult(BaseModel):
    """
    Output of the Deterministic Auditor — PURE PYTHON MATH, not LLM math.

    Cross-checks performed:
    1. Bank deposits (operating) ≈ Homeowner payments received
    2. Vendor invoices from list ≈ Bank withdrawals (operating)
    3. Invoice list totals ≈ Sum of individual vendor invoices
    4. Bank statement ending balance ≈ Balance sheet cash amount
    5. Income statement actuals ≈ Bank transaction totals
    6. Reserve fund deposits match reserve income statement
    """
    # --- Operating fund checks ---
    total_deposits_operating: float
    total_withdrawals_operating: float
    total_homeowner_payments: float
    total_vendor_invoices_from_list: float = Field(
        description="Sum from CINCSystems invoice list"
    )
    total_vendor_invoices_individual: float = Field(
        description="Sum from individual vendor invoice PDFs"
    )
    deposit_vs_payment_gap: float = Field(
        description="Operating deposits minus homeowner payments; should be ~0"
    )
    invoice_list_vs_withdrawal_gap: float = Field(
        description="Invoice list total minus operating withdrawals; should be ~0"
    )

    # --- Reserve fund checks ---
    total_deposits_reserve: float
    total_withdrawals_reserve: float
    reserve_fund_balance: float

    # --- Cross-document consistency checks ---
    invoice_list_vs_individual_match: bool = Field(
        description="Do CINCSystems invoice list totals match individual invoice PDFs?"
    )
    bank_ending_vs_balance_sheet_match: bool = Field(
        description="Does bank statement ending balance match balance sheet cash?"
    )
    income_actuals_vs_bank_match: bool = Field(
        description="Do income statement actuals reconcile with bank transactions?"
    )

    # --- Budget analysis ---
    budget_overrun_categories: list[str] = Field(
        default_factory=list,
        description="Expense categories where actual > budget"
    )
    revenue_shortfall_categories: list[str] = Field(
        default_factory=list,
        description="Income categories where actual < budget"
    )

    # --- Delinquency summary ---
    total_delinquent_balance: float = Field(
        default=0.0,
        description="Total unpaid HOA dues across all homeowners"
    )
    accounts_in_collections: int = Field(
        default=0,
        description="Number of accounts at Step 4 (collections)"
    )

    # --- Overall assessment ---
    flagged_issues: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool
