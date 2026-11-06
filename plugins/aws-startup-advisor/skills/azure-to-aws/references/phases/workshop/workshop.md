---
_phase: workshop
_title: "What-If Workshop (Optional)"
_kind: sidebar
_requires_phase: estimate
_gates: generate
_trigger:
  {
    _when: "user opts in post-Estimate (estimate-assemble offer [B], or says what if / reprice / workshop mode / compare scenarios)",
  }
_input:
  - azure-resource-inventory.json
  - preferences.json
  - aws-design.json
  - estimation-infra.json
_knowledge:
  - { file: references/shared/schema-workshop-scenarios.md }
  - { file: references/vendored/workshop/workshop-invariants.md }
_fragments:
  - _id: sheet
    _trigger: { _always: true }
    _file: phases/workshop/workshop-sheet.md
  - _id: refresh
    _trigger: { _when: "user chose Apply & reprice" }
    _file: phases/workshop/workshop-refresh.md
  - _id: compare
    _trigger: { _when: "user chose Compare scenarios OR after a successful refresh" }
    _file: phases/workshop/workshop-compare.md
_assemble:
  _file: phases/workshop/workshop-assemble.md
_produces:
  - scenarios/index.json
_interactive: true
_preconditions:
  - _check_phase_completed: estimate
    _on_failure: _halt_and_inform
  - _check_file_exists:
      [
        azure-resource-inventory.json,
        preferences.json,
        aws-design.json,
        estimation-infra.json,
      ]
    _on_failure: _unrecoverable
_postconditions:
  - _check_file_exists: scenarios/index.json
    _on_failure: _warn_and_skip
  - _validate_json: scenarios/index.json
    _on_failure: _warn_and_skip
---

# Sidebar: What-If Workshop

## Orientation

Change an assumption, reprice, and compare — without re-running Discover. This is a
**sidebar**: off-backbone, entered only by its `_trigger`, and it returns control
rather than advancing. It never appears as `current_phase`.

`_gates: generate` means Generate must not start while this sidebar is unresolved.
Resolution includes a decline — a declined sidebar is still `"completed"`, because
`_gates` holds ordering, never participation. Whether the user actually engaged is a
separate signal, carried by whether `scenarios/index.json` exists.

The cross-skill invariants for the workshop live in
`references/vendored/workshop/workshop-invariants.md` and win on any disagreement
with the unit files here.

Knobs on the sheet: region, HA, compute target, cost optimization, CPU architecture.
**The architecture default is `x86_64`** here, matching the skill default rather than
the repo-wide Graviton default — see SKILL.md § Philosophy.

## Status — build step 6

Implemented. The knob set (region, HA posture, compute target, cost
optimization, CPU architecture), the Apply & reprice mechanics, the
comparison table, and the sidebar-resolve handoff back to the decision gate
are ported from `gcp-to-aws`'s equivalent, adapted to this skill's knobs and
its Premium/Balanced/Optimized scenario schema — see each fragment's own
Status note for what changed versus GCP's version.

## Step: Guard re-entry after Generate

Mandatory, and the single authoritative point for it: run this step before any
other step of the sidebar, so it covers every path into the workshop (Apply &
reprice, Compare, or resolving without ever reaching `workshop-refresh.md`).
`workshop-refresh.md` relies on it and does not re-check. Do not re-run
Discover, live capture or the Terraform/Bicep/ARM parse.

Read `$MIGRATION_DIR/.phase-status.json`. The guard fires when ANY of:

1. `phases.generate` is `"completed"`;
2. `phases.generate` is `"in_progress"` (an interrupted Generate);
3. `current_phase == "generate"` with `run_mode` set (decision-gate option C
   was taken; `phases.generate` can still be `"pending"` when Generate was never
   entered, which is why this condition reads `current_phase`);
4. `current_phase == "complete"` with `run_mode` set (a resolved decide or
   decide-and-execute state).

The ordinary entry from the decision gate's option B (`run_mode: "decide"`,
`current_phase: "estimate"`, `phases.generate: "pending"`) matches none of
these, so the guard does not fire.

On fire, tell the user the previous decision/execution state is stale and ask
them to confirm re-entering the workshop: the confirmation Estimate's
`_re_entry_guard` (`stop_unless_confirmed`) asks before Estimate re-runs over
Generate output, here required on all four conditions. On confirm, set
`phases.generate`, the backbone phase downstream of Estimate, back to
`"pending"` (`reset_downstream_to_pending`, read-merge-write), then run the
next step.

**Do NOT delete anything Generate wrote.** `terraform/` (including
`terraform.tfvars` and any edits to `baseline.tf`/`variables.tf`),
`ai-migration/`, `generation-*.json`, `validation-report.json`,
`MIGRATION_GUIDE.md`, `README.md` and `migration-report.html` stay untouched:
never modified, deleted or archived by workshop re-entry. Generate tells users
to fill in the tfvars values and to edit `baseline.tf` for the security-baseline
opt-out (`generate-artifacts-docs.md` § Step 1, `terraform/README.md`), and an
edited file keeps its generated filename, so no filename-based rule can tell a
disposable generated file from a customer-edited one. Design/Estimate artifacts
are overwritten by the reprice; the previous execution pack is not. A previous
pack on disk beside a fresh decision is the expected state; the next accepted
Generate run overwrites it in its own course.

If the user does NOT confirm, **stop**: do not set `phases.workshop`, patch
preferences or re-run Design/Estimate. The execution pack and the
decide/execute state are left exactly as they were.

## Step: Normalize state on an accepted re-entry

Whenever the guard fired and the user confirmed, whichever of its four
conditions fired, set `current_phase` to `"estimate"` and remove the `run_mode`
key (read-merge-write; remove it, do not set it to null). An absent `run_mode`
is the truthful state here: the decision gate's question is open again, and
`estimate-assemble.md` § Step 3 writes `run_mode` when the gate is re-presented
on exit. A resumed session then matches SKILL.md's workshop resume
(`current_phase == "estimate"`) and reaches the decision gate, never Generate.
When the guard did not fire, leave `current_phase` and `run_mode` unchanged.

Then set `phases.workshop` to `"in_progress"` if it is not already; never set
`current_phase` to `workshop`.

## Step: Run the sidebar

1. Present the sheet (`workshop-sheet.md`).
2. On Apply & reprice, run `workshop-refresh.md`: patch preferences → re-run Design →
   re-run Estimate → snapshot the result as a scenario.
3. On Compare, or after a successful refresh, run `workshop-compare.md`.
4. Run `workshop-assemble.md` to resolve the sidebar and return control.
