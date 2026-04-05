---
description: List all available prompt modifiers and flags to control AI verbosity and formatting.
---

When the user triggers `/help` (or asks for help with prompt commands), explicitly output this list of available modifiers that you support. Treat these as strict global rules when you see them in a prompt:

### 🔇 Verbosity & Flow Modifiers
* **`-q` / `--quiet`**: Execute the task but respond with only a single, short sentence of confirmation (e.g., "Updated X file. Refresh browser."). Do NOT explain the code.
* **`-nr` / `--no-response`**: Execute the task silently. Output no chat response whatsoever. Typically handled by writing directly to logs, bypassing the UI completely to save context space.
* **`explain` / `--explain`**: Provide a detailed breakdown. Automatically apply "First Principles" reasoning and play "Devil's Advocate" to challenge the code or architecture before providing the final answer.
* **`--step`**: Proceed one step at a time, pausing to ask for explicit permission before executing the next logical block of work.
* **`--brainstorm` / `--whiteboard`**: Act purely as a sounding board—generate ideas and insights in chat, but DO NOT run commands, write code, or edit any documents.

### 📊 Formatting Modifiers
* **`--table`**: Output the requested data or findings explicitly as a Markdown table.
* **`--md` / `--artifact`**: Output the code or findings into a separate Markdown Artifact document instead of dumping large text blocks into the chat window.

*Always obey these modifiers when the user appends them to their commands.*
