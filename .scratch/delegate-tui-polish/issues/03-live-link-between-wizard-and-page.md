# 03 — The wizard and the page stay in sync

**What to build:** `o` serves the page from 127.0.0.1 behind a random key. The page reads the wizard's tiers and board and sends each change back; the wizard applies them between keys. A tier or board set on either side shows on both.

Spec: `.scratch/delegate-tui-polish/spec.md`

**Blocked by:** 01, 02

**Status:** implemented 2026-11-01, on `claude/project-thread-5eiff5`. The last box waits on the user.

- [x] `page_link.py` binds only 127.0.0.1, refuses a request without the key or with another Host, and writes nothing to disk.
- [x] `Wizard.apply_page_changes` takes tier and board changes; the curses loop polls every 300 ms.
- [x] `test_tier_matrix.py` covers the server; a Chromium run checked a click on the page reaching the wizard and a wizard change reaching the page.
- [ ] The user checks the round trip on the Mac.
