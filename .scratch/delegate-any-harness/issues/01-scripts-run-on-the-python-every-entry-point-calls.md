# 01 — Scripts run on the Python every entry point calls

**What to build:** Every script parses on the Python that `python3` resolves to on Orin's machines, or the entry points name the interpreter they need. Today `scripts/delegate.py:172-232` and `scripts/bench_page.py:695` put a string literal with the same quote inside f-string braces, which only Python 3.12+ accepts, and 17 call sites run plain `python3`. Checked 2026-10-02: on 3.10 and 3.11 only those two files fail to compile.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] The supported minimum Python is stated once (README and `make test`), and it is no newer than the oldest `python3` on the Mac or omarchy.
- [ ] Every script and `tools/delegate-dashboard/*.py` compiles on that minimum (`python3.X -m py_compile`).
- [ ] `make test` fails fast with a clear message on an older interpreter instead of a SyntaxError traceback.
