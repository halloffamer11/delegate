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

**Status:** landed 2026-10-11. `Ads` normalizes the relay's usage record into Token counts
`{in, out, cache_read, cache_write}` (None when it reported neither input nor output);
`Report.tokens`, `runs.Finish.tokens` and the `DISPATCH_FIELDS` entry `tokens` replace `usage`
in its place, and `report.compute_cost(tokens, lane, catalog)` reads only those four keys.
test_relay a9 (one row per spelling, and none from a relay that reported none) and a3 (the grok
gate-cancel replay), test_runs 1 (the outcome key order), test_dispatch 1 (`tokens` null end to
end) and test_report's dollar and unmeasured cases verify it. No box is open.

- [x] `report.py` defines no `INPUT_KEYS`, `OUTPUT_KEYS`, `CACHE_READ_KEYS` or `CACHE_WRITE_KEYS` and reads no relay key spelling.
- [x] `runs.Finish` and `runs.DISPATCH_FIELDS` name `tokens`, not `usage`, in the same position, and test_runs' outcome key-order case expects `tokens`.
- [x] Replaying the grok gate-cancel fixture through `Ads` gives tokens `{"in": 16595, "out": 794, "cache_read": 5888, "cache_write": 0}`.
- [x] Every spelling the report accepted before normalizes through `Ads` in the test_relay table.
- [x] A relay that reports no usage (the fake relay, codex) records tokens null, and the report says unmeasured, not $0.00.
- [x] test_report's grok, claude, terra, explicit-lane and unpriced cases pass on `dispatch.json` `tokens` fixtures with the same dollar figures.
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

**What shipped.**
- `scripts/relays.py`: `_TOKEN_SPELLINGS` maps each Token count to the usage spellings the report
  used to keep, read in the same order, and the private `_tokens(usage)` turns `result.json`'s
  `usage` into `{in, out, cache_read, cache_write}`, a missing count read as 0, or None when the
  record is absent, not an object, or has neither input nor output. `Report.tokens` replaces
  `Report.usage`; `_settle` hands it to the Finish. The raw record stays in the relay's
  `result.json`.
- `scripts/runs.py`: `Finish.tokens` replaces `Finish.usage`, and `DISPATCH_FIELDS` names `tokens`
  where it named `usage` (between `session` and `touched_files`). The module docstring says
  `dispatch.json`'s `tokens` are the Run's Token counts and `result.json` keeps the raw record.
- `scripts/report.py`: `INPUT_KEYS`, `OUTPUT_KEYS`, `CACHE_READ_KEYS`, `CACHE_WRITE_KEYS` and
  `_first_present` are gone. `compute_cost(tokens, lane_name, catalog)` reads the four keys;
  anything but an object is unmeasured ("relay reported no token counts"). `cmd_log` and
  `cmd_cost` read `dispatch["tokens"]`, and `log --run`'s help names tokens.
- `references/architecture.md`: the `relays.py` entry names the normalization, and the
  `report.py` entry gained the cost line (`log --run` and `cost` price a Run from `tokens`;
  null tokens or a Run directory from before them are unmeasured). CONTEXT.md's Token counts
  entry stays true as written.

**How it was verified.**
- Red first: test_relay a9 failed with no `tokens` field on the Finish, then s1 with
  `Report.__new__() got an unexpected keyword argument 'tokens'`; test_runs 1 ended its Run blocked
  because `Finish` took no `tokens`; test_report's grok, claude, terra, explicit-lane and unpriced
  cases read unmeasured on the `tokens` fixtures, and the new raw-usage case read measured.
- test_relay, new: a9 replays a staged `result.json` per spelling (four input, four output, four
  cache-read and two cache-write spellings; a cache count rides with an input count), a count that
  is not a number, and four records with no counts (null, cache only, not an object, absent),
  plus the fake relay's `usage: null` (as codex reports), which gives None. Changed: a3 expects
  the grok gate-cancel replay's tokens `{in: 16595, out: 794, cache_read: 5888, cache_write: 0}`
  and that the run's own `result.json` still holds the raw record; s1 and a4 carry tokens.
- test_runs 1 expects `tokens` in the outcome, and pins the outcome key order with a literal.
  test_dispatch 1 (end to end through the fake relay on a codex Lane) reads `tokens` null and no
  `usage` key in `dispatch.json`.
- test_report: every fixture writes `tokens`; the dollar figures are unchanged ($0.45 grok,
  $0.10 claude cache write, terra's null cache-write price adding 0, explicit lane $0.024 in,
  unpriced). Null tokens log unmeasured and `runs` shows unmeasured, not $0.00. New: `cost` of a
  Run directory holding only a raw `usage` record is unmeasured.
- A mutation check turned each case red: reading any non-null value as a count (a9), dropping the
  neither-input-nor-output rule (a9), passing the raw record through (a3, a4, a9), dropping
  `tokens` from the outcome (test_runs 1), `DISPATCH_FIELDS` naming `usage` again (test_dispatch
  1), and the report falling back to, or reading, `usage` (test_report).
- `evals.py ping --offline` still passes claude, codex, agy and grok. `make test` is green with
  every proxy variable pointed at a closed port, on Python 3.9 and 3.13.

**Deviations.**
- `Ads` reads a count only when it is a number (an int or a float, never a bool); a value that is
  not falls through to the next spelling. The report used to take any non-null value, which a
  string would have crashed at pricing time.
- `compute_cost`'s unmeasured reason reads "relay reported no token counts" (was "relay reported
  no token usage"). Its result keeps the `input_tokens` ... `cache_write_tokens` and `usd_*` keys
  that `runs.jsonl` already stores; those are the report's own record keys, not relay spellings
  it reads.
- The neither-input-nor-output rule lives in `Ads` alone; `compute_cost` treats any object as
  counts and reads a missing key as 0.
- `references/architecture.md`'s `report.py` entry had no cost line to update, so this ticket
  added one.
