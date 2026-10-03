"""The harness adapter interface every module in this package implements.

A Harness is one CLI that runs models. Everything delegate knows about one
harness lives in its module: the binary, the efforts it offers, how its models
are listed and parsed, how its Meters are probed, and the relay flags a run on
it takes. The rest of delegate asks the registry (`harnesses.get(name)`) and
never names a harness itself.
"""

EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")


class Harness:
    """Defaults for an adapter; a harness module overrides what differs."""

    # The harness's name, as lanes.json writes it and as a Lane name ends:
    # `<model-effort>@<name>`.
    name = None
    # The CLI's file name on PATH. Not always the harness name: Kiro's is
    # `kiro-cli`.
    binary = None
    # The efforts the harness offers, and so the only efforts a Lane on it may
    # carry (ticket 19 of the redesign).
    efforts = ()
    # True when the effort is part of the model slug (agy's
    # `gemini-3.8-flash-high`), so a Lane's model names its effort and an
    # effort override is ignored.
    effort_in_slug = False
    # The first word of the harness's own vendor's model slugs. The refresh
    # proposes Lanes for the harness's own vendor's models only.
    vendor = None
    # True for a harness that serves every vendor's models on its own Meter
    # (Kiro): the refresh proposes Lanes for all of them.
    any_vendor = False
    # For a harness the catalog may have no Lane on yet: (meter name, meter
    # record without `harness`) and the weight and timeout its first Lanes
    # start from. None means the refresh adds no Lane until one exists.
    starter_meter = None
    starter_lane = None
    # The command that lists models (or, for a harness with no list command,
    # the one whose output the adapter reads its efforts from), and the
    # fixture file that stands in for its output in tests.
    list_command = None
    fixture_file = None
    # True when the harness has no list command, so its models are the ones
    # the catalog names by hand, and newer ones come from the benchmark rows'
    # published names (`published_name`).
    catalog_models = False
    # For a catalog_models harness: a regex a benchmark row's published name
    # must fully match to name one of its models. Group 1 is the level word and
    # group 2 the version, e.g. `Claude Opus 5.5`.
    published_name = None
    # What `discover.py --efforts` adds when a model takes no effort level.
    no_effort_note = "The harness runs this model with no effort level."
    # The delegate-skills relay directory that runs a Lane on this harness.
    relay = None

    def __init__(self):
        if self.binary is None:
            self.binary = self.name
        if self.relay is None:
            self.relay = f"{self.name}-delegate"
        if self.fixture_file is None:
            self.fixture_file = f"{self.name}-models.txt"

    def __repr__(self):
        return f"<harness {self.name}>"

    # -- discovery ---------------------------------------------------------

    def parse_models(self, raw):
        """Models from the list command's output: dicts with `slug`,
        `display_name` and `efforts`. A catalog_models harness has none."""
        raise NotImplementedError(f"{self.name} has no model list")

    def efforts_from_help(self, raw):
        """For a catalog_models harness, the efforts its list command's output
        names, in order, or []."""
        return []

    def model_takes_effort(self, slug):
        """False for a model the harness runs with no effort level at all."""
        return True

    def family(self, slug):
        """(base, effort) for a model slug: the effort the slug carries, for a
        harness whose effort is part of the slug, else (slug, None)."""
        return slug or "", None

    def lane_model(self, model, effort):
        """The model string a Lane on this discovered model at this effort
        carries."""
        return model["slug"]

    # -- meters ------------------------------------------------------------

    def probe(self):
        """The harness's Meter rows, as `usage.lane` builds them. A harness
        with no usage source returns one row with an unknown Remaining, which
        the Gate never vetoes."""
        import usage
        if not usage.which(self.name):
            return [usage.lane(self.name, None, note="absent")]
        return [usage.lane(self.name, None, note="no usage source")]

    # (old, new) note texts a cached Meter row is read with: a note an
    # earlier probe wrote that now reads differently.
    note_renames = ()

    # -- dispatch ----------------------------------------------------------

    def run_args(self, effort, timeout, write_dir):
        """(relay flags, env overrides or None) for one run, after the
        `--brief --cd --out-dir --model` every relay takes."""
        args = ["--effort", effort, "--timeout", timeout]
        if not write_dir:
            args.append("--read-only")
        return args, None

    def prompt_note(self, write_dir):
        """Extra text for the worker prompt's permission clause, or ""."""
        return ""

    def browser_probe_effort(self):
        """The effort a browser probe overrides to, or None to keep the
        Lane's."""
        return "low"
