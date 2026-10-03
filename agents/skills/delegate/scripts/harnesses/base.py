"""The harness adapter interface every module in this package implements.

A Harness is one CLI that runs models. Everything delegate knows about one
harness lives in its module: the binary, the efforts it offers, how its models
are listed and parsed, how its Meters are probed, and the relay flags a run on
it takes. The rest of delegate asks the registry (`harnesses.get(name)`) and
never names a harness itself.
"""

EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
# The same words longest first, for a pattern that reads an effort off the end
# of a name: `-xhigh` has to be tried before `-high`.
EFFORTS_LONGEST_FIRST = tuple(sorted(EFFORTS, key=len, reverse=True))


class Harness:
    """Defaults for an adapter; a harness module overrides what differs."""

    # The harness's name, as lanes.json writes it and as a Lane name ends:
    # `<model-effort>@<name>`.
    name = None
    # The CLI's file name on PATH. Not always the harness name: Kiro's is
    # `kiro-cli`.
    binary = None
    # The efforts the harness offers, and so the only efforts a Lane on it may
    # carry (ticket 19 of the redesign); a harness with the effort in the slug
    # also offers any effort a slug it lists names (`offers_effort`).
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
        """For a catalog_models harness, the effort words its list command's
        output names, in order, or []. A word delegate does not know stays in,
        so the refresh can name it (`split_efforts`)."""
        return []

    def split_efforts(self, words):
        """(efforts, unknown) for the effort words a harness lists for one model:
        the ones a Lane on this harness may carry, in listed order, and the rest.

        A word outside EFFORTS is one delegate does not know yet, and a word the
        harness's `efforts` leaves out is one delegate does not run it at; the
        refresh names both rather than proposing a Lane that no catalog check
        would pass. A harness that carries the effort in the slug offers what it
        lists, so only a word outside EFFORTS is unknown there.
        """
        efforts, unknown = [], []
        for word in words or ():
            word = str(word).strip().lower()
            if not word or word in efforts or word in unknown:
                continue
            known = word in EFFORTS and (self.effort_in_slug or word in self.efforts)
            (efforts if known else unknown).append(word)
        return efforts, unknown

    def offers_effort(self, model, effort):
        """True when a Lane on `model` may carry `effort`: the harness offers it,
        or, where the effort is part of the slug, the slug names it."""
        if effort in self.efforts:
            return True
        return self.effort_in_slug and self.family(model)[1] == effort

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
