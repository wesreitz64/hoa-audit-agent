# 🏗️ HOA Financial Audit Swarm

> A stateful, multi-agent system for auditing HOA financial documents using LangGraph, Pydantic, and LlamaParse. Demonstrates **Deterministic Stewardship** — knowing when to use AI and when to use Python math.

## Architecture

```
📄 57-Page HOA PDF
    ↓
[Node 1: Triage Router] — classifies pages by type
    ↓
[Node 2a: Invoice Extractor]     ─┐
[Node 2b: Bank Statement Extractor] ─┤→ Strict Pydantic schemas
[Node 2c: Ledger Extractor]      ─┘
    ↓
[Node 3: Deterministic Auditor] — Python math cross-checks
    ↓
[HITL Veto Point] — LangGraph interrupt() for confidence < 80%
    ↓
[Node 4: Report Generator] — Structured JSON + audit trail
```

## Quick Start

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/hoa-audit-agent.git
cd hoa-audit-agent
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your OPENAI_API_KEY to .env

# Validate schemas (no API key needed)
python test_schemas.py

# Run LangGraph quickstart
python quickstart_langgraph.py
```

## Tech Stack

| Technology | Purpose |
|---|---|
| **LangGraph** v1.1.4 | Stateful agent orchestration with durable execution |
| **Pydantic** v2.12 | Type-safe data contracts for all extractions |
| **LangChain** | LLM integration layer |
| **LlamaParse** | PDF → structured markdown extraction |

## Project Status

- [x] Project scaffolding & environment
- [x] Pydantic data schemas defined
- [x] LangGraph quickstart verified
- [ ] Phase 1: Complete LangGraph learning
- [ ] Phase 2: Build audit swarm nodes
- [ ] Phase 3: Evals & production polish

## License

MIT
