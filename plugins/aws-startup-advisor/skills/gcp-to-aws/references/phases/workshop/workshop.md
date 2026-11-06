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
2. **Stale Generate/decide guard (mandatory, single authoritative point).** It
   runs before any other Entry step or Loop branch, so it covers every path
   into the workshop (Apply & reprice, Compare scenarios, or exiting without
   ever reaching `workshop-refresh.md`). `workshop-refresh.md` relies on it and
   does not re-check.

   Read `$MIGRATION_DIR/.phase-status.json`. The guard fires when ANY of:

   1. `phases.generate` is `"completed"`;
   2. `phases.generate` is `"in_progress"` (an interrupted Generate);
   3. `current_phase == "generate"` with `run_mode` set (Decision-gate option
      C was taken; `phases.generate` can still be `"pending"` when Generate was
      never entered, which is why this condition reads `current_phase`);
   4. `current_phase == "complete"` with `run_mode` set (a resolved decide or
      decide-and-execute state, e.g. the decide-complete resume).

   On fire, tell the user the previous decision/execution state is stale and
   ask them to confirm re-entering the workshop (the same confirmation
   `estimate.md` § Completion Handoff Gate requires before Estimate re-runs
   over Generate output). On confirm, set `phases.generate` (the backbone
   phase downstream of Estimate) back to `"pending"` in `.phase-status.json`
   (read-merge-write), then run step 3.

   **Do NOT delete anything Generate wrote.** `terraform/`, `scripts/`,
   `ai-migration/`, `generation-*.json`, `MIGRATION_GUIDE.md`, `README.md` and
   `migration-report.html` stay untouched: never modified, deleted or archived
   by workshop re-entry. Generate tells users to copy
   `terraform/terraform.tfvars.example` to `terraform.tfvars` and fill it in
   (`generate-artifacts-docs.md` fill-in checklist), and customer-edited files
   keep their generated filenames, so no filename-based rule can tell a
   disposable generated file from a customer-edited one. Design/Estimate
   artifacts are overwritten by the reprice; the previous execution pack is
   not.

   Reaching the Decision gate with that pack still on disk is the supported
   state: `validate-migration-report.py --mode decision` decides
   "pre-execution" from `.phase-status.json` `phases.generate` (reset to
   `"pending"` above), not from whether `terraform/` or `generation-*.json`
   exist (see `references/shared/validate-migration-report.md`). The next
   accepted Generate run overwrites the pack in its own course.

   If the user does NOT confirm, **stop** here: do not set
   `phases.workshop`, patch preferences or re-run Design/Estimate. The
   execution pack and the decide/execute state are left exactly as they were.
3. **Normalize `current_phase`/`run_mode` on every accepted re-entry
   (mandatory).** Whenever step 2 fired and the user confirmed, whichever of
   its four conditions fired, also set `current_phase` to `"estimate"` and
   remove the `run_mode` key (read-merge-write; remove it, do not set it to
   null). This returns the run to the pre-gate state: a session resumed
   after the workshop then matches the `workshop` row in `SKILL.md` § State
   Machine (`current_phase == "estimate"`) and reaches the Decision gate,
   instead of the `generate`, decide-complete or legacy-generate rows. When
   step 2 did not fire, leave `current_phase` and `run_mode` unchanged.
4. Set `phases.workshop` to `"in_progress"`. Do **not** change `current_phase`
   further — sidebars never own it (it stays `"estimate"` until exit/decline).

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
