import { NextResponse } from 'next/server';
import Database from 'better-sqlite3';
import path from 'path';

export async function GET() {
  try {
    const dbPath = path.join(process.cwd(), 'public', 'data', 'audit.db');
    const db = new Database(dbPath, { readonly: true });

    const records = db.prepare(`
      SELECT period, unit_id, homeowner_name, owner_type, prev_balance, billing, receipts, adjustments, prepaid, ending_balance
      FROM homeowner_records
      ORDER BY unit_id, period
    `).all();

    return NextResponse.json({ records });

  } catch (error) {
    console.error("Database Error:", error);
    return NextResponse.json(
      { error: "Failed to fetch homeowner records from SQLite Database." }, 
      { status: 500 }
    );
  }
}
