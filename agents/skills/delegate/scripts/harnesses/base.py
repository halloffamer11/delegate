"""The harness adapter interface every module in this package implements.

A Harness is one CLI that runs models. Everything delegate knows about one
harness lives in its module: the binary, the efforts it offers, how its models
are listed and parsed, how its Meters are probed, and the relay flags a run on
it takes. The rest of delegate asks the registry (`harnesses.get(name)`) and
never names a harness itself.
"""
import copy
import os
import re
import shutil

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
    # The first word of the harness's own vendor's model slugs (`owns`).
    vendor = None
    # For a harness the catalog may have no Lane on yet: (meter name, meter
    # record without `harness`) and the weight and timeout its first Lanes
    # start from (`starter`). None means the refresh adds no Lane until one
    # exists.
    starter_meter = None
    starter_lane = None
    # The command that lists models (or, for a harness with no list command,
    # the one whose output the adapter reads its efforts from), and the
    # fixture file that stands in for its output in tests.
    list_command = None
    fixture_file = None
    # True when the harness has no list command. Only the registry reads it,
    # to put such a harness last in `discovery_order`; everything else asks
    # the adapter's verbs (`models`, `generation`, `present_in`).
    catalog_models = False
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

    def installed(self):
        """Whether this harness's CLI is on PATH, by the binary it names. The
        one answer to the question: ranking, probes and dispatch all ask here."""
        return shutil.which(self.binary) is not None

    def present_in(self, fixture_dir):
        """Whether discovery from a fixture directory counts this harness as
        present: its list command's fixture is there."""
        return os.path.isfile(os.path.join(fixture_dir, self.fixture_file))

    def models(self, raw, error, lanes):
        """(models, error, complete) for discovery.

        `raw` and `error` are what the list command printed, or why it could
        not be read; `lanes` are the catalog's Lanes on this harness, {name:
        lane}. Each model is a dict with `slug`, `display_name` and `efforts`.
        `complete` says the list is everything the harness runs, so a Lane
        whose model is not on it is on a retired model.
        """
        if error is not None:
            return [], error, True
        try:
            return self.parse_models(raw), None, True
        except Exception as e:
            return [], f"unparseable output: {e}", True

    def parse_models(self, raw):
        """Models from the list command's output: dicts with `slug`,
        `display_name` and `efforts`."""
        raise NotImplementedError(f"{self.name} has no model list")

    def generation(self, models, published_names):
        """The models the refresh works from, given the ones discovery found
        on this harness (each with `level`, `version` and `superseded`) and the
        names the benchmark rows publish. A harness whose list is complete
        works from its list as it is."""
        return [copy.deepcopy(item) for item in models]

    def owns(self, slug):
        """True for a model of the harness's own vendor: the refresh proposes
        Lanes for these only (`gpt-*` on codex, `gemini-*` on agy)."""
        return bool(self.vendor) and (slug or "").split("-")[0] == self.vendor

    def lane_meter(self, slug):
        """The Meter a Lane on this model goes on when the model decides it, or
        None when a new Lane takes its donor's Meter. agy serves two quota pools,
        so there the model's group decides (ticket 31 of any-harness)."""
        return None

    def starter(self):
        """(meter name, meter record, lane record) the first Lane on this
        harness starts from when the catalog has no Lane on it to copy, or
        None when the refresh adds no Lane until one exists."""
        if self.starter_meter is None or self.starter_lane is None:
            return None
        meter_name, meter = self.starter_meter
        return meter_name, copy.deepcopy(meter), copy.deepcopy(self.starter_lane)

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

    def meters(self):
        """The harness's Meter rows, as `usage.meter_row` builds them. An absent CLI
        gives one `absent` row and a probe that raises one `probe failed` row,
        here for every harness; each adapter's `read_meters` reads the rest.
        Every such row has an unknown Remaining, which the Gate never vetoes."""
        import usage
        if not self.installed():
            return [usage.meter_row(self.name, None, note="absent")]
        try:
            return self.read_meters()
        except Exception as e:  # noqa
            return [usage.meter_row(self.name, None, note=f"probe failed: {e}")]

    def read_meters(self):
        """The Meter rows the installed CLI reports. A harness with no usage
        source reports one row with an unknown Remaining."""
        import usage
        return [usage.meter_row(self.name, None, note="no usage source")]

    # The probe groups `read_meters` reports, each one Meter
    # (`usage.meter_name`): None is the harness's own name.
    meter_groups = (None,)

    def meter_names(self):
        """The Meter names this harness's probe reports, for a message."""
        import usage
        return tuple(usage.meter_name(self.name, group) for group in self.meter_groups)

    def reports_meter(self, name, models=()):
        """Whether the probe reports a Meter by this name, given the models
        the catalog's Lanes run on it. A catalog Meter it does not report would
        have an unknown Remaining for good, which the Gate never vetoes, so
        `catalog check` refuses it."""
        return name in self.meter_names()

    # (old, new) note texts a cached Meter row is read with: a note an
    # earlier probe wrote that now reads differently.
    note_renames = ()

    # -- dispatch ----------------------------------------------------------

    def effort_for(self, lane, override):
        """(effort, ignored) for one run on `lane` with an `--effort` override
        or None: the effort the run takes, and why an override was not used,
        or None. Raises ValueError for an override the harness does not offer,
        which is refused rather than passed to a CLI that may run something
        else (ticket 19). A word delegate does not know passes through, for
        the caller's own check to name."""
        if override in EFFORTS and override not in self.efforts:
            raise ValueError(f"{self.name} does not offer effort '{override}'")
        if override is None:
            return lane["effort"], None
        if self.effort_in_slug:
            return lane["effort"], f"{self.name} carries effort in the model name"
        return override, None

    # Patterns (case-insensitive) for the harness's own words when it refuses
    # a run because its usage limit is reached (ticket 43). Only wording seen
    # in a real run goes here.
    limit_patterns = ()

    def usage_limit(self, text):
        """The line of `text` where the harness says its usage limit is
        reached, or None."""
        for line in (text or "").splitlines():
            if any(re.search(p, line, re.I) for p in self.limit_patterns):
                return line.strip()
        return None

    def blocked_reason(self, run_dir):
        """Why a run the relay calls completed did not finish, read from the
        run directory, or None. Only a harness whose events say so has one."""
        return None

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
