import sys
import time
import json
from pydantic import BaseModel, Field
from typing import List, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from src.config import get_llm
from src.utils.pdf_reader import extract_pages

class IncomeStatementRow(BaseModel):
    category: str = Field(description="The financial line item category (e.g. Assessment General, Electricity, Landscape/Grounds Contract)")
    gl_code: Optional[str] = Field(description="The GL code if present (e.g. 4000-00)", default=None)
    month_actual: float = Field(description="The Current Period (Month) Actual amount (e.g. 9965.62)", default=0.0)
    month_budget: float = Field(description="The Current Period (Month) Budget amount (e.g. 11925.00)", default=0.0)
    ytd_actual: float = Field(description="The Year-to-date Actual amount (e.g. 88799.82)")
    ytd_budget: float = Field(description="The Year-to-date Budget amount (e.g. 23850.00)", default=0.0)
    annual_budget: float = Field(description="The Total Annual Budget amount", default=0.0)
    type: str = Field(description="Either 'INCOME' or 'EXPENSE'")

class IncomeStatementExtraction(BaseModel):
    items: List[IncomeStatementRow]

PROMPT = """You are an expert HOA auditor.
Extract ALL line items from the provided Income Statement (Budget vs Actual) page.

Focus specifically on the "Current Period" columns to get `month_actual` and `month_budget`.
Focus specifically on the "Year-to-date" columns to get `ytd_actual` and `ytd_budget`.
Also extract the `annual_budget`.

Categorize each row strictly as 'INCOME' or 'EXPENSE'.
Skip sub-total lines like "Total ADMINISTRATIVE EXPENSES", only extract the raw line items (e.g., 5000-00 Mgmt Contract).
Format amounts as standard floats (remove $ and commas).
If an actual or budget amount is empty or a hyphen ('-'), use 0.0.
"""

def extract_income_statement(pdf_path: str, triage_results_path: str = "data/triage_full_results.json"):
    print("Loading triage results...")
    try:
        triage = json.load(open(triage_results_path, encoding="utf-8"))
    except FileNotFoundError:
        print("No triage results found. Run triage first.")
        return []

    # Find income statement pages
    income_pages = [t["page_number"] for t in triage if t["page_type"] == "income_statement"]
    if not income_pages:
        print("No income statement pages found.")
        return []

    all_pages = extract_pages(pdf_path)
    pages_to_process = [p for p in all_pages if p.page_number in income_pages]

    model = get_llm()
    structured = model.with_structured_output(IncomeStatementExtraction)

    all_items = []
    print(f"Extracting from {len(pages_to_process)} income statement pages...")
    for page in pages_to_process:
        print(f"  Processing page {page.page_number}...")
        result = structured.invoke([
            SystemMessage(content=PROMPT),
            HumanMessage(content=f"Page {page.page_number}:\n\n{page.text}")
        ])
        all_items.extend(result.items)
    
    print(f"✅ Extracted {len(all_items)} income/expense line items.")
    return all_items

if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "data/sample_pdfs/Briarwyck Monthly Financials 2026 2.pdf"
    items = extract_income_statement(pdf)
    
    print("\n--- EXTRACTED DATA ---")
    for item in items:
        print(f"{item.type:<8} {item.category:<40} YTD Actual: ${item.ytd_actual:<10.2f} YTD Budget: ${item.ytd_budget:<10.2f}")
