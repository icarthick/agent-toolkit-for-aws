---
_fragment: resources
_of_phase: decommission
_contributes:
  - decommission-plan.md (Schedule table and Data to keep section)
---

# Decommission — Resources

> **Fragment unit.** See `decommission.md` for how it is composed into the phase.

Builds one schedule row per source resource: when it may go, what must be kept or
exported first, and its place in the deletion order. It reads the run's artifacts
only and runs nothing against Azure.

## Step 1: List the source resources

- **Infra track:** every `resources[]` entry of `azure-resource-inventory.json`, keyed
  by `azure_id`. Include resources Design skipped or deferred (monitoring, diagnostic
  settings, role assignments): they still exist in Azure and still bill or hold access.
- **AI-only track:** every `infrastructure[]` entry of `ai-workload-profile.json`, plus
  one row for the direct provider account when `summary.ai_source` is `openai`,
  `anthropic` or `both` (its API keys are retired once traffic runs on Bedrock).

Name each row by its `name` and ARM type (`azure_type`, or `type` on the AI track).
Do not copy a full `azure_id` into the plan when a name and resource group identify
the resource; the plan is meant to be shared with the people who carry it out.

## Step 2: Keep-until

Every row's keep-until is the cutover date plus the rollback window the user gave
in `decommission.md` step 2. Use a later date only for a stated reason, and write
the reason in the row:

- a resource that is the failback target for data (the source database, storage
  that receives writes) stays until the post-cutover data check in
  `MIGRATION_GUIDE.md` has passed and the final export is verified;
- DNS zones and records stay until every client resolves the AWS endpoints.

## Step 3: Data to retain or export

For each row, state what must be kept before deletion, or `none` with the reason.
Use the resource's role, not its name:

| Resource role                                                   | Keep or export before deletion                                                                                                    |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Database (Flexible Server, Azure SQL, Cosmos DB)                | a final backup or export taken after writes stopped on Azure, and a row-count or checksum comparison against the AWS copy         |
| Storage account, file share, container registry                 | confirm the AWS copy is complete; keep an archive of anything not migrated that a retention policy or contract requires          |
| Key Vault                                                       | confirm every secret, key and certificate the AWS side needs now lives in AWS; record what was retired. Never copy secret VALUES into the plan |
| Log Analytics, Application Insights, activity and audit logs    | export what your compliance or audit duty requires before the workspace or subscription goes                                      |
| Compute (App Service, AKS, VMs, Functions)                      | usually none: the code and images live in source control or a registry. Keep VM disk snapshots only if a rollback needs them      |
| Network, identity, role assignments                             | none, after confirming nothing on AWS still reaches Azure through them (VPN, private endpoints, managed identities)               |
| Azure OpenAI / AI Search / Machine Learning                     | fine-tuning data, prompt flows, indexes and evaluation sets you still need; usage history if it backs a cost comparison           |
| Direct provider account (OpenAI, Anthropic)                     | usage exports for the cost comparison; then revoke the API keys the application used                                             |

## Step 4: Deletion order, dependants first

Number the rows so that a resource is deleted only after everything that depends on
it is gone:

1. Derive dependencies from the inventory: an `edges[]` entry from A `to` B means A
   depends on B, and a child `azure_id` (one that has another resource's `azure_id` as
   its prefix) depends on that parent.
2. Order by the reverse of those dependencies: edge and front-door resources and
   compute first, then data, then network, identity and secrets, then resource groups
   last. Use `azure-resource-clusters.json` tiers to break ties (edge, compute, data,
   network_identity_secrets), the reverse of the order Generate built AWS in.
3. Resources with no edges sort by that tier order.
4. If the edges form a cycle, put the resources in the same step and say so.
5. On the AI-only track, order is application traffic switched, then the provider
   account's keys revoked, then deployments, then the accounts that held them.

Give each row its pre-deletion check: the AWS replacement from `aws-design.json` (or
`aws-design-ai.json`) is serving, its data check passed, and the keep-until date has
passed. Write the action as a step for a person, for example "Delete the App Service
`<name>` in the portal or CLI once the checks above pass, then confirm it no longer
appears in its resource group". Never write the command.

## Contribution

Contribute to the assembler:

- the cutover date, rollback window and keep-until date;
- the schedule rows: step number, resource name, type, resource group, depends on,
  AWS replacement, keep-until, data to retain or export, pre-deletion check;
- any resource whose order or data could not be derived, with the reason.
