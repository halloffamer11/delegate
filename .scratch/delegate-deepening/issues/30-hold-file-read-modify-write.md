# 30 — Two runs settling at once can lose a Usage-limit hold

**What to build:** a follow-up to Candidate B, found by the Codex review of the effort
(finding B-4). `usage.hold` and `usage.release` read the hold file beside the Meter
snapshot, change one Meter's entry and write the whole file back, with no lock. Two Runs
that settle at the same moment on different Meters can each read the file before the
other writes, so the second write drops the first one's hold (or brings back a hold the
first one released). A dropped hold lets the next `rank` pick a Meter the harness has just
refused; a stale hold keeps a Meter at nothing left until its weekly reset or 24 hours.

The race is older than this effort: `mark_limited`, which `hold` replaced, read and wrote
the cache the same way. So the effort kept the behavior and left the design here.

Choose how the hold file takes concurrent writers, then build it test-first. Two shapes to
weigh: an advisory lock (`fcntl.flock` on POSIX; the Windows probes in
`harnesses/base.py` need an equivalent or a documented gap) held across the read and the
write; or one file per Meter, so a hold and a release never share a document.

Spec: `.scratch/delegate-deepening/spec.md` (B. Meters; the Usage-limit hold)

**Blocked by:** none

**Status:** needs-triage

- [ ] A test starts two processes that hold and release different Meters against one
  cache path many times, and every hold that should stand is present at the end.
- [ ] `references/architecture.md` names how the hold file takes concurrent writers.
