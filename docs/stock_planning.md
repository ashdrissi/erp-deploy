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

## Activation Checklist

1. Review the company settings and collapsible examples.
2. Confirm stock Sales Order Item delivery dates are populated.
3. Confirm Item lead times and Purchase Order schedule dates are maintained.
4. Start with `Create Draft Pick List`.
5. Review dashboard plans and partial-Pick behavior.
6. Enable automatic Pick List submission only after warehouse validation.
