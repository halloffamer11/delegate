# Maintenance

Checks for delegate itself: run them after changing a script, a relay pin or
the catalog format.

## Tests

`make test` in the checkout runs every script's test (stdlib only, no
network, no harness CLI needed). After touching one script, its own file is
enough: `python3 tests/test_<script>.py` from the skill directory.

## Evals

- `make eval-ping`: sends a trivial job to every installed harness and checks
  each returns `pong` with a valid `return.json`. It spends a little quota.
- `make eval-orchestrate`: the same job sent through the skill from each
  orchestrator profile with a headless launch; each run directory must match.
- `EVAL_ARGS=--offline` runs either against the fake relay and stub CLIs.

## Browser probes

`python3 scripts/browser_probes.py` runs the disposable and agent-profile
browser probes on every harness (`--dry-run` previews the commands). Live runs
spend quota. A native lane's rows read `NATIVE`: dispatch that lane with the
probe brief yourself and spawn the agent its native line names. A pass counts
only with evidence the browser was used, such as Playwright's page snapshots
in the probe's working directory; the nonce alone can be copied from the
brief.

## Relays and models

- `sh scripts/ads.sh check` confirms the pinned relays;
  `sh scripts/ads.sh install` restores them (`make install`, `make runtime` and `delegate setup` run it when the check fails).
- A model slug that stops resolving is edited in `lanes.json`. These list the
  current ones: `agy models`, `codex debug models`, `grok models`,
  `kiro-cli chat --list-models --format json`.
