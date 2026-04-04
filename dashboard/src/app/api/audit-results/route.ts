import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    // In dev: process.cwd() is .../hoa-audit-agent/dashboard
    // We want .../hoa-audit-agent/data/audit_results/batch_summary.json
    const dataPath = path.join(process.cwd(), '../data/audit_results/batch_summary.json');
    
    if (!fs.existsSync(dataPath)) {
      return NextResponse.json({ error: "Batch summary not found." }, { status: 404 });
    }

    const fileContents = await fs.promises.readFile(dataPath, 'utf8');
    const data = JSON.parse(fileContents);
    
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error reading audit results:", error);
    return NextResponse.json({ error: "Failed to load audit results" }, { status: 500 });
  }
}
