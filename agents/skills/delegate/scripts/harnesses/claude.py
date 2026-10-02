"""Claude Code: `claude`. It has no model list command."""
import json
import os
import re
import time
from datetime import datetime

from .base import EFFORTS, Harness

# Claude models that take no effort level at all. The Claude Code docs
# (https://code.claude.com/docs/en/model-config, checked 2026-09-12) list the models that take effort and say "Models not
# listed here do not support effort"; Haiku is not listed. Matched as a word in
# the model slug.
MODELS_WITHOUT_EFFORT = ("haiku",)


class Claude(Harness):
    name = "claude"
    # `claude --help` (Claude Code 2.1.269): `--effort <level>` with
    # `(low, medium, high, xhigh, max)` on the next line; the same five in
    # https://code.claude.com/docs/en/model-config. That page also says Haiku
    # supports no effort level, which is a model's limit, not the harness's:
    # `model_takes_effort` applies it.
    efforts = ("low", "medium", "high", "xhigh", "max")
    vendor = "claude"
    # Claude has no list command; `claude --help` is read for its efforts.
    list_command = ["claude", "--help"]
    fixture_file = "claude-help.txt"
    catalog_models = True
    no_effort_note = ("Claude Code's docs (https://code.claude.com/docs/en/model-config) "
                      "say Haiku supports no effort level.")
    # One published name for one claude model: `Claude Opus 5.5`. Claude Code
    # names no model, so the benchmark rows are the only list of them there is.
    published_name = re.compile(r"claude\s+([A-Za-z]+)\s+([0-9]+(?:\.[0-9]+)*)", re.I)

    def efforts_from_help(self, raw):
        """The efforts `claude --help` lists for `--effort`, in its order, or [].

        The values sit in parentheses in the flag's description, which wraps onto
        the lines after the flag (`--effort <level>  Effort level for the current
        session` then `(low, medium, high, xhigh, max)`), so the description runs
        until the next line that starts a flag.
        """
        lines = (raw or "").splitlines()
        for index, line in enumerate(lines):
            if not re.match(r"\s*--effort\b", line):
                continue
            description = [line]
            for following in lines[index + 1:]:
                if re.match(r"\s*-", following):
                    break
                description.append(following)
            found = re.search(r"\(([^()]*)\)", " ".join(description))
            if not found:
                return []
            words = [w.strip().lower() for w in re.split(r"[,|/]", found.group(1))]
            return [w for w in words if w in EFFORTS]
        return []

    def model_takes_effort(self, slug):
        words = re.split(r"[^a-z0-9]+", (slug or "").lower())
        return not any(word in words for word in MODELS_WITHOUT_EFFORT)

    def probe(self):
        import usage
        if not usage.which(self.name): return [usage.lane(self.name, None, note="absent")]
        # Run from the home directory: inside the dotfiles project the same command
        # did not return within 45 s (2026-09-18), and from ~ it takes about 3 s.
        r = usage.run(["claude", "-p", "--permission-mode", "plan", "--output-format", "json", "/usage"], timeout=60, stdin_data="",
                      cwd=os.path.expanduser("~"))
        if not r or r.returncode != 0: return [usage.lane(self.name, None, note="probe failed")]
        try: text = json.loads(r.stdout)["result"]
        except Exception as e: return [usage.lane(self.name, None, note=f"unexpected output: {e}")]
        def pct(label):
            m = re.search(re.escape(label) + r":\s*(\d+)% used(?: · resets ([^\n]+))?", text)
            return (None, None) if not m else (1 - int(m.group(1)) / 100.0, m.group(2))
        f5, r5 = pct("Current session"); fw, rw = pct("Current week (all models)")
        lanes = [usage.lane(self.name, "general", f5, fw, reset(r5), reset(rw),
                            note=f"resets: 5h '{r5}', weekly '{rw}'")]
        # per-model weekly meters, e.g. "Current week (Fable): 86% used"
        for m in re.finditer(r"Current week \(([^)]+)\):\s*(\d+)% used(?: · resets ([^\n]+))?", text):
            name = m.group(1)
            if name.lower() == "all models": continue
            fm = 1 - int(m.group(2)) / 100.0
            wk = min(fw, fm) if fw is not None else fm
            lanes.append(usage.lane(self.name, name.lower(), f5, wk, reset(r5), reset(m.group(3) or rw),
                                    note=f"model-meter weekly {m.group(2)}% used; resets '{m.group(3)}'",
                                    remaining_weekly_model=fm))
        return lanes


def reset(text):
    """'Sep 8 at 2:59pm (America/New_York)' -> epoch seconds, or None. The year is
    not printed: assume the current one, roll forward if that lands in the past."""
    if not text: return None
    m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}) at (\d{1,2})(?::(\d{2}))?(am|pm) \(([^)]+)\)", text)
    if not m: return None
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(m.group(6)); hour = int(m.group(3)) % 12 + (12 if m.group(5) == "pm" else 0)
        minute = m.group(4) or "00"
        year = datetime.now(tz).year
        t = datetime.strptime(f"{m.group(1)} {m.group(2)} {year} {hour}:{minute}", "%b %d %Y %H:%M").replace(tzinfo=tz)
        if t.timestamp() < time.time() - 86400: t = t.replace(year=year + 1)
        return t.timestamp()
    except Exception:
        return None


HARNESS = Claude()
