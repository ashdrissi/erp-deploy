# Sales Order Technical Lists

## Purpose

Sales Order Technical Lists separate the commercial Sales Order from the approved execution definition used for procurement. Each submitted Sales Order has one stable Technical List and any number of immutable submitted revisions.

New procurement uses only the current submitted revision. Existing Material Requests and Purchase Orders keep their exact historical revision and line references.

## Activation

The feature is disabled by default. Configure it on the `Technical Lists` tab of each Company:

1. Enable `Enable Sales Order Technical Lists`.
2. Set an effective date so older Sales Orders keep their existing flow.
3. Select `Apply to All Business Types` or add explicit `CRM Business Type` rows.
4. Decide whether a Project is required and whether drafts are created automatically.
5. Save the Company. Internal editing rules and the standard Material Request route are applied automatically.

The client-facing Company tab does not expose route, editing-rule, stock-planning, or delivery switches. Internally, design additions, source exclusions, change reasons, and non-stock/service items are enabled. The standard route is `Approved Technical List to Material Request`.

No company name or business-type label is interpreted by application code.

## Annex Chain

The `Fiches annexes` phase-based workspace extends the revision annex model across the whole commercial chain. Each of `Quotation`, `Sales Order`, `Sales Order Technical List Revision`, and `Project` has one `Fiches annexes` tab with compact internal phase tabs and source filters; Technical Lists remain optional and their phases only appear for configured Companies.

Phase ownership and lifecycle:

- `Opportunity` annexes are shared CRM sources. Each draft `Quotation` keeps automatically synchronized `Opportunity Snapshot` copies, and a draft Quotation's CRM phase edits the live Opportunity annexes.
- Submitting one Quotation freezes only its own snapshots; other draft Quotations keep synchronizing.
- `Sales Order` shows frozen `Opportunity Snapshot` and source Quotation annexes read-only and owns separate direct annexes, frozen on submission.
- `Sales Order Technical List Revision` shows upstream phases read-only and owns editable execution copies plus technical-specific annexes, frozen on submission. New revisions inherit previous execution copies.
- `Project` shows CRM, Quotation, Sales Order, and current Technical Revision phases read-only and owns its Project annexes.

Freeze semantics: an annex is content-frozen with a canonical content hash when its owner is submitted; the submission hook locks the owning document row, so concurrent saves cannot insert or mutate unfrozen annexes after the freeze. Synchronized snapshot origins are immutable from the API and only the configured lifecycle writes them. Imported execution copies are independent drafts with preserved provenance, snapshot definition, values, and physically copied attachments.

## Annex Configuration

Document Template targets are dynamic DocType links. To import a CRM annex from the Sales Order, configure the same template for both `Sales Order` and `Sales Order Technical List Revision`, then enable `Allow Execution Copy from Upstream` on the revision target.

Target documents are limited to the core business chain: `Opportunity`, `Quotation`, `Sales Order`, `Project`, `Forecast Load Plan`, and `Sales Order Technical List Revision`.

For a technical-only annex, target only `Sales Order Technical List Revision` and enable `Allow Direct Creation`.

Target metadata controls:

- Allow Direct Creation — the annex can be created and edited directly on this document.
- Allow Execution Copy from Upstream — an upstream Quotation or Sales Order annex can be copied into a revision as an editable execution copy.
- Required for Revision — the revision cannot be submitted without this annex.
- Must Be Complete — the annex must be fully completed before the revision can be submitted.
- Selected by Default — the annex is created or copied automatically when a new revision is initialized.
- Display Order

Change reasons on modified, added, or excluded item rows are optional by default and can be required per Company with `custom_technical_list_require_change_reason`.

Template statuses use `Complete`; the runtime never compares status labels. Required fields are enforced server-side when an annex enters a complete status.

Imported annexes are independent draft snapshots. Their source annex, source timestamp, template definition, values, and referenced files are preserved without changing the CRM annex.

## Operator Safety

The standalone `Orderlift Annex Document` list is deliberately hidden for business users: annexes are reached through their permission-checked parent workspaces. Deleting a submitted or synchronized annex is blocked by the annex integrity guard. A parent submission and concurrent annex saves are serialized with a row lock on the owning document.

## Workflow

`Sales Order Technical List Revision` is submittable and uses native Frappe Workflow configuration. Approval authority comes from DocPerm and Workflow transitions, not role names in feature code.

The procurement gate uses three semantic facts only:

- revision `docstatus` is submitted;
- revision is the Technical List's `current_revision`;
- approval hash still matches its immutable content.

Submitting a newer revision makes it current. Earlier submitted revisions stay available for historical procurement traceability.

## Procurement Routes

Safe adapter actions are installed for:

- Technical Revision to Material Request
- Technical Revision to Purchase Order

Administrators assemble enabled `Technical Procurement Action` rows into ordered `Technical Procurement Route` records. Routes and labels are configurable; arbitrary Python methods are not accepted.

Normal users do not configure routes. Every Company receives the internal Material Request route automatically. The native Sales Order Create menu stays visible, but scoped companies require a current submitted Technical List before operational documents can proceed. Material Requests are created from the approved revision; direct PO/RFQ creation is redirected to the MR-first flow. Native Pick List and Delivery Note creation is permitted only after approval. Sales Invoice and payment flows remain tied directly to the Sales Order and are not gated.

Generated transactions are always drafts. Native MR, RFQ, Supplier Quotation, and PO workflows remain responsible for their own approval and submission.

Every sourced procurement row carries:

- Technical List
- Technical Revision
- Technical Revision Item
- Stable Technical Line Key
- Approval Hash
- Procurement Route and Action

The same server guard validates Desk, API, Data Import, native mappings, and background inserts. Procurement outside an enabled Company's configured scope remains unchanged.

## User Interfaces

- `Technical List Manager` lists permission-visible submitted Sales Orders, including missing lists.
- `Sales Order > Technical List` is read-only and shows the active revision's item quantities, variances, warehouse, required date, annex statuses, and actions.
- `Project > Technical Lists` aggregates every linked Sales Order Technical List with its execution items and annex statuses.
- The revision form owns editing, annexes, Workflow actions, submission, and procurement actions.
- `Technical Annexes` opens the copied Sales Order annex snapshots and Technical List-specific templates. Draft revision annexes are editable; submitted revision annexes are read-only. The Project view exposes both Project annexes and each linked Technical List's annex popup.
- Every chain document uses the compact `Fiches annexes` tab: `View`/`Edit` opens the exact annex in the existing popup editor, and saving a revision-owned annex refreshes the revision's manifest and readiness state.

## Rollout Safety

Enable one Company only after its applicability, annex templates, DocPerm, Workflow, and procurement route are configured. Use the effective date to avoid retroactively blocking historical Sales Orders.
