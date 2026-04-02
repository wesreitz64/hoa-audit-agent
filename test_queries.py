"""Quick test: run several questions and save clean output."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.query_agent import run_query_agent

questions = [
    "How much did we spend on electricity?",
    "Which vendor got paid the most?",
    "Show me all payments over $1000",
    "What is the total spending by GL category?",
]

output_lines = []
for q in questions:
    output_lines.append(f"\n{'='*60}")
    output_lines.append(f"  Q: {q}")
    output_lines.append(f"{'='*60}")
    answer = run_query_agent(q)
    output_lines.append(f"\n  A: {answer}\n")

result = "\n".join(output_lines)
Path("data/query_results.txt").write_text(result, encoding="utf-8")
print("Results saved to data/query_results.txt")
