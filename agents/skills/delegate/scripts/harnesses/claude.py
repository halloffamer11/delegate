"""Claude Code: `claude`. It has no model list command."""
import copy
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
# One published name for one claude model: `Claude Opus 5.5`. Claude Code
# names no model, so the benchmark rows are the only list of newer ones.
PUBLISHED_NAME = re.compile(r"claude\s+([A-Za-z]+)\s+([0-9]+(?:\.[0-9]+)*)", re.I)


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
    # `/usage` reports the session's general Meter and a weekly Meter per
    # model it names (`Current week (Fable)`), so `claude-<model>` is any model
    # word (`model_meter_name`).
    meter_groups = ("general",)

    def meter_names(self):
        return ("claude-general", "claude-<model>")

    def reports_meter(self, name, models=()):
        """`claude-general`, or `claude-<word>` for a word in the slug of a
        model the catalog runs on that Meter (`claude-fable` for
        `claude-fable-5-1`), which is the word `/usage` names it by."""
        if name == "claude-general":
            return True
        prefix = f"{self.name}-"
        if not name.startswith(prefix):
            return False
        word = name[len(prefix):]
        return any(word in re.split(r"[^a-z0-9]+", (slug or "").lower()) for slug in models)

    # -- discovery: the catalog names the models, the benchmark rows name
    # newer ones, and `claude --help` names the efforts ---------------------

    def present_in(self, fixture_dir):
        """Always: the catalog names the models, and a missing help fixture
        only means the efforts come from `efforts`."""
        return True

    def help_efforts(self, raw, error):
        """(efforts, unknown) from `claude --help`'s output: the efforts it
        lists that a Lane may carry, else `efforts` when it lists none or could
        not be read, and the words it lists that no Lane on claude may carry."""
        efforts, unknown = self.split_efforts(self.efforts_from_help(raw) if error is None else [])
        return (efforts or list(self.efforts)), unknown

    def models(self, raw, error, lanes):
        """One model per model the catalog's claude Lanes run, never a guessed
        one: Claude Code has no list command, so the catalog is the list, and
        it is never complete (a newer model comes from `generation`)."""
        efforts, unknown = self.help_efforts(raw, error)
        out, seen = [], set()
        for lane in lanes.values():
            slug = lane.get("model", "")
            if slug in seen:
                continue
            seen.add(slug)
            takes = self.model_takes_effort(slug)
            out.append({"slug": slug, "display_name": None,
                        "efforts": list(efforts) if takes else [],
                        "unknown_efforts": list(unknown) if takes else [],
                        "reason": "hand-named, undiscoverable"})
        return out, None, False

    def generation(self, models, published_names):
        """The catalog's models, newest version per level, and a newer one for
        each level a benchmark row names.

        A published name `Claude <Level> <version>` (`PUBLISHED_NAME`) denotes
        `claude-<level>-<major>[-<minor>]`, and only for a level the catalog
        already runs. A level keeps its catalog model until a newer version of
        it is named (ticket 33).
        """
        out = [copy.deepcopy(item) for item in models]
        current = {}
        for item in out:
            best = current.get(item["level"])
            if best is None or tuple(item["version"]) > tuple(best["version"]):
                current[item["level"]] = item
        newer = {}
        for name in published_names or ():
            found = PUBLISHED_NAME.fullmatch(str(name).strip())
            if not found:
                continue
            level = f"{self.vendor}-{found.group(1).lower()}"
            version = tuple(int(number) for number in found.group(2).split("."))
            base = current.get(level)
            if base is None or version <= tuple(base["version"]):
                continue
            if level not in newer or version > newer[level][0]:
                newer[level] = (version, found.group(2))
        for level, (version, text) in newer.items():
            base = current[level]
            slug = "-".join([*level.split("-"), *text.split(".")])
            base["superseded"] = f"{slug} is newer"
            takes = self.model_takes_effort(slug)
            out.append({
                "harness": self.name,
                "slug": slug,
                "display_name": None,
                "lane": "none",
                "lanes": [],
                # the level's efforts: one model of a level takes what the level takes
                "efforts": list(base["efforts"]) if takes else [],
                "unknown_efforts": list(base.get("unknown_efforts") or []) if takes else [],
                "reason": "named by the benchmark rows",
                "level": level,
                "version": list(version),
                "superseded": None,
                "members": {},
            })
        return out

    def efforts_from_help(self, raw):
        """The efforts `claude --help` lists for `--effort`, in its order, or [].
        A word outside EFFORTS is kept (`split_efforts` sorts it out).

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
            # a word delegate does not know yet stays in for the refresh to
            # name, as long as the parentheses are the effort list at all
            if not any(w in EFFORTS for w in words):
                return []
            return [w for w in words if w]
        return []

    def model_takes_effort(self, slug):
        words = re.split(r"[^a-z0-9]+", (slug or "").lower())
        return not any(word in words for word in MODELS_WITHOUT_EFFORT)

    def read_meters(self):
        import usage
        # Run from the home directory: inside the dotfiles project the same command
        # did not return within 45 s (2026-09-18), and from ~ it takes about 3 s.
        r = usage.run(["claude", "-p", "--permission-mode", "plan", "--output-format", "json", "/usage"], timeout=60, stdin_data="",
                      cwd=os.path.expanduser("~"))
        if not r or r.returncode != 0: return [usage.meter_row(self.name, None, note="probe failed")]
        try: text = json.loads(r.stdout)["result"]
        except Exception as e: return [usage.meter_row(self.name, None, note=f"unexpected output: {e}")]
        def pct(label):
            m = re.search(re.escape(label) + r":\s*(\d+)% used(?: · resets ([^\n]+))?", text)
            return (None, None) if not m else (1 - int(m.group(1)) / 100.0, m.group(2))
        f5, r5 = pct("Current session"); fw, rw = pct("Current week (all models)")
        lanes = [usage.meter_row(self.name, "general", f5, fw, reset(r5), reset(rw),
                            note=f"resets: 5h '{r5}', weekly '{rw}'")]
        # per-model weekly meters, e.g. "Current week (Fable): 86% used"
        for m in re.finditer(r"Current week \(([^)]+)\):\s*(\d+)% used(?: · resets ([^\n]+))?", text):
            name = model_meter_name(m.group(1))
            if name == "all models": continue
            fm = 1 - int(m.group(2)) / 100.0
            wk = min(fw, fm) if fw is not None else fm
            lanes.append(usage.meter_row(self.name, name, f5, wk, reset(r5), reset(m.group(3) or rw),
                                    note=f"model-meter weekly {m.group(2)}% used; resets '{m.group(3)}'",
                                    remaining_weekly_model=fm))
        return lanes


def model_meter_name(label):
    """The Meter word for a `/usage` model label: `Fable` and `Fable 5.2` are
    both `fable`, so a version in the label never moves the row off the
    catalog's `claude-fable` Meter, whose Gate would then never see it."""
    words = [w for w in label.lower().split() if not re.fullmatch(r"v?\d+(?:\.\d+)*", w)]
    return " ".join(words) or label.lower().strip()


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
