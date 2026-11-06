---
_phase: workshop
_title: "What-If Workshop (Optional Sidebar)"
_kind: sidebar
_requires_phase: estimate
_gates: generate
_trigger: { _when: "the user opts in after Estimate (Decision-gate option [B], or says what if / reprice / workshop mode / compare scenarios) and the infra Estimate artifacts exist" }
_input:
  - gcp-resource-inventory.json
  - preferences.json
  - aws-design.json
  - estimation-infra.json
_fragments:
  - _id: sheet
    _trigger: { _always: true }
    _file: phases/workshop/workshop-sheet.md
  - _id: refresh
    _trigger: { _when: "scenarios/index.json is missing (baseline capture, before the sheet) or the user chose Apply & reprice" }
    _file: phases/workshop/workshop-refresh.md
  - _id: compare
    _trigger: { _when: "the user chose Compare scenarios, or after a successful refresh" }
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
        gcp-resource-inventory.json,
        preferences.json,
        aws-design.json,
        estimation-infra.json,
      ]
    _on_failure: _halt_and_inform
_postconditions:
  - _check_file_exists: scenarios/index.json
    _on_failure: _warn_and_skip
  - _validate_json: scenarios/index.json
    _on_failure: _warn_and_skip
---

# Phase: What-If Workshop (Optional Sidebar)

> **Sidebar**, not a backbone step — same class as Feedback. Entered only when
> the user opts in after Estimate (or says what if / reprice / workshop mode /
> compare scenarios). Never becomes `current_phase`. Returns control to the
> Estimate→Generate flow. Contract:
> `references/shared/schema-workshop-scenarios.md`.

**Execute ALL steps in order. Do not skip or deviate.**

## Prerequisites

1. `$MIGRATION_DIR/.phase-status.json` has `phases.estimate == "completed"`.
2. Infra route artifacts exist: `gcp-resource-inventory.json`, `preferences.json`,
   `aws-design.json`, `estimation-infra.json`.
3. **AI-only / billing-only NO-OP for this pilot:** If `gcp-resource-inventory.json`
   is missing (AI-only or billing-only run), do **not** enter the infra workshop.
   Tell the user this pilot covers IaC infra repricing only; continue toward
   Generate / Feedback.

## Entry

1. Do **not** re-run Discover / live CLI / Terraform parse.
2. If `phases.generate` is `completed`, require Estimate re-entry confirm and reset
   generate (and later) to `pending` before refreshing.
3. Set `phases.workshop` to `"in_progress"`. Do **not** change `current_phase`
   (leave at `"estimate"` until exit/decline).

## Loop

1. If `scenarios/index.json` missing → load `workshop-refresh.md` § Baseline capture.
2. Load `workshop-sheet.md` — present knobs + actions.
3. Branch:
   - **Apply & reprice** → `workshop-refresh.md` → `workshop-compare.md`
   - **Compare scenarios** → `workshop-compare.md`
   - **Done / exit** → `workshop-assemble.md` → returns to the Decision gate in `estimate.md`
   - **Exit to full Clarify** → danger; Clarify re-entry only on explicit confirm

## Hard rules

| Rule                        | Behavior                                                           |
| --------------------------- | ------------------------------------------------------------------ |
| Inventory frozen            | Never write `gcp-resource-inventory.json`, clusters, or `capture/` |
| Inner Design/Estimate       | Artifact rewrite only — see `workshop-refresh.md` § Inner runs     |
| Max 5 scenarios             | Warn + name eviction before delete                                 |
| Working tree = active       | prefs / design / estimation match active scenario                  |
| No BigQuery target knobs    | Keep deferred specialist rows; do not invent warehouse targets     |
| No agentic outcome override | Do not mutate `ai_constraints.agentic.*` in v1                     |

These rules restate the canonical contract in
`references/vendored/workshop/workshop-invariants.md` (vendored from
`skills/shared/workshop/workshop-invariants.md`, kept byte-identical by
`shared:sync`). When this table and that file disagree, the invariants
file wins — fix this table.

## Decline without entering

When the user chooses Decision-gate option **A** (done for now) or **C**
(generate) without entering the workshop, mark `phases.workshop` `"completed"`
(resolved/declined); the gate's choice handling in `estimate.md` sets
`run_mode` and `current_phase`.
