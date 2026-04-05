# HOA Financial Audit Swarm — Project Handover & Context

## 🎯 Overall Goal
Finalize a multi-agent, deterministic AI swarm that autonomously parses monthly Homeowner Association (HOA) financial packets. The system cross-references Bank Statements against the internal Invoice Ledger to find explicit discrepancies, unapproved checks, and budget manipulation. The parsed data is securely deposited into a local SQLite `/data/audit.db` database and aggregated onto a beautiful, Next.js white-label Data Warehouse dashboard.

## 📝 Operating Instructions (For AI Assistant)
1. **At the start of every session**, read this document to inherit the exact context.
2. **Context Window Management**: This project relies on extremely large, complex files (dense Python scrapers, Next.js UI). To prevent context overflow or sluggish behavior:
   - **Number the prompts**: Keep a strict count of the user prompts (Prompts 1, 2, 3, etc.).
   - **When you get to #11**, your prompt MUST begin exactly with: "Time for a new conversation."
   - Before hitting the limit, you MUST update this document (checking off completed tasks and adding new ones).
   - Finally, politely ask the user to close the current session and start a new one to keep your operational capability lightning-fast.
3. **Updating the Ledger**: Whenever you complete a major milestone, check off the relevant `[ ]` task below.

---

## 📋 Task Masterplan

### Phase 1: Swarm Data Pipeline (Completed ✔️)
- [x] Node 1: Triage Document structure and pagination using Anthropic Vision.
- [x] Node 2a: Extract internal Vendor Invoice Ledger into structured Pydantic models.
- [x] Node 2b: Extract Unapproved/Pending Checks.
- [x] Node 2c: Extract YTD Income Statements mapped dynamically per GL Account.
- [x] Finalize `graph.py` compilation batch loop script.

### Phase 2: Data Warehouse Dashboard (Completed ✔️)
- [x] Build Next.js UI architecture.
- [x] Map `income_statement_ytd` against `month_actual`, `month_budget`, `ytd_actual`, and `annual_budget`.
- [x] Implement deterministic Print Layout CSS (`print:text-black`, `print:bg-white`) fitting seamlessly on standard letters.
- [x] Map Historical Time Periods (e.g., `January 2026`) dynamically across dropdown filters.
- [x] Build Vendor Payment Auditing Matrix. Add `StartDate`/`EndDate` filters. Add interactive `.sort()` to every column.

### Phase 3: Banking Reconciliation & Determinism (Current Focus 🚧)
- [x] Determine methodology for extracting row-by-row Bank Transactions from the native Bank Statements in the PDF (Adopted Python Strategy Pattern using regex).
- [x] Cross-Reference `all_invoices` (Management Company Claims) vs. Native Bank Outflows. Find missing checks or blatant double payments.
- [ ] Highlight missing or out-of-order check sequence anomalies natively on the dashboard.
- [ ] Add explicit warnings to the Next.js UI when the AI detects that an invoice (like the May $3,485 to Neon Monkey) appears twice for the exact same transaction, but mapping to different payment types.

### Phase 4: Homeowner AR Extraction (Future Focus ⏳)
- [ ] Map deterministically PrePaid and Delinquent Owner accounts.
- [ ] Ensure `Association Total` cross-verifies directly against the physical mathematical additions.

### Phase 5: Developer Experience & Knowledge Base (Completed ✔️)
- [x] Integrate `VSCode Tour Expert` agent workflow to generate native CodeTours.
- [x] Create Software Architecture CodeTour with Mermaid Component & Use Case Diagrams (`.tours/2-architecture.tour`).
- [x] Generate pre-rendered PNG architecture diagrams (`.tours/images/`) — CodeTour tooltips cannot render Mermaid natively.
- [x] Create **Trust Sandwich** diagram showing AI Layer → Deterministic Layer → Human Layer trust boundaries.
- [x] Enforce strict prompt-limit numbering (Prompt max #10) to prevent context drift.

---

## 🧠 Lessons Learned & Critical Architecture Notes
- **Accounting Period Delay Effect**: The management company labels financial packets by the *delivery month* (e.g. `2026.02`), but the actual financial data is strictly from the *previous accounting period* (January). Keep mapping deterministically aligned to the physical `invoice_date` without artificially shifting months dynamically, as this creates visual hallucinations when analyzing check clearing dates!
- **Data Ingestion Loop**: UI depends entirely on SQLite. Anytime you modify the AI extraction logic or `audit_*.json`, you **MUST** manually run `python -m src.ingest_db` to push changes to the Dashboard.
- **Double Payments / Voided Checks**: A vendor (like Neon Monkey LLC) may appear multiple times for the exact same `$3485.00` check if the management company reported it paid by Check in May's packet, and then re-reported it paid by ACH in June's packet. To verify true theft vs voided checks, the Swarm MUST natively map Bank Transactions and intersect the sets!
- **Prompt Modifiers (Global Rule)**: Always respect user flags (-q, --quiet, --table, --md, explain, --step) embedded in prompts to control verbosity and formatting. Type `/help` to see the full list of supported modifiers, or `/tour` to generate a CodeTour walkthrough.
- **CodeTour Cannot Render Mermaid**: VS Code's built-in Markdown renderer (used by CodeTour tooltips) does NOT support Mermaid diagrams. You must pre-render diagrams to `.png` images and embed them via `![alt](.tours/images/filename.png)` syntax.
- **Trust Sandwich Pattern**: The pipeline architecture separates AI (non-deterministic LLM parsing) → Deterministic (pure Python math) → Human (HITL veto). This three-layer pattern is the key portfolio differentiator for senior AI architect roles — label it explicitly in all architecture diagrams.
- **Multi-Agent Orchestration (Token Savings & Determinism)**: Breaking down monolithic tasks (like `/progress`) into smaller, single-function micro-agents limits context window overflow. By isolating **Probabilistic (Cost/AI)** nodes from **Deterministic (Free/Scripts)** nodes, we strictly only spend tokens when LLM reasoning is required. Tasks like Context Gathering (natively reading files), Verifiers (checking syntax), and Updaters (modifying Markdown) are 100% free pure Python logic. This deterministic enforcement directly wraps the AI calls, eliminating infinite hallucination loops and lowering compute costs.
  
  ```mermaid
  graph TD
      classDef aicost fill:#9333ea,stroke:#7e22ce,stroke-width:3px,color:#fff,font-weight:bold
      classDef scriptfree fill:#2563eb,stroke:#1d4ed8,stroke-width:3px,color:#fff,font-weight:bold
      classDef hitl fill:#ef4444,stroke:#dc2626,stroke-width:3px,color:#fff,font-weight:bold
      classDef doc fill:#475569,stroke:#334155,stroke-width:2px,color:#fff
  
      subgraph Legend ["Architecture Legend"]
          direction LR
          L1["AI Node - Probabilistic Cost"]:::aicost
          L2["Script Node - Deterministic Free"]:::scriptfree
          L3["Human-in-Loop - Gates"]:::hitl
      end
  
      User(["User Request Prompt"]):::scriptfree
      
      ContextScript["Context Retrieval Script (Native RAG)"]:::scriptfree
      Verifier["Verifier Script (Python/Regex Linters)"]:::scriptfree
      UpdaterAgent["Updater Script (Writes Markdown and Code)"]:::scriptfree
      
      Orchestrator{"Orchestrator Agent LLM"}:::aicost
      CoderAgent["Coder Agent LLM"]:::aicost
      DiagramAgent["Diagram Agent LLM"]:::aicost
      
      HITL{"Human Approval Gate"}:::hitl
      
      ProgressMD[("PROGRESS.md")]:::doc
      CodeBase[("Local Codebase")]:::doc
  
      User -->|Triggers process| ContextScript
      ContextScript -.->|Feeds raw text| Orchestrator
      
      Orchestrator -->|Delegates Task| CoderAgent
      Orchestrator -->|Delegates Task| DiagramAgent
      
      CoderAgent -->|Submits string| Verifier
      DiagramAgent -->|Submits string| Verifier
      
      Verifier -->|Syntax Error Router| CoderAgent
      Verifier -->|Syntax Error Router| DiagramAgent
      
      Verifier -->|Passes Linter| HITL
      
      HITL -->|Rejects with Feedback| Orchestrator
      HITL -->|Approves| UpdaterAgent
      
      UpdaterAgent -->|Updates| ProgressMD
      UpdaterAgent -->|File System Write| CodeBase
  ```
- **Archivist / Reflection Pattern**: Implementing a `--close` flag on initialized workflows (like `/progress`) converts the swarm into an Archivist/Reflection Agent before session teardown. It automatically compresses the conversation's architectural decisions, new workflow instructions, and bug fixes into high-density rules. This prevents tribal knowledge loss between sessions and ensures structural continuity across context window wipes.
- **Updater/Archivist Code Review Gate**: For highly-sensitive applications (like Financial Auditing), the Updater agent must explicitly halt and request a Human-In-The-Loop (HITL) approval for any uncommitted code generated in the session. This sacrifices unsupervised automation overnight for guaranteed protection against hallucinated overwrite errors.
- **Explain Modifier Protocol**: The `--explain` workflow parameter forces AI responses into a strict "First Principles" vs "Devil's Advocate" breakdown format. This ensures every architectural decision is inherently challenged and validated before execution.
- **Phase 3 Trust Sandwich implementations**: Phase 3 (Bank Reconciliation) effectively demonstrates the "Trust Sandwich" architecture. The deterministic auditor (`Node 3`) handles 100% of mathematical cross-referencing (finding missing/double checks) locally in Python for 0 tokens, only tagging in the expensive `claude-3-5-sonnet` model for final forensic anomaly evaluation.

---
*(AI Note: Update the tasks above using the `multi_replace_file_content` tool when completing milestones.)*
