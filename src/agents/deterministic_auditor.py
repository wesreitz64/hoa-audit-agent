"""
Node 3: Deterministic Auditor — Pure Python Financial Reconciliation

NO LLM CALLS. This is the "sandwich bread" layer — deterministic math
that cross-checks the outputs of the three extractors against each other.

Reconciliation Checks:
  1. Bank deposits (operating) ≈ Homeowner receipts (ledger)
  2. Bank withdrawals (operating) ≈ Invoice list payments
  3. Per-homeowner formula: Ending = Prev + Billing + Receipts + Adj + PrePaid
  4. Reserve fund transfer consistency (CincXfer out = CincXfer in)
  5. Rejected check detection and redeposit matching
  6. Net cash flow sanity
  7. 🚩 Unapproved check detection (RED FLAG — governance)

Usage:
    python -m src.agents.deterministic_auditor
    python -m src.agents.deterministic_auditor --verbose
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

BANK_JSON = DATA_DIR / "extraction_bank_statements.json"
LEDGER_JSON = DATA_DIR / "extraction_homeowner_ledger.json"
INVOICE_JSON = DATA_DIR / "extraction_invoice_list.json"

# Tolerance for floating-point comparison (pennies)
TOLERANCE = 0.01
# Tolerance for aggregate comparisons (catches rounding across many rows)
AGGREGATE_TOLERANCE = 1.00


# ──────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────

@dataclass
class ReconciliationCheck:
    """Result of a single reconciliation check."""
    name: str
    description: str
    source_a: str            # e.g. "Bank Statement"
    source_b: str            # e.g. "Homeowner Ledger"
    amount_a: float
    amount_b: float
    difference: float
    tolerance: float
    passed: bool
    details: list[str] = field(default_factory=list)
    severity: str = "info"   # "info", "warning", "critical"

    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return (
            f"{status} | {self.name}\n"
            f"       {self.source_a}: ${self.amount_a:>12,.2f}\n"
            f"       {self.source_b}: ${self.amount_b:>12,.2f}\n"
            f"       Difference:  ${self.difference:>12,.2f}  "
            f"(tolerance: ${self.tolerance:,.2f})"
        )


@dataclass
class HomeownerFormulaResult:
    """Result of per-homeowner balance formula check."""
    unit_id: str
    homeowner_name: str
    prev_balance: float
    billing: float
    receipts: float
    adjustments: float
    prepaid: float
    ending_balance: float
    computed_ending: float
    difference: float
    passed: bool
    has_prepaid_carryforward: bool = False

    def __str__(self):
        status = "✅" if self.passed else "❌"
        flag = " ⚡CARRYFORWARD" if self.has_prepaid_carryforward else ""
        return (
            f"  {status} {self.unit_id} ({self.homeowner_name}){flag}\n"
            f"     Prev({self.prev_balance:>9,.2f}) + Bill({self.billing:>9,.2f}) "
            f"+ Rcpt({self.receipts:>9,.2f}) + Adj({self.adjustments:>9,.2f}) "
            f"+ PreP({self.prepaid:>9,.2f}) = {self.computed_ending:>9,.2f}  "
            f"vs  Ending({self.ending_balance:>9,.2f})  Δ={self.difference:>8,.2f}"
        )


@dataclass
class AuditReport:
    """Complete deterministic audit output."""
    timestamp: str
    period: str

    # Aggregate checks
    checks: list[ReconciliationCheck] = field(default_factory=list)

    # Per-homeowner formula results
    homeowner_results: list[HomeownerFormulaResult] = field(default_factory=list)

    # Anomalies detected
    rejected_checks: list[dict] = field(default_factory=list)
    unapproved_checks: list[dict] = field(default_factory=list)
    pending_invoices: list[dict] = field(default_factory=list)
    unmatched_deposits: list[dict] = field(default_factory=list)
    unmatched_withdrawals: list[dict] = field(default_factory=list)

    # Summary
    total_checks: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    confidence_score: float = 0.0
    requires_human_review: bool = False
    flagged_issues: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────────────────────

def load_json(path: Path) -> list[dict]:
    """Load extracted JSON data with validation."""
    if not path.exists():
        print(f"  ❌ ERROR: {path.name} not found at {path}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"  ✓ Loaded {len(data)} records from {path.name}")
    return data


# ──────────────────────────────────────────────────────────────
# Check 1: Bank Deposits vs Homeowner Receipts
# ──────────────────────────────────────────────────────────────

def check_deposits_vs_receipts(
    bank_txns: list[dict],
    ledger: list[dict],
    verbose: bool = False,
) -> ReconciliationCheck:
    """
    Do bank deposits (operating account) reconcile with homeowner receipts?

    Bank side: Sum of all credits to operating account (8763)
    Ledger side: Sum of abs(receipts) for all homeowners

    These WON'T match exactly because:
    - Bank deposits include timing of check deposits
    - Ledger receipts reflect when CINCSystems recorded the payment
    - Rejected checks appear as both a credit and a debit
    - Some deposits may be non-homeowner (e.g., insurance refunds)

    But they should be CLOSE, and the difference should be explainable.
    """
    # Bank: all operating credits
    operating_credits = [
        t for t in bank_txns
        if t['transaction_type'] == 'credit' and t['account_type'] == 'operating'
    ]
    total_bank_deposits = sum(t['amount'] for t in operating_credits)

    # Ledger: absolute value of all receipts (receipts are negative in ledger)
    total_ledger_receipts = sum(abs(h['receipts']) for h in ledger)

    difference = total_bank_deposits - total_ledger_receipts

    details = [
        f"Bank operating credits: {len(operating_credits)} transactions",
        f"Homeowner ledger entries: {len(ledger)} accounts",
    ]

    # Identify rejected checks (they inflate bank deposits artificially)
    rejected = [
        t for t in bank_txns
        if t['transaction_type'] == 'debit'
        and 'REJECTED' in t['description'].upper()
    ]
    if rejected:
        rejected_total = sum(t['amount'] for t in rejected)
        details.append(
            f"Rejected checks found: {len(rejected)} totaling ${rejected_total:,.2f}"
        )
        details.append(
            f"Adjusted difference (removing rejected): "
            f"${difference - rejected_total:,.2f}"
        )

    # Check for non-homeowner deposits
    non_homeowner = [
        t for t in operating_credits
        if not any(kw in t['description'].upper() for kw in [
            'DEPOSIT', 'ONLINEPAY', 'PAYABLI', 'ASSN DUES'
        ])
    ]
    if non_homeowner:
        nh_total = sum(t['amount'] for t in non_homeowner)
        details.append(
            f"Non-homeowner deposits: {len(non_homeowner)} totaling ${nh_total:,.2f}"
        )

    if verbose:
        details.append("\n--- Bank Deposit Breakdown ---")
        # Group by description pattern
        patterns = {}
        for t in operating_credits:
            key = t['description'].split()[0] if t['description'] else 'UNKNOWN'
            if key not in patterns:
                patterns[key] = {'count': 0, 'total': 0.0}
            patterns[key]['count'] += 1
            patterns[key]['total'] += t['amount']
        for pattern, stats in sorted(patterns.items()):
            details.append(
                f"  {pattern}: {stats['count']} txns, ${stats['total']:,.2f}"
            )

    passed = abs(difference) <= AGGREGATE_TOLERANCE

    return ReconciliationCheck(
        name="Bank Deposits vs Homeowner Receipts",
        description="Operating account deposits should approximate homeowner payments received",
        source_a="Bank Operating Deposits",
        source_b="Homeowner Ledger Receipts (abs)",
        amount_a=total_bank_deposits,
        amount_b=total_ledger_receipts,
        difference=difference,
        tolerance=AGGREGATE_TOLERANCE,
        passed=passed,
        details=details,
        severity="critical" if not passed else "info",
    )


# ──────────────────────────────────────────────────────────────
# Check 2: Bank Withdrawals vs Invoice List
# ──────────────────────────────────────────────────────────────

def check_withdrawals_vs_invoices(
    bank_txns: list[dict],
    invoices: list[dict],
    verbose: bool = False,
) -> ReconciliationCheck:
    """
    Do bank withdrawals match the invoice list total?

    Bank side: Sum of all debits from operating account (8763),
               EXCLUDING rejected checks, inter-account transfers (CincXfer)
    Invoice side: Sum of all invoice amounts from CINCSystems list

    Note: Vendor Pay debits are invoice payments.
    Other debits (Auto Pay, EFT) are also invoice-related utility payments.
    """
    # Bank: all operating debits
    operating_debits = [
        t for t in bank_txns
        if t['transaction_type'] == 'debit' and t['account_type'] == 'operating'
    ]

    # Exclude non-invoice debits: rejected checks, inter-account transfers
    invoice_related_debits = [
        t for t in operating_debits
        if 'REJECTED' not in t['description'].upper()
        and 'CINCXFER' not in t['description'].upper()
    ]

    # Also separate out checks (may or may not be in invoice list)
    vendor_pay_debits = [
        t for t in invoice_related_debits
        if 'VENDOR PAY' in t['description'].upper()
    ]
    check_debits = [
        t for t in invoice_related_debits
        if t['description'].upper().startswith('CHECK')
    ]
    auto_debits = [
        t for t in invoice_related_debits
        if t not in vendor_pay_debits and t not in check_debits
    ]

    total_bank_withdrawals = sum(t['amount'] for t in invoice_related_debits)
    total_invoices = sum(inv['amount'] for inv in invoices)
    difference = total_bank_withdrawals - total_invoices

    details = [
        f"Operating debits (total): {len(operating_debits)}",
        f"  Vendor Pay: {len(vendor_pay_debits)} = ${sum(t['amount'] for t in vendor_pay_debits):,.2f}",
        f"  Checks:     {len(check_debits)} = ${sum(t['amount'] for t in check_debits):,.2f}",
        f"  Auto/ACH:   {len(auto_debits)} = ${sum(t['amount'] for t in auto_debits):,.2f}",
        f"Invoice list entries: {len(invoices)}",
    ]

    # Try to match each invoice to a bank debit
    if verbose:
        details.append("\n--- Invoice ↔ Bank Matching ---")
        for inv in invoices:
            matches = [
                t for t in invoice_related_debits
                if abs(t['amount'] - inv['amount']) < TOLERANCE
            ]
            status = "✅" if matches else "⚠️"
            details.append(
                f"  {status} {inv['vendor_name']}: ${inv['amount']:,.2f} "
                f"({inv['payment_type']}) — {len(matches)} bank match(es)"
            )

    passed = abs(difference) <= AGGREGATE_TOLERANCE

    return ReconciliationCheck(
        name="Bank Withdrawals vs Invoice List",
        description="Operating account payments should match CINCSystems approved invoices",
        source_a="Bank Operating Withdrawals (excl. rejected/transfers)",
        source_b="CINCSystems Invoice List",
        amount_a=total_bank_withdrawals,
        amount_b=total_invoices,
        difference=difference,
        tolerance=AGGREGATE_TOLERANCE,
        passed=passed,
        details=details,
        severity="critical" if not passed else "info",
    )


# ──────────────────────────────────────────────────────────────
# Check 3: Per-Homeowner Formula Verification
# ──────────────────────────────────────────────────────────────

def check_homeowner_formulas(
    ledger: list[dict],
    verbose: bool = False,
) -> list[HomeownerFormulaResult]:
    """
    For each homeowner, verify:
      Ending = Prev + Billing + Receipts + Adjustments + PrePaid

    Accounts with PrePaid carryforward (Lesson #16) will NOT balance
    and should be flagged but NOT counted as errors.
    """
    results = []

    for h in ledger:
        computed = (
            h['prev_balance']
            + h['billing']
            + h['receipts']
            + h['adjustments']
            + h['prepaid']
        )
        # Use round to avoid floating-point artifacts
        computed = round(computed, 2)
        actual = round(h['ending_balance'], 2)
        diff = round(actual - computed, 2)
        passed = abs(diff) < TOLERANCE

        # Detect PrePaid carryforward pattern (Lesson #16):
        # CINCSystems zeroes out the PrePaid column in the Homeowner Totals
        # row, but absorbs the carryforward amount directly into Ending Bal.
        # Indicator: prepaid==$0 in totals AND formula doesn't balance AND
        # the actual ending is MORE negative than computed (hidden credit).
        #
        # Example: TPB96 (Carolyn Jobe) — computed=-21.28, actual=-379.44
        #   The PrePaid line item has ($358.16) but Totals shows $0.00.
        #   diff = -379.44 - (-21.28) = -358.16 (exactly the hidden PrePaid)
        has_carryforward = False
        if not passed and h['prepaid'] == 0.0 and diff < -TOLERANCE:
            has_carryforward = True

        results.append(HomeownerFormulaResult(
            unit_id=h['unit_id'],
            homeowner_name=h['homeowner_name'],
            prev_balance=h['prev_balance'],
            billing=h['billing'],
            receipts=h['receipts'],
            adjustments=h['adjustments'],
            prepaid=h['prepaid'],
            ending_balance=actual,
            computed_ending=computed,
            difference=diff,
            passed=passed,
            has_prepaid_carryforward=has_carryforward,
        ))

    return results


# ──────────────────────────────────────────────────────────────
# Check 4: Reserve Fund Transfer Consistency
# ──────────────────────────────────────────────────────────────

def check_reserve_transfers(
    bank_txns: list[dict],
    verbose: bool = False,
) -> ReconciliationCheck:
    """
    CincXfer debit from operating should equal CincXfer credit to reserve.
    These are inter-account reserve fund contributions.
    """
    # Operating side: debit with CincXfer
    xfer_out = [
        t for t in bank_txns
        if 'CINCXFER' in t['description'].upper()
        and t['transaction_type'] == 'debit'
        and t['account_type'] == 'operating'
    ]

    # Reserve side: credit with CincXfer
    xfer_in = [
        t for t in bank_txns
        if 'CINCXFER' in t['description'].upper()
        and t['transaction_type'] == 'credit'
        and t['account_type'] == 'reserve'
    ]

    total_out = sum(t['amount'] for t in xfer_out)
    total_in = sum(t['amount'] for t in xfer_in)
    difference = total_out - total_in

    details = [
        f"Operating → Reserve transfers: {len(xfer_out)}",
        f"Reserve ← Operating transfers: {len(xfer_in)}",
    ]

    if verbose:
        for t in xfer_out:
            details.append(f"  OUT: {t['transaction_date']} ${t['amount']:,.2f} ({t['description']})")
        for t in xfer_in:
            details.append(f"  IN:  {t['transaction_date']} ${t['amount']:,.2f} ({t['description']})")

    passed = abs(difference) <= TOLERANCE

    return ReconciliationCheck(
        name="Reserve Fund Transfer Consistency",
        description="CincXfer out of operating must equal CincXfer into reserve",
        source_a="Operating CincXfer (debit)",
        source_b="Reserve CincXfer (credit)",
        amount_a=total_out,
        amount_b=total_in,
        difference=difference,
        tolerance=TOLERANCE,
        passed=passed,
        details=details,
        severity="critical" if not passed else "info",
    )


# ──────────────────────────────────────────────────────────────
# Check 5: Rejected Check Detection
# ──────────────────────────────────────────────────────────────

def detect_rejected_checks(
    bank_txns: list[dict],
    verbose: bool = False,
) -> list[dict]:
    """
    Find rejected checks and attempt to match them with redeposits.

    Pattern: A check deposited on date X appears as a credit,
    then later appears as a debit with "REJECTED FOR POOR IMAGE QUALITY".
    The same check should be redeposited later.
    """
    rejected = []

    reject_txns = [
        t for t in bank_txns
        if t['transaction_type'] == 'debit'
        and 'REJECTED' in t['description'].upper()
    ]

    for rtx in reject_txns:
        amount = rtx['amount']
        # Find potential redeposits (same amount, later date, credit)
        redeposits = [
            t for t in bank_txns
            if t['transaction_type'] == 'credit'
            and abs(t['amount'] - amount) < TOLERANCE
            and t['transaction_date'] > rtx['transaction_date']
            and t['account_type'] == 'operating'
        ]

        rejected.append({
            'description': rtx['description'],
            'amount': amount,
            'date': rtx['transaction_date'],
            'redeposit_found': len(redeposits) > 0,
            'redeposit_count': len(redeposits),
            'redeposit_dates': [t['transaction_date'] for t in redeposits],
        })

    return rejected


# ──────────────────────────────────────────────────────────────
# Check 7: 🚩 Unapproved Check Detection (RED FLAG)
# ──────────────────────────────────────────────────────────────

def detect_unapproved_checks(
    bank_txns: list[dict],
    invoices: list[dict],
    verbose: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    RED FLAG: Find checks that cleared the bank but do NOT appear
    on the CINCSystems approved Invoice List.

    The Invoice List (pages 7-8) is the official record of all vendor
    payments approved by the property manager. Any check that clears
    the bank without appearing on this list bypassed the standard
    approval process.

    Returns:
        (unapproved_checks, pending_invoices)
        - unapproved_checks: bank debits with no invoice list match
        - pending_invoices: invoices with no bank debit match (timing)
    """
    # Get all check debits from operating account
    check_debits = [
        t for t in bank_txns
        if t['transaction_type'] == 'debit'
        and t['account_type'] == 'operating'
        and t['description'].upper().startswith('CHECK')
    ]

    # Get all invoice amounts for matching
    invoice_amounts = [inv['amount'] for inv in invoices]

    # Find checks with no matching invoice amount
    unapproved = []
    matched_invoice_indices = set()

    for check in check_debits:
        found_match = False
        for i, inv in enumerate(invoices):
            if i in matched_invoice_indices:
                continue
            if abs(check['amount'] - inv['amount']) < TOLERANCE:
                matched_invoice_indices.add(i)
                found_match = True
                break
        if not found_match:
            unapproved.append({
                'description': check['description'],
                'amount': check['amount'],
                'date': check['transaction_date'],
                'source_page': check.get('source_page'),
                'flag': 'UNAPPROVED — not on CINCSystems Invoice List',
            })

    # Also find invoices that didn't match any bank debit
    # (these are timing issues — approved but not yet cleared)
    all_operating_debits = [
        t for t in bank_txns
        if t['transaction_type'] == 'debit'
        and t['account_type'] == 'operating'
        and 'REJECTED' not in t['description'].upper()
        and 'CINCXFER' not in t['description'].upper()
    ]
    debit_amounts_used = set()
    pending = []

    for inv in invoices:
        found = False
        for j, deb in enumerate(all_operating_debits):
            if j in debit_amounts_used:
                continue
            if abs(deb['amount'] - inv['amount']) < TOLERANCE:
                debit_amounts_used.add(j)
                found = True
                break
        # Also check if the invoice can be matched by summing
        # multiple debits (e.g., PMI $980.50 = $824 + $156.50)
        if not found:
            # Try to find a combination of unmatched debits that sum to invoice
            remaining = [
                deb for j, deb in enumerate(all_operating_debits)
                if j not in debit_amounts_used
            ]
            # Simple 2-debit combination check
            for a_idx, a in enumerate(remaining):
                for b_idx, b in enumerate(remaining):
                    if a_idx >= b_idx:
                        continue
                    if abs(a['amount'] + b['amount'] - inv['amount']) < TOLERANCE:
                        found = True
                        break
                if found:
                    break

        if not found:
            pending.append({
                'vendor_name': inv['vendor_name'],
                'amount': inv['amount'],
                'payment_type': inv.get('payment_type', 'Unknown'),
                'paid_date': inv.get('paid_date'),
                'flag': 'PENDING — approved but not yet cleared bank',
            })

    return unapproved, pending


# ──────────────────────────────────────────────────────────────
# Check 6: Net Cash Flow Sanity
# ──────────────────────────────────────────────────────────────

def check_net_cash_flow(
    bank_txns: list[dict],
    verbose: bool = False,
) -> ReconciliationCheck:
    """
    Operating account net cash flow:
      Total Credits - Total Debits = Net Change

    This is informational — we can't verify without beginning/ending
    balances on the bank statement, but it's useful context.
    """
    op_credits = sum(
        t['amount'] for t in bank_txns
        if t['transaction_type'] == 'credit' and t['account_type'] == 'operating'
    )
    op_debits = sum(
        t['amount'] for t in bank_txns
        if t['transaction_type'] == 'debit' and t['account_type'] == 'operating'
    )
    net = op_credits - op_debits

    details = [
        f"Operating credits:  {sum(1 for t in bank_txns if t['transaction_type']=='credit' and t['account_type']=='operating')} transactions",
        f"Operating debits:   {sum(1 for t in bank_txns if t['transaction_type']=='debit' and t['account_type']=='operating')} transactions",
        f"Net cash flow: ${net:>+,.2f} ({'positive — more in than out' if net >= 0 else 'negative — more out than in'})",
    ]

    return ReconciliationCheck(
        name="Operating Net Cash Flow",
        description="Total deposits minus total withdrawals for the period",
        source_a="Operating Credits",
        source_b="Operating Debits",
        amount_a=op_credits,
        amount_b=op_debits,
        difference=net,
        tolerance=0,  # Informational only
        passed=True,  # Always passes — it's informational
        details=details,
        severity="info",
    )


# ──────────────────────────────────────────────────────────────
# Main Audit Runner
# ──────────────────────────────────────────────────────────────

def run_audit(verbose: bool = False) -> AuditReport:
    """Execute all deterministic reconciliation checks."""

    print(f"\n{'='*70}")
    print(f"  🔍 DETERMINISTIC AUDITOR — Node 3")
    print(f"  Pure Python Math Reconciliation Engine")
    print(f"  No LLM calls. No AI. Just arithmetic and logic.")
    print(f"{'='*70}\n")

    # Load all extracted data
    print("Loading extracted data...")
    bank_txns = load_json(BANK_JSON)
    ledger = load_json(LEDGER_JSON)
    invoices = load_json(INVOICE_JSON)
    print()

    report = AuditReport(
        timestamp=datetime.now().isoformat(),
        period="February 2026",
    )

    # ── Run aggregate checks ──────────────────────────────────

    print("─" * 70)
    print("  AGGREGATE RECONCILIATION CHECKS")
    print("─" * 70)

    # Check 1: Deposits vs Receipts
    check1 = check_deposits_vs_receipts(bank_txns, ledger, verbose)
    report.checks.append(check1)
    print(f"\n{check1}")
    if verbose:
        for d in check1.details:
            print(f"       {d}")

    # Check 2: Withdrawals vs Invoices
    check2 = check_withdrawals_vs_invoices(bank_txns, invoices, verbose)
    report.checks.append(check2)
    print(f"\n{check2}")
    if verbose:
        for d in check2.details:
            print(f"       {d}")

    # Check 3: Reserve Transfers
    check4 = check_reserve_transfers(bank_txns, verbose)
    report.checks.append(check4)
    print(f"\n{check4}")
    if verbose:
        for d in check4.details:
            print(f"       {d}")

    # Check 4: Net Cash Flow (informational)
    check6 = check_net_cash_flow(bank_txns, verbose)
    report.checks.append(check6)
    print(f"\n{check6}")
    if verbose:
        for d in check6.details:
            print(f"       {d}")

    # ── Homeowner formula checks ──────────────────────────────

    print(f"\n{'─'*70}")
    print("  PER-HOMEOWNER FORMULA VERIFICATION")
    print(f"  Ending = Prev + Billing + Receipts + Adjustments + PrePaid")
    print(f"{'─'*70}")

    hw_results = check_homeowner_formulas(ledger, verbose)
    report.homeowner_results = hw_results

    passed = [r for r in hw_results if r.passed]
    failed_real = [r for r in hw_results if not r.passed and not r.has_prepaid_carryforward]
    carryforward = [r for r in hw_results if r.has_prepaid_carryforward]

    print(f"\n  Total homeowners:        {len(hw_results)}")
    print(f"  ✅ Formula balanced:     {len(passed)}")
    print(f"  ⚡ PrePaid carryforward: {len(carryforward)} (expected — see Lesson #16)")
    print(f"  ❌ Unexplained:          {len(failed_real)}")

    if verbose or failed_real:
        if failed_real:
            print(f"\n  --- Unexplained Formula Failures ---")
            for r in failed_real:
                print(r)

    if verbose and carryforward:
        print(f"\n  --- PrePaid Carryforward Accounts ---")
        for r in carryforward:
            print(r)

    if verbose and passed:
        print(f"\n  --- Balanced Accounts ---")
        for r in passed:
            print(r)

    # ── 🚩 RED FLAGS: Unapproved Checks ──────────────────────

    print(f"\n{'─'*70}")
    print("  🚩 RED FLAG CHECK: UNAPPROVED PAYMENTS")
    print(f"  Checks that cleared the bank WITHOUT Invoice List approval")
    print(f"{'─'*70}")

    unapproved, pending = detect_unapproved_checks(bank_txns, invoices, verbose)
    report.unapproved_checks = unapproved
    report.pending_invoices = pending

    if unapproved:
        total_unapproved = sum(u['amount'] for u in unapproved)
        print(f"\n  🔴 {len(unapproved)} UNAPPROVED CHECK(S) — ${total_unapproved:,.2f}")
        for u in unapproved:
            print(f"     • {u['description']}: ${u['amount']:,.2f} on {u['date']}")
            print(f"       ⚠️ {u['flag']}")
        report.red_flags.append(
            f"UNAPPROVED CHECKS: {len(unapproved)} check(s) totaling "
            f"${total_unapproved:,.2f} cleared the bank without appearing "
            f"on the CINCSystems approved Invoice List. Board should "
            f"investigate: {', '.join(u['description'] for u in unapproved)}"
        )
    else:
        print("\n  ✅ All checks match approved invoices")

    if pending:
        total_pending = sum(p['amount'] for p in pending)
        print(f"\n  🟡 {len(pending)} PENDING INVOICE(S) — ${total_pending:,.2f}")
        for p in pending:
            print(f"     • {p['vendor_name']}: ${p['amount']:,.2f} ({p['payment_type']})")
            print(f"       ℹ️ {p['flag']}")

    # ── Rejected checks ───────────────────────────────────────

    print(f"\n{'─'*70}")
    print("  REJECTED CHECK ANALYSIS")
    print(f"{'─'*70}")

    rejected = detect_rejected_checks(bank_txns, verbose)
    report.rejected_checks = rejected

    if rejected:
        for rc in rejected:
            redeposit_info = (
                f"redeposited on {', '.join(rc['redeposit_dates'])}"
                if rc['redeposit_found']
                else "⚠️ NO REDEPOSIT FOUND"
            )
            print(f"  ⚠️ {rc['description']}")
            print(f"     Amount: ${rc['amount']:,.2f} on {rc['date']}")
            print(f"     Status: {redeposit_info}")
    else:
        print("  ✅ No rejected checks found")

    # ── Compute summary ───────────────────────────────────────

    print(f"\n{'='*70}")
    print("  AUDIT SUMMARY")
    print(f"{'='*70}")

    aggregate_checks = report.checks
    aggregate_passed = sum(1 for c in aggregate_checks if c.passed)
    aggregate_total = len(aggregate_checks)

    formula_pass_rate = (len(passed) + len(carryforward)) / max(len(hw_results), 1)

    # Confidence = weighted average:
    #   60% aggregate checks, 30% homeowner formulas, 10% rejected check handling
    aggregate_score = aggregate_passed / max(aggregate_total, 1)
    rejected_score = 1.0 if all(rc['redeposit_found'] for rc in rejected) else 0.5 if rejected else 1.0

    confidence = (
        0.60 * aggregate_score
        + 0.30 * formula_pass_rate
        + 0.10 * rejected_score
    )
    confidence = round(confidence, 4)

    report.total_checks = aggregate_total + len(hw_results)
    report.checks_passed = aggregate_passed + len(passed) + len(carryforward)
    report.checks_failed = (aggregate_total - aggregate_passed) + len(failed_real)
    report.confidence_score = confidence
    report.requires_human_review = confidence < 0.80 or len(failed_real) > 0

    # Build flagged issues list
    for c in aggregate_checks:
        if not c.passed:
            report.flagged_issues.append(f"[{c.severity.upper()}] {c.name}: Δ=${c.difference:,.2f}")
    for r in failed_real:
        report.flagged_issues.append(
            f"[WARNING] {r.unit_id} ({r.homeowner_name}): formula off by ${r.difference:,.2f}"
        )
    for rc in rejected:
        if not rc['redeposit_found']:
            report.flagged_issues.append(
                f"[WARNING] Rejected check ${rc['amount']:,.2f} on {rc['date']} — no redeposit found"
            )
    for u in unapproved:
        report.flagged_issues.append(
            f"[RED FLAG] {u['description']}: ${u['amount']:,.2f} on {u['date']} — not on approved Invoice List"
        )

    print(f"\n  Aggregate checks:      {aggregate_passed}/{aggregate_total} passed")
    print(f"  Homeowner formulas:    {len(passed)}/{len(hw_results)} balanced "
          f"(+{len(carryforward)} carryforward)")
    print(f"  Rejected checks:       {len(rejected)} found, "
          f"{sum(1 for rc in rejected if rc['redeposit_found'])} redeposited")
    print(f"  Unapproved checks:     {len(unapproved)} found")
    print(f"\n  Confidence Score:      {confidence:.1%}")
    print(f"  Requires Human Review: {'YES' if report.requires_human_review else 'NO'}")

    if report.red_flags:
        print(f"\n  🚩 RED FLAGS ({len(report.red_flags)}):")
        for rf in report.red_flags:
            print(f"    🔴 {rf}")

    if report.flagged_issues:
        print(f"\n  Flagged Issues ({len(report.flagged_issues)}):")
        for issue in report.flagged_issues:
            print(f"    • {issue}")

    print(f"\n{'='*70}\n")

    return report


def save_audit_report(report: AuditReport, output_path: Optional[Path] = None):
    """Save audit results to JSON for downstream consumption."""
    if output_path is None:
        output_path = DATA_DIR / "audit_result.json"

    result = {
        "timestamp": report.timestamp,
        "period": report.period,
        "summary": {
            "total_checks": report.total_checks,
            "checks_passed": report.checks_passed,
            "checks_failed": report.checks_failed,
            "confidence_score": report.confidence_score,
            "requires_human_review": report.requires_human_review,
        },
        "aggregate_checks": [
            {
                "name": c.name,
                "source_a": c.source_a,
                "amount_a": c.amount_a,
                "source_b": c.source_b,
                "amount_b": c.amount_b,
                "difference": c.difference,
                "passed": c.passed,
                "severity": c.severity,
                "details": c.details,
            }
            for c in report.checks
        ],
        "homeowner_formula_results": {
            "total": len(report.homeowner_results),
            "passed": sum(1 for r in report.homeowner_results if r.passed),
            "carryforward": sum(1 for r in report.homeowner_results if r.has_prepaid_carryforward),
            "failed": sum(
                1 for r in report.homeowner_results
                if not r.passed and not r.has_prepaid_carryforward
            ),
            "failures": [
                {
                    "unit_id": r.unit_id,
                    "homeowner_name": r.homeowner_name,
                    "computed_ending": r.computed_ending,
                    "actual_ending": r.ending_balance,
                    "difference": r.difference,
                    "has_prepaid_carryforward": r.has_prepaid_carryforward,
                }
                for r in report.homeowner_results
                if not r.passed
            ],
        },
        "rejected_checks": report.rejected_checks,
        "red_flags": {
            "unapproved_checks": report.unapproved_checks,
            "pending_invoices": report.pending_invoices,
            "summary": report.red_flags,
        },
        "flagged_issues": report.flagged_issues,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    print(f"  📄 Audit report saved to {output_path.name}")
    return output_path


# ──────────────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Node 3: Deterministic Auditor — Financial Reconciliation Engine"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed breakdown of every check"
    )
    parser.add_argument(
        "--save", "-s", action="store_true",
        help="Save audit report to JSON"
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Custom output path for audit report JSON"
    )
    args = parser.parse_args()

    report = run_audit(verbose=args.verbose)

    if args.save:
        save_audit_report(report, args.output)
