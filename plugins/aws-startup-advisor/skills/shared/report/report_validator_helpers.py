"""Helpers shared by the migration-report validators.

Canonical source: `skills/shared/report/report_validator_helpers.py`. Each skill
that ships a report validator carries a byte-identical copy under its own
`references/vendored/report/`, kept in step by `tools/sync-vendored.py`, so the
validator still runs when the skill folder is installed on its own.

Consumers:
  - `scripts/validate-migration-report.py` (gcp-to-aws and azure-to-aws reports)
  - `skills/heroku-to-aws/scripts/validate-heroku-migration-report.py`

Only behaviour the two validators share lives here. `unmatched_phrases` takes the
phrase matcher as an argument because each validator keeps its own: the
gcp-to-aws one reads the phrase as HTML visible text, the Heroku one only folds
dashes and whitespace.

Validators load this file by path (`importlib.util.spec_from_file_location`),
not through `sys.path` or `sys.modules`, so loading both validators in one
process cannot collide on a module name. Stdlib only.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from html.parser import HTMLParser

# Whole-dollar part below this is small enough that a cents digit is itself
# meaningful precision (matches the skill rule's own examples: $1.50, $0.40).
CENTS_MEANINGFUL_BELOW = 2

# Elements whose subtree the browser never renders — an anchor (or its text)
# inside one must never stand in for the visible figure. Mirrors the
# validators' currency text parsers' inert sets so the anchor collector and the
# currency parser agree on what "rendered" means.
ANCHOR_INERT_TAGS = {"script", "style", "template"}


def canonical_money(value: float) -> str:
    """Canonical display form for a dollar amount, matching the emitter's own
    rule (each skill's report currency rule / the currency-formatting gate):
    monthly-scale totals (>= $2) round to the nearest whole dollar; genuinely
    small totals (< $2) keep two-decimal cents. Both the rendered figure and the
    JSON figure pass through this SAME function before comparison, so a correctly
    rounded `$113` for `112.90` matches, and the small-total exception (e.g.
    `$0.40`) is preserved instead of being truncated to `0`."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise
    # Decide precision on the ROUNDED magnitude, not the raw one, so a value that
    # rounds up ACROSS the $2 threshold canonicalizes consistently with how it
    # renders. Otherwise 1.999 (raw < 2 -> "2.00") would mismatch a displayed $2
    # (2.0 >= 2 -> "2"): both must land on "2". round() first, then classify.
    rounded_whole = int(round(v))
    if abs(rounded_whole) >= CENTS_MEANINGFUL_BELOW:
        return str(rounded_whole)  # nearest-dollar; 112.90->113, 112.4->112, 1.999->2
    return f"{v:.2f}"  # genuinely small total: retain cents (0.40 -> "0.40")


def normalize_money(text: str) -> str | None:
    """Reduce a rendered money string to its canonical display form for exact
    comparison against the JSON figure (same normalization on both sides via
    `canonical_money`). '$1,415/mo' -> '1415'; '$112.90' -> '113'; '$0.40' ->
    '0.40'. Returns None when no dollar amount is present."""
    m = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text)
    if not m:
        return None
    try:
        return canonical_money(float(m.group(1).replace(",", "")))
    except (TypeError, ValueError):
        return None


class CostAnchorParser(HTMLParser):
    """Collect the rendered text of every `data-cost-key="..."` element.

    Uses the stdlib HTML parser rather than a regex so that:
    (a) markup inside an HTML comment is never mistaken for a real anchor —
        comments are a distinct token the parser never re-tokenizes as tags;
    (b) nested child markup is read through the anchored element's OWN matching
        close tag, not the first `</` encountered, by counting nested
        opens/closes — and a NESTED `data-cost-key` element is collected as its
        own anchor too (an outer anchor being open must not swallow a recognized
        inner figure), tracked on a stack;
    (c) inert subtrees (`<script>`, `<style>`, `<template>`) are skipped — their
        content is never rendered by the browser, so an anchor or dollar token
        placed there must not satisfy the visible-figure requirement, even when
        the inert element itself carries `data-cost-key`;
    (d) an element with a `hidden` attribute is skipped for the same
        reason — its subtree is not rendered.
    Character references are decoded automatically (`convert_charrefs=True`).
    """

    # Void elements never have an end tag, so they must not be pushed onto the
    # element stack (doing so would desync every subsequent close).
    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[tuple[str, str]] = []  # (key, inner text), document order
        # One frame per open non-void element, innermost last. Each frame:
        #   {"tag", "inert": bool, "hidden": bool, "anchor": {key,parts}|None}
        # `inert`/`hidden` are STICKY down the subtree (an element inside an inert
        # or hidden ancestor is itself skipped) — computed as ancestor-or-self.
        self._stack: list[dict] = []

    def _in_skip(self) -> bool:
        """True when the current point is inside an inert or hidden subtree."""
        return bool(self._stack) and (self._stack[-1]["inert"] or self._stack[-1]["hidden"])

    @staticmethod
    def _is_hidden(attrs: list[tuple[str, str | None]]) -> bool:
        # `hidden` is a BOOLEAN attribute: its mere presence hides the subtree,
        # regardless of value. In HTML `hidden="false"` is NOT a not-hidden value —
        # "false" is an invalid value for a boolean attribute, whose invalid-value
        # default is the Hidden state. So any `hidden` attribute (including
        # `hidden=""`, `hidden="hidden"`, and `hidden="false"`) hides the element;
        # only the attribute's ABSENCE leaves it visible.
        return "hidden" in dict(attrs)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        parent = self._stack[-1] if self._stack else None
        # inert/hidden are STICKY: an element inside an inert/hidden ancestor is
        # itself inert/hidden. Kept as clean booleans (never a truthy list).
        inert = bool(parent and parent["inert"]) or tag in ANCHOR_INERT_TAGS
        hidden = bool(parent and parent["hidden"]) or self._is_hidden(attrs)
        anchor = None
        key = dict(attrs).get("data-cost-key")
        # Start a new anchor only when this element is actually rendered.
        if key and not inert and not hidden:
            anchor = {"key": key.lower(), "parts": []}
        frame = {"tag": tag, "inert": inert, "hidden": hidden, "anchor": anchor}
        if tag not in self._VOID_TAGS:
            self._stack.append(frame)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ANCHOR_INERT_TAGS or self._in_skip():
            return
        parent_hidden = self._stack[-1]["hidden"] if self._stack else False
        key = dict(attrs).get("data-cost-key")
        # A self-closed anchor has no text content; record it (empty) only if rendered.
        if key and not parent_hidden and not self._is_hidden(attrs):
            self.results.append((key.lower(), ""))

    def handle_endtag(self, tag: str) -> None:
        if tag in self._VOID_TAGS:
            return
        # Pop to the nearest matching open tag (tolerate minor misnesting). Every
        # frame in the popped slice that carried an anchor is emitted — including
        # any INNER anchors implicitly closed by an outer element's end tag — so a
        # nested `data-cost-key` is never silently dropped. Emit innermost-first,
        # then the matched frame, all in the order they closed.
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                popped = self._stack[i:]
                del self._stack[i:]
                for frame in reversed(popped):  # innermost closes first
                    if frame["anchor"] is not None:
                        self.results.append(
                            (frame["anchor"]["key"], "".join(frame["anchor"]["parts"]))
                        )
                return
        # Unmatched close tag: ignore.

    def handle_data(self, data: str) -> None:
        if self._in_skip():
            return
        # Append rendered text to every open anchor on the stack (an outer
        # anchor's text legitimately includes its children's text).
        for frame in self._stack:
            if frame["anchor"] is not None:
                frame["anchor"]["parts"].append(data)


def cost_anchor_matches(html: str) -> list[tuple[str, str]]:
    """Parse `html` and return every (data-cost-key, rendered text) pair found
    outside comments and non-rendered markup (script/style/template/hidden),
    including nested recognized anchors."""
    parser = CostAnchorParser()
    parser.feed(html)
    parser.close()
    return parser.results


def dig(d: dict, path: tuple[str, ...]):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def word_shingles(text: str, size: int = 4) -> set[str]:
    """Word phrases used to recognize a rendered condition without requiring a verbatim copy."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        return set()
    if len(words) <= size:
        return {" ".join(words)}
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def unmatched_phrases(
    phrases: list[object],
    rendered_items: list[str],
    phrase_rendered: Callable[[str, str], bool],
) -> list[str]:
    """Return artifact phrases that cannot be assigned distinct rendered items.

    `phrase_rendered(phrase, item)` decides whether one rendered item shows one
    phrase. Each validator passes its own matcher, because the two normalize the
    artifact phrase differently (see the module docstring).
    """
    matched_items: dict[int, int] = {}

    def assign(phrase_index: int, seen_items: set[int]) -> bool:
        phrase = str(phrases[phrase_index])
        for item_index, item in enumerate(rendered_items):
            if item_index in seen_items or not phrase_rendered(phrase, item):
                continue
            seen_items.add(item_index)
            previous = matched_items.get(item_index)
            if previous is None or assign(previous, seen_items):
                matched_items[item_index] = phrase_index
                return True
        return False

    for phrase_index in range(len(phrases)):
        assign(phrase_index, set())
    matched_phrases = set(matched_items.values())
    return [str(phrase) for index, phrase in enumerate(phrases) if index not in matched_phrases]
