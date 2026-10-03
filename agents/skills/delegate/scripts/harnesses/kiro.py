"""Kiro: `kiro-cli`, Amazon's Kiro CLI.

Kiro serves other vendors' models (Anthropic's, OpenAI's and open-weight ones)
on its own credit Meter, so a Lane on Kiro runs a model this catalog may also
run on that vendor's own harness, against a different subscription. Facts here
are from kiro.dev, read 2026-10-02/03:

- headless is `kiro-cli chat --no-interactive`, which needs `KIRO_API_KEY`
  (Pro tier and up) (docs/cli/headless);
- `kiro-cli chat --list-models --format json` lists the models
  (docs/reference/cli-commands); the JSON's field names are not documented, so
  `parse_models` reads the plausible spellings and the fixture stands in until
  a real listing replaces it;
- `--effort` takes low, medium, high, xhigh or max, and not every model
  supports every level (docs/models/effort); `--model` and `--effort` apply to
  the one session in V3;
- no usage or credits command is documented, so the Meter's Remaining is
  unknown, which the Gate never vetoes.
"""
import json

from .base import Harness

EFFORT_KEYS = ("efforts", "supported_efforts", "supportedEfforts", "effort_levels",
               "effortLevels", "reasoning_efforts", "reasoningEfforts")
ID_KEYS = ("model_id", "modelId", "id", "slug", "name")
NAME_KEYS = ("model_name", "modelName", "display_name", "displayName", "name")
# Kiro's model router: it picks a model per request, so a Lane on it names no
# model a benchmark could score (docs/models/available-models).
ROUTER = "auto"


class Kiro(Harness):
    name = "kiro"
    binary = "kiro-cli"
    efforts = ("low", "medium", "high", "xhigh", "max")
    list_command = ["kiro-cli", "chat", "--list-models", "--format", "json"]
    fixture_file = "kiro-models.json"
    # Kiro's first Lanes have no Lane on the harness to copy a Meter, a weight
    # or a timeout from, so the refresh starts them from this, and adds the
    # Meter when the catalog has none. Plan and price are the Kiro Pro list
    # price, which headless needs at least; edit them in lanes.json.
    starter_meter = ("kiro", {"plan": "Kiro Pro", "price_month": 20, "probe": "usage.py",
                              "note": "UNMEASURED: plan and price_month assumed; no usage "
                                      "source, so Remaining is unknown"})
    starter_lane = {"meter_weight": 1, "timeout": "30m"}

    def owns(self, slug):
        """Kiro serves every vendor's models on its own Meter, so all are its own."""
        return True

    def parse_models(self, raw):
        """Models from `kiro-cli chat --list-models --format json`: a list, or
        an object holding one under `models`. Each entry's id, name and
        supported efforts are read from whichever documented-looking key holds
        them; a model whose entry names no effort takes the harness's efforts.
        A listed word Kiro's `efforts` lacks goes in `unknown_efforts`.
        The router (`auto`) is left out."""
        doc = json.loads(raw)
        items = doc.get("models") if isinstance(doc, dict) else doc
        if not isinstance(items, list):
            raise ValueError("expected a JSON list of models, or an object with 'models'")
        models = []
        for item in items:
            if isinstance(item, str):
                item = {"id": item}
            if not isinstance(item, dict):
                continue
            slug = next((item[k] for k in ID_KEYS if isinstance(item.get(k), str) and item[k].strip()), None)
            if not slug or slug.strip().lower() == ROUTER:
                continue
            slug = slug.strip()
            display = next((item[k] for k in NAME_KEYS if isinstance(item.get(k), str)), slug)
            listed = next((item[k] for k in EFFORT_KEYS if isinstance(item.get(k), list)), None)
            words = [str(e).strip().lower() for e in listed or ()]
            efforts = (list(self.efforts) if listed is None
                       else [e for e in self.efforts if e in words])
            # a word Kiro lists that no Lane on it may carry (`none`, or one
            # delegate does not know yet) is kept for the refresh to name
            unknown = [w for w in words if w and w not in self.efforts]
            models.append({"slug": slug, "display_name": display, "efforts": efforts,
                           "unknown_efforts": unknown})
        return models


HARNESS = Kiro()
