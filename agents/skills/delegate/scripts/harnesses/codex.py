"""Codex: `codex`, OpenAI's CLI."""
import json
import os
import subprocess
import time

from .base import EFFORTS, Harness


class Codex(Harness):
    name = "codex"
    # Every effort; `codex debug models` lists them per model, and ultra is one
    # of them (checked 2026-09-12).
    efforts = EFFORTS
    vendor = "gpt"
    list_command = ["codex", "debug", "models"]
    fixture_file = "codex-debug-models.json"

    def parse_models(self, raw):
        """Parses JSON output from `codex debug models`.

        Only models whose visibility is 'list' are reported. Models with
        visibility 'hide' (such as gpt-reserve and codex-auto-review) are
        internal or automated and are not offered to human users; excluding
        them is deliberate.
        """
        doc = json.loads(raw)
        if not isinstance(doc, dict) or "models" not in doc:
            raise ValueError("missing 'models' array in JSON output")

        models = []
        for item in doc["models"]:
            if not isinstance(item, dict):
                continue
            # Deliberately exclude hidden/internal models
            if item.get("visibility") != "list":
                continue
            slug = item.get("slug")
            if not slug:
                continue
            efforts = []
            for level in item.get("supported_reasoning_levels", []):
                if isinstance(level, dict) and "effort" in level:
                    efforts.append(level["effort"])
            models.append({
                "slug": slug,
                "display_name": item.get("display_name"),
                "efforts": efforts,
                "supported_reasoning_levels": item.get("supported_reasoning_levels", []),
                # codex names the replacement of a model it is retiring; that is the
                # harness saying the model is superseded (ticket 33)
                "upgrade": item.get("upgrade"),
            })
        return models

    def probe(self):
        import usage
        if not usage.which(self.name): return [usage.lane(self.name, None, note="absent")]
        try:
            p = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True)
            def send(o): p.stdin.write(json.dumps(o) + "\n"); p.stdin.flush()
            def recv(i, timeout=20):
                t0 = time.time()
                while time.time() - t0 < timeout:
                    line = p.stdout.readline()
                    if not line: break
                    try: m = json.loads(line)
                    except ValueError: continue
                    if m.get("id") == i: return m
                return None
            send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "delegate-usage", "version": "0.1"}}})
            if not recv(1): raise RuntimeError("no initialize response")
            send({"method": "initialized"}); time.sleep(0.5)
            send({"id": 2, "method": "account/rateLimits/read", "params": {}})
            m = recv(2)
            p.terminate()
            rl = (m or {}).get("result", {}).get("rateLimits") or {}
            def win(w): return (None, None) if not w else (1 - w["usedPercent"] / 100.0, w.get("resetsAt"))
            # codex labels windows primary/secondary; identify by duration when present
            wins = {}
            for key in ("primary", "secondary"):
                w = rl.get(key)
                if not w: continue
                mins = w.get("windowDurationMins") or 0
                wins["weekly" if mins >= 24 * 60 else "5h"] = win(w)
            f5, r5 = wins.get("5h", (None, None)); fw, rw = wins.get("weekly", (None, None))
            return [usage.lane(self.name, None, f5, fw, r5, rw, note=f"plan={rl.get('planType')}")]
        except Exception as e:  # noqa
            return [usage.lane(self.name, None, note=f"probe failed: {e}")]

    def run_args(self, effort, timeout, write_dir):
        args = ["--effort", effort, "--timeout", timeout, "--skip-git-repo-check"]
        env = None
        home = codex_home()
        if home:
            env = {"CODEX_HOME": home}
        else:
            args.append("--ignore-user-config")
        if not write_dir:
            args.append("--read-only")
        return args, env


def codex_home():
    """The delegate-owned CODEX_HOME, or None when this machine has none.

    A codex worker must reach the disposable browser and nothing else that is in
    Orin's own config: no plugins, no Gmail, no codex-cli, no node_repl, no
    hooks, no notify, and not ~/.codex/AGENTS.md, which symlinks his global
    CLAUDE.md. A home of delegate's own holds one MCP server and gives exactly
    that, so a run that finds one drops --ignore-user-config and points codex at
    it. A machine without the home keeps the old isolation, which stays correct
    and has no browser. `make delegate-codex-home` builds it.
    """
    home = os.environ.get("DELEGATE_CODEX_HOME") or os.path.expanduser("~/.local/share/delegate/codex-home")
    return home if os.path.isfile(os.path.join(home, "config.toml")) else None


HARNESS = Codex()
