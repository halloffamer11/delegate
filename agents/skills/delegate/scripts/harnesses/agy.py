"""Antigravity: `agy`, Google's CLI. Its effort is part of the model slug."""
import json
import re

from .base import Harness

COMBINED_NOTE = ("agy combined remaining is the lower window, an assumption, "
                 "not a vendor bound")
# The note the reversed rule wrote (modular ticket 13). A cache from that time
# still carries it beside null figures; a read replaces both together.
SUPERSEDED_NOTE = "agy combined remaining and pace unknown until a vendor joint bound exists"

# `gemini-3.8-flash-high` -> ("gemini-3.8-flash", "high")
_SUFFIX = re.compile(r"^(.+)-(low|medium|high)$")


class Agy(Harness):
    name = "agy"
    # `agy --help`: `--effort ... (low|medium|high)`, and `agy models` lists a
    # -low, -medium and -high slug per Gemini Flash model (checked 2026-09-12).
    efforts = ("low", "medium", "high")
    effort_in_slug = True
    vendor = "gemini"
    list_command = ["agy", "models"]
    note_renames = ((SUPERSEDED_NOTE, COMBINED_NOTE),)
    fixture_file = "agy-models.txt"

    def family(self, slug):
        """The agy slug family a model slug belongs to: (base, effort).

        agy carries the effort in the slug, so `gemini-3.8-flash-high` is the model
        `gemini-3.8-flash` at effort high. A slug whose suffix is not an effort agy
        offers is a family of its own, with no effort: `(slug, None)`.

        One rule in one place. Discovery groups a harness listing with it
        (`parse_models`) and the carry rule groups a lane's rows with it
        (`bench.model_families`), so the wizard can never disagree with the models
        discovery reported (ticket 30).
        """
        text = slug or ""
        found = _SUFFIX.match(text)
        if not found or found.group(2) not in self.efforts:
            return text, None
        return found.group(1), found.group(2)

    def parse_models(self, raw):
        """One entry per slug family from `agy models`, in listed order.

        A first line 'Fetching available models...' is skipped; each model line
        is formatted as '<slug>\\t<display name>'. agy carries the effort in the
        slug: `gemini-3.8-flash-high`, `-medium` and `-low` are one model at
        three efforts, so they are reported as `gemini-3.8-flash` with efforts
        [low, medium, high] and `members` mapping each effort to the slug agy
        accepts. A slug without an effort suffix agy offers is a family of one
        with no efforts.
        """
        return self.group(parse_listing(raw))

    def group(self, raw_models):
        families, order = {}, []
        for item in raw_models:
            slug = item["slug"]
            base, effort = self.family(slug)
            family = families.get(base)
            if family is None:
                display = item.get("display_name")
                if effort and display:
                    display = re.sub(r"\s*\((?:low|medium|high)\)\s*$", "", display, flags=re.I) or display
                family = {"slug": base, "display_name": display, "efforts": [], "members": {}}
                families[base] = family
                order.append(base)
            if effort:
                if effort not in family["efforts"]:
                    family["efforts"].append(effort)
                family["members"][effort] = slug
            else:
                family["members"][None] = slug
        out = []
        for base in order:
            family = families[base]
            family["efforts"].sort(key=self.efforts.index)
            out.append(family)
        return out

    def lane_model(self, model, effort):
        """agy names the effort in the slug, so the family says which slug an
        effort takes."""
        return (model.get("members") or {}).get(effort, model["slug"])

    def probe(self):
        import usage
        if not usage.which(self.name): return [usage.lane(self.name, None, note="absent")]
        r = usage.run(["agy", "--print", "/usage", "--output-format", "json"], timeout=90, stdin_data="")
        if not r or r.returncode != 0: return [usage.lane(self.name, None, note="probe failed")]
        try:
            groups = json.loads(r.stdout)["command"]["data"]["groups"]
        except Exception as e:
            return [usage.lane(self.name, None, note=f"unexpected output: {e}")]
        out = []
        for g in groups:
            meter = "gemini" if "gemini" in g["name"].lower() else "claude-gpt"
            f5 = fw = r5 = rw = None
            for b in g.get("buckets", []):
                if b.get("window") == "5h": f5, r5 = b.get("remaining_fraction"), usage.iso(b.get("reset_time", ""))
                elif b.get("window") == "weekly": fw, rw = b.get("remaining_fraction"), usage.iso(b.get("reset_time", ""))
            # No vendor bound joins the two windows, so the note says what the
            # combined figure is: the lower window, an assumption (ticket 31).
            out.append(usage.lane(self.name, meter, f5, fw, r5, rw, note=COMBINED_NOTE))
        return out or [usage.lane(self.name, None, note="no groups")]

    def run_args(self, effort, timeout, write_dir):
        # agy has no effort flag: the slug carries it.
        args = ["--print-timeout", timeout]
        args.append("--read-only" if not write_dir else "--dangerously-skip-permissions")
        return args, None

    def prompt_note(self, write_dir):
        if write_dir:
            return ""
        return ("Browser tools are permitted. Terminal commands run inside a sandbox confined to the "
                "workspace; you still must not create, edit, or delete files.\n")

    def browser_probe_effort(self):
        return None


def parse_listing(text):
    """The raw slugs `agy models` prints, before grouping into families."""
    models = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Fetching available models"):
            continue
        if "\t" in line:
            parts = line.split("\t", 1)
            slug = parts[0].strip()
            display_name = parts[1].strip() if len(parts) > 1 else None
        else:
            parts = line.split(None, 1)
            slug = parts[0].strip()
            display_name = parts[1].strip() if len(parts) > 1 else None
        if slug:
            models.append({
                "slug": slug,
                "display_name": display_name,
            })
    return models


HARNESS = Agy()
