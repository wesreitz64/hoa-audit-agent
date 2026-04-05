import { NextResponse } from 'next/server';
import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';

export async function GET() {
  try {
    // The db is copied into the public folder for Vercel deployment support
    const dbPath = path.join(process.cwd(), 'public', 'data', 'audit.db');
    
    const db = await open({
      filename: dbPath,
      driver: sqlite3.Database
    });

    // We want to return the raw Income Statements
    const incomeStatements = await db.all(`
      SELECT period, type, category, gl_code, month_actual, month_budget, ytd_actual, ytd_budget, annual_budget 
      FROM income_statement_ytd
      ORDER BY type, category
    `);

    // And we want the joined Vendor Invoice data matched to GL codes if applicable
    const vendorInvoices = await db.all(`
      SELECT period, vendor_name, amount, gl_account_name, gl_account_code, invoice_date, paid_date, payment_type
      FROM all_invoices
      ORDER BY amount DESC
    `);

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
