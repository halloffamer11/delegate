# delegate

Agent skills that route worker jobs to Claude Code, Codex, Antigravity (`agy`) or Grok
by task class, model capability and remaining subscription usage.

## Install

Needs Python 3.9 or newer as `python3` (macOS ships 3.9 at `/usr/bin/python3`) and
`node` for relayed lanes. The scripts use the standard library only.

```sh
git clone https://github.com/halloffamer11/delegate ~/projects/delegate
make -C ~/projects/delegate install          # skills, courier agent, `delegate` command, codex home
make -C ~/projects/delegate delegate-wizard  # write this machine's catalog
```

`install` links each skill as a directory symlink into `~/.claude/skills`,
`~/.agents/skills` and `~/.kiro/skills`. Set `HARNESS_SKILL_DIRS` in `local.mk` to
change that list.

## Test

```sh
make test                   # with python3
make test PYTHON=python3.9  # with another interpreter
```

`make test` stops with a message when the interpreter is older than 3.9.
