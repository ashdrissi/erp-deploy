# Cash-Flow Backend Semantics

The cash-flow service is company-scoped and reports all calculated cash values in the active company's default currency. `source_amount` and `source_currency` preserve the attributed document or payment currency where it is available.

## Funding and horizons

- Funding gap is the absolute value of the lowest chronological cumulative cash position, not the final forecast balance.
- Context funding paths are calculated independently. Portfolio funding uses one consolidated chronological event path and is not the sum of context gaps.
- Events on the same date apply outflows before inflows as a conservative intraday assumption.
- For 13-week, monthly, and custom horizons, actual cash through the start date forms the opening position. Current open commitments already overdue at the start are applied first, followed by events through the end date.
- Cash and accrual KPIs exclude events or source documents dated after the horizon end. Open invoice/order commitments are current-state values; the service does not claim to reconstruct a historical outstanding snapshot.

## Accrual and cash layers

- Purchase Invoice totals contribute to actual-cost accrual.
- Purchase Invoice outstanding amounts and residual Purchase Order schedules contribute to committed cash outflow.
- Landed-cost forecasts are replaced once by attributed PO accrual or direct PI accrual. Actual cost and outstanding cash are not both deducted from the same forecast.
- Supplier PI returns reverse direct PI accrual coverage independently of signed actual cost. For example, an original PI of 100 followed by a return of 60 leaves actual cost and forecast coverage of 40, so 60 of a planned landed cost of 100 reappears as uncovered forecast.
- If both direct PO advances and PI coverage exist and their overlap cannot be proven, PI coverage alone reduces the PO residual. The response emits `ambiguous_po_replacement_overlap` and lowers confidence.
- Negative Sales/Purchase Invoice outstanding values reverse the normal cash direction and use an absolute event amount.

## Profitability

- Profitability is lifecycle-scoped and does not change with the 13-week, monthly, or custom cash horizon.
- Expected Revenue HT comes from submitted Sales Order net totals. Expected Revenue TTC and expected taxes are reported separately; taxes are excluded from profit.
- Invoiced Revenue HT comes from attributed submitted Sales Invoice net totals. Sales returns reduce invoiced revenue.
- Baseline Cost is the company-currency sum of `Sales Order Item.qty * source_landed_cost`.
- Actual Cost HT comes from attributed submitted Purchase Invoice net totals. Purchase returns reduce actual cost.
- Committed Cost is the submitted Purchase Order net amount not yet covered by submitted Purchase Invoices.
- Forecast Cost is the positive remainder of Baseline Cost after Actual and Committed Cost. Actual and committed overruns are never hidden by the baseline.
- Expected Profit is Expected Revenue HT minus Expected Cost. Actual Profit to Date is Invoiced Revenue HT minus Actual Cost HT.
- Payment Entries never change expected or actual profit. Customer receipts less supplier payments are Net Cash Flow only.
- Expected Cost and Expected Profit are marked Incomplete when any Sales Order item lacks landed cost. Raw zero-cost arithmetic is never presented as a valid profit; Cost Forecast Final explicitly confirms that no additional uncovered cost is expected.

## Forecast closure

- Revenue Forecast Final removes uninvoiced Sales Order revenue and residual Sales Order cash inflows. Submitted invoice receivables and customer payments remain.
- Cost Forecast Final removes uncovered theoretical cost and its forecast cash outflow. Submitted Purchase Orders, Purchase Invoices, payables, and supplier payments remain.
- Project closure state controls the complete Project context. Sales Order closure state applies only while the order is standalone.
- Finance Admin, Orderlift Admin, and System Manager can close or reopen forecasts through the financial detail workspace.

## Other-charge costs

- Saved Other Charges may define a default expected unit cost HT.
- Quotation users may snapshot or override that expected unit cost per charge row.
- The generated Quotation Item stores the unit cost in `source_landed_cost`; the existing Quotation-to-Sales-Order pricing snapshot carries it to Sales Order Item.
- A selling Other Charge without expected cost remains revenue but emits the normal missing-landed-cost warning. Historical costs are never guessed.

## Payment attribution

- A Payment Entry attributes only the bank-side amount represented by its references. Bank cash beyond supported references remains unassigned and emits `partially_unassigned_payment`.
- `custom_source_payment_amount` and `custom_source_document_currency` are allocated proportionally when present.
- Inline invoice paid amounts are reduced by exact Payment Entry source amounts. A partial Payment Entry therefore leaves only the unpaid inline residual instead of suppressing the whole invoice.

## Lineage and completeness

- Standalone Sales Orders can receive procurement through `Purchase Order Item.sales_order`, the native `Purchase Invoice Item.po_detail` PO-item chain, or a direct `Purchase Invoice Item.custom_sales_order` charge.
- Direct PI Sales Order charges must target a submitted, same-company, standalone Sales Order and cannot coexist with Project or PO lineage on that invoice row.
- Source queries are permission-aware and bounded in deterministic recent order. Missing permissions/sources emit `unavailable_source`; limits emit `source_truncated`. Either condition prevents High confidence.
- Detail event rows are selected for the requested horizon (including overdue open commitments, excluding opening-position actuals) and capped once by `MAX_DETAIL_EVENTS`. `events`, bucket `events`, `receivables`, and `payables` are all subsets of that same bounded set; bucket amounts/positions and alerts still use the complete horizon event set.
- Detail responses include horizon-scoped `bounded_events` counts and `detail_completeness`; truncation emits `detail_events_truncated`. Portfolio responses include `detail_completeness`.
