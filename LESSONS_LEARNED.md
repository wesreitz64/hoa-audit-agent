# 📚 Lessons from Building an AI Financial Audit Swarm

> **By Wes Reitz** — Learned hands-on building a multi-agent HOA financial audit system with LangGraph, Claude, and Pydantic.
>
> These are hard-won insights from production development, not textbook theory.

---

## 1. Two Kinds of PDFs — And Why It Matters

| Type | How it's made | Text extraction | Accuracy | Cost |
|---|---|---|---|---|
| **Digital-native** | Software generates the PDF directly from a database (CINCSystems, QuickBooks, bank portals) | PyMuPDF reads embedded text instantly | 100% | Free |
| **Scanned/image** | Paper → scanner → photo wrapped in PDF | Requires OCR (Tesseract, AWS Textract, LlamaParse) | 85-95% | Paid, slow |

**The insight:** Before building any AI document processing pipeline, check if `page.get_text()` returns content. If it does, you don't need OCR at all — you skip an entire layer of complexity and error. Most business-to-business documents (bank statements, management reports, utility bills) are digital-native. Scanned PDFs are mostly handwritten notes, old contracts, and photographed receipts.

**One-liner for your blog:** *"70% of the PDFs your AI will process already have perfect text inside them. Check before you pay for OCR."*

---

## 2. Built-in Checksums — Let the Source System Verify Your AI

CINCSystems (and most accounting software) puts **subtotals and grand totals** at the bottom of every report:

```
Reliant Total:                              $   41.78
Briarwyck Owners Association, Inc. 11 Invoice(s) Totaling:  $ 9,966.13
GRAND 11 Invoice(s) Totaling:               $9,966.13
```

**The pattern:**
1. Let the LLM extract individual records from the page
2. Sum the extracted amounts with Python (deterministic math)
3. Compare against the grand total the source system already printed
4. If they don't match → flag for human review

**Why this is powerful:** You never ask the LLM to do math. The LLM reads text and fills in fields. Python does the arithmetic. The source document provides the answer key. Three independent checks, zero trust in any single one.

**One-liner:** *"Don't ask your AI to do math. Let it read, let Python calculate, and let the source document grade the homework."*

---

## 3. Eval Every Node Before Building the Next One

**The anti-pattern:** Build all 4 nodes → test at the end → discover Node 1 was wrong → Nodes 2-4 wasted

**The correct pattern:**
```
Build Node 1 → Eval → Fix → Eval again → PASS → 
Build Node 2 → Eval → Fix → Eval again → PASS → ...
```

**Real example from this project:**
- Node 1 (Triage Router) classified 53 pages. Initial run: 86.8% accuracy.
- 7 pages labeled `homeowner_aging` should have been `homeowner_ledger`
- If we'd built the aging extractor first, it would have received wrong pages and produced garbage
- Fixed the prompt, re-ran only the 7 bad pages (saved 46 API calls), hit 100%

**One-liner:** *"In AI pipelines, errors compound downstream. Eval at every node or pay the tax at the end — in tokens, time, and trust."*

---

## 4. LLM Confidence Scores Are Unreliable

Claude classified 53 pages. Seven were wrong. Every single one had **95% confidence**.

| Page | Claude's Label | Correct Label | Claude's Confidence |
|---|---|---|---|
| 47 | homeowner_aging | homeowner_ledger | 95% |
| 48 | homeowner_aging | homeowner_ledger | 95% |
| ... | ... | ... | 95% |

**The lesson:** LLMs are poorly calibrated for uncertainty. A model saying "95% confident" doesn't mean it's right 95% of the time. It means the model is always that confident — right or wrong.

**What to do instead:**
- Use **keyword-based validation** (if text contains "Receivables Type Balances" → it's a ledger, period)
- Use **deterministic checksums** (sum of parts = reported total)
- Use **human-in-the-loop** for genuinely ambiguous cases
- Don't gate decisions on LLM confidence scores alone

**One-liner:** *"An LLM saying '95% confident' is like a used car salesman saying 'trust me.' Verify with deterministic checks."*

---

## 5. Domain Knowledge Beats Prompt Engineering

The hardest classification problem wasn't solved by a better prompt. It was solved by understanding what the documents actually are:

- **"Homeowner Aging Report"** = "How old is the debt?" (collections focus — 30/60/90 day buckets)
- **"Receivables Type Balances"** = "What happened this month?" (accounting focus — billing, receipts, adjustments)

PMI uses confusing titles. The AI used confusing labels. A Board member who reviews these monthly could distinguish them instantly because they know the *purpose*, not just the format.

**The lesson:** The most valuable person on an AI project isn't the prompt engineer — it's the domain expert who can say "that's wrong, and here's why." AI architectures need a seat at the table for subject matter experts, not just engineers.

**One-liner:** *"The $200k AI architect isn't the one who writes the best prompts — it's the one who asks the right questions to the right domain expert."*

---

## 6. Token Cost Management — Re-run Only What Failed

When Node 1 had 7 misclassifications out of 53 pages:
- ❌ **Naive approach:** Re-run all 53 pages = 53 API calls = ~$0.20
- ✅ **Smart approach:** Re-run only the 7 failed pages = 7 API calls = ~$0.03

We cached results to JSON after every run. When the prompt was fixed, we loaded previous results, replaced only the re-run pages, and saved back. Total cost of the fix: **3 cents.**

**The pattern:**
1. Save every API result to disk immediately (JSON)
2. When something fails, identify which specific items failed
3. Re-run only those items
4. Merge results back into the full dataset

**One-liner:** *"Cache everything, re-run nothing you don't have to. Your API bill is a leaky bucket — plug every hole."*

---

## 7. The Header/Detail/Footer Pattern in Financial Documents

Almost every CINCSystems report follows the same structure:

```
VENDOR HEADER (bold, left):   "PMI Cross Timbers - Mgmt Mod Only"
  LINE ITEM:  Invoice #4012   $824.00   Management Fee
  LINE ITEM:  Invoice #4123   $156.50   Admin Fees  
VENDOR FOOTER (bold, right):  "PMI Cross Timbers - Mgmt Mod Only Total: $980.50"
```

**Why it matters for extraction:**
- The LLM should extract **one record per vendor** using the **footer total**
- NOT one record per line item (that double-counts)
- The footer total is the amount that appears in the bank statement as one withdrawal

**Failure example:** First extraction attempt created 11 records ($10,790.13) because Claude treated the $824 line item AND the $980.50 total as separate invoices. After fixing the prompt to explain header/detail/footer structure: 9 records ($9,966.13) — matching the PDF's grand total exactly.

**One-liner:** *"Teach your AI the document's anatomy — header, detail, footer — not just 'extract the numbers.'"*

---

## 8. Schema-First Development for AI Agents

Before writing a single line of agent code, we defined the exact output structure using Pydantic:

```python
class InvoiceListItem(BaseModel):
    vendor_name: str
    amount: float = Field(ge=0)  # Can't be negative
    gl_account_code: str
    confidence: float = Field(ge=0.0, le=1.0)  # Bounded
```

**Why this works:**
- The LLM's output is **validated automatically** — if it returns a negative amount, Pydantic rejects it
- Every downstream node knows exactly what data shape to expect
- Tests can be written with real values before the agent even exists
- Schema changes are visible in git diffs — the "contract" is version-controlled

**One-liner:** *"Define what your AI should output before you tell it how to think. Pydantic is your AI's contract law."*

---

## 9. The 3-Provider Fallback Pattern

During development, both OpenAI and Claude ran out of credits at different times. Solution: auto-detect and fallback:

```python
def get_llm():
    if os.getenv("ANTHROPIC_API_KEY"):   return Claude
    elif os.getenv("GOOGLE_API_KEY"):    return Gemini
    elif os.getenv("OPENAI_API_KEY"):    return OpenAI
    else: raise "No API key found"
```

**Why this matters in production:** API downtime, rate limits, and credit exhaustion are not edge cases — they're Tuesday. A single-provider architecture is a single point of failure.

**One-liner:** *"Your AI system should have a backup LLM the way your house has a backup generator. When Claude goes down at 2am, Gemini picks up."*

---

## 10. The Sandwich Architecture — Deterministic Bread, AI Filling

The most important pattern in this entire project is how we use AI:

```
┌─────────────────────────────────────────────────────┐
│  DETERMINISTIC (Python)     — Read PDF text         │  Free, can't fail
│  DETERMINISTIC (Python)     — Filter by page type   │  Free, can't fail
│  ┌───────────────────────────────────────────────┐  │
│  │  AI (Claude)             — Extract data        │  │  Costs $, CAN fail
│  └───────────────────────────────────────────────┘  │
│  DETERMINISTIC (Python)     — Verify totals match   │  Free, can't fail
│  DETERMINISTIC (Python)     — Save to JSON          │  Free, can't fail
└─────────────────────────────────────────────────────┘
```

The AI is **sandwiched** between layers that are 100% reliable. Python handles everything it's good at — reading files, filtering lists, doing math, saving results. Claude handles the ONE thing Python can't do: reading messy human text and deciding what it means.

**The cost and risk breakdown:**

| Step | Who does it | Cost | Can fail? |
|---|---|---|---|
| Read PDF text from file | PyMuPDF (Python) | Free | No |
| Decide which pages to process | Python (load cached JSON) | Free | No |
| Read text → fill structured fields | Claude (LLM) | ~$0.005/page | **Yes** |
| Verify sum of parts = grand total | Python math | Free | No |
| Save results to disk | Python file I/O | Free | No |

**The trust boundary:** Everything outside the AI layer is trusted. Everything inside is verified. The AI is never the final word — it proposes, Python confirms.

**Why this matters:**
- If Claude hallucinates an amount, the checksum catches it
- If Claude misses an invoice, the count check catches it (PDF says "11 Invoice(s)")
- If Claude returns malformed data, Pydantic rejects it before it reaches your database
- The AI never does math, never makes decisions, never touches the file system

**Compare to the naive approach:**
```
❌ NAIVE:    PDF → LLM → "summarize the invoices and total them" → trust the output
✅ SANDWICH: PDF → Python reads text → LLM fills fields → Python verifies math → save
```

The naive approach gives you a paragraph of text you can't programmatically verify. The sandwich gives you structured data you can audit, compare, and prove.

**One-liner:** *"Never let your AI be the first or last step. Sandwich it between deterministic layers that can verify its work."*

---

## 11. Not Everything Needs an LLM — Know When to Use Python Instead

We tried two approaches to extract 47 bank transactions from SouthState Bank statements:

| Approach | Time | Cost | Accuracy | Result |
|---|---|---|---|---|
| Claude structured output | 9+ minutes | ~$0.05 | Never finished | **Timed out** |
| Python regex parser | < 1 second | $0.00 | 100% | **47 transactions, verified** |

**Why Claude failed:** Structured output mode forces the LLM to generate the ENTIRE JSON response before returning — no streaming, no partial results. With 47 transactions × 8 fields each = 376 JSON values to generate token-by-token. It's like asking someone to recite a phone book from memory in one breath.

**Why Python worked:** Bank statements have rigid, mechanical formatting:
```
Line 1: 02/04/2026           ← Always MM/DD/YYYY, always its own line
Line 2: CORP ICL/RDC DEPOSIT ← Description, always the next line
Line 3: $1,389.92            ← Amount, always the line after that
```

A 3-line regex pattern extracts every transaction perfectly. Section headers ("Deposits", "Electronic Debits") tell you credit vs debit. No judgment required.

**The decision framework:**
```
Can a regex or predictable pattern extract this data?
├── YES → Use Python. Faster, free, deterministic, debuggable.
│         Examples: bank statements, CSV-like tables, structured headers
│
└── NO  → Use the LLM. It handles ambiguity that requires judgment.
          Examples: classifying page types, vendor name normalization,
                    understanding invoice header/detail/footer grouping
```

**Why we used Claude for invoices but Python for bank statements:**
- **Invoice List:** Variable vendor names, mixed GL codes, header/detail/footer grouping — requires *judgment* to decide what's a line item vs a vendor total
- **Bank Statement:** Every transaction follows the same rigid 3-line format — requires *pattern matching*, not judgment

**The deeper insight:** Your AI budget is finite. Every token spent on something Python could do is a token NOT spent on something only AI can do. The engineer who reaches for an LLM for everything is like a surgeon who uses a scalpel to open a door — technically possible, but wasteful and slow.

**One-liner:** *"Use AI for judgment, Python for patterns. If a regex can do it, the LLM shouldn't."*

---

## 12. Multi-Page Reports — Think in Documents, Not Pages

Bank statements, aging reports, and ledgers span multiple pages. The same section flows across page boundaries:

```
Page 14:                          Page 15:
  Other Credits                     Other Credits (continued)
    02/05  OnlinePay  $124.00         02/11  OnlinePay  $255.44
    02/06  OnlinePay  $124.00         02/12  Payabli    $127.72
    (page break)                      02/18  Payabli    $105.44
                                    Electronic Debits
                                      02/06  City of C  $97.24
                                      ...
```

**The problem:** If you process pages independently, you miss that "Other Credits (continued)" on page 15 is the same section from page 14. Your parser needs to carry state across pages.

**The pattern:**
1. **Group pages by document** — pages 14-19 are ONE operating statement, not 6 separate pages
2. **Look for "(continued)" headers** — they tell you the current section
3. **Use the first page's summary as checksum** — "30 Credit(s) totaling $13,262.54" is the answer key for ALL pages in that statement
4. **"Intentionally blank" pages are delimiters** — they mark the boundary between documents (operating → reserve)

**The checksum pattern for multi-page reports:**
```python
# Page 14 header tells us the expected totals for pages 14-15 combined:
#   "30 Credit(s) This Period  $13,262.54"
#   "15 Debit(s) This Period   $11,957.74"
# Parse pages 14 + 15, sum all credits, compare to $13,262.54 → MATCH ✅
```

**One-liner:** *"A page is not a document. Carry state across page breaks, and let the first page's summary verify the last page's data."*

---

## 13. SQL Beats RAG for Financial Data — Don't Vector-Search Numbers

When we needed to answer questions like "How much did we spend on electricity?" there were two paths:

| Approach | How it works | Good for | Bad for |
|---|---|---|---|
| **RAG (vector search)** | Embed chunks → similarity search → LLM reads matches | Unstructured text, narrative documents | Precise numeric aggregation |
| **SQL (structured query)** | Load clean data → LLM writes SQL → execute → format | Numbers, dates, totals, comparisons | Free-form prose |

**We chose SQL**, and here's why:

```
RAG approach:  "How much on electricity?"
  → Embeds question → Finds chunks mentioning "electric"
  → LLM reads 3 text chunks → Guesses "$67.43" (maybe)
  → No way to verify, no audit trail

SQL approach:  "How much on electricity?"
  → LLM writes: SELECT SUM(amount) FROM invoices WHERE gl_account_name = 'Electricity'
  → SQLite returns: 67.43 (exact, deterministic)
  → You can see the query, re-run it, audit it
```

**The key insight:** Once you've extracted structured data (amounts, dates, vendor names, GL codes), that data is **already tabular**. Shoving it into a vector database and doing similarity search is like putting a spreadsheet through a blender and then asking someone to read the smoothie.

**The architecture we built:**
```
Extracted JSON → SQLite database (with indexes, generated columns)
                     ↓
User question → LLM generates SQL → Execute → LLM formats answer
                     ↓
"Granite Landscape was paid $4,979.50 — 59% of total spending"
(with invoice numbers, dates, and source citations)
```

**Bonus — the SQL agent self-corrects:** If the generated SQL has a syntax error, we catch it, send the error back to the LLM, and let it fix the query. Two-shot SQL generation covers 99% of questions.

**When to use RAG instead:**
- Meeting minutes ("What did the board discuss about the pool?")
- Contracts and legal documents ("What are the landscaping contract terms?")
- Any document where meaning lives in paragraphs, not numbers

**One-liner:** *"If your data has columns, use SQL. If your data has paragraphs, use RAG. Financial data has columns — stop vector-searching your spreadsheets."*

---

## 14. Generated Columns and Indexes — Let the Database Do the Work

When designing the SQLite schema, we added generated columns:

```sql
CREATE TABLE bank_transactions (
    transaction_date TEXT NOT NULL,    -- '2026-02-15'
    -- Auto-derived for grouping queries:
    month TEXT GENERATED ALWAYS AS (substr(transaction_date, 1, 7)) STORED,  -- '2026-02'
    year  TEXT GENERATED ALWAYS AS (substr(transaction_date, 1, 4)) STORED   -- '2026'
);
```

**Why this matters for the AI query agent:**
- The LLM can write `GROUP BY month` instead of `GROUP BY substr(transaction_date, 1, 7)`
- Simpler SQL = fewer syntax errors = fewer retry calls = lower token cost
- Indexes on `month` make aggregation queries instant even with thousands of rows

**The broader pattern:** When building a database that an LLM will query, **optimize for LLM ergonomics** — descriptive column names, pre-computed groupings, and lookup tables. The easier you make it for the LLM to write correct SQL, the fewer tokens you burn on retries.

**One-liner:** *"Design your schema for your dumbest user — because that user is an LLM writing SQL."*

---

*More lessons coming as we build the Reconciliation Engine and Audit Report Generator...*
