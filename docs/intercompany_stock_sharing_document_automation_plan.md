# Inter-Company Stock Sharing and Document Automation Plan

## 1. Core Business Model

A source company shares commercial data with another company.

```text
Seller Company B
- Owns the source Selling Price List
- Owns physical stock
- Decides whether stock is visible
- Defines document automation

Buyer Company A
- Receives a synchronized Buying Price List
- Uses it in the Pricing Builder
- Generates its own Selling Price List
- Sees shared stock when preparing Quotations
- Submits internal Purchase Orders to Company B
```

The `Price List Sharing` row is the control point for both:

- Stock visibility.
- Inter-company document automation.

# Part A: Stock Sharing

## 2. Stock-Sharing Configuration

Add to each `Price List Sharing` row:

| Field | Purpose |
|---|---|
| Share Stock Availability | Allow the target company to see source-company availability |
| Stock Sharing Status | Ready, Disabled, or Configuration Required |
| Last Stock Check | Last successful availability lookup |
| Stock Sharing Message | Readiness or error information |

Default `Share Stock Availability` to disabled.

The source company remains in control. Disabling the option immediately stops new live stock lookups.

## 3. Eligible Warehouses

Do not automatically expose every warehouse because transit, rejected, QC, or internal warehouses may not represent sellable stock.

Add a Warehouse setting:

```text
Allow Intercompany Stock Sharing
```

Only warehouses meeting all conditions are included:

- Belong to the source company.
- Enabled.
- Not a group.
- Explicitly allowed for inter-company stock sharing.

This is configured once on Warehouse. The Price List Sharing row remains simple.

The target company does not see warehouse names. It sees only the aggregated availability.

## 4. Available Stock Calculation

Use:

```text
Available Shared Stock
=
sum(max(actual_qty - reserved_stock, 0))
```

Calculate this independently for each eligible warehouse.

`reserved_stock` represents hard physical reservations created through Stock Reservation Entries.

Do not deduct ordinary unallocated Sales Order demand. That demand has not yet physically reserved stock.

Do not expose:

- Valuation.
- Cost.
- Stock ledger.
- Batch details.
- Serial numbers.
- Warehouse names.
- Other items outside the shared pricing relationship.

## 5. Item Eligibility

Company A may see Company B's stock only when the Quotation Item is traceable to the sharing relationship.

Resolution:

```text
Quotation Item
-> Company A Selling Item Price
-> Source Buying Price List
-> Shared Buying Price List
-> Price List Sharing row
-> Company B source Selling Price List
-> Company B shared stock
```

Use existing provenance fields such as:

- `Price List.custom_source_buying_price_lists`
- `Item Price.custom_source_buying_price_list`
- `Price List.custom_is_shared_from`
- `Item Price.custom_is_shared_from`

The item must also have an active price in the original source list.

An unrelated quotation containing the same Item must not receive shared stock visibility.

## 6. Multiple Source Companies

Resolve shared stock per Quotation Item.

Example:

| Item | Price Source | Shared Stock Source |
|---|---|---|
| Motor | Distribution buying list | Distribution |
| Door | Turkey buying list | Turkey |
| Installation service | Internal pricing | None |

Do not combine stock from multiple companies unless the line has one explicit and unambiguous source.

If provenance is ambiguous, show:

```text
Shared Stock Source Unavailable
```

Do not guess.

## 7. Quotation Display

The Quotation already records current-company stock. Keep that unchanged and add separate shared-stock fields.

### Quotation Item fields

- Shared Available Stock.
- Shared Stock Source Company.
- Shared Stock Status.
- Shared Stock Checked On.

Recommended display:

```text
Own Company Stock: 2
Shared Available Stock: 8
Source: Orderlift Maroc Distribution
Checked: 05/08/2026 14:32
Status: Available
```

### Availability statuses

| Status | Meaning |
|---|---|
| Available | Shared quantity covers the quoted quantity |
| Partially Available | Some quantity is available |
| Out of Stock | No shared quantity is available |
| Stock Not Shared | Source company disabled visibility |
| Source Unavailable | Price provenance could not be resolved |
| Configuration Required | No eligible source warehouses |
| Check Failed | A temporary lookup error occurred |

Availability is informational. It must not block Quotation saving or submission by default.

## 8. Stock Refresh Behavior

Refresh shared stock:

- When an item is added.
- When the selected price source changes.
- When the Quotation company changes.
- Before saving a draft Quotation.
- Through a `Refresh Stock Availability` button.

Persist the result as a point-in-time snapshot.

Do not silently refresh submitted Quotations. Submitted documents retain their historical snapshot.

The UI should explain:

> Availability is informational and does not reserve stock. Stock is reserved only after Sales Order confirmation and Pick List submission.

## 9. Shared-Stock Security

Implement a dedicated server service, not a generic cross-company stock API.

The server must derive access from:

- The Quotation company.
- The Quotation Item's price provenance.
- The active Price List Sharing row.
- The target company on that sharing row.
- The stock-sharing checkbox.
- The source company's eligible warehouses.

The service returns only:

- Item code.
- Aggregated available quantity.
- Source company.
- Status.
- Check timestamp.

The requesting user does not need direct permission to Company B's warehouses or Bin records. The explicit sharing relationship grants only this restricted aggregate view.

# Part B: Inter-Company Document Automation

## 10. Automation Configuration

Add these options to each `Price List Sharing` row:

### Internal Sales Order

- Create Sales Order automatically.
- Submit Sales Order automatically.

### Procurement

- Create Material Request automatically.
- Submit Material Request automatically.
- Create supplier Purchase Order automatically.
- Submit supplier Purchase Order automatically.

### Fulfilment

- Create Pick List automatically.
- Submit Pick List automatically.

There is no separate reservation checkbox.

Submitting the Pick List already reserves stock through the merged Pick List/reservation implementation.

## 11. Configuration Dependencies

Enforce:

- Submit Sales Order requires Create Sales Order.
- Submit Material Request requires Create Material Request.
- Create supplier PO requires Create and Submit Material Request.
- Submit supplier PO requires Create supplier PO.
- Submit Pick List requires Create Pick List.
- Material Request and Pick List processing require a submitted Sales Order.
- All automation is disabled when the sharing row is inactive.
- Document automation requires a valid shared Buying Price List.
- Stock sharing remains independent from document automation.

The expanded sharing row should show a readable summary:

> Share stock availability. On buyer PO submission, create and submit the seller Sales Order, create a draft Material Request, and create a draft Pick List.

## 12. Automation Trigger

Start only when Company A submits its internal Purchase Order.

Do not generate downstream documents from draft PO saves.

The PO must use:

- An internal Supplier representing Company B.
- The synchronized Buying Price List from the sharing relationship.
- Items covered by that relationship.

After the PO commits, queue the automation in the background.

A downstream failure must not roll back the original PO submission.

## 13. Internal Party Readiness

Before activation, require:

### In Company A

- Internal Supplier representing Company B.
- Supplier enabled and allowed to transact with Company A.

### In Company B

- Internal Customer representing Company A.
- Customer enabled and allowed to transact with Company B.

Also validate:

- Matching currencies.
- Active source and shared Price Lists.
- Correct company ownership.
- Valid addresses and tax configuration.
- Correct items and UOMs.

Provide a dry-run/apply setup command for internal parties. Do not silently create accounting masters during migration.

## 14. Sales Order Generation

On Company A's submitted PO:

1. Resolve the active sharing row from the PO's primary mirrored Buying Price List.
2. Validate the internal Supplier and Customer relationship.
3. Create Company B's Sales Order.
4. Use Company B's original Selling Price List.
5. Copy exact PO items, quantities, UOMs, rates, and delivery dates.
6. Add native inter-company and source-row references.
7. Save as draft or submit according to configuration.

The generated SO may bypass the normal Quotation requirement only when all inter-company validations pass.

Normal manually-created Sales Orders remain subject to existing Quotation rules.

Internal Sales Orders must not generate normal sales commissions.

If the SO remains draft, downstream automation waits until a user submits it.

## 15. Material Request Generation

After the generated SO is submitted:

- Create a Purchase-type Material Request in Company B.
- Use only remaining quantities not already requested.
- Link every row to the Sales Order and Sales Order Item.
- Copy warehouse and schedule dates.
- Keep Material Request pricing fields empty.
- Save as draft or submit according to configuration.

If the MR remains draft, supplier PO automation waits for manual submission.

## 16. Supplier Purchase Order Generation

After the MR is submitted:

1. Resolve the company-specific default supplier for every Item.
2. Group items by supplier.
3. Create one PO per supplier.
4. Use the supplier's configured Buying Price List.
5. Run existing Orderlift PO pricing and approval validations.
6. Save or submit each PO according to configuration.

Do not guess when a supplier or buying price is missing.

Mark the step `Needs Attention` and report:

- Item.
- Missing supplier.
- Missing Buying Price List.
- Missing Item Price.
- Invalid UOM or currency.

Successful supplier POs remain valid even if another supplier group fails.

## 17. Pick List and Reservation

After the generated SO is submitted:

### Create only

- Create a draft Pick List.
- Resolve item locations through native ERPNext logic.
- Let warehouse staff review warehouses, batches, serials, and quantities.
- No stock reservation exists while the Pick List is draft.

### Create and submit

- Create the Pick List.
- Submit it.
- Existing `on_submit` hook automatically creates Stock Reservation Entries.
- Existing cancellation hook cancels those reservations when the Pick List is cancelled.

Automatic submission requires:

- Stock reservation enabled in Stock Settings.
- Valid source warehouses.
- Available stock.
- Valid batch and serial allocations where applicable.

If submission fails:

- Preserve the draft Pick List.
- Mark the step `Needs Attention`.
- Notify users with `stock_reservation_management`.
- Allow retry after review.

# Part C: Tracking and Operations

## 18. Intercompany Automation Run

Create one `Intercompany Automation Run` per submitted source PO.

Record:

- Source PO.
- Buyer company.
- Seller company.
- Source Selling Price List.
- Shared Buying Price List.
- Configuration snapshot.
- Generated documents.
- Triggered by.
- Start and completion timestamps.
- Overall status.
- Last error.
- Retry count.

Track steps separately:

- Sales Order.
- Material Request.
- Supplier Purchase Orders.
- Pick List.

Statuses:

- Queued.
- Running.
- Draft Created.
- Submitted.
- Waiting for User.
- Completed.
- Needs Attention.
- Failed.
- Skipped.

## 19. Failure and Retry

Retry must be idempotent.

Before creating anything:

- Lock the source PO/run.
- Check the automation record.
- Check native inter-company references.
- Check generated-document links.
- Reuse existing drafts.
- Never recreate submitted documents.

Independent branches continue independently.

Example:

```text
Sales Order: Submitted
Material Request: Submitted
Supplier PO: Needs Attention
Pick List: Submitted and Reserved
```

Fixing the supplier pricing and retrying should retry only the supplier PO step.

## 20. Cancellation

Do not automatically cascade-cancel submitted downstream documents.

When the source PO is cancelled:

- Mark the automation run as Source Cancelled.
- Show all generated documents.
- Notify responsible users.
- Require controlled cancellation through the normal document lifecycle.

Cancelling a Pick List continues to cancel its reservations automatically.

# Part D: Technical Implementation

## 21. Main Components

### Price List Sharing

Extend:

- `orderlift_sales/doctype/price_list_sharing/price_list_sharing.json`
- `orderlift_sales/doctype/price_list_sharing/price_list_sharing.py`
- Active Price List form script

Add stock-sharing and automation fields, dependency validation, summaries, and readiness checks.

### Warehouse

Add:

```text
custom_allow_intercompany_stock_sharing
```

Default it off.

### Shared Stock Service

Add a focused service to:

- Resolve Item Price provenance.
- Validate the sharing relationship.
- Query eligible source warehouses.
- Calculate available quantity.
- Return safe aggregate values.

### Quotation

Extend:

- `quotation_hooks.populate_quotation_stock_snapshot`
- Quotation custom fields.
- Quotation Item custom fields.
- Active Quotation client script.

Preserve current-company stock separately from shared stock.

### Automation Service

Add an orchestrator responsible for:

- PO submit queueing.
- SO mapping.
- MR generation.
- Supplier PO generation.
- Pick List generation.
- Step tracking.
- Retry and notifications.

### Validation Adjustments

Add narrowly-scoped handling for:

- Cross-company transaction creation.
- Inter-company SO without Quotation.
- Source selling vs mirrored buying Price Lists.
- Internal commission exclusion.

Do not weaken normal company, pricing, or document validations.

# Part E: Delivery Phases

## 22. Recommended Rollout

### Phase 1: Price Sharing Hardening

- Fix Item Price mirror identity using Item, UOM, validity, and source row.
- Populate mirror provenance consistently.
- Detect stale and duplicate shared lists.
- Verify Pricing Builder provenance.

### Phase 2: Stock Sharing

- Add Warehouse eligibility.
- Add Share Stock Availability.
- Implement secure aggregate lookup.
- Display shared availability on Quotation Items.
- Add snapshot timestamps and statuses.

### Phase 3: Automation Foundation

- Add automation options.
- Add readiness report.
- Add Automation Run and step tracking.
- Configure internal parties.

### Phase 4: Internal Sales Order

- Generate draft SOs.
- Validate rates and links.
- Add optional SO submission.
- Exclude internal commissions.

### Phase 5: Procurement

- Add MR generation/submission.
- Add supplier-grouped PO generation/submission.
- Reuse existing buying-price validation.

### Phase 6: Fulfilment

- Add Pick List generation/submission.
- Use the existing automatic reservation behavior.
- Add shortage notifications and retry.

### Phase 7: Pilot

Pilot:

```text
Seller: Orderlift Maroc Distribution
Buyer: Orderlift Maroc Installation
```

Recommended initial settings:

| Setting | Pilot |
|---|---|
| Share Stock Availability | Yes |
| Create Sales Order | Yes |
| Submit Sales Order | No |
| Create Material Request | Yes |
| Submit Material Request | No |
| Create supplier PO | No |
| Create Pick List | Yes |
| Submit Pick List | No |

Enable automatic submissions progressively after validating each step.

# Business Logic Summary

You receive the following complete business behavior:

1. Company B shares a Selling Price List with Company A.
2. Company A receives it as a synchronized Buying Price List.
3. Company B can optionally share aggregate available stock.
4. Only explicitly eligible Company B warehouses contribute to shared availability.
5. Company A sees Company B's available quantity only for Quotation Items derived from that shared pricing relationship.
6. Company A never sees Company B's warehouses, costs, valuation, batches, serials, or stock ledger.
7. Shared stock is informational and does not reserve anything at Quotation stage.
8. Company A can build and publish its own Selling Price List from the shared Buying Price List.
9. When Company A submits an internal PO, Company B can automatically receive a Sales Order.
10. The Sales Order can remain draft or be submitted automatically.
11. A Material Request can be generated and optionally submitted.
12. Supplier POs can be generated by supplier and optionally submitted.
13. A Pick List can be generated and optionally submitted.
14. Submitting the Pick List automatically reserves the picked stock.
15. Cancelling the Pick List automatically cancels its reservations.
16. Downstream failures never undo the original submitted PO.
17. Every generated document is linked, audited, retryable, and protected from duplication.
18. Stock visibility and document automation remain independently configurable for every shared Price List relationship.
