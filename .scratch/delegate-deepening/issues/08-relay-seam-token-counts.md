# 08 — The report prices a Run from Token counts, not relay key spellings

**What to build:** Candidate G, ticket G4 (lane run-and-relay, its last ticket). `Ads`
normalizes the relay's usage record into Token counts keyed like a Lane's price record:
`{"in", "out", "cache_read", "cache_write"}`. It moves the key spellings out of
`report.py` (`input_tokens`, `inputTokens`, `prompt_tokens`, `promptTokens`;
`output_tokens`, `outputTokens`, `completion_tokens`, `completionTokens`;
`cache_read_input_tokens`, `cachedInputTokens`, `cached_tokens`, `cache_read_tokens`;
`cache_creation_input_tokens`, `cacheCreationInputTokens`). The result is None when the
relay reported neither input nor output.

`Report.tokens` and `runs.Finish.tokens` replace `usage`, and in the same change the
`runs.DISPATCH_FIELDS` entry `usage` becomes `tokens` and keeps its position; C's test_runs
outcome key-order case follows. The raw record stays in the relay's own `result.json`.
`report.compute_cost(tokens, lane_name, catalog)` reads the four keys. `cmd_log` and
`cmd_cost` read `dispatch['tokens']`, and the `--run` help text says tokens. test_report's
fixtures write `dispatch.json` with `tokens` and keep their dollar figures.

In test_relay, add a table that replays staged `result.json` files through `Ads`, one per
spelling. Also replay the real grok gate-cancel fixture and expect
`{in: 16595, out: 794, cache_read: 5888, cache_write: 0}`. Update the cost line in
`references/architecture.md` and the comment in `runs.py`'s docstring. `CONTEXT.md`'s
Token counts entry was added with the spec; keep it true to what ships.

Spec: `.scratch/delegate-deepening/spec.md` (G. Relay seam; decision G.2)

**Blocked by:** 05 A relay that crashes before writing its result says why

**Status:** ready-for-agent

- [ ] `report.py` defines no `INPUT_KEYS`, `OUTPUT_KEYS`, `CACHE_READ_KEYS` or `CACHE_WRITE_KEYS` and reads no relay key spelling.
- [ ] `runs.Finish` and `runs.DISPATCH_FIELDS` name `tokens`, not `usage`, in the same position, and test_runs' outcome key-order case expects `tokens`.
- [ ] Replaying the grok gate-cancel fixture through `Ads` gives tokens `{"in": 16595, "out": 794, "cache_read": 5888, "cache_write": 0}`.
- [ ] Every spelling the report accepted before normalizes through `Ads` in the test_relay table.
- [ ] A relay that reports no usage (the fake relay, codex) records tokens null, and the report says unmeasured, not $0.00.
- [ ] test_report's grok, claude, terra, explicit-lane and unpriced cases pass on `dispatch.json` `tokens` fixtures with the same dollar figures.
- [ ] `make test` passes on Python 3.9 and 3.13.
