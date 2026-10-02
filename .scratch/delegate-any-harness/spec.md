# Delegate from any harness: review, design and plan

Read on 2026-10-02 from `halloffamer11/delegate` main (`23489e8`) and the
`halloffamer11/delegate-skills` fork. Reference: Anthropic's
[skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

## 1. Code review (code-review skill, high effort, whole repo)

Ranked most to least severe. Paths are under `agents/skills/delegate/` unless noted.

1. **Python 3.12+ only, but run as plain `python3`.** `scripts/delegate.py:172-232` and
   `scripts/bench_page.py:695` put a `", "` string inside f-string braces, which older
   Pythons reject. Every entry point (Makefile, shebangs, SKILL.md, courier, wrappers) calls
   `python3`. On macOS's `/usr/bin/python3` (3.9) every dispatch dies with a SyntaxError.
   One-character fix per line, or pin the interpreter.
2. **Courier can report a job finished while it is still running.** `agents/agents/courier.md:15`
   treats the first log line starting `delegate:` as the result. Dispatch also writes
   early `delegate:` lines, such as the agy "effort override ignored" warning and the
   native-lane line, and neither has `run=`.
3. **Missing `node` leaves a phantom running job.** `scripts/delegate.py:478` starts the relay
   after `ledger_start` without catching FileNotFoundError, so there is no finish event, no
   return.json, and the statusline shows a running glyph until the timeout.
4. **`--effort` on a native claude lane is accepted, recorded, and ignored.** `scripts/delegate.py:763`.
   The agent file fixes the effort, but dispatch.json says otherwise.
5. **`run` probes every vendor twice back to back.** `scripts/delegate.py:865`. That includes
   `claude -p /usage` twice, which can itself spend Claude quota.
6. **Unpriced lanes report $0.00 as measured.** `scripts/report.py:251`. The wizard creates new
   lanes with a null price.
7. **`usage.which()` disagrees with `shutil.which`.** `scripts/usage.py:200` (dead `if False` branch;
   accepts directories), so a probe can report "failed" where ranking reports "absent".
8. **SKILL.md contradicts its frontmatter.** `SKILL.md:4` sets `disable-model-invocation: true`, but the
   description says to use it "before any Agent, Workflow, or teammate spawn" and the body calls it
   model-invocable. The model is told to route and then is not allowed to.
9. **Hardcoded `"claude-fable"` meter name in the statusline.** `scripts/report.py:640`.
10. **Statusline tests depend on the host's installed CLIs.** `tests/test_report.py:302`. `report.py:559`
    checks PATH for each harness CLI and the test never stubs PATH. With stub `claude/codex/agy/grok`
    binaries all 107 checks pass. This is the 10 failures seen earlier, not a rendering bug.

## 2. How delegate works today

- **Core:** ~14k lines of stdlib Python in `scripts/`. `catalog.py` (lanes, routing, validation),
  `usage.py` (meter probes), `rank.py` (Class range → tier/order/pace pick), `delegate.py` (brief → run),
  `discover.py` (model discovery), setup wizard + TUI, bench pages, report/statusline.
- **Execution:** relayed lanes go through ADS (`node <ads>/skills/<harness>-delegate/scripts/relay.mjs
  --brief --cd --out-dir --model [flags]`), and delegate maps ADS `result.json` to its own
  `return.json` contract. Native lanes (`@claude`) never reach the relay. Instead delegate prints
  `agent=lane-<model-effort>` and the Claude session spawns that subagent itself.
- **ADS (the reference implementation)** is orchestrator-agnostic by design: anything with a shell can
  write a brief, run a relay, poll `result.json`. It has 17 relays, no Kiro, and each relay is a full copy
  (~650-1,300 lines) because a `skills add` install copies one directory only; parity is enforced by test.
  Its "lane" is just a name bound to one CLI: no ranking, no quota.

## 3. Is the problem "an adapter per harness"?

Partly. The adapters themselves are not the problem. Every harness really does need its own
discovery, quota probe, and flag mapping, and both 2026-09-15 deep-modules reviews said to keep that
boundary. The problem is that **there is no adapter type**, so each harness's knowledge is smeared
across the codebase, and **the orchestrator is hardwired to Claude Code**.

**Harness knowledge with no single home:**
- Four copies of the harness list: `catalog.py:39`, `browser_probes.py:32`, `ads.sh:17`, `discover.py:124`.
- `shutil.which(<harness name>)` in five places. This assumes the binary is named after the harness,
  which breaks for Kiro (`kiro-cli`).
- Per-harness if/elif chains in four concerns:
  - discovery: `discover.py:461`, with a claude special case in about 8 places;
  - meter probes: `usage.py:219-400`;
  - relay flags: `delegate.py:441-473`;
  - effort rules: `catalog.py:56`, plus `agy_family` in three files.
- The probes already share an implicit interface (each returns meter rows). Discovery and dispatch don't.

**Orchestrator = Claude Code, assumed in:**
- `delegate.py:62` `ORCHESTRATOR="claude"`.
- `setup.py:31,434-500`, which writes `~/.claude/agents/lane-*.md` in Claude subagent format.
- The courier, a Claude subagent.
- `SKILL.md:86`, which tells the session to use Claude's Agent tool.
- `~/.claude/skills/...` paths in SKILL.md, the four wrappers, council, and the courier.
- Claude-only frontmatter (`disable-model-invocation`, `$ARGUMENTS`).

The Makefile already links the skills into `~/.kiro/skills` and `~/.agents/skills`, but from there
they point back at Claude paths.

The 2026-09-08 assessment rated delegate "Claude Code only" and ADS "any agent with a shell". No later
document took orchestrating from another harness on as a goal, so this is new scope, not unfinished work.

## 4. Proposed abstraction

Two adapter roles, one registry, and a CLI core that any harness can drive.

**1/ Harness registry (one source of truth).** One module per harness under `scripts/harnesses/`,
implementing one protocol. The registry lists them, and everything else iterates the registry.

```
binary            "kiro-cli"
efforts           allowed effort levels, and whether effort lives in the slug (agy)
discover()        -> models         (command + parser)
probe()           -> meter rows      (or "unknown": the Gate never vetoes unknown)
run_args(job)     -> argv/env for the relay, read-only mapping, browser extras
parse_events()    optional (grok gate-cancel today)
```

**2/ Orchestration is harness-agnostic.** No script names an orchestrator. Every harness that can
run a shell and read files orchestrates the same way: `delegate run` relays the job and the caller reads
the run directory. That default needs no knowledge of the caller, so an unknown or new harness works
with no change. Running a Lane in-process (native Lanes) is an optional capability declared as data in
an orchestrator profile: whether the harness supports it, where its agent files live, their template,
and the spawn instruction the skill prints. Claude Code is the first profile, not a code path. The
orchestrator is detected from the environment or `--orchestrator`; anything unrecognised gets the
default. The courier and statusline become optional extras over the same run directory.

**3/ CLI is the contract; SKILL.md is thin and portable.** `delegate rank|run|status|setup` on PATH
(the `bin/delegate` already exists) with JSON output. SKILL.md and the wrappers call `delegate ...`,
never `~/.claude/skills/...`. The four typed wrappers fold into `/delegate`: a user-stated harness constraint
(`/delegate agy <task>`) restricts ranking to that harness's Lanes.

**4/ Kiro CLI as a worker.** Headless is `kiro-cli chat --no-interactive --agent <a> --trust-tools=<cats>
--output-format stream-json`, which needs `KIRO_API_KEY` (Pro tier and up) per
[Kiro headless docs](https://kiro.dev/docs/cli/headless/). Models list with `kiro-cli chat --list-models
--format json` per the [CLI reference](https://kiro.dev/docs/reference/cli-commands/). I found no
documented headless model flag or usage/credits command, so model is chosen via the agent config and
the meter starts as "unknown" (not verified beyond those two pages). Recommended route: add a
`kiro-delegate` relay to the fork (same `result.json` contract, upstreamable to ADS) rather than a
Python-only path, so execution stays in one layer.

## 5. Requested features, against what is settled

- **Custom classes.** Today `catalog.py:62` hardcodes five classes as a closed tuple, and the 2026-09-15
  consultation chose to keep it closed. Making classes data means a class list in `routing.json` with
  floor and ceiling, guide text in `classes.md`, and a validator. The multi-domain proposal (M7) already
  sketched this. It reopens a session decision, not an ADR.
- **Semi-automated tier picking from Artificial Analysis.** ADR 0001 and the consultation say *the human
  sets Tier; the board assists*. A wizard that **proposes** each new lane's tier from AA bands, with you
  confirming, fits inside that rule. A wizard that writes tiers on its own would reopen it, which is
  your call.
- **More automated `delegate global` / `delegate project`.** For example, detect a new model on any
  harness at dispatch time and queue it for the wizard, instead of waiting for a manual run.

## 6. Skill design against the best-practices doc

- **Degrees of freedom are inverted in places.**
  - Dispatch is fragile (a narrow bridge, in the doc's terms) and should be low freedom: one exact
    command. Today SKILL.md explains catalog-edit semantics, wizard internals and ticket history inline.
  - Classification is judgment and is rightly high freedom (`classes.md`).
- **Progressive disclosure.**
  - SKILL.md is 118 lines but 15 KB, because its lines are very long.
  - `references/architecture.md` is 26 KB in 122 lines (one line is 8,163 characters) with no table of
    contents. The doc asks for a ToC on any reference over 100 lines.
  - Wizard and catalog-edit detail belongs in references, not SKILL.md.
- **Time-sensitive content.** SKILL.md cites tickets by number four times. That history belongs in
  tickets, not the skill.
- **Description.** It should say in the third person what the skill does and when to use it, and agree
  with the invocation setting (finding 8).
- **Evals.** The delegate skill has none (council has `evals.md`). The doc asks for at least three
  scenarios before rewriting the skill, and for testing across models. This is the natural first step
  of a refactor.

## 7. Tickets

`.scratch/delegate-any-harness/issues/`. Order: review fixes (01-08) and the
user-invoked-only consistency (09), evals (10), the harness registry (11), the CLI-first skill
(12), harness-agnostic orchestration (13), Kiro (14-15), the features (16-18), the
skill rewrite (19), and a routing diagram in the README (20).
