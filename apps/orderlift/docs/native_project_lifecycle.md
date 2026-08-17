# Native Project Lifecycle

## Authoritative fields

- `Sales Order.project` is the only Project link used by Orderlift runtime code.
- `Project.project_type` and native `Project Type` records define Project types.
- `Opportunity.custom_project_type` is a configurable Link to `Project Type` and is copied to new Projects.
- `Project.custom_source_opportunity` identifies the one source Opportunity for lifecycle automation.

## Migration safety

`orderlift.patches.v1_0.migrate_native_project_lifecycle` runs before model sync. It creates missing historical `Project Type` records, copies empty native values, and refuses conflicting Sales Order Project links or conflicting Opportunity type values.

Run its diagnostics without changing data:

```bash
bench --site <site> execute orderlift.patches.v1_0.migrate_native_project_lifecycle.run
```

The post-model retirement patch removes `Sales Order.custom_installation_project` only after every legacy value is represented by `Sales Order.project`. It also refuses retirement while any blank native Project type still needs migration. Legacy Project type fields are removed when migration is lossless; a differing Project historical type is retained hidden and read-only rather than discarded.

## Opportunity stages

Status Control exposes `Auto create Project` only for Opportunity Sales Stages. After all configured required checks pass, moving an Opportunity to such a stage:

- locks the Opportunity row to serialize concurrent moves;
- re-runs required checks only after taking that lock;
- rejects multiple or ambiguous source Projects and Sales Orders, including mixed header/Quotation lineage;
- creates or reuses one Project;
- copies company, customer, CRM classification, party/site context, and native Project Type;
- preflights write permission, company access, customer/company consistency, and exclusive Opportunity lineage for every affected Sales Order;
- links every non-cancelled related Sales Order through native `project`, whether its source is the direct Opportunity field or a Quotation item;
- preserves the target Sales Stage and existing auto-close behavior.

The submitted-order link is a narrow system operation because native Project must also be updated on submitted Sales Orders. It runs only after all affected orders pass the preflight above; inaccessible or inconsistent families fail without partial fan-out.

The `Has submitted payment` Opportunity check accepts a submitted Payment Entry only when it is a customer `Receive` entry with a positive allocation to a related Sales Order or related Sales Invoice. Supplier payments, customer refunds (`Pay`), zero allocations, negative return allocations, drafts, and cancellations do not satisfy it.

Cancellation checks inspect cancelled linked Quotations and Sales Orders. Normal attachment, presence, delivery, billing, and Project fan-out logic continues to use only non-cancelled documents.

Future Sales Orders from the same Opportunity are linked by the Sales Order validation hook. Sales Order statuses never trigger Project creation.

## Orders Pipeline

The Sales Order Pipeline queries permission-visible, non-cancelled Sales Orders whose native `project` is empty. This condition is applied in `frappe.get_list` before the 200-row limit, regardless of CRM Business Type or Project Type.
