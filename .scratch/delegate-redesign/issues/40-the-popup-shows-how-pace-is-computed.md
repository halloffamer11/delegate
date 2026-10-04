# 40 — The usage popup shows how Pace is computed

**What to build:** The Herdr popup (`prefix+shift+U`) shows, for each Meter, the weekly
Pace as its calculation (week quota left ÷ share of the week left), and for each Tier
where its Lanes stand against the steal line (leader + margin). It says how far each
Tier leader is from handing over, in quota points at the current reading. Raised by
The user 2026-09-27.

Everything reads the Meters at the moment of display. No usage history and no burn
rate: the user, 2026-09-27, "We can only make a decision based on the usage at the time of
sending a delegation" (`docs/adr/0001-settled-delegate-decisions.md`).

**Prototype:** branch `worktree/delegate-redesign-popup`, file
`.scratch/delegate-redesign/prototype/popup_variants.py`. Run it from that checkout:
`python3 .scratch/delegate-redesign/prototype/popup_variants.py` (left and right arrows
switch layouts).

- Round one (`556f439`): A worksheet, B dot plot per Tier, C quota-vs-time bars. The user
  picked B, and found C too busy, with "quota" and "week" undefined.
- Round two (`36d0aaa`): Meters at the top, then each Tier's lanes grouped by harness,
  visual first, in the glossary's terms. D puts the Meters and the Tiers on one Pace
  axis, one row per Meter in each Tier. E shows each Meter as a weekly Remaining bar
  with a share-of-week tick, then one row per lane. D is 23 rows and E is 27, so the
  popup needs about 50% or 60% height, up from 40%.

**Blocked by:** None — can start immediately.

**Status:** ready-for-human. Layout D built 2026-10-04 as the recommended pick, pending the user's choice; the prototype branch is pushed (`968e534`).

- [ ] The user picks a layout, or parts of several.
- [x] `report.py statusline --popup` renders it from the cached Meters only, with tests in
      `test_report.py`, and it fits the popup (85% × 40%, about 118 × 20). Built as D: the
      Meter rows write Pace as `= Remaining ÷ share of week`, and each Tier shows its leader,
      how many points its Meter can fall before the Tier hands over, and for each other
      Meter the Pace it needs to lead. Both figures replay `rank.choose`, now shared, so
      the popup cannot disagree with a Pick. `┊` marks a rival's needed Pace, not leader +
      Margin: without an Order a rival needs only the leader's Pace, and the Margin
      applies only across Order. The test catalog renders in 19 rows; a real catalog with
      seven Meters needs about 30, so the Herdr popup's height goes to 60% in dotfiles.
      With Meters off, or no harness CLI on PATH, the popup keeps the old rows.
- [ ] The prototype branch is removed after the pick is recorded here.

Open detail: the handover figure for Tier 4 assumes the `claude-fable` Meter does not
drop when `claude-general` is spent. Whether the two weekly pools move together is not
verified.
