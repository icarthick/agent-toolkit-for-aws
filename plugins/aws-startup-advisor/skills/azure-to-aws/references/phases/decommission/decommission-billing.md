---
_fragment: billing
_of_phase: decommission
_contributes:
  - decommission-plan.md (Billing close-out section)
---

# Decommission — Billing Close-out

> **Fragment unit.** See `decommission.md` for how it is composed into the phase.

Builds the checklist that closes the Azure bill after the last resource is gone.
It reads the run's artifacts only and runs nothing against Azure.

## Terms change; the plan points to them

Microsoft sets and changes the terms for cancelling reservations and support plans
(refund limits, fees, notice periods). This repository holds none of them, so the
plan states no limit, fee or amount. Each item tells the person to read the current
terms in the Azure portal or Microsoft Learn before acting. Write a number only if
it was read from Microsoft's documentation in this run, and cite where it came from.

## The checklist

Write each item as a step for a person, with what to confirm when it is done:

1. **Export cost and billing data** before access ends: the invoices and the cost
   history you need for records, audit or the AWS cost comparison. Confirm the export
   files open and cover the whole period.
2. **Reservations and savings plans**: list every reservation and savings plan on
   the billing account. For each, read the current cancel, exchange and refund terms
   and decide whether to cancel, exchange or let it run out. A commitment can keep
   billing after the resources it covered are deleted.
3. **Support plan**: decide when to cancel it. Keep it until the last deletion step
   is done if you may need Microsoft support during the shutdown.
4. **Marketplace and third-party subscriptions** bought through Azure (SaaS offers,
   licenses): cancel each with its publisher's terms in mind.
5. **Spending, budgets and alerts**: keep cost alerts on until the bill reaches
   zero, so a forgotten resource shows up.
6. **Close the subscription**, after one full billing period with no charges, by
   following Microsoft's current subscription cancellation steps. Note any retention
   period during which data can still be recovered.
7. **Access**: remove the people, service principals and credentials that existed
   only for the Azure estate, last, once nothing above needs them.

When `preferences.json` or the inventory records an Azure licensing posture (Hybrid
Benefit, Windows or SQL Server licenses), add an item to review where those licenses
go next under their own terms; do not state an outcome.

## Contribution

Contribute the Billing close-out items above, adapted to what the run's artifacts
show, to the assembler.
