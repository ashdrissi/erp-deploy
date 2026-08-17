# Confirmed Order Stock Planning

Orderlift stock planning starts from effective confirmed demand. It uses submitted Sales Order stock-item rows until a current submitted Sales Order Technical List revision exists, then uses that approved revision's execution quantities and dates instead. It coordinates physical stock, incoming Purchase Orders, logistics dates, Material Requests, and Pick Lists without creating Stock Reservation Entries directly.

## Configuration

Open `Warehouse & Stock > Stock Planning Settings`. This opens the custom `stock-planning-settings-control` page, with a company selector and one business-friendly form per allowed company. The underlying records remain company-scoped `Stock Planning Settings` documents, created disabled during migration and whenever a new Company is added.

Stock Manager, Orderlift Admin, and System Manager can edit settings. Logistics, purchasing, and sales managers receive read-only access according to the managed role matrix.

Important settings:

- `When Stock Protection Is Due`: alert only, create a draft Pick List, or create and submit a Pick List.
- `Rely on Incoming Stock`: permits safe submitted incoming supply to delay use of current stock.
- `Incoming Safety Delay`: defines both the latest safe arrival before delivery and the backup check before the incoming date.
- `Procurement Safety Delay`: internal purchasing time added before the Item lead time.
- `Allow Partial Pick Lists`: protects available stock and keeps the remaining quantity open.
- `Protected Stock Floor`: optional Item Reorder Level protection.
- Automatic Material Requests: optional draft or submitted Purchase requests for uncovered demand.

The custom settings page contains collapsible worked examples for protection dates, reliable and unsafe incoming stock, backup checks, partial backup Pick Lists, and competing Sales Orders.

## Dates

For each submitted Sales Order stock-item row:

```text
Stock Protection Date
= Delivery Date - Item Lead Time - Procurement Safety Delay
```

```text
Latest Safe Incoming Date
= Delivery Date - Incoming Safety Delay
```

```text
Incoming Backup Check Date
= Incoming Date - Incoming Safety Delay
```

`Item.lead_time_days` is the primary procurement delay. The company fallback applies only when the Item value is empty.

## Incoming Allocation

Only pending quantities from submitted Purchase Orders are supply. The expected date uses the latest active inbound Forecast Load Plan deadline when available, then the Purchase Order Item or parent schedule date.

Incoming quantity is allocated once using:

1. Earliest Sales Order Item delivery date.
2. Oldest Stock Demand Plan creation time.
3. Stable plan name tie-breaker.

Later Sales Orders cannot reuse quantity already allocated to an earlier confirmed demand.

## Pick List Protection

At the Stock Protection Date:

- Without safe incoming coverage, create a Pick List from physical sellable stock.
- With safe incoming coverage, wait until receipt or the Incoming Backup Check Date.
- If incoming becomes physical stock early, create the Pick List immediately.
- At the backup date, create a Pick List from physical stock still available.
- If only part is available, create a partial Pick List and keep the balance allocated to incoming.
- If no physical backup exists, keep waiting and show an incoming dependency risk.

The planner never creates Stock Reservation Entries. A submitted Pick List activates the existing automatic reservation hook. Pick List cancellation releases those reservations.

Orderlift extends Pick List validation to permit multiple partial Pick Lists for one Sales Order Item while preventing their total quantity from exceeding undelivered demand.

## Dashboard

The Stock Dashboard includes `Confirmed Order Stock Planning` with:

- Open plan, due, waiting incoming, partial, shortage, and fully reserved counts.
- Sales Order, Item, delivery date, status, demand, incoming allocation, Pick List, shortage, and next action.
- Semantic colors: green covered/reserved, blue incoming, gray not due, orange action/risk, red late/shortage.
- Manager-only links to settings and `Run Planning`.
- Planning alerts merged into the existing Live Alerts panel.

## Scheduler and Events

The hourly scheduler recalculates enabled companies. Recalculation is also queued after relevant Sales Order, Purchase Order, Purchase Receipt, Stock Entry, and Pick List changes.

Submitted Sales Orders create one `Stock Demand Plan` per stock item row. Cancellation marks plans cancelled; it does not silently cancel submitted downstream documents.

## Quotation and Sales Order Stock Preview

The Stock by Warehouse table and the item-grid stock columns on Quotation, Sales Order, and Pricing Sheet now include planner-aware columns:

- `Available After SO`: per warehouse, on hand minus open confirmed demand for that warehouse; per item row, total on hand minus open confirmed demand.
- `Projected Available`: per warehouse, Available After SO plus open Purchase Order quantity expected into that warehouse; per item row, On Hand minus `To Reserve` plus `Usable Incoming`.

`To Reserve` and `Usable Incoming` come from the read-only `simulate_reservation_outcome` mirror of the automatic Pick List decision. It uses the saved company `Stock Planning Settings` even when planning is disabled (built-in defaults when no record exists) and never writes documents. The simulation follows the same protection date, incoming safety, delivery priority, partial-Pick-List, and protected-floor rules as the planner.

## Shared Company Stock

The `Shared Company Stock` table on Quotation, Sales Order, Pricing Sheet, and Purchase Order shows warehouse stock in sharing-linked companies. Both directions resolve:

- Active `Price List Sharing` targets of selling price lists owned by the document company.
- Owner companies of the selling lists mirrored into the buying lists used on the document, including the stamped `custom_source_buying_price_lists` of the selling lists themselves (internal supplier side).
- On Purchase Orders, the internal supplier's `represents_company` is also included.

Rows include the company, warehouse, on hand, Available After SO, and Projected Available, using the same per-warehouse formulas as the document-company table.

Visibility is by design not restricted to the user's company access: anyone who can open the document sees stock quantities of the sharing-linked companies.

Quotation stores these values at save time (historical). Sales Order and Purchase Order do not store them: a live form script refreshes the Stock by Warehouse, Shared Company Stock, and item-grid stock columns on form load and on item/price-list/supplier changes, so the preview always reflects current reality, including after submission.

## Activation Checklist

1. Review the company settings and collapsible examples.
2. Confirm stock Sales Order Item delivery dates are populated.
3. Confirm Item lead times and Purchase Order schedule dates are maintained.
4. Start with `Create Draft Pick List`.
5. Review dashboard plans and partial-Pick behavior.
6. Enable automatic Pick List submission only after warehouse validation.
