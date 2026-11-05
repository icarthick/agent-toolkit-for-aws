# Workshop Scenarios — Artifact Contract (Azure)

Contract for the workshop sidebar's scenario store. `workshop-refresh.md` writes the
snapshots and manifests; `workshop-assemble.md` is the single creator of the index.
The cross-skill invariants that govern the workshop itself live in
`references/vendored/workshop/workshop-invariants.md` and win on any disagreement
with this file.

## Directory layout

```
$MIGRATION_DIR/
├── azure-resource-inventory.json   # FROZEN
├── preferences.json                # active scenario preferences
├── aws-design.json                 # active scenario design
├── estimation-infra.json           # active scenario estimate
└── scenarios/
    ├── index.json
    ├── scenario-001.json
    ├── scenario-001.preferences.json
    ├── scenario-001.aws-design.json
    ├── scenario-001.estimation-infra.json
    └── …
```

Max **5** scenarios — beyond that the comparison stops informing a decision. Warn
and name the oldest non-baseline scenario before evicting it.

## `scenarios/index.json`

```jsonc
{
  "baseline_scenario_id": "scenario-001",
  "active_scenario_id": "scenario-001", // workshop-refresh.md sets this to the snapshot Apply/resume is on; equals baseline at capture
  "max_scenarios": 5, // the five-scenario cap from the shared workshop invariants
  "inventory_fingerprint": "<sha256 hex of azure-resource-inventory.json>", // frozen at baseline capture; refresh aborts when the inventory bytes change
  "scenarios": [
    {
      "scenario_id": "scenario-001",
      "label": "baseline",
      "created_at": "<ISO 8601>",
      "source": "baseline",
      "manifest": "scenarios/scenario-001.json"
    }
  ]
}
```

Use these full field names in capture, refresh, compare, and the report. Both
selected IDs must identify a listed scenario, the baseline stays listed, and IDs are
unique. Costs and knobs live in each entry's manifest, not in the index.

## `scenarios/scenario-NNN.json` (manifest)

```jsonc
{
  "scenario_id": "scenario-002", // REQUIRED
  "label": "single-az, Elastic Beanstalk",
  "created_at": "<ISO 8601>",
  "source": "baseline|workshop", // REQUIRED
  "preferences_subset": {
    "data.availability.value": "single-az",
    "design_constraints.compute_target.value": "elastic_beanstalk"
  },
  "preferences_fingerprint": "<sha256 of saved preferences bytes>",
  "aws_design_fingerprint": "<sha256 of saved design bytes>",
  "estimation_summary": { // REQUIRED
    "aws_monthly_premium": 0, // REQUIRED
    "aws_monthly_balanced": 0, // REQUIRED
    "aws_monthly_optimized": 0, // REQUIRED
    "complexity_tier": "small|medium|large", // REQUIRED
    "pricing_source": "cached|cached_stale|cached_fallback|unavailable", // REQUIRED
    "region_note": null,
    "calculator_url": null,
    "recommendation_outcome": "go|conditional_go|defer_for_evidence|stay"
  },
  "paths": { // REQUIRED
    "preferences": "scenarios/scenario-002.preferences.json",
    "aws_design": "scenarios/scenario-002.aws-design.json",
    "estimation_infra": "scenarios/scenario-002.estimation-infra.json"
  },
  "stale": false,
  "stale_reason": null,
  "corrected_at_gate": null
}
```

- **`source`** is `baseline` for the original capture and `workshop` for later applies.
- **`preferences_subset` records only the delta**: the knob paths (from
  `workshop-sheet.md`) that differ from the baseline, not a whole preferences file.
  The complete preferences live in the snapshot at `paths.preferences`.
- **`estimation_summary`** carries the three Premium/Balanced/Optimized monthly tiers
  from `estimation-infra.json` (`estimate-infra.md` § Part 2E — Balanced is the
  anchor), its `complexity_tier`, and `pricing_source` copied from the estimate's
  `pricing_source.status`. Pricing is cache-only, so a scenario repriced after a
  region change carries a `region_note` and is presented as approximate.
  `calculator_url` is always `null`: no shareable calculator link is produced.
  `recommendation_outcome` is a copy of the inner estimate's `recommendation.outcome`
  when it wrote one; omit it or set it `null` otherwise.
- The fingerprints and `region_note` are optional. When supplied, hash the saved
  bytes, not reserialized JSON. Each path must exist and point to the matching
  scenario's complete artifact.

## Manifest fields written outside the sidebar

Three per-scenario manifest fields are owned by `estimate-assemble.md` § Scenario
reconciliation, not by the workshop. They exist because a decision-gate correction or
a Step 3b cutover answer can re-price the working tree **after** scenarios were saved,
and `workshop-invariants.md` § 4 requires the working artifacts to match the active
scenario.

| Field               | Type             | Written when                                                                                                          |
| ------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------- |
| `stale`             | boolean          | `true` on every non-active scenario after a gate-side write **changed the estimate**; `false` (or absent) otherwise — a provenance-only write (an unchanged Step 3b answer) leaves it alone |
| `stale_reason`      | string or `null` | with `stale: true` — which row changed at the decision gate and that this scenario was priced before it                                                                                     |
| `corrected_at_gate` | string or `null` | on the active scenario, the dotted key of the row the gate corrected or confirmed (Step 3b, changed or not); its snapshot copies were overwritten in place                                   |

The sidebar never sets these. A new snapshot starts with `stale: false` and the other
two `null`. `workshop-compare.md` suffixes `(stale)` to a stale row and the report's
what-if table labels it; neither re-prices it — the next sidebar Apply snapshots a
fresh scenario against the corrected working tree.

## Status — implemented

The shapes above are the contract. The knob set, reprice, and comparison
rendering are in `references/phases/workshop/`.
