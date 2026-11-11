---
_phase: decommission
_title: "Plan the Azure Decommission (Optional)"
_requires_phase: generate
_input:
  - preferences.json
  - { file: azure-resource-inventory.json, _when: "run has an infra track" }
  - { file: azure-resource-clusters.json, _when: "run has an infra track" }
  - { file: aws-design.json, _when: "run has an infra track" }
  - { file: MIGRATION_GUIDE.md, _when: "run has an infra track" }
  - { file: ai-workload-profile.json, _when: "run has an AI track" }
  - { file: aws-design-ai.json, _when: "run has an AI track" }
_fragments:
  - _id: resources
    _trigger: { _always: true }
    _file: phases/decommission/decommission-resources.md
  - _id: billing
    _trigger: { _always: true }
    _file: phases/decommission/decommission-billing.md
_assemble:
  _file: phases/decommission/decommission-assemble.md
_produces:
  - decommission-plan.md
_advances_to: complete
_interactive: true
_preconditions:
  - _check_phase_completed: generate
    _on_failure: _halt_and_inform
  - _check_single_active_phase: true
    _on_failure: _halt_and_inform
  - _assert: "the user accepted the Decommission offer (SKILL.md § Decommission routing) or explicitly asked for a decommission plan this turn. A declined or unanswered offer never reaches this gate: the routing resolves the phase as skipped without running it."
    _on_failure: _halt_and_inform
  - _assert: "preferences.json exists and validates. WHEN the run has an infra track: azure-resource-inventory.json and aws-design.json exist and validate. WHEN the run is AI-only (no azure-resource-inventory.json): ai-workload-profile.json and aws-design-ai.json exist and validate."
    _on_failure: _halt_and_inform
_postconditions:
  - _check_file_exists: decommission-plan.md
    _on_failure: _halt_and_inform
  - _assert: "decommission-plan.md states the cutover date and the rollback window exactly as the user gave them in this phase, and every keep-until date in it is that cutover date plus that rollback window, or a later date with its reason stated in the row. No date or window length was defaulted or invented."
    _on_failure: _halt_and_inform
  - _assert: "the schedule table in decommission-plan.md has one row per source resource: every resources[] azure_id of azure-resource-inventory.json on an infra track, and every infrastructure[] entry of ai-workload-profile.json plus one row per direct provider account that summary.ai_source names (openai, anthropic, or both) on an AI track. Each row carries a keep-until date, the data to retain or export (or 'none' with the reason), and a deletion step number, and the step numbers put every resource after the resources that depend on it (dependants first)."
    _on_failure: _halt_and_inform
  - _assert: "decommission-plan.md has a Billing close-out section covering cost and billing exports, reservations and savings plans, support plans, Marketplace and third-party subscriptions, and closing the subscription; each item is a step for a person, and it states no refund limit, fee or amount that was not read from Microsoft's documentation in this run."
    _on_failure: _halt_and_inform
  - _assert: "no Azure CLI or PowerShell command that deletes, purges, stops, deallocates, or cancels anything appears anywhere in decommission-plan.md, and no script was written. Every step is phrased for a person to carry out in the Azure portal or CLI and confirm."
    _on_failure: _halt_and_inform
_forbids_files:
  - azure-resource-inventory.json
  - azure-resource-clusters.json
  - ai-workload-profile.json
  - preferences.json
  - aws-design.json
  - aws-design-ai.json
  - estimation-infra.json
  - estimation-ai.json
  - MIGRATION_GUIDE.md
  - migration-report.html
  - terraform/
  - ai-migration/
  - "*.sh"
  - "*.ps1"
---

# Phase 6: Plan the Azure Decommission (Optional)

## Orientation

Plan how the Azure estate is shut down once the AWS environment has taken over:
for each source resource, how long to keep it, what data to keep or export first,
and in which order to delete it, plus how to close the Azure bill. The output is
`$MIGRATION_DIR/decommission-plan.md`, a checklist for a person.

This phase is opt-in. SKILL.md § Decommission routing offers it once Generate has
completed; a declined offer marks `phases.decommission` as `"skipped"` and the run
completes without loading this file.

## This phase advises; it never acts on Azure

The skill's access to the source cloud is read-only and consent-gated, and this phase
keeps it that way. It reads only the run's artifacts in `$MIGRATION_DIR` and runs no
`az` command. It writes no Azure CLI or PowerShell command that deletes, purges, stops,
deallocates or cancels anything, and no script: every step in the plan names the
resource, the check that must pass first, and leaves the action to a person in the
Azure portal or CLI. The `_forbids_files` and the last postcondition hold this.

## Inputs by track

- **Infra track** (`azure-resource-inventory.json` exists): the source resources are
  its `resources[]`. Their `edges[]` and `azure_id` containment give the dependency
  order; `azure-resource-clusters.json` gives the tier; `aws-design.json` names the
  AWS target that replaces each one; `MIGRATION_GUIDE.md` holds the cutover steps
  the rollback window protects.
- **AI-only track** (no inventory): the source resources are the
  `ai-workload-profile.json` `infrastructure[]` entries (Azure OpenAI accounts and
  deployments, AI Search, Machine Learning workspaces), plus the direct provider
  account (OpenAI, Anthropic) when `summary.ai_source` names one, whose API keys are
  retired after cutover; `aws-design-ai.json` names the Bedrock target.

## Step: Run the phase

1. Verify the entry gate.
2. **Ask for the two dates the plan is built on, in one message.** The repository
   has no Azure rollback-window default, so none is applied:

   ```
   To schedule the Azure shutdown I need two things:

   1. Your planned (or actual) cutover date to AWS (YYYY-MM-DD)
   2. How long to keep Azure running after cutover as your rollback
      window (for example "14 days")
   ```

   Do not continue until both are answered. If the user does not know the cutover
   date yet, stop here and say the plan can be made later by asking for it; leave
   `phases.decommission` as `"in_progress"` so a resume asks again. Keep-until is
   the cutover date plus the rollback window.
3. Run `decommission-resources.md` and `decommission-billing.md`, passing them the
   cutover date, the rollback window and the keep-until date.
4. Run `decommission-assemble.md`.
5. Evaluate `_postconditions`. On all-pass emit `HANDOFF_OK` and advance to
   `complete`; on any failure emit `GATE_FAIL` and stop.
6. Tell the user where the plan is, that nothing in Azure was changed, and that the
   first deletion step should wait until the keep-until date and the plan's
   pre-deletion checks pass. Then apply SKILL.md § Sidebar Placement "After Generate".
