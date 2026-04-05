import json
import sqlite3
import glob
from pathlib import Path

def create_database():
    db_path = Path("data") / "audit.db"
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Initializing SQLite Database Schema...")

    # Table for period summaries
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS monthly_summary (
        period TEXT PRIMARY KEY,
        pdf_name TEXT,
        confidence REAL,
        total_checks INTEGER,
        checks_passed INTEGER,
        red_flags INTEGER
    )''')

    # Table for specific unapproved checks
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS unapproved_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT,
        amount REAL,
        flag TEXT,
        description TEXT,
        FOREIGN KEY(period) REFERENCES monthly_summary(period)
    )''')

    # Table for specific pending invoices
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pending_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT,
        amount REAL,
        vendor_name TEXT,
        payment_type TEXT,
        FOREIGN KEY(period) REFERENCES monthly_summary(period)
    )''')

    # Table for homeowner ledger anomalies (pre-paid bugs, double charges)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS homeowner_anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT,
        unit_id TEXT,
        homeowner_name TEXT,
        actual_ending REAL,
        computed_ending REAL,
        difference REAL,
        has_prepaid_carryforward BOOLEAN,
        FOREIGN KEY(period) REFERENCES monthly_summary(period)
    )''')
    
    # Table for full homeowner records (100% extracted rows)
    cursor.execute("DROP TABLE IF EXISTS homeowner_records")
    cursor.execute('''
    CREATE TABLE homeowner_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT,
        unit_id TEXT,
        homeowner_name TEXT,
        owner_type TEXT,
        prev_balance REAL,
        billing REAL,
        receipts REAL,
        adjustments REAL,
        prepaid REAL,
        ending_balance REAL,
        FOREIGN KEY(period) REFERENCES monthly_summary(period)
    )''')
    
    # Table for full Income Statement (Budget vs Actual) YTD
    cursor.execute("DROP TABLE IF EXISTS income_statement_ytd")
    cursor.execute('''
    CREATE TABLE income_statement_ytd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT,
        category TEXT,
        gl_code TEXT,
        month_actual REAL,
        month_budget REAL,
        ytd_actual REAL,
        ytd_budget REAL,
        annual_budget REAL,
        type TEXT,
        FOREIGN KEY(period) REFERENCES monthly_summary(period)
    )''')

    # Table for ALL Vendor Invoices
    cursor.execute("DROP TABLE IF EXISTS all_invoices")
    cursor.execute('''
    CREATE TABLE all_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period TEXT,
        vendor_name TEXT,
        invoice_number TEXT,
        invoice_date TEXT,
        paid_date TEXT,
        amount REAL,
        gl_account_code TEXT,
        gl_account_name TEXT,
        payment_type TEXT,
        authorized_by TEXT,
        source_page INTEGER,
        FOREIGN KEY(period) REFERENCES monthly_summary(period)
    )''')
    
    # Clear existing data so we can ingest freshly
    cursor.execute("DELETE FROM monthly_summary")
    cursor.execute("DELETE FROM unapproved_checks")
    cursor.execute("DELETE FROM pending_invoices")
    cursor.execute("DELETE FROM homeowner_anomalies")
    cursor.execute("DELETE FROM homeowner_records")
    cursor.execute("DELETE FROM income_statement_ytd")
    cursor.execute("DELETE FROM all_invoices")

    conn.commit()
    return conn, cursor

def ingest_jsons():
    conn, cursor = create_database()
    json_pattern = str(Path("data") / "audit_results" / "audit_*.json")
    files = glob.glob(json_pattern)
    
    print(f"Discovered {len(files)} audit JSON files. Ingesting into SQLite...")

    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        period = data.get("period", "Unknown")
        summary = data.get("summary", {})
        red_flags = data.get("red_flags", {})
        homeowner_results = data.get("homeowner_formula_results", {})

        # Insert Summary
        cursor.execute('''
        INSERT OR REPLACE INTO monthly_summary 
        (period, pdf_name, confidence, total_checks, checks_passed, red_flags) 
        VALUES (?, ?, ?, ?, ?, ?)''', (
            period,
            data.get("pdf", ""),
            summary.get("confidence_score", 0),
            summary.get("total_checks", 0),
            summary.get("checks_passed", 0),
            summary.get("checks_failed", 0)
        ))

        # Insert Unapproved Checks
        unapproved = red_flags.get("unapproved_checks", [])
        for uc in unapproved:
            cursor.execute('''
            INSERT INTO unapproved_checks (period, amount, flag, description) 
            VALUES (?, ?, ?, ?)''', (
                period,
                uc.get("amount", 0.0),
                uc.get("flag", ""),
                uc.get("description", "")
            ))

        # Insert Pending Invoices
        pending = red_flags.get("pending_invoices", [])
        for inv in pending:
            cursor.execute('''
            INSERT INTO pending_invoices (period, amount, vendor_name, payment_type) 
            VALUES (?, ?, ?, ?)''', (
                period,
                inv.get("amount", 0.0),
                inv.get("vendor_name", ""),
                inv.get("payment_type", "")
            ))

        # Insert Homeowner Anomalies
        anomalies = homeowner_results.get("failures", [])
        for anom in anomalies:
            cursor.execute('''
            INSERT INTO homeowner_anomalies (period, unit_id, homeowner_name, actual_ending, computed_ending, difference, has_prepaid_carryforward) 
            VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                period,
                anom.get("unit_id", ""),
                anom.get("homeowner_name", ""),
                anom.get("actual_ending", 0.0),
                anom.get("computed_ending", 0.0),
                anom.get("difference", 0.0),
                anom.get("has_prepaid_carryforward", False)
            ))
            
        # Insert ALL Homeowner Records
        records = data.get("homeowner_records", [])
        for rec in records:
            cursor.execute('''
            INSERT INTO homeowner_records (period, unit_id, homeowner_name, owner_type, prev_balance, billing, receipts, adjustments, prepaid, ending_balance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                period,
                rec.get("unit_id", ""),
                rec.get("homeowner_name", ""),
                rec.get("owner_type", ""),
                rec.get("prev_balance", 0.0),
                rec.get("billing", 0.0),
                rec.get("receipts", 0.0),
                rec.get("adjustments", 0.0),
                rec.get("prepaid", 0.0),
                rec.get("ending_balance", 0.0)
            ))
            
        # Insert ALL Invoices
        all_invs = data.get("all_invoices", [])
        for inv in all_invs:
            cursor.execute('''
            INSERT INTO all_invoices (period, vendor_name, invoice_number, invoice_date, paid_date, amount, gl_account_code, gl_account_name, payment_type, authorized_by, source_page)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                period,
                inv.get("vendor_name", ""),
                inv.get("invoice_number", ""),
                inv.get("invoice_date", ""),
                inv.get("paid_date", ""),
                inv.get("amount", 0.0),
                inv.get("gl_account_code", ""),
                inv.get("gl_account_name", ""),
                inv.get("payment_type", ""),
                inv.get("authorized_by", ""),
                inv.get("source_page", 0)
            ))

        # Insert Income Statement YTD
        inc_states = data.get("income_statement", [])
        for inc in inc_states:
            cursor.execute('''
            INSERT INTO income_statement_ytd (period, category, gl_code, month_actual, month_budget, ytd_actual, ytd_budget, annual_budget, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                period,
                inc.get("category", ""),
                inc.get("gl_code", ""),
                inc.get("month_actual", 0.0),
                inc.get("month_budget", 0.0),
                inc.get("ytd_actual", 0.0),
                inc.get("ytd_budget", 0.0),
                inc.get("annual_budget", 0.0),
                inc.get("type", "")
            ))

    conn.commit()
    print("✅ Successfully ingested all data into SQLite (data/audit.db)")
    
    # Print quick verification query
    cursor.execute("SELECT SUM(amount) FROM unapproved_checks")
    total_unapproved = cursor.fetchone()[0] or 0.0
    print(f"📊 Total Unauthorized Money Caught By AI: ${total_unapproved:,.2f}")
    
    conn.close()

if __name__ == "__main__":
    ingest_jsons()
