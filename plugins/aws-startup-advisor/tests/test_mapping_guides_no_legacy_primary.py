"""Text contract: mapping-guide recommendation cells name only models the lifecycle registry allows.

`skills/shared/ai/ai-model-lifecycle.md` Rules 1-3 and its "Mapping Guides" integration point:
a "Best Bedrock Match" (or equivalent target) cell holds Active models only. A Legacy model may be
named elsewhere with a `Legacy — EOL YYYY-MM-DD` label as an alternative; an excluded or Removed
model is not named in a recommendation cell at all.

The banned set is read from the registry itself (the Legacy / EOL table rows whose Status is
`legacy` or `excluded`, plus the Removed list), so a registry refresh moves this test with it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS = PLUGIN_ROOT / "skills"
SHARED_AI = SKILLS / "shared" / "ai"
LIFECYCLE = SHARED_AI / "ai-model-lifecycle.md"

GUIDES = [
    SHARED_AI / "ai-gemini-to-bedrock.md",
    SHARED_AI / "ai-openai-to-bedrock.md",
    SHARED_AI / "ai-anthropic-to-bedrock.md",
    SHARED_AI / "ai-openrouter-to-bedrock.md",
    SKILLS / "gcp-to-aws" / "references" / "design-refs" / "ai-gemini-to-bedrock.md",
    SKILLS / "gcp-to-aws" / "references" / "phases" / "design" / "design-ai.md",
]

# Table columns whose cells are the guide's recommendation for a source model or tier.
RECOMMENDATION_COLUMNS = {
    "best bedrock match",
    "bedrock target",
    "bedrock gpt target",
    "cross-family target",
    "cross-family alternative",
    "bedrock model id",
    "bedrock equivalent",
    "model selection",
}


def _registry_section(text: str, heading_prefix: str) -> str:
    start = text.index(heading_prefix)
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _clean_name(name: str) -> str:
    name = name.split(" / ")[0]
    name = re.sub(r"\s+(all sizes|Instruct)$", "", name.strip())
    return re.sub(r"\s+v\d+$", "", name).strip()


def _banned_models() -> dict[str, str]:
    """Map each banned model name or id to its registry status."""
    text = LIFECYCLE.read_text(encoding="utf-8")
    banned: dict[str, str] = {}

    live = _registry_section(text, "## Legacy / EOL Models")
    for line in live.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[1].startswith("`"):
            continue
        status = cells[4].strip("* ").lower()
        if status not in {"legacy", "excluded"}:
            continue
        banned[_clean_name(cells[0])] = status
        for model_id in re.findall(r"`([^`]+)`", cells[1]):
            banned[model_id] = status

    removed = live[live.index("**Removed") :]
    for match in re.finditer(r"^- (.+?) \(`([^`]+)`", removed, flags=re.MULTILINE):
        banned[_clean_name(match.group(1))] = "removed"
        banned[match.group(2)] = "removed"
    return banned


def _name_pattern(name: str) -> re.Pattern[str]:
    # "Claude Sonnet 4" must not match "Claude Sonnet 4.6"; "Llama 3.2" must not match "Llama 3.20".
    return re.compile(r"(?<![\w.-])" + re.escape(name) + r"(?!\.?\d|\w)", re.IGNORECASE)


def _recommendation_cells(path: Path):
    header: list[str] | None = None
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        for column, cell in zip(header, cells):
            if column in RECOMMENDATION_COLUMNS:
                yield lineno, column, cell


def test_registry_yields_a_banned_set() -> None:
    banned = _banned_models()
    # Anchors from the registry at the time this test was written; if a refresh removes them,
    # the parser still has to find the remaining Legacy and Removed rows.
    assert any(status == "legacy" for status in banned.values()), banned
    assert any(status == "removed" for status in banned.values()), banned


@pytest.mark.parametrize("guide", GUIDES, ids=lambda p: str(p.relative_to(SKILLS)))
def test_recommendation_cells_hold_no_legacy_excluded_or_removed_model(guide: Path) -> None:
    banned = _banned_models()
    patterns = {name: _name_pattern(name) for name in banned}
    found = []
    for lineno, column, cell in _recommendation_cells(guide):
        for name, pattern in patterns.items():
            if pattern.search(cell):
                found.append(f"{guide.name}:{lineno} [{column}] {name} ({banned[name]}): {cell[:120]}")
    assert not found, (
        "A recommendation cell names a model the lifecycle registry marks Legacy, excluded or "
        "Removed. Use the registry's Active Replacement; keep a Legacy model only as a labelled "
        "alternative outside the recommendation column.\n" + "\n".join(found)
    )
