import { NextResponse } from 'next/server';
import Database from 'better-sqlite3';
import path from 'path';

export async function GET() {
  try {
    // The db is copied into the public folder for Vercel deployment support
    const dbPath = path.join(process.cwd(), 'public', 'data', 'audit.db');
    
    // better-sqlite3 is synchronous
    const db = new Database(dbPath, { readonly: true });

    // We want to return the raw Income Statements
    const incomeStatements = db.prepare(`
      SELECT period, type, category, gl_code, month_actual, month_budget, ytd_actual, ytd_budget, annual_budget 
      FROM income_statement_ytd
      ORDER BY type, category
    `).all();

    // And we want the joined Vendor Invoice data matched to GL codes if applicable
    const vendorInvoices = db.prepare(`
      SELECT period, vendor_name, amount, gl_account_name, gl_account_code, invoice_date, paid_date, payment_type
      FROM all_invoices
      ORDER BY amount DESC
    `).all();

    return NextResponse.json({
      incomeStatements,
      vendorInvoices
    });

  } catch (error) {
    console.error("Database Error:", error);
    return NextResponse.json(
      { error: "Failed to fetch YTD Vendor report from SQLite Database." }, 
      { status: 500 }
    );
  }
}
