"""Guard: azure-to-aws design-ai.md Step 0.5 reads the Region code that Clarify writes.

Clarify writes `target_region` as an object whose `value` is the Region code: at
`global.target_region` in a full run (schema-preferences.md, clarify-assemble.md) and at
`design_constraints.target_region` in an AI-only run (clarify-ai-only.md). Step 0.5 must
resolve the `.value` string from those paths, in that order, and default to `us-east-1`.
"""
from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
AZURE_REFS = PLUGIN_ROOT / "skills" / "azure-to-aws" / "references"
DESIGN_AI_MD = AZURE_REFS / "phases" / "design" / "design-ai.md"
CLARIFY_AI_ONLY_MD = AZURE_REFS / "phases" / "clarify" / "clarify-ai-only.md"
SCHEMA_PREFERENCES_MD = AZURE_REFS / "shared" / "schema-preferences.md"


def _step_0_5() -> str:
    text = DESIGN_AI_MD.read_text(encoding="utf-8")
    match = re.search(r"^## Step 0\.5:.*?(?=^## )", text, flags=re.MULTILINE | re.DOTALL)
    assert match, "design-ai.md has no Step 0.5 section"
    return match.group(0)


def test_step_0_5_reads_full_run_value_first() -> None:
    step = _step_0_5()
    full = step.find("`global.target_region.value`")
    ai_only = step.find("`design_constraints.target_region.value`")
    assert full != -1, "Step 0.5 must read global.target_region.value (full run)"
    assert ai_only != -1, "Step 0.5 must read design_constraints.target_region.value (AI-only run)"
    assert full < ai_only, "the full-run path must be resolved before the AI-only path"


def test_step_0_5_keeps_us_east_1_default() -> None:
    assert "`us-east-1`" in _step_0_5()


def test_step_0_5_does_not_use_the_bare_object_as_region() -> None:
    step = _step_0_5()
    bare = re.findall(r"`(?:global|design_constraints)\.target_region`", step)
    assert not bare, f"Step 0.5 reads target_region without .value: {bare}"


def test_producers_still_write_target_region_as_an_object_with_value() -> None:
    schema = SCHEMA_PREFERENCES_MD.read_text(encoding="utf-8")
    assert re.search(r'"target_region":\s*\{[^}]*"value"', schema), (
        "schema-preferences.md no longer writes global.target_region as an object with value"
    )
    ai_only = CLARIFY_AI_ONLY_MD.read_text(encoding="utf-8")
    assert re.search(r'"target_region":\s*\{\s*//[^\n]*\n\s*"value"', ai_only), (
        "clarify-ai-only.md no longer writes design_constraints.target_region as an object with value"
    )
