"""
HOA Financial Query Agent — Natural Language SQL Interface

Ask questions about HOA finances in plain English, get precise SQL-backed answers.

The agent:
1. Translates your question into SQL
2. Runs it against the SQLite database
3. Formats the results with context and source citations

Examples:
    "How much did we spend on electricity?"
    "Show me all payments over $1,000"
    "What's our total income vs expenses for February?"
    "Which vendor got paid the most?"
    "Are there any bank debits without matching invoices?"

Usage:
    python -m src.agents.query_agent                    # Interactive mode
    python -m src.agents.query_agent "your question"    # Single query
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.config import get_llm
from src.db.schema import DEFAULT_DB, build_database


# ── Database introspection ──────────────────────────────────────────

def get_db_schema(db_path: Path) -> str:
    """Get the full database schema as a string for LLM context."""
    conn = sqlite3.connect(str(db_path))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    schema_parts = []
    for (table_name,) in tables:
        create_sql = conn.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        ).fetchone()[0]

        row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        # Get sample data (first 3 rows)
        sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchall()
        columns = [desc[0] for desc in conn.execute(f"SELECT * FROM {table_name} LIMIT 1").description]

        schema_parts.append(f"-- Table: {table_name} ({row_count} rows)")
        schema_parts.append(create_sql + ";")
        if sample:
            schema_parts.append(f"-- Sample data ({table_name}):")
            schema_parts.append(f"-- Columns: {', '.join(columns)}")
            for row in sample:
                schema_parts.append(f"--   {row}")
        schema_parts.append("")

    conn.close()
    return "\n".join(schema_parts)


def get_summary_stats(db_path: Path) -> str:
    """Get key summary stats the LLM can reference."""
    conn = sqlite3.connect(str(db_path))

    stats = []
    stats.append("=== DATABASE SUMMARY ===")

    # Bank transaction totals
    row = conn.execute("""
        SELECT
            COUNT(*) as total_txns,
            SUM(CASE WHEN transaction_type='credit' THEN amount ELSE 0 END) as total_credits,
            SUM(CASE WHEN transaction_type='debit' THEN amount ELSE 0 END) as total_debits,
            MIN(transaction_date) as earliest_date,
            MAX(transaction_date) as latest_date
        FROM bank_transactions
    """).fetchone()
    stats.append(f"Bank Transactions: {row[0]} total")
    stats.append(f"  Credits (income): ${row[1]:,.2f}")
    stats.append(f"  Debits (expenses): ${row[2]:,.2f}")
    stats.append(f"  Date range: {row[3]} to {row[4]}")

    # Invoice totals
    row = conn.execute("""
        SELECT COUNT(*), SUM(amount), COUNT(DISTINCT vendor_name)
        FROM invoices
    """).fetchone()
    stats.append(f"Invoices: {row[0]} total, ${row[1]:,.2f} sum, {row[2]} vendors")

    # GL categories
    rows = conn.execute("""
        SELECT gl_account_name, SUM(amount) as total
        FROM invoices
        GROUP BY gl_account_name
        ORDER BY total DESC
    """).fetchall()
    stats.append("Spending by GL Category:")
    for name, total in rows:
        stats.append(f"  {name}: ${total:,.2f}")

    conn.close()
    return "\n".join(stats)


# ── System prompt ───────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the HOA Financial Analyst for Briarwyck Owners Association.
You answer questions about HOA finances by writing and executing SQL queries against a SQLite database.

IMPORTANT RULES:
1. ALWAYS write a SQL query to answer the question — never guess or estimate.
2. Format monetary values with $ and commas (e.g., $4,979.50).
3. When asked about spending categories, use the `invoices` table which has `gl_account_name`.
4. The `bank_transactions` table has raw bank data. Use it for cash flow, balance, and reconciliation questions.
5. "Electricity" includes vendors like "Ambit" and "Reliant" — check the `gl_account_name` column.
6. Always mention the source data (which table, how many rows matched).
7. If a question is ambiguous, query both tables and explain the difference.
8. Dates are in ISO format (YYYY-MM-DD). Use substr() or date functions for filtering.
9. The `month` column (auto-generated) is in YYYY-MM format — use it for monthly aggregations.

{schema}

{summary}
"""


# ── Query execution ─────────────────────────────────────────────────

def execute_query(db_path: Path, sql: str) -> tuple[list[str], list[tuple]]:
    """Execute a SQL query and return column names + rows."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows
    except Exception as e:
        return ["error"], [(str(e),)]
    finally:
        conn.close()


def run_query_agent(question: str, db_path: Path = DEFAULT_DB) -> str:
    """Ask a natural language question, get a SQL-backed answer."""

    # Ensure database exists
    if not db_path.exists():
        print("  Database not found — building from extracted JSON...")
        build_database(db_path)

    schema = get_db_schema(db_path)
    summary = get_summary_stats(db_path)

    llm = get_llm()

    # Step 1: Generate SQL from the question
    sql_prompt = f"""Given this database schema and summary:

{schema}

{summary}

Write a SQLite query to answer this question: "{question}"

Return ONLY the SQL query, nothing else. No markdown formatting, no explanation.
If multiple queries are needed, separate them with a semicolon but handle each independently.
"""

    sql_response = llm.invoke(sql_prompt)
    sql_query = sql_response.content.strip()

    # Clean up any markdown formatting the LLM might add
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    print(f"\n  📊 SQL Generated:")
    print(f"  {'-'*50}")
    for line in sql_query.split('\n'):
        print(f"    {line}")
    print(f"  {'-'*50}")

    # Step 2: Execute the query
    columns, rows = execute_query(db_path, sql_query)

    if columns == ["error"]:
        # If query failed, let the LLM try to fix it
        print(f"  ⚠ Query failed: {rows[0][0]}")
        print(f"  Attempting to fix...")

        fix_prompt = f"""The SQL query failed with this error: {rows[0][0]}

Original question: "{question}"
Failed query: {sql_query}

Schema:
{schema}

Write a corrected SQLite query. Return ONLY the SQL, nothing else."""

        fix_response = llm.invoke(fix_prompt)
        sql_query = fix_response.content.strip().replace("```sql", "").replace("```", "").strip()

        print(f"\n  📊 Corrected SQL:")
        for line in sql_query.split('\n'):
            print(f"    {line}")

        columns, rows = execute_query(db_path, sql_query)

    # Step 3: Format results as a table for the LLM
    result_text = f"Columns: {columns}\n"
    for row in rows[:50]:  # Cap at 50 rows
        result_text += f"  {row}\n"
    if len(rows) > 50:
        result_text += f"  ... ({len(rows)} total rows, showing first 50)\n"

    # Step 4: Let the LLM interpret the results
    answer_prompt = f"""You are the HOA Financial Analyst for Briarwyck Owners Association.

The board member asked: "{question}"

You ran this SQL query:
{sql_query}

And got these results:
{result_text}

Now provide a clear, professional answer. Rules:
- Format dollar amounts with $ and commas
- Mention specific vendors, dates, or check numbers when relevant
- If the data reveals something noteworthy (e.g., one vendor dominates spending), mention it
- Be concise but thorough
- End with the data source (e.g., "Source: 9 invoices from February 2026 financials")
"""

    answer_response = llm.invoke(answer_prompt)
    return answer_response.content


# ── Interactive CLI ─────────────────────────────────────────────────

def interactive_mode(db_path: Path = DEFAULT_DB):
    """Run the query agent in interactive conversation mode."""
    print("\n" + "="*60)
    print("  🏠 HOA Financial Query Agent — Briarwyck")
    print("  Ask questions about HOA finances in plain English.")
    print("  Type 'quit' to exit, 'sql:' prefix for raw SQL.")
    print("="*60)

    # Ensure database exists
    if not db_path.exists():
        print("\n  Building database from extracted JSON...")
        build_database(db_path)
        print()

    while True:
        try:
            question = input("\n  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Goodbye! 👋")
            break

        if not question:
            continue
        if question.lower() in ('quit', 'exit', 'q'):
            print("\n  Goodbye! 👋")
            break

        # Raw SQL mode
        if question.lower().startswith('sql:'):
            raw_sql = question[4:].strip()
            columns, rows = execute_query(db_path, raw_sql)
            print(f"\n  Columns: {columns}")
            for row in rows:
                print(f"    {row}")
            print(f"  ({len(rows)} rows)")
            continue

        # Natural language query
        print(f"\n  🔍 Processing: \"{question}\"")
        try:
            answer = run_query_agent(question, db_path)
            print(f"\n  {'─'*50}")
            print(f"  {answer}")
            print(f"  {'─'*50}")
        except Exception as e:
            print(f"\n  ❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        # Single question mode
        question = " ".join(sys.argv[1:])
        answer = run_query_agent(question)
        print(f"\n{answer}")
    else:
        # Interactive mode
        interactive_mode()
