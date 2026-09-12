# Penske CX Copilot — Synthetic Demo Data

This package contains fictional data for an internal CX Copilot demonstration. It contains no real Penske, customer, employee, or operational data.

## Structured datasets

- `customers.csv`: fictional customer profiles
- `vehicles.csv`: vehicle and operational status
- `contracts.csv`: rental/lease relationships
- `invoices.csv`: billing transactions
- `payments.csv`: payment activity
- `service_records.csv`: vehicle maintenance history
- `cases.csv`: CX complaints and inquiries
- `case_interactions.csv`: historical touchpoints

## Knowledge documents

- `policies/billing_adjustment_policy.md`
- `policies/duplicate_charge_policy.md`
- `policies/maintenance_downtime_policy.md`
- `policies/escalation_and_approval_policy.md`

## Demo cases

| Case | Scenario | Expected direction |
|---|---|---|
| CASE-3021 | Maintenance downtime overlaps billing | Prorated adjustment; manager approval |
| CASE-3022 | Duplicate invoice charge | Full reversal of duplicate |
| CASE-3023 | Valid recurring charge | Explain charge; no adjustment |
| CASE-3024 | Payment not reflected | Trace payment before collection action |
| CASE-3025 | Roadside delay and repeat contact | Escalate for service review |

All identifiers and values are deliberately synthetic.
