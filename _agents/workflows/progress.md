---
description: Resume context from the PROGRESS.md handover document.
---

When the user triggers `/progress`, execute the following steps exactly as written:

1. **Read the Handover Document**: Immediately use the `view_file` tool to read the contents of `/WORKING_DIRECTORY/PROGRESS.md`.
2. **Internalize the Context**: Parse the Overall Goal, the checked/unchecked task list, and explicitly apply the "Operating Instructions" (such as the 10-turn cutoff limit) to your internal prompt parameters.
3. **Report Readiness**: Give the user a brief, 2-sentence summary acknowledging the current active Phase & Objective, and confirm that you are ready to begin the next unchecked task on the list.
4. **List Referenced Documents**: Explicitly list out all documents and files you have used or referenced during this setup phase before prompting the user for their next input.
5. **Do Not Execute the Task Yet**: Wait for the user to explicitly confirm or provide additional input before writing new code.
6. **Close Flag Handling (`--close` or `-close`)**: If the user provides this flag alongside the command, instantly act as the "Updater/Archivist Agent". Do NOT perform the regular setup. Instead:
   - **Code Review (HITL)**: Scan the conversation for any uncommitted code. Propose these changes cleanly and ask for final Human-in-the-Loop (HITL) approval. Do not save code to disk without it.
   - Use the `replace_file_content` tool to formally check off `[x]` completed tasks in `PROGRESS.md` based on what was achieved.
   - Scan for newly discovered bugs or architectural decisions and append them to the "Lessons Learned" section in `PROGRESS.md`.
   - Output a brief summary and explicitly instruct the user to close the chat and start a new session.
