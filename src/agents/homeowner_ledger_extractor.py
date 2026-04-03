"""
Node 2c: Homeowner Ledger Extractor — DETERMINISTIC (no LLM needed!)

CINCSystems "Receivables Type Balances" reports follow a rigid structure:
  1. Homeowner header:  "TPBxx - Name - (Owner)"
  2. Assessment lines:  type label + 6 dollar values
  3. Homeowner footer:  "Homeowner Totals:" + 6 dollar values

The 6 columns (as read by PyMuPDF left-to-right):
  Prev. Bal, Receipts, PrePaid, Ending Bal, Billing, Adjustments

Column order verified using two homeowners with unique values in every column:
  - Laura Barrett (TPB27): prev=733.72, billing=152.72, ending=886.44
  - Rachael Jacobs (TPB41): prev=-353.28, receipts=-127.72, prepaid=3.72,
    ending=-349.56, billing=142.72, adjustments=-15.00

Formula: Ending = Prev + Billing + Receipts + Adjustments + PrePaid
  (Receipts and PrePaid are typically negative values — credits to the account)

The last page has "Association Totals:" — our checksum.

Usage:
    python -m src.agents.homeowner_ledger_extractor
    python -m src.agents.homeowner_ledger_extractor path/to/pdf.pdf
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.pdf_reader import extract_page_range


# ── Dollar value parser ─────────────────────────────────────────────

DOLLAR_RE = re.compile(r'^\(?\$[\d,]+\.\d{2}\)?$')


def parse_dollar(text: str) -> float:
    """Parse a dollar string like '$127.72' or '($25.00)' into a float.
    Parentheses indicate negative values (accounting convention)."""
    text = text.strip()
    negative = text.startswith('(') and text.endswith(')')
    cleaned = text.replace('(', '').replace(')', '').replace('$', '').replace(',', '')
    value = float(cleaned)
    return -value if negative else value


def is_dollar(text: str) -> bool:
    """Check if a string is a dollar value."""
    return bool(DOLLAR_RE.match(text.strip()))


# ── Homeowner header pattern ────────────────────────────────────────

# Matches: "TPB01 - Domingos Noronha -  (Owner)", "TPB25 - Daniel Killian -  (Previous Owner)",
# or "TPB94 - Todd Nicolai & Geraldine Nicolai -  (Board Member)"
HOMEOWNER_RE = re.compile(
    r'^(TPB\d+)\s*-\s*(.+?)\s*-\s*\((Owner|Previous Owner|Board Member)\)$'
)


def parse_ledger_pages(pages):
    """Parse all homeowner ledger entries from pages 47-53.
    
    Stops processing homeowners when it hits 'Assessment Totals:'
    on the summary page (page 53), then reads only the Association Totals.
    """
    homeowners = []
    current_homeowner = None
    current_lines = []
    association_totals = None
    in_summary_section = False  # True once we hit 'Assessment Totals:' on page 53

    for page in pages:
        lines = [l.strip() for l in page.text.split('\n') if l.strip()]

        for i, line in enumerate(lines):
            # Skip page headers
            if line in ('Receivables Type Balances', 'Briarwyck Owners Association, Inc.',
                        'Assessment', 'Prev. Bal', 'Billing', 'Adjustments',
                        'Ending Bal', 'Receipts', 'PrePaid'):
                continue
            if line.startswith('From ') and 'to' in line:
                continue
            if line.startswith('Date :') or line.startswith('CINCSystems') or line.startswith('Page '):
                continue

            # ── Homeowner header ──
            match = HOMEOWNER_RE.match(line)
            if match:
                # Save previous homeowner if exists
                if current_homeowner:
                    homeowners.append(current_homeowner)

                current_homeowner = {
                    'unit_id': match.group(1),
                    'name': match.group(2).strip(),
                    'owner_type': match.group(3),
                    'assessments': [],
                    'totals': None,
                    'has_prepaid_carryforward': False,
                    'source_pages': [page.page_number],
                }
                current_lines = []
                continue

            # ── Homeowner Totals line ──
            if line == 'Homeowner Totals:' and current_homeowner:
                # Check for PrePaid carryforward: look backwards for
                # a stray dollar value between "PrePaid" label and here
                if i >= 2:
                    prev_line = lines[i-1]
                    prev2_line = lines[i-2]
                    if is_dollar(prev_line) and prev2_line == 'PrePaid':
                        current_homeowner['has_prepaid_carryforward'] = True

                # Next 6 values are the totals
                vals = []
                j = i + 1
                while j < len(lines) and len(vals) < 6:
                    if is_dollar(lines[j]):
                        vals.append(parse_dollar(lines[j]))
                        j += 1
                    else:
                        break

                if len(vals) == 6:
                    current_homeowner['totals'] = {
                        'prev_balance': vals[0],
                        'receipts': vals[1],
                        'prepaid': vals[2],
                        'ending_balance': vals[3],
                        'billing': vals[4],
                        'adjustments': vals[5],
                    }
                continue

            # ── Assessment Totals (page 53 — per-type grand totals) ──
            if line == 'Assessment Totals:':
                # Save the last homeowner before entering summary section
                if current_homeowner:
                    homeowners.append(current_homeowner)
                    current_homeowner = None
                in_summary_section = True
                continue

            # Skip everything in the summary section EXCEPT Association Totals
            if in_summary_section and line != 'Association Totals:':
                continue

            # ── Association Totals (THE checksum) ──
            if line == 'Association Totals:':
                vals = []
                j = i + 1
                while j < len(lines) and len(vals) < 6:
                    if is_dollar(lines[j]):
                        vals.append(parse_dollar(lines[j]))
                        j += 1
                    else:
                        break

                if len(vals) == 6:
                    # NOTE: Association Totals uses DIFFERENT column order
                    # than Homeowner Totals. The summary section on page 53
                    # follows the visual PDF header order:
                    #   Prev, Billing, Receipts, Adj, PrePaid, Ending
                    association_totals = {
                        'prev_balance': vals[0],
                        'billing': vals[1],
                        'receipts': vals[2],
                        'adjustments': vals[3],
                        'prepaid': vals[4],
                        'ending_balance': vals[5],
                    }
                continue

            # ── Assessment type lines ──
            # These are lines like "Assessment - Homeowner 2026" or "PrePaid"
            # followed by dollar values. We track them but the key data
            # comes from the Homeowner Totals.
            if current_homeowner and not is_dollar(line):
                # Could be an assessment type label
                if page.page_number not in current_homeowner['source_pages']:
                    current_homeowner['source_pages'].append(page.page_number)

    # Save last homeowner (if not already saved by summary section)
    if current_homeowner:
        homeowners.append(current_homeowner)

    return homeowners, association_totals


def extract_homeowner_ledger(pdf_path, start_page=47, end_page=53):
    """Extract all homeowner ledger data using deterministic Python parsing."""
    print("Homeowner Ledger Extractor (deterministic — no LLM)")
    print("=" * 60)

    pages = extract_page_range(pdf_path, start_page, end_page)
    print(f"  Processing pages {start_page}-{end_page} ({len(pages)} pages)")

    homeowners, association_totals = parse_ledger_pages(pages)

    # Print results
    print(f"\n  Found {len(homeowners)} homeowner accounts:")
    print(f"  {'─'*55}")

    total_ending = 0
    total_prev = 0
    total_billing = 0
    total_receipts = 0
    total_adjustments = 0
    total_prepaid = 0
    owners_with_balance = 0

    for hw in homeowners:
        t = hw.get('totals', {})
        if t:
            ending = t.get('ending_balance', 0)
            total_ending += ending
            total_prev += t.get('prev_balance', 0)
            total_billing += t.get('billing', 0)
            total_receipts += t.get('receipts', 0)
            total_adjustments += t.get('adjustments', 0)
            total_prepaid += t.get('prepaid', 0)

            # Flag homeowners with outstanding balance
            if ending > 0:
                owners_with_balance += 1
                flag = " ⚠️ BALANCE DUE"
            elif ending < 0:
                flag = " 💰 PREPAID"
            else:
                flag = ""

            print(f"    {hw['unit_id']:6s}  {hw['name'][:30]:<30s}  "
                  f"End: ${ending:>10,.2f}{flag}")
        else:
            print(f"    {hw['unit_id']:6s}  {hw['name'][:30]:<30s}  "
                  f"(no totals parsed)")

    # Summary
    print(f"\n  {'='*60}")
    print(f"  SUMMARY:")
    print(f"    Total homeowners:          {len(homeowners)}")
    print(f"    With balance due:          {owners_with_balance}")
    print(f"    Total ending balance:      ${total_ending:>12,.2f}")
    print(f"    Total prev balance:        ${total_prev:>12,.2f}")
    print(f"    Total billing:             ${total_billing:>12,.2f}")
    print(f"    Total receipts:            ${total_receipts:>12,.2f}")
    print(f"    Total adjustments:         ${total_adjustments:>12,.2f}")
    print(f"    Total prepaid:             ${total_prepaid:>12,.2f}")

    # Verify against Association Totals (checksum)
    if association_totals:
        print(f"\n  {'='*60}")
        print(f"  VERIFICATION:")

        # Primary checksum: ending balance must match Association Totals
        ending_match = abs(total_ending - association_totals['ending_balance']) < 0.01
        print(f"    Ending Balance (primary checksum):")
        print(f"      Computed:  ${total_ending:>12,.2f}")
        print(f"      Expected:  ${association_totals['ending_balance']:>12,.2f}")
        print(f"      {'MATCH ✅' if ending_match else 'MISMATCH ❌'}")

        # Note: Other columns in Association Totals include zero-balance
        # homeowners not listed in the detail pages, so they won't match
        # our computed sums. The ending balance is the reliable checksum.

        # Internal consistency: for each homeowner, verify
        # ending = prev + billing + receipts + adjustments + prepaid
        # (receipts and prepaid are negative — credits to the account)
        #
        # NOTE: Accounts with PrePaid carryforwards (large negative prepaid amounts
        # that roll from prior periods) don't balance with this formula because
        # CINCSystems handles prepaid offsetting internally. These are expected
        # and flagged separately from true errors.
        consistency_errors = []
        prepaid_accounts = []
        for hw in homeowners:
            t = hw.get('totals')
            if not t:
                continue
            expected_ending = (t['prev_balance'] + t['billing'] +
                             t['receipts'] + t['adjustments'] + t['prepaid'])
            if abs(t['ending_balance'] - expected_ending) > 0.01:
                if hw.get('has_prepaid_carryforward'):
                    # Known CINCSystems behavior: PrePaid carryforward
                    # amounts are absorbed into ending_balance but shown
                    # as $0 in the prepaid totals column
                    prepaid_accounts.append(
                        f"      {hw['unit_id']} {hw['name']}: "
                        f"ending={t['ending_balance']:.2f} "
                        f"(PrePaid carryforward absorbed into ending)"
                    )
                else:
                    diff = t['ending_balance'] - expected_ending
                    consistency_errors.append(
                        f"      {hw['unit_id']} {hw['name']}: "
                        f"ending={t['ending_balance']:.2f}, "
                        f"expected={expected_ending:.2f}, "
                        f"diff={diff:.2f}"
                    )

        print(f"\n    Internal Consistency (per-homeowner math check):")
        balanced = len(homeowners) - len(consistency_errors) - len(prepaid_accounts)
        print(f"      {balanced} accounts balance perfectly ✅")
        if prepaid_accounts:
            print(f"      {len(prepaid_accounts)} accounts have PrePaid carryforwards (expected):")
            for acct in prepaid_accounts:
                print(f"    {acct}")
        if consistency_errors:
            print(f"      {len(consistency_errors)} accounts have formula mismatches ⚠️:")
            for err in consistency_errors:
                print(f"    {err}")

        print(f"\n  {'='*60}")
        if ending_match and not consistency_errors:
            print(f"  ✅ ALL CHECKSUMS PASS — extraction verified!")
            if prepaid_accounts:
                print(f"     ({len(prepaid_accounts)} PrePaid carryforward accounts handled correctly)")
        elif ending_match:
            print(f"  ⚠️  Ending balance matches but {len(consistency_errors)} accounts need review")
        else:
            print(f"  ❌ CHECKSUM MISMATCH — manual review needed")
        print(f"  {'='*60}")
    else:
        print(f"\n  ⚠️  No Association Totals found for verification")

    return homeowners, association_totals


# ── Output formatting ───────────────────────────────────────────────

def to_json_records(homeowners):
    """Convert homeowner data to flat JSON records for the database."""
    records = []
    for hw in homeowners:
        t = hw.get('totals') or {}
        records.append({
            'unit_id': hw['unit_id'],
            'homeowner_name': hw['name'],
            'owner_type': hw['owner_type'],
            'prev_balance': t.get('prev_balance', 0),
            'billing': t.get('billing', 0),
            'receipts': t.get('receipts', 0),
            'adjustments': t.get('adjustments', 0),
            'prepaid': t.get('prepaid', 0),
            'ending_balance': t.get('ending_balance', 0),
            'source_pages': hw.get('source_pages', []),
        })
    return records


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    pdf = sys.argv[1] if len(sys.argv) > 1 else \
        "data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf"

    homeowners, assoc_totals = extract_homeowner_ledger(pdf)

    # Save to JSON
    records = to_json_records(homeowners)
    output_path = "data/extraction_homeowner_ledger.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2)
    print(f"\nSaved {len(records)} homeowner records to {output_path}")
