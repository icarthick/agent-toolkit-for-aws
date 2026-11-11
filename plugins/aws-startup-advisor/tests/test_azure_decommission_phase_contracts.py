"""Guard: the azure-to-aws Decommission phase stays wired, opt-in, and advice-only.

Decommission is an opt-in backbone phase after Generate. Its contract lives in phase-file
frontmatter and in SKILL.md prose, so these tests pin:

1. The backbone derived from frontmatter runs Generate -> Decommission -> complete, and
   Generate carries the re-entry guard that protects decommission-plan.md.
2. The decommission phase, its fragments and its assembler are mutually consistent.
3. SKILL.md's state-validation sets match the derived backbone and declare `skipped`.
4. The shared state schema accepts `skipped` (so a declined run validates) and still
   rejects an unknown status.
5. No phase file carries an Azure CLI or PowerShell command that deletes, stops or
   cancels anything. The scan reads commands (code spans and code blocks), not the prose
   that states the rule.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL = PLUGIN_ROOT / "skills" / "azure-to-aws"
PHASES = SKILL / "references" / "phases"
DECOMMISSION_DIR = PHASES / "decommission"
DECOMMISSION = DECOMMISSION_DIR / "decommission.md"
GENERATE = PHASES / "generate" / "generate.md"
SKILL_MD = SKILL / "SKILL.md"
SHARED_SCHEMA = PLUGIN_ROOT / "skills" / "shared" / "state" / "phase-status.schema.json"
VALIDATE_ARTIFACTS = PLUGIN_ROOT / "scripts" / "validate-artifacts.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(path: Path) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", _read(path), re.DOTALL)
    assert m, f"{path.name}: no YAML frontmatter"
    return m.group(1)


def _scalar(fm: str, key: str) -> str | None:
    """A top-level `key: value` scalar from frontmatter, or None when absent."""
    m = re.search(rf"^{re.escape(key)}:[ \t]*(\S[^\n]*)$", fm, re.MULTILINE)
    return m.group(1).strip().strip('"') if m else None


def _block(fm: str, key: str) -> str:
    """The indented lines under a top-level `key:` in frontmatter."""
    m = re.search(rf"^{re.escape(key)}:[ \t]*\n((?:[ \t]+[^\n]*\n?)+)", fm, re.MULTILINE)
    return m.group(1) if m else ""


def _backbone_chain() -> list[str]:
    """Walk the backbone from the `_init` phase along `_advances_to`, as the interpreter does."""
    backbone: dict[str, str] = {}
    head = None
    for orchestrator in sorted(PHASES.glob("*/*.md")):
        if orchestrator.stem != orchestrator.parent.name:
            continue
        fm = _frontmatter(orchestrator)
        if _scalar(fm, "_kind") == "sidebar":
            continue
        phase = _scalar(fm, "_phase")
        backbone[phase] = _scalar(fm, "_advances_to")
        if _scalar(fm, "_init") == "true":
            head = phase
    assert head, "no backbone phase carries _init: true"
    chain = [head]
    while chain[-1] != "complete":
        nxt = backbone[chain[-1]]
        assert nxt not in chain, f"backbone loops at {nxt}"
        chain.append(nxt)
    return chain


def test_backbone_runs_generate_then_decommission_then_complete() -> None:
    assert _backbone_chain() == [
        "discover", "clarify", "design", "estimate", "generate", "decommission", "complete",
    ]


def test_generate_guards_the_decommission_plan_on_reentry() -> None:
    fm = _frontmatter(GENERATE)
    assert _scalar(fm, "_advances_to") == "decommission"
    guard = _block(fm, "_re_entry_guard")
    assert re.search(r"_stale_if_completed:\s*decommission\b", guard)
    assert re.search(r"_stale_artifact:\s*decommission-plan\.md\b", guard)
    assert re.search(r"_on_reentry:\s*stop_unless_confirmed\b", guard)
    assert re.search(r"_on_confirm:\s*reset_downstream_to_pending\b", guard)
    body = _read(GENERATE)
    assert "advance to\n   `decommission`" in body, "generate.md step 5 must advance to decommission"
    assert "advance to\n   `complete`" not in body


def test_decommission_phase_is_an_interactive_backbone_phase() -> None:
    fm = _frontmatter(DECOMMISSION)
    assert _scalar(fm, "_phase") == "decommission"
    assert _scalar(fm, "_requires_phase") == "generate"
    assert _scalar(fm, "_advances_to") == "complete"
    assert _scalar(fm, "_kind") in (None, "backbone")
    assert _scalar(fm, "_interactive") == "true", "the phase asks the opt-in dates; it cannot be dispatched"
    assert _scalar(fm, "_exec") is None and "_exec:" not in fm
    pre = _block(fm, "_preconditions")
    assert re.search(r"_check_phase_completed:\s*generate\b", pre)
    assert re.search(r"_check_single_active_phase:\s*true\b", pre)
    assert "decommission-plan.md" in _block(fm, "_produces")
    post = _block(fm, "_postconditions")
    assert re.search(r"_check_file_exists:\s*decommission-plan\.md\b", post)
    forbids = _block(fm, "_forbids_files")
    for path in ("azure-resource-inventory.json", "terraform/", "*.sh"):
        assert path in forbids, f"decommission.md _forbids_files must include {path}"


def test_decommission_units_match_the_phase() -> None:
    fm = _frontmatter(DECOMMISSION)
    fragments = re.findall(r"_id:\s*(\S+)\s*\n\s*_trigger:[^\n]*\n\s*_file:\s*(\S+)", _block(fm, "_fragments"))
    assert {fid for fid, _ in fragments} == {"resources", "billing"}
    for fid, rel in fragments:
        unit = SKILL / "references" / rel
        assert unit.is_file(), f"fragment file {rel} is missing"
        ufm = _frontmatter(unit)
        assert _scalar(ufm, "_fragment") == fid
        assert _scalar(ufm, "_of_phase") == "decommission"
        assert "decommission-plan.md" in _block(ufm, "_contributes")
    assemble_rel = re.search(r"_file:\s*(\S+)", _block(fm, "_assemble")).group(1)
    afm = _frontmatter(SKILL / "references" / assemble_rel)
    assert _scalar(afm, "_of_phase") == "decommission"
    assert "decommission-plan.md" in _block(afm, "_produces")
    reads = _block(afm, "_reads")
    for fid, _ in fragments:
        assert fid in reads, f"assembler does not read fragment {fid}"


def _rule(text: str, number: int) -> str:
    m = re.search(rf"^{number}\. \*\*[^\n]*$", text, re.MULTILINE)
    assert m, f"SKILL.md State Validation rule {number} is missing"
    return m.group(0)


def _braced(line: str) -> list[str]:
    m = re.search(r"\{([a-z_, ]+)\}", line)
    assert m, f"no set in: {line[:80]}"
    return [item.strip() for item in m.group(1).split(",")]


def test_skill_md_state_validation_covers_decommission() -> None:
    text = _read(SKILL_MD)
    chain = _backbone_chain()
    core = chain[:-1]
    assert "decommission" in _braced(_rule(text, 3))
    current = _braced(_rule(text, 5))
    assert set(current) == set(chain), "valid current_phase must be the backbone plus complete"
    ordered = re.search(r"\[([a-z_, ]+)\]", _rule(text, 6)).group(1)
    assert [p.strip() for p in ordered.split(",")] == core
    assert set(_braced(_rule(text, 7))) == set(core)
    status = _rule(text, 4)
    assert "`skipped`" in status and "`decommission` only" in status


def test_skill_md_declares_opt_in_routing_and_legacy_runs() -> None:
    text = _read(SKILL_MD)
    section = text[text.index("### Decommission routing"):text.index("### Input Security")]
    assert "**Resolved statuses:** `skipped`, for `phases.decommission` only" in section
    decline = re.search(r"\*\*B\*\*[^\n]*\n[^\n]*\n", section).group(0)
    assert '`"skipped"`' in decline and '`"complete"`' in decline and "ONE state write" in decline
    assert "no\n  `phases.decommission` key" in section, "legacy runs without the key must be covered"
    assert "still\n  reads as complete" in section
    assert "decision-only run" in section
    after_generate = re.search(r"^- \*\*After Generate\*\*:[^\n]*$", text, re.MULTILINE).group(0)
    assert "Decommission routing" in after_generate


def _load_validator():
    spec = importlib.util.spec_from_file_location("_validate_artifacts_decommission", VALIDATE_ARTIFACTS)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("status", "valid"), [("skipped", True), ("completed", True), ("declined", False)])
def test_state_file_with_decommission_status_validates(tmp_path: Path, status: str, valid: bool) -> None:
    assert "skipped" in json.loads(_read(SHARED_SCHEMA))["properties"]["phases"]["additionalProperties"]["enum"]
    state = {
        "migration_id": "0101-0000",
        "last_updated": "2026-01-01T00:00:00Z",
        "current_phase": "complete",
        "run_mode": "decide_and_execute",
        "phases": {
            "discover": "completed", "clarify": "completed", "design": "completed",
            "estimate": "completed", "workshop": "completed", "generate": "completed",
            "decommission": status, "feedback": "completed",
        },
    }
    (tmp_path / ".phase-status.json").write_text(json.dumps(state), encoding="utf-8")
    validator = _load_validator()
    findings: list = []
    validator.validate_run_dir(tmp_path, "azure-to-aws", validator.load_manifest(validator.DEFAULT_MANIFEST), findings)
    errors = [f for f in findings if f.severity == "error"]
    assert (not errors) is valid, [f.as_dict() for f in errors]


# A command that acts on Azure: the CLI with a destructive verb, or a destructive Az cmdlet.
_DESTRUCTIVE = re.compile(
    r"\baz\s+(?:[a-z][\w-]*\s+)*?(?:delete|purge|stop|deallocate|cancel|remove)\b"
    r"|\b(?:Remove|Stop|Disable)-Az\w+",
    re.IGNORECASE,
)


def _commands(text: str) -> list[str]:
    """Code blocks and inline code spans: the places a phase file writes a command."""
    blocks = re.findall(r"^```[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    without_blocks = re.sub(r"^```[^\n]*\n.*?^```", "", text, flags=re.MULTILINE | re.DOTALL)
    return blocks + re.findall(r"`([^`\n]+)`", without_blocks)


def _destructive_commands(text: str) -> list[str]:
    return [c for c in _commands(text) if _DESTRUCTIVE.search(c)]


@pytest.mark.parametrize(
    "sample",
    [
        "Run `az group delete --name rg-prod --yes` after cutover.",
        "```bash\naz webapp stop --name app --resource-group rg\n```\n",
        "Then `Remove-AzResourceGroup -Name rg-prod`.",
        "```\naz keyvault purge --name kv\n```\n",
    ],
)
def test_destructive_command_scan_catches_commands(sample: str) -> None:
    assert _destructive_commands(sample), sample


def test_destructive_command_scan_ignores_prose_and_read_only_commands() -> None:
    sample = "It writes no Azure CLI command that deletes anything, and runs no `az` command. `az resource list`."
    assert not _destructive_commands(sample)


def test_decommission_phase_files_write_no_destructive_azure_command() -> None:
    files = sorted(DECOMMISSION_DIR.glob("*.md"))
    assert len(files) >= 3
    found = {f.name: _destructive_commands(_read(f)) for f in files}
    assert not any(found.values()), found
