"""
Homeowner Ledger Report Generator
==================================
Produces a clean, one-page-readable report from the homeowner ledger extraction.
Data appears in the same order as the PDF for easy visual verification.

Usage:
    python -m src.reports.homeowner_ledger_report
    python -m src.reports.homeowner_ledger_report --json data/extraction_homeowner_ledger.json
"""
import sys
import json
import argparse
from datetime import datetime

# ── Report formatting ────────────────────────────────────────────────

WIDTH = 120
COL_HDR = (
    f"{'#':>3} {'Unit':>6} {'Name':<32} "
    f"{'Prev Bal':>11} {'Billing':>11} {'Receipts':>11} "
    f"{'Adjust':>11} {'PrePaid':>11} {'Ending':>11}"
)
SEP = '─' * WIDTH
THIN_SEP = '-' * WIDTH


def fmt_dollar(val):
    """Format dollar value: (1,234.56) for negative, 1,234.56 for positive."""
    if val < -0.005:
        return f"({abs(val):>,.2f})"
    elif val > 0.005:
        return f"{val:>,.2f} "
    else:
        return f"{'0.00':>s} "


def fmt_row(num, unit, name, prev, bill, rcpt, adj, pp, ending):
    """Format a single homeowner row."""
    return (
        f"{num:>3} {unit:>6} {name[:32]:<32} "
        f"{fmt_dollar(prev):>11} {fmt_dollar(bill):>11} {fmt_dollar(rcpt):>11} "
        f"{fmt_dollar(adj):>11} {fmt_dollar(pp):>11} {fmt_dollar(ending):>11}"
    )


def generate_report(records, report_date=None):
    """Generate the full report as a list of lines."""
    if report_date is None:
        report_date = datetime.now().strftime('%B %d, %Y')

    lines = []
    lines.append('=' * WIDTH)
    lines.append('  BRIARWYCK OWNERS ASSOCIATION — HOMEOWNER LEDGER REPORT')
    lines.append(f'  Receivables Type Balances (Pages 47-53)')
    lines.append(f'  Generated: {report_date}')
    lines.append('=' * WIDTH)
    lines.append('')

    # Column headers
    lines.append(COL_HDR)
    lines.append(SEP)

    # Data rows (already in PDF order)
    totals = {'prev_balance': 0, 'billing': 0, 'receipts': 0,
              'adjustments': 0, 'prepaid': 0, 'ending_balance': 0}
    balance_due_count = 0
    prepaid_count = 0
    zero_count = 0

    for i, r in enumerate(records, 1):
        row = fmt_row(
            i, r['unit_id'], r['homeowner_name'],
            r['prev_balance'], r['billing'], r['receipts'],
            r['adjustments'], r['prepaid'], r['ending_balance']
        )
        lines.append(row)

        # Accumulate totals
        for col in totals:
            totals[col] += r[col]

        # Classify
        if r['ending_balance'] > 0.005:
            balance_due_count += 1
        elif r['ending_balance'] < -0.005:
            prepaid_count += 1
        else:
            zero_count += 1

    # Totals row
    lines.append(SEP)
    lines.append(
        f"{'':>3} {'':>6} {'TOTALS (' + str(len(records)) + ' accounts)':<32} "
        f"{fmt_dollar(totals['prev_balance']):>11} {fmt_dollar(totals['billing']):>11} "
        f"{fmt_dollar(totals['receipts']):>11} {fmt_dollar(totals['adjustments']):>11} "
        f"{fmt_dollar(totals['prepaid']):>11} {fmt_dollar(totals['ending_balance']):>11}"
    )
    lines.append('=' * WIDTH)

    # Summary stats
    lines.append('')
    lines.append('  SUMMARY')
    lines.append(THIN_SEP)
    lines.append(f'  Total accounts with activity:  {len(records):>5}')
    lines.append(f'  Balance due (owe money):       {balance_due_count:>5}')
    lines.append(f'  PrePaid / Credit:              {prepaid_count:>5}')
    lines.append(f'  Current (zero balance):        {zero_count:>5}')
    lines.append(f'  Total ending balance:        ${totals["ending_balance"]:>12,.2f}')
    lines.append(THIN_SEP)

    # Note about missing homeowners
    lines.append('')
    lines.append(f'  NOTE: This report includes only the {len(records)} accounts that had')
    lines.append(f'  activity during this period (pages 47-53). Accounts with no')
    lines.append(f'  activity are not listed in the Receivables Type Balances report.')
    lines.append(f'  The full roster (~96 units) appears on the Aging Report (pages 9-13).')
    lines.append('')

    return '\n'.join(lines)


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='Homeowner Ledger Report')
    parser.add_argument('--json', default='data/extraction_homeowner_ledger.json',
                        help='Path to extraction JSON')
    parser.add_argument('--output', '-o', default=None,
                        help='Output file (default: print to stdout)')
    args = parser.parse_args()

    with open(args.json, 'r', encoding='utf-8') as f:
        records = json.load(f)

    report = generate_report(records)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f'Report saved to {args.output}')
    else:
        print(report)
