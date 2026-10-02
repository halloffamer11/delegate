# delegate/Makefile — install delegate on this machine and run its tools.
#
# Usage:
#   make install             # link the skills, the courier agent and the `delegate` command; write the codex home
#   make test                # every script test and the dashboard test (stdlib only, no network);
#                            # PYTHON=python3.X picks the interpreter, 3.9 or newer
#   make eval-ping           # eval 1: a pong job on every installed harness (spends a little quota);
#                            # EVAL_ARGS=--offline runs it on the fake relay and stub CLIs
#   make eval-orchestrate    # eval 3: the same job sent through the skill from each orchestrator harness
#   make delegate-codex-home # delegate's own CODEX_HOME: the disposable browser and nothing else
#   make delegate-wizard     # the catalog wizard on this machine's catalog with the accepted benchmark rows;
#                            # WIZARD_ARGS adds flags (e.g. --tiers-from FILE, --plain)
#   make delegate-dashboard  # link and open the Herdr dashboard; DELEGATE_DASHBOARD_PLACEMENT overrides split
#
# The two short forms, once `make install` has linked bin/delegate into ~/.local/bin
# (ticket 34). Neither needs a checkout path:
#   delegate global [args]   # delegate-wizard, with the args as WIZARD_ARGS
#   delegate project [args]  # the dashboard for the current directory's Git project
#
# Editing:
#   - install links each skill as ONE whole-directory symlink to this checkout, so an
#     edit is live with no reinstall. It does not use the skills CLI: that CLI installs a
#     copy, and delegate also needs the codex home and a machine-local catalog.
#   - HARNESS_SKILL_DIRS: which harnesses receive the skills; override in local.mk
#   - ~/.config/delegate/{lanes,routing}.json and the lane-*.md agents in ~/.claude/agents
#     are machine-local and never in the repo. `make delegate-wizard` writes them.
#   - Recipes must be indented with a literal TAB (make syntax rule)
-include local.mk

HARNESS_SKILL_DIRS ?= $(HOME)/.claude/skills $(HOME)/.agents/skills $(HOME)/.kiro/skills
SKILLS := $(notdir $(wildcard $(CURDIR)/agents/skills/*))
# Accepted benchmark rows the wizard reads (repo-relative). The pre-screen and the
# benchmark page use AA and Terminal-Bench; swerb rows are evidence only.
DELEGATE_ROWS ?= .scratch/delegate-redesign/_data/aa-accepted.json .scratch/delegate-redesign/_data/tbench-accepted.json
DELEGATE_DASHBOARD_PLACEMENT ?= split
# The interpreter `make test` runs. Every entry point calls plain `python3`, so the
# oldest one in use sets the minimum: 3.9, macOS's /usr/bin/python3.
PYTHON ?= python3

.PHONY: install test eval-ping eval-orchestrate delegate-codex-home delegate-wizard delegate-dashboard

install: delegate-codex-home
	@# A real directory at a link path is someone's data: stop rather than nest a link inside it.
	@for t in $(HARNESS_SKILL_DIRS); do for s in $(SKILLS); do \
		if [ -e $$t/$$s ] && [ ! -L $$t/$$s ]; then echo "ERROR: $$t/$$s is a real directory — move it aside first"; exit 1; fi; \
	done; done
	for t in $(HARNESS_SKILL_DIRS); do mkdir -p $$t && for s in $(SKILLS); do ln -sfn $(CURDIR)/agents/skills/$$s $$t/$$s; done; done
	mkdir -p $(HOME)/.claude/agents $(HOME)/.local/bin
	ln -sfn $(CURDIR)/agents/agents/courier.md $(HOME)/.claude/agents/courier.md
	ln -sfn $(CURDIR)/bin/delegate $(HOME)/.local/bin/delegate

test:
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else "make test: delegate needs Python 3.9 or newer; $(PYTHON) is " + sys.version.split()[0])'
	@cd $(CURDIR)/agents/skills/delegate && for f in tests/test_*.py; do \
		$(PYTHON) $$f >/dev/null 2>&1 && echo "ok   $$f" || { echo "FAIL $$f"; fail=1; }; \
	done; exit $${fail:-0}
	$(PYTHON) $(CURDIR)/tools/delegate-dashboard/test_dashboard.py >/dev/null 2>&1 && echo "ok   tools/delegate-dashboard/test_dashboard.py"

eval-ping:
	$(PYTHON) $(CURDIR)/agents/skills/delegate/scripts/evals.py ping $(EVAL_ARGS)

eval-orchestrate:
	$(PYTHON) $(CURDIR)/agents/skills/delegate/scripts/evals.py orchestrate $(EVAL_ARGS)

delegate-codex-home:
	mkdir -p $(HOME)/.local/share/delegate/codex-home $(HOME)/.cache/playwright-mcp
	sed 's|@HOME@|$(HOME)|g' $(CURDIR)/agents/skills/delegate/assets/codex-home/config.toml > $(HOME)/.local/share/delegate/codex-home/config.toml
	@if [ -f $(HOME)/.codex/auth.json ]; then \
		ln -sfn $(HOME)/.codex/auth.json $(HOME)/.local/share/delegate/codex-home/auth.json; \
	else \
		echo "NOTE: ~/.codex/auth.json is absent — run 'codex login', then 'make delegate-codex-home' again"; \
	fi

# Writes this machine's catalog, ~/.config/delegate, and the agent file of each new
# native claude lane straight into ~/.claude/agents, so a new lane is live with no
# second command (ticket 33). Neither is in the repo.
delegate-wizard:
	python3 $(CURDIR)/agents/skills/delegate/scripts/setup.py $(foreach f,$(DELEGATE_ROWS),--effort-rows $(CURDIR)/$(f)) $(WIZARD_ARGS)

delegate-dashboard:
	@test "$${HERDR_ENV:-}" = 1
	@test -n "$${HERDR_PANE_ID:-}"
	@"$${HERDR_BIN_PATH:-herdr}" plugin link "$(CURDIR)/tools/delegate-dashboard"
	@python3 "$(CURDIR)/tools/delegate-dashboard/open.py" --placement "$(DELEGATE_DASHBOARD_PLACEMENT)" --target-pane "$${HERDR_PANE_ID}"
