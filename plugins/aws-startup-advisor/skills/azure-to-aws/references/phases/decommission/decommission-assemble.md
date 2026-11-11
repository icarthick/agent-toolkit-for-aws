---
_assemble: assemble-decommission
_of_phase: decommission
_reads:
  - resources (fragment contribution)
  - billing (fragment contribution)
_produces:
  - decommission-plan.md
---

# Decommission — Assemble

> **Assembler unit.** The single creator of `decommission-plan.md`. See
> `decommission.md` for how it is composed into the phase.

## Step 1: Write the plan

Write `$MIGRATION_DIR/decommission-plan.md` with these sections, in order:

1. **Title and status line**: "Azure decommission plan — a checklist for a person
   to carry out. Nothing in Azure has been changed."
2. **Dates**: the cutover date and rollback window as the user gave them, and the
   keep-until date they give.
3. **Before you start**: the AWS environment is serving all traffic, the
   verification steps in `MIGRATION_GUIDE.md` have passed (infra track), and the
   keep-until date has passed.
4. **Schedule**: one table, one row per source resource, sorted by step number:

   | Step | Resource | Type | Resource group | Depends on | AWS replacement | Keep until | Data to retain or export | Check before deleting |
   | ---- | -------- | ---- | -------------- | ---------- | --------------- | ---------- | ------------------------ | --------------------- |

   On the AI-only track the resource group column may read `n/a` for a direct
   provider account.
5. **Data to keep**: the exports from the schedule gathered in one list, with where
   each copy will be kept and for how long, as the user's retention duties require.
6. **Billing close-out**: the billing fragment's checklist.
7. **Could not derive**: resources whose order or data could not be derived, with
   the reason, or "None".

## Step 2: Check the plan before the gate

Re-read the written file and confirm, fixing the plan (never the inputs) if any fails:

- the schedule has exactly one row per source resource the resources fragment listed;
- every row's step number is lower than the step of each resource in its "Depends
  on" column, so a resource's dependants are deleted before it (resources in one
  cycle share a step);
- no line, code span or code block holds an Azure CLI or PowerShell command that
  deletes, purges, stops, deallocates or cancels anything. Rewrite any such line as a
  step for a person;
- no secret value, connection string or key appears.
