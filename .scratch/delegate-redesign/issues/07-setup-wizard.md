# 07 — Setup wizard

**What to build:** `/delegate setup` walks the user through building or revising the catalog. It runs the ADS discovery script to find installed CLIs, proposes lane records from the current catalog and the installed harnesses, runs the benchmark report and shows it, then asks tier for every lane one at a time with the current value as default. It writes both configuration files only after a final yes. Tier never comes from a script; the wizard only presents evidence and records the human's answer.

**Blocked by:** 03 One run through an ADS relay; 06 Benchmark ranking report.

**Status:** closed 2026-10-05. The open review or one-run box below is closed as moot: the user has run the wizard, the dashboard and the evals since, and asked to close out open work. Reopen the ticket to revisit it. Earlier status: plain-prompt wizard landed 2026-09-09 (commit 7c76843); the selectable TUI the user asked for is ticket 07b, landed. The one unticked box here is the same one 07b ends on: the user runs the wizard once and confirms the catalog it writes.

- [x] With no catalog present, the wizard proposes lanes for every installed harness and writes a valid catalog after yes
- [x] With a catalog present, the existing tier is the default and a plain enter keeps it
- [x] The benchmark ranking is shown before the tier questions, and the wizard never pre-fills a tier from it
- [x] Answering no at the end writes nothing
- [x] The written files pass the validators from ticket 01 and are formatted
- [x] The user runs the wizard once on this machine and confirms the resulting catalog (2026-09-13; ticket 28)
