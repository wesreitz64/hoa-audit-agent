import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    const resultsDir = path.join(process.cwd(), '../data/audit_results');
    
    if (!fs.existsSync(resultsDir)) {
      return NextResponse.json({ error: "Audit results directory not found." }, { status: 404 });
    }

    const files = await fs.promises.readdir(resultsDir);
    const auditFiles = files.filter(f => f.startsWith('audit_') && f.endsWith('.json'));

    const aggregatedData = [];

    for (const file of auditFiles) {
      const filePath = path.join(resultsDir, file);
      const fileContents = await fs.promises.readFile(filePath, 'utf8');
      const data = JSON.parse(fileContents);
      
      // Map it into the structure expected by the frontend
      // Ensure we pull in the rich red flag details, not just a count!
      aggregatedData.push({
        pdf: file,
        period: data.period,
        confidence: data.summary?.confidence_score || 0,
        checks_passed: data.summary?.checks_passed || 0,
        total_checks: data.summary?.total_checks || 0,
        red_flags_count: data.summary?.checks_failed || 0,
        status: "complete",
        detailed_flags: data.red_flags || {},
        homeowner_results: data.homeowner_formula_results || {},
        aggregate_checks: data.aggregate_checks || []
      });
    }
    
    return NextResponse.json(aggregatedData);
  } catch (error) {
    console.error("Error reading audit results:", error);
    return NextResponse.json({ error: "Failed to load audit results" }, { status: 500 });
  }
}
