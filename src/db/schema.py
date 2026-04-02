"""
HOA Audit Database — SQLite Schema & Data Loader

Converts extracted JSON data into a queryable SQLite database.
Tables mirror the extraction schemas but are optimized for SQL analysis:
  - bank_transactions: All deposits, debits, checks from bank statements
  - invoices: Approved vendor payments with GL account categorization

Usage:
    python -m src.db.schema                    # Build from default JSON files
    python -m src.db.schema --db custom.db     # Specify output database
"""

import json
import sqlite3
import sys
from pathlib import Path

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "hoa_audit.db"
DEFAULT_BANK_JSON = PROJECT_ROOT / "data" / "extraction_bank_statements.json"
DEFAULT_INVOICE_JSON = PROJECT_ROOT / "data" / "extraction_invoice_list.json"


def create_tables(conn: sqlite3.Connection):
    """Create the HOA financial database schema."""
    conn.executescript("""
        DROP TABLE IF EXISTS bank_transactions;
        DROP TABLE IF EXISTS invoices;
        DROP TABLE IF EXISTS gl_accounts;

        -- Bank statement transactions (operating + reserve accounts)
        CREATE TABLE bank_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_date TEXT NOT NULL,          -- ISO format: 2026-02-15
            description TEXT NOT NULL,
            amount REAL NOT NULL,                    -- Always positive
            transaction_type TEXT NOT NULL            -- 'credit' or 'debit'
                CHECK(transaction_type IN ('credit', 'debit')),
            account_type TEXT NOT NULL                -- 'operating' or 'reserve'
                CHECK(account_type IN ('operating', 'reserve')),
            account_number_last4 TEXT NOT NULL,
            running_balance REAL,
            source_page INTEGER,
            -- Derived columns for easier querying
            month TEXT GENERATED ALWAYS AS (substr(transaction_date, 1, 7)) STORED,
            year TEXT GENERATED ALWAYS AS (substr(transaction_date, 1, 4)) STORED
        );

        -- Invoices / approved vendor payments
        CREATE TABLE invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL,
            invoice_number TEXT,
            invoice_date TEXT,                       -- ISO format
            paid_date TEXT,                          -- ISO format
            amount REAL NOT NULL,
            gl_account_code TEXT,                    -- e.g. '58-5500-00'
            gl_account_name TEXT,                    -- e.g. 'Electricity'
            payment_type TEXT,                       -- 'Check', 'ACH', 'EFT', 'Auto Pay'
            authorized_by TEXT,
            bank_account_last4 TEXT,
            source_page INTEGER,
            -- Derived columns
            month TEXT GENERATED ALWAYS AS (substr(paid_date, 1, 7)) STORED,
            year TEXT GENERATED ALWAYS AS (substr(paid_date, 1, 4)) STORED
        );

        -- GL Account lookup (auto-populated from invoice data)
        CREATE TABLE gl_accounts (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT                            -- Derived top-level category
        );

        -- Indexes for common query patterns
        CREATE INDEX idx_bank_date ON bank_transactions(transaction_date);
        CREATE INDEX idx_bank_type ON bank_transactions(transaction_type);
        CREATE INDEX idx_bank_account ON bank_transactions(account_type);
        CREATE INDEX idx_bank_month ON bank_transactions(month);
        CREATE INDEX idx_invoice_vendor ON invoices(vendor_name);
        CREATE INDEX idx_invoice_gl ON invoices(gl_account_code);
        CREATE INDEX idx_invoice_paid ON invoices(paid_date);
        CREATE INDEX idx_invoice_month ON invoices(month);
    """)
    print("  ✓ Tables created: bank_transactions, invoices, gl_accounts")


def load_bank_transactions(conn: sqlite3.Connection, json_path: Path):
    """Load bank statement transactions from extracted JSON."""
    if not json_path.exists():
        print(f"  ⚠ Skipping bank transactions — {json_path} not found")
        return 0

    with open(json_path, 'r', encoding='utf-8') as f:
        transactions = json.load(f)

    conn.executemany("""
        INSERT INTO bank_transactions
            (transaction_date, description, amount, transaction_type,
             account_type, account_number_last4, running_balance, source_page)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (t['transaction_date'], t['description'], t['amount'],
         t['transaction_type'], t['account_type'],
         t['account_number_last4'], t.get('running_balance'),
         t.get('source_page'))
        for t in transactions
    ])
    conn.commit()
    print(f"  ✓ Loaded {len(transactions)} bank transactions")
    return len(transactions)


def load_invoices(conn: sqlite3.Connection, json_path: Path):
    """Load invoice list from extracted JSON."""
    if not json_path.exists():
        print(f"  ⚠ Skipping invoices — {json_path} not found")
        return 0

    with open(json_path, 'r', encoding='utf-8') as f:
        invoices = json.load(f)

    conn.executemany("""
        INSERT INTO invoices
            (vendor_name, invoice_number, invoice_date, paid_date, amount,
             gl_account_code, gl_account_name, payment_type, authorized_by,
             bank_account_last4, source_page)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (inv['vendor_name'], inv.get('invoice_number'), inv.get('invoice_date'),
         inv.get('paid_date'), inv['amount'], inv.get('gl_account_code'),
         inv.get('gl_account_name'), inv.get('payment_type'),
         inv.get('authorized_by'), inv.get('bank_account_last4'),
         inv.get('source_page'))
        for inv in invoices
    ])
    conn.commit()
    print(f"  ✓ Loaded {len(invoices)} invoices")
    return len(invoices)


def populate_gl_accounts(conn: sqlite3.Connection):
    """Auto-populate GL account lookup from invoice data."""
    # Map GL code prefixes to categories
    category_map = {
        '50': 'Administration',
        '52': 'Insurance',
        '54': 'Legal',
        '58': 'Utilities',
        '61': 'Common Area',
        '63': 'Grounds/Landscape',
    }

    rows = conn.execute("""
        SELECT DISTINCT gl_account_code, gl_account_name FROM invoices
        WHERE gl_account_code IS NOT NULL
    """).fetchall()

    for code, name in rows:
        prefix = code.split('-')[0] if code else ''
        category = category_map.get(prefix, 'Other')
        conn.execute("""
            INSERT OR REPLACE INTO gl_accounts (code, name, category)
            VALUES (?, ?, ?)
        """, (code, name, category))

    conn.commit()
    print(f"  ✓ Populated {len(rows)} GL accounts")
    return len(rows)


def build_database(
    db_path: Path = DEFAULT_DB,
    bank_json: Path = DEFAULT_BANK_JSON,
    invoice_json: Path = DEFAULT_INVOICE_JSON,
):
    """Build the complete HOA audit database from extracted JSON data."""
    print(f"\n{'='*60}")
    print(f"  HOA Audit Database Builder")
    print(f"{'='*60}")
    print(f"  Output: {db_path}")

    # Ensure output directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB to rebuild fresh
    if db_path.exists():
        db_path.unlink()
        print(f"  (removed existing database)")

    conn = sqlite3.connect(str(db_path))
    try:
        create_tables(conn)
        bank_count = load_bank_transactions(conn, bank_json)
        invoice_count = load_invoices(conn, invoice_json)
        gl_count = populate_gl_accounts(conn)

        # Print summary stats
        print(f"\n{'='*60}")
        print(f"  DATABASE READY")
        print(f"    Bank transactions:  {bank_count}")
        print(f"    Invoices:           {invoice_count}")
        print(f"    GL accounts:        {gl_count}")

        # Quick validation
        total_debits = conn.execute(
            "SELECT SUM(amount) FROM bank_transactions WHERE transaction_type='debit'"
        ).fetchone()[0] or 0
        total_credits = conn.execute(
            "SELECT SUM(amount) FROM bank_transactions WHERE transaction_type='credit'"
        ).fetchone()[0] or 0
        total_invoices = conn.execute(
            "SELECT SUM(amount) FROM invoices"
        ).fetchone()[0] or 0

        print(f"\n  QUICK VALIDATION:")
        print(f"    Bank credits:  ${total_credits:>10,.2f}")
        print(f"    Bank debits:   ${total_debits:>10,.2f}")
        print(f"    Invoice total: ${total_invoices:>10,.2f}")
        print(f"{'='*60}\n")

    finally:
        conn.close()

    return db_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build HOA audit SQLite database")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Output database path")
    parser.add_argument("--bank-json", type=Path, default=DEFAULT_BANK_JSON)
    parser.add_argument("--invoice-json", type=Path, default=DEFAULT_INVOICE_JSON)
    args = parser.parse_args()

    build_database(args.db, args.bank_json, args.invoice_json)
