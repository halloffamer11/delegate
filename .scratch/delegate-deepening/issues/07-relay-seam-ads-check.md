# 07 — Only the ADS adapter knows node, the pin and the relay argv

**What to build:** Candidate G, ticket G3 (lane run-and-relay). Add `Relay.check`:
`Ads.check` runs `sh ads.sh check` with `ADS_DIR` set to the adapter's resolved directory
and returns the first line it printed on failure, or None. `Scripted.check` returns its
`ready`. Add `relays.DEFAULT_DIR` and resolve the directory once in `Ads` (the argument,
else `$ADS_DIR`, else the default). `resolve()` asks the relay's check for a relayed Lane
in place of its own subprocess, and `resolved['ads_dir']` goes away.

`delegate.dispatch` and `delegate.run` take `relay=None`, which defaults to
`relays.Ads(ads_dir)`, so a caller can hand in a `Scripted` fake in-process; C's
in-process Run tests can use it. Add a one-line comment in `ads.sh` pointing to
`relays.DEFAULT_DIR`.

In test_relay, test `check` against the world with the right pin, a wrong pin
(`ADS_FAKE_GIT_SHA`), node missing, and a missing relay script. Test argv and env per
harness through `Ads.run` with the fake relay's `argv.json` and `env.json`; these replace
test_dispatch 9a to 9h, 9a2, the argv half of 24, and 31f. Add a test that `DEFAULT_DIR`
equals `ads.sh`'s `ADS_DIR` default. In test_dispatch, add one in-process case that runs
dispatch with `relay=Scripted(...)` and asserts the Job the fake received (harness,
model, an `--effort` override, write and cwd); it replaces 9b. Keep 12c and 12d as
end-to-end wiring.

Spec: `.scratch/delegate-deepening/spec.md` (G. Relay seam; decision G.4)

**Blocked by:** 05 A relay that crashes before writing its result says why; 06 The offline eval and the dispatch tests share one world that the host's Seatbelt never reaches

**Status:** ready-for-agent

- [ ] `delegate.py` runs no `sh ads.sh` and names no ADS directory.
- [ ] `relays.Ads.check` returns None on the pinned world, and one line naming the cause for a wrong pin, a missing node and a missing relay script.
- [ ] A dispatch whose relay check refuses exits 2 with no run directory and no Ledger start (12c and 12d still pass end to end).
- [ ] The argv and env cases run through `relays.Ads` in test_relay, and 9a to 9h, 9a2, the argv half of 24 and 31f are deleted from test_dispatch.
- [ ] `delegate.dispatch(..., relay=relays.Scripted(...))` runs in-process with no node, and a test reads the Job the fake received.
- [ ] A test asserts that `relays.DEFAULT_DIR` equals the `ADS_DIR` default in `ads.sh`.
- [ ] `make test` passes on Python 3.9 and 3.13.
