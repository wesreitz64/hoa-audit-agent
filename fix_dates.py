import json
import os
import re
from pathlib import Path

def get_period_from_name(name):
    # Matches 'audit_2026.02 Briarwyck...'
    m = re.search(r'(\d{4})\.(\d{2})', name)
    if m:
        year = int(m.group(1))
        month_idx = int(m.group(2))
            
        month_names = ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        return f"{month_names[month_idx]} {year}"
    
    # Matches '2026 2'
    m = re.search(r'(\d{4})\s+(\d{1,2})', name)
    if m:
        year = int(m.group(1))
        month_idx = int(m.group(2))
            
        month_names = ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        return f"{month_names[month_idx]} {year}"
        
    return None

def main():
    print("Fixing period dates in all generated JSON files...")
    results_dir = Path("data/audit_results")
    
    count = 0
    for file_path in results_dir.glob("audit_*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            correct_period = get_period_from_name(file_path.name)
            
            if correct_period and data.get("period") != correct_period:
                old = data.get("period")
                data["period"] = correct_period
                file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                print(f"Shifted {file_path.name}: {old} -> {correct_period}")
                count += 1
                
        except Exception as e:
            print(f"Failed to process {file_path}: {e}")
            
    print(f"Updated {count} files. Remember to run python -m src.ingest_db to apply to SQLite UI.")
    
if __name__ == "__main__":
    main()
