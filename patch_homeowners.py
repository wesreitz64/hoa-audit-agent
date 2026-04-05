import sys
import glob
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.pdf_reader import extract_pages
from src.agents.homeowner_ledger_extractor import parse_ledger_pages, to_json_records

def patch_jsons():
    # Find all PDFs in data/sample_pdfs
    pdf_files = list(Path("data/sample_pdfs").glob("*.pdf"))
    
    # Pre-map them by stem
    pdf_map = {f.stem: f for f in pdf_files}
    
    # Load all json results
    json_files = list(Path("data/audit_results").glob("audit_*.json"))
    
    for j_path in json_files:
        if j_path.name == "audit_result.json": continue
        if j_path.name == "batch_summary.json": continue
        
        # Determine the PDF name from the JSON
        pdf_stem = j_path.stem.replace("audit_", "")
        
        if pdf_stem not in pdf_map:
            print(f"Skipping {j_path.stem}, no matching PDF found in data/sample_pdfs.")
            continue
            
        pdf_path = pdf_map[pdf_stem]
        print(f"\nProcessing {pdf_path.name}...")
        
        # Read ALL pages
        all_pages = extract_pages(str(pdf_path))
        
        # We need to find the homeowner ledger pages visually
        # They have "Receivables Type Balances" and "Assessment"
        ledger_pages = []
        for p in all_pages:
            # Typical CINCSystems header for homeowner ledger
            if "Receivables Type Balances" in p.text and "Homeowner" in p.text:
                ledger_pages.append(p)
                
        if not ledger_pages:
            # Try another match
            for p in all_pages:
                if "Receivables Type Balances" in p.text and "Owner" in p.text:
                    ledger_pages.append(p)
                    
        if not ledger_pages:
            print(f"  No ledger pages found!")
            continue
            
        print(f"  Found {len(ledger_pages)} ledger pages.")
        
        # Extract homeowner records
        try:
            homeowners, totals = parse_ledger_pages(ledger_pages)
            records = to_json_records(homeowners)
            print(f"  Extracted {len(records)} homeowner records.")
            
            # Update JSON
            with open(j_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            data["homeowner_records"] = records
            
            with open(j_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            print(f"  Saved to {j_path.name}")
        except Exception as e:
            print(f"  Failed extraction: {e}")

if __name__ == "__main__":
    patch_jsons()
