import sqlite3
import json

def analyze():
    db = sqlite3.connect('dashboard/public/data/audit.db')
    cur = db.cursor()
    
    with open('investigation_results.txt', 'w') as f:
        f.write('--- QUESTION 1: JOHN ORTIZ / PREPAIDS ---\n')
        cur.execute('''SELECT period, unit_id, homeowner_name, actual_ending, computed_ending, difference, has_prepaid_carryforward 
                       FROM homeowner_anomalies 
                       WHERE homeowner_name LIKE '%Ortiz%' OR homeowner_name LIKE '%John%' ''')
        for r in cur.fetchall():
            f.write(str(r) + '\n')
            
        f.write('\n--- QUESTION 2: NEON MONKEY ---\n')
        cur.execute('''SELECT period, vendor_name, amount, invoice_date, paid_date, gl_account_name 
                       FROM all_invoices 
                       WHERE vendor_name LIKE '%Neon%' OR vendor_name LIKE '%Monkey%' ORDER BY invoice_date''')
        sums = 0
        for r in cur.fetchall():
            f.write(str(r) + '\n')
            sums += r[2]
        f.write(f'Total Paid to Neon Monkey: {sums}\n')
        
        f.write('\n--- QUESTION 3: FIELD DAY ---\n')
        cur.execute('''SELECT * FROM all_invoices WHERE vendor_name LIKE '%Field%' OR gl_account_name LIKE '%Field%' OR invoice_number LIKE '%Field%' ''')
        for r in cur.fetchall():
            f.write(str(r) + '\n')
            
        f.write('\n--- QUESTION 4: $1000 DEP JUNE/JULY ---\n')
        cur.execute('''SELECT period, category, month_actual FROM income_statement_ytd WHERE month_actual = 1000''')
        for r in cur.fetchall():
            f.write(str(r) + '\n')
            
        # Also check all invoices for Jil or 1000
        cur.execute('''SELECT vendor_name, amount, period FROM all_invoices WHERE amount = 1000 OR vendor_name LIKE '%Jil%' ''')
        for r in cur.fetchall():
            f.write(str(r) + '\n')

if __name__ == '__main__':
    analyze()
