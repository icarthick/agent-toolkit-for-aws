"""Contracts for gcp-to-aws's opt-in Decommission phase.

The phase plans shutting down the source cloud after Generate. Three rules must hold:

- it is opt-in and offered only after Generate in a decide_and_execute run;
- it is advice and a checklist only: the phase file carries no command that deletes,
  destroys, disables or shuts down a source resource;
- runs whose state file has no `decommission` key (they started before the phase
  existed) still read as complete, so the state machine keeps a back-compat row and the
  validation enums accept the missing key.

Each check is a function over text, so the negative cases below prove it fails on a
mutated copy instead of passing vacuously.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = PLUGIN_ROOT / "skills" / "gcp-to-aws"
SKILL_MD = SKILL_ROOT / "SKILL.md"
PHASE_FILE = SKILL_ROOT / "references" / "phases" / "decommission" / "decommission.md"
GENERATE_MD = SKILL_ROOT / "references" / "phases" / "generate" / "generate.md"
SCHEMA_MD = SKILL_ROOT / "references" / "shared" / "schema-phase-status.md"
GATES_MD = SKILL_ROOT / "references" / "shared" / "handoff-gates.md"

# A source-cloud command that removes or stops something: gcloud/gsutil/bq/terraform
# verbs, in any order on one line after the tool name.
DESTRUCTIVE_COMMAND = re.compile(
    r"\b(?:gcloud\b[^\n]*\b(?:delete|destroy|disable|stop|remove-iam-policy-binding)\b"
    r"|gsutil\b[^\n]*\b(?:rm|rb)\b"
    r"|gcloud\s+storage\b[^\n]*\b(?:rm|buckets\s+delete)\b"
    r"|bq\s+rm\b"
    r"|terraform\s+destroy\b)"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def destructive_commands(text: str) -> list[str]:
    return [m.group(0) for m in DESTRUCTIVE_COMMAND.finditer(text)]


def phase_contract_gaps(text: str) -> list[str]:
    required = {
        "generate precondition": 'phases.generate == "completed"',
        "run_mode precondition": 'run_mode == "decide_and_execute"',
        "output artifact": "$MIGRATION_DIR/decommission-plan.md",
        "keep-until column": "Keep until",
        "retain/export column": "Retain / export first",
        "deletion order": "Deletion order (dependants first)",
        "billing closure": "## Billing closure",
        "success gate": "HANDOFF_OK | phase=decommission",
        "failure gate": "GATE_FAIL | phase=decommission",
        "person carries it out": "for a person to carry out and confirm",
    }
    return [name for name, needle in required.items() if needle not in text]


def skill_state_machine_gaps(text: str) -> list[str]:
    gaps = []
    if "workshop, generate, decommission, feedback}" not in text:
        gaps.append("valid phases enum")
    if "generate, decommission, complete}" not in text:
        gaps.append("valid current_phase enum")
    if "[discover, clarify, design, estimate, generate, decommission]" not in text:
        gaps.append("ordered core phases")
    if "| legacy-complete |" not in text or "**no** `decommission` key" not in text:
        gaps.append("legacy no-key row")
    if "| decommission-offer |" not in text:
        gaps.append("offer row")
    if "**Decommission is opt-in (HARD RULE):**" not in text:
        gaps.append("opt-in hard rule")
    if "**Generate is opt-in (HARD RULE):**" not in text:
        gaps.append("Generate opt-in hard rule")
    if "**Clarify is mandatory:**" not in text:
        gaps.append("Clarify mandatory rule")
    if "references/phases/decommission/decommission.md" not in text:
        gaps.append("phase file reference")
    return gaps


def test_phase_file_has_its_contract() -> None:
    assert PHASE_FILE.is_file()
    assert phase_contract_gaps(_read(PHASE_FILE)) == []


def test_phase_file_stays_within_context_budget() -> None:
    assert len(_read(PHASE_FILE).splitlines()) < 400


def test_phase_file_writes_no_destructive_command() -> None:
    assert destructive_commands(_read(PHASE_FILE)) == []


def test_destructive_command_check_catches_a_delete() -> None:
    mutated = _read(PHASE_FILE) + "\n```bash\ngcloud sql instances delete orders-db --quiet\n```\n"
    assert destructive_commands(mutated) == ["gcloud sql instances delete"]
    assert destructive_commands("run `gsutil -m rm -r gs://bucket`") != []
    assert destructive_commands("then terraform destroy -auto-approve") != []


def test_phase_contract_check_catches_a_missing_gate() -> None:
    mutated = _read(PHASE_FILE).replace("HANDOFF_OK | phase=decommission", "HANDOFF_OK")
    assert phase_contract_gaps(mutated) == ["success gate"]


def test_skill_state_machine_names_the_phase() -> None:
    assert skill_state_machine_gaps(_read(SKILL_MD)) == []


def test_state_machine_check_catches_a_missing_legacy_row() -> None:
    mutated = _read(SKILL_MD).replace("| legacy-complete |", "| legacy |")
    assert skill_state_machine_gaps(mutated) == ["legacy no-key row"]


def test_generate_seeds_the_offer_and_never_auto_loads() -> None:
    text = _read(GENERATE_MD)
    assert 'Set `phases.decommission` to `"pending"`' in text
    assert "Never load the phase without a Yes." in text
    # The completion write still ends the executed run at `complete`; telemetry and the
    # acceptance lifecycle key on it.
    assert 'Set `current_phase` to `"complete"`' in text


def test_schema_and_gates_include_the_phase() -> None:
    schema = _read(SCHEMA_MD)
    assert "workshop, generate, decommission, feedback." in schema
    assert "A missing `decommission` key is valid" in schema
    gates = _read(GATES_MD)
    assert "phase=<discover|clarify|design|estimate|generate|decommission>" in gates
    assert "| **decommission** |" in gates
    assert "field=decommission-plan.md \\| reason=stale_downstream" in gates


def test_existing_gcp_fixtures_stay_valid_without_the_key() -> None:
    """Fixtures written before the phase existed have no `decommission` key; that is
    the back-compat case, so any value present must still be a valid status."""
    seen = 0
    for path in (PLUGIN_ROOT / "fixtures").rglob(".phase-status.json"):
        status = json.loads(path.read_text(encoding="utf-8"))
        if status.get("owning_skill") != "GCP_TO_AWS":
            continue
        seen += 1
        value = (status.get("phases") or {}).get("decommission")
        assert value in (None, "pending", "in_progress", "completed"), path
    assert seen > 0
