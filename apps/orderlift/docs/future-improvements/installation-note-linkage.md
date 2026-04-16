# Installation Note Linkage

## Overview

`Installation Note` exists natively in ERPNext and is available on the live site. It is not currently integrated into Orderlift's custom installation and after-sales flow.

Today, Orderlift's main installation / support flow is centered on:

- `Sales Order`
- `Delivery Note`
- `Project`
- `SAV Ticket`
- SIG project QC (`Installation QC Item` on `Project`)

`Installation Note` is therefore present, but currently acts as an isolated native document rather than a first-class part of the custom flow.

## Current State

### Native `Installation Note`

Confirmed on the live site:

- DocType: `Installation Note`
- Module: `Selling`
- Submittable: yes

Relevant native fields:

- `customer`
- `company`
- `project`

Relevant child-table fields on `Installation Note Item`:

- `item_code`
- `serial_and_batch_bundle`
- `prevdoc_docname`
- `prevdoc_doctype`

### Orderlift Custom Flow

Current custom flow already links:

- `Sales Order.custom_installation_project` -> `Project`
- `SAV Ticket.installation_project` -> `Project`
- `SAV Ticket.sales_order` -> `Sales Order`
- `SAV Ticket.delivery_note` -> `Delivery Note`
- `SAV Ticket.sales_invoice` -> `Sales Invoice`

What is missing:

- no `installation_note` link on `SAV Ticket`
- no auto-fill from `Installation Note`
- no explicit `Installation Note` references in Orderlift custom code
- no operations pipeline mapping for `Installation Note`

## Why It Matters

`Installation Note` adds one thing the current flow does not capture cleanly on its own: proof of installation execution.

That makes it useful for:

- install date traceability
- distinguishing delivery issues vs installation issues
- post-install SAV context
- warranty start logic
- project closure evidence

## Recommended Future Positioning

Use the documents like this:

- `Project` = installation umbrella / execution container
- `Installation Note` = proof that installation happened
- `SAV Ticket` = issue / complaint / after-sales case

This keeps responsibilities clean:

- project tracks execution and QC
- installation note records the field installation act
- SAV tracks defects, complaints, and interventions after or during installation

## Recommended Future Implementation

### Phase 1 — Link `Installation Note` to SAV

Add a new optional Link field on `SAV Ticket`:

- `installation_note` -> `Installation Note`

Use it primarily for:

- installation defect tickets
- post-install complaints
- warranty/install-date derivation

### Phase 2 — Auto-fill From `Installation Note`

When a user selects `installation_note` on `SAV Ticket`, auto-fill:

- `customer`
- `installation_project`
- install date
- item / serial context where available
- possibly site / address context

### Phase 3 — Add To Operations / Link Graph

Extend the operations pipeline / linkage map so `Installation Note` can be traversed alongside:

- `Sales Order`
- `Delivery Note`
- `Project`
- `SAV Ticket`

### Phase 4 — Dashboard / Analytics

Once data volume exists, use `Installation Note` for:

- install-to-SAV recurrence timing
- post-install defect rate
- time from delivery to installation
- time from installation to first SAV complaint

## Implementation Priority

This should not outrank the current core links:

1. `Project`
2. `Serial No`
3. `Delivery Note`
4. `Sales Invoice`

But it is important enough to include as a secondary core link because it closes the gap between:

- shipped
- installed
- supported after installation

## Suggested Rules

- keep `installation_note` optional globally
- strongly recommend it for installation-related SAV
- consider making it required later for `Installation Defect` only, if process maturity justifies it

## Related Files For Future Work

| File | Purpose |
|------|---------|
| `orderlift_sav/doctype/sav_ticket/sav_ticket.json` | Add `installation_note` link field |
| `orderlift_sav/doctype/sav_ticket/auto_fill.py` | Add `Installation Note` cascade resolution |
| `orderlift_sav/doctype/sav_ticket/sav_ticket.py` | Add validation / derived-field logic |
| `orderlift_logistics/page/operations_pipeline/operations_pipeline.py` | Add `Installation Note` graph mapping |
| `orderlift_sav/page/sav_dashboard/sav_dashboard.py` | Future post-install analytics |
