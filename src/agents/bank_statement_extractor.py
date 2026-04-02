"""
Node 2b: Bank Statement Extractor — DETERMINISTIC (no LLM needed!)

SouthState Bank statements have perfectly structured text that PyMuPDF
extracts in a predictable 3-line pattern (date, description, amount).
We parse this with Python regex — zero API calls, instant, 100% reliable.

This is a key lesson: if the text is structured enough, skip the LLM entirely.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.utils.pdf_reader import extract_pages


def parse_bank_page(text, page_num, account_type, account_last4):
    """Parse transactions from a single bank statement page using regex."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    transactions = []
    
    # Section tracking
    current_section = None
    credit_sections = {'Deposits', 'Other Credits'}
    debit_sections = {'Electronic Debits', 'Other Debits', 'Checks Cleared'}
    skip_sections = {'Account Summary', 'Summary of Accounts', 'Daily Balances', 'Interest Summary'}
    all_sections = credit_sections | debit_sections | skip_sections
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Detect section headers (including "(continued)" variants)
        clean_header = re.sub(r'\s*\(continued\)', '', line)
        if clean_header in all_sections:
            current_section = clean_header
            i += 1
            continue
        
        # Also match the "(continued)" reference at top of page
        if '(continued)' in line.lower():
            # Try to extract the section from context
            for sec in all_sections:
                if sec.lower() in line.lower():
                    current_section = sec
                    break
            i += 1
            continue
        
        # Skip non-transaction sections
        if current_section in skip_sections or current_section is None:
            i += 1
            continue
        
        # Skip sub-headers and summary lines
        if line in ('Date', 'Description', 'Amount', 'Check Nbr'):
            i += 1
            continue
        if 'item(s) totaling' in line:
            i += 1
            continue
        if line.startswith('Statement Ending') or line.startswith('Page ') or line.startswith('Account Number'):
            current_section = None  # End of transaction sections
            i += 1
            continue
        if line.startswith('* Indicates') or line.startswith('BRIARWYCK OWNERS'):
            i += 1
            continue
        
        # ── CHECKS CLEARED: different format (check#, date, amount) ──
        if current_section == 'Checks Cleared':
            check_match = re.match(r'^(\d+)\*?$', line)  # Check number (possibly with *)
            if check_match and i + 2 < len(lines):
                check_num = check_match.group(0).rstrip('*')
                date_line = lines[i + 1]
                amount_line = lines[i + 2]
                
                date_match = re.match(r'^(\d{2}/\d{2}/\d{4})$', date_line)
                amount_match = re.match(r'^\$?([\d,]+\.\d{2})$', amount_line)
                
                if date_match and amount_match:
                    txn_date_str = date_match.group(1)
                    amount = float(amount_match.group(1).replace(',', ''))
                    iso_date = f"{txn_date_str[6:]}-{txn_date_str[0:2]}-{txn_date_str[3:5]}"
                    
                    txn = {
                        'transaction_date': iso_date,
                        'description': f"Check #{check_num}",
                        'amount': amount,
                        'transaction_type': 'debit',
                        'account_type': account_type,
                        'account_number_last4': account_last4,
                        'running_balance': None,
                        'source_page': page_num,
                    }
                    transactions.append(txn)
                    print(f"    - {txn_date_str}  ${amount:>10,.2f}  Check #{check_num}")
                    i += 3
                    continue
            i += 1
            continue
        
        # ── STANDARD TRANSACTIONS: date → description (possibly multi-line) → amount ──
        date_match = re.match(r'^(\d{2}/\d{2}/\d{4})$', line)
        if date_match and i + 2 < len(lines):
            txn_date_str = date_match.group(1)
            
            # Collect description lines until we hit an amount
            desc_parts = []
            j = i + 1
            while j < len(lines):
                amount_match = re.match(r'^\$?([\d,]+\.\d{2})$', lines[j])
                if amount_match:
                    amount = float(amount_match.group(1).replace(',', ''))
                    description = ' '.join(desc_parts)
                    txn_type = 'credit' if current_section in credit_sections else 'debit'
                    iso_date = f"{txn_date_str[6:]}-{txn_date_str[0:2]}-{txn_date_str[3:5]}"
                    
                    txn = {
                        'transaction_date': iso_date,
                        'description': description,
                        'amount': amount,
                        'transaction_type': txn_type,
                        'account_type': account_type,
                        'account_number_last4': account_last4,
                        'running_balance': None,
                        'source_page': page_num,
                    }
                    transactions.append(txn)
                    
                    symbol = '+' if txn_type == 'credit' else '-'
                    print(f"    {symbol} {txn_date_str}  ${amount:>10,.2f}  {description[:55]}")
                    
                    i = j + 1
                    break
                # Check if we hit another date (malformed entry)
                if re.match(r'^\d{2}/\d{2}/\d{4}$', lines[j]):
                    break
                desc_parts.append(lines[j])
                j += 1
            else:
                i += 1
            continue
        
        i += 1
    
    return transactions


def extract_bank_statements(pdf_path):
    """Extract all bank transactions using deterministic Python parsing."""
    print("Bank Statement Extractor (deterministic — no LLM)")
    print("=" * 60)
    
    pages = extract_pages(pdf_path)
    all_txns = []
    
    # Pages 14-15 = Operating (8763), Page 20 = Reserve (8766)
    for pnum in [14, 15, 20]:
        p = [p for p in pages if p.page_number == pnum][0]
        acct_type = 'operating' if pnum <= 19 else 'reserve'
        acct_last4 = '8763' if pnum <= 19 else '8766'
        
        print(f"\n  Page {pnum} ({acct_type}/{acct_last4}):")
        txns = parse_bank_page(p.text, pnum, acct_type, acct_last4)
        all_txns.extend(txns)
        print(f"    --- {len(txns)} transactions ---")
    
    # Verify against PDF account summary
    op = [t for t in all_txns if t['account_type'] == 'operating']
    res = [t for t in all_txns if t['account_type'] == 'reserve']
    
    op_credits = sum(t['amount'] for t in op if t['transaction_type'] == 'credit')
    op_debits = sum(t['amount'] for t in op if t['transaction_type'] == 'debit')
    res_credits = sum(t['amount'] for t in res if t['transaction_type'] == 'credit')
    
    print(f"\n{'=' * 60}")
    print(f"  VERIFICATION (vs PDF Account Summary)")
    print(f"  OPERATING (8763): {len(op)} transactions")
    print(f"    Credits:  ${op_credits:>10,.2f}  (PDF: $13,262.54)  {'MATCH' if abs(op_credits - 13262.54) < 0.01 else 'MISMATCH'}")
    print(f"    Debits:   ${op_debits:>10,.2f}  (PDF: $11,957.74)  {'MATCH' if abs(op_debits - 11957.74) < 0.01 else 'MISMATCH'}")
    print(f"  RESERVE (8766): {len(res)} transactions")
    print(f"    Credits:  ${res_credits:>10,.2f}  (PDF: $303.61)    {'MATCH' if abs(res_credits - 303.61) < 0.01 else 'MISMATCH'}")
    print(f"{'=' * 60}")
    
    return all_txns


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf"
    
    txns = extract_bank_statements(pdf)
    
    output_path = "data/extraction_bank_statements.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(txns, f, indent=2)
    print(f"\nSaved {len(txns)} transactions to {output_path}")
