# 29 — Dispatch queues models the catalog lacks

**What to build:** Dispatch notices models no Lane runs and queues them for the next
`delegate global`, whose start page names them. At most once a day, dispatch starts a
detached scan that runs the wizard's own discovery and refresh against the global lanes.
It never delays or fails the dispatch. `dispatch --model <slug>` naming a model no Lane runs
queues it too. The wizard's confirm write empties the queue. The human still sets each new
Lane's Tier (ADR 0001).

From ticket 18: Orin picked "Queue + follow" on 2026-10-03.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-03. `scripts/model_queue.py` owns the queue (`new-models.json`
beside the meter cache, or `$DELEGATE_MODEL_QUEUE`). `delegate.py` calls `kick` after
resolve, and `note` when `--model` matches no Lane. The wizard's start facts add a
"Dispatch noticed" line, and both write paths empty the queue. `$DELEGATE_MODEL_SCAN=off`
stops the scan; the stubbed tests and the offline evals set it. Claude has no model list,
so the scan adds no Claude model; the wizard still finds those from benchmark rows.
Verified: `tests/test_model_queue.py`, and `make test` on 3.9 and 3.13. Orin's Mac: after
one real dispatch, `python3 scripts/model_queue.py show` lists what the scan found.

- [x] A dispatch starts at most one scan a day, detached, and never waits on it.
- [x] A model no Lane runs reaches the wizard's start page.
- [x] The wizard's write empties the queue.
- [ ] Orin sees a queued model on his Mac.
