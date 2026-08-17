# Stock Dashboard

The custom `stock-dashboard` page is the primary operational view for current stock.

It also includes confirmed-order stock planning. See `docs/stock_planning.md`.

## Company and warehouse scope

- The active company in the global company switcher is authoritative.
- Every KPI, warehouse card, item row, movement, and Stock Entry row is restricted to that company.
- Warehouse User Permissions further narrow the available warehouses.
- Switching company reloads the Desk session and the dashboard data.

## Stock by Item

Use the toolbar to filter by warehouse, item group, and stock status, or to sort by stock quantities and item identity.

- `On Hand`: current physical quantity in Bin.
- `Available After SO`: on-hand quantity minus open confirmed demand.
- `Open SO Qty`: open confirmed demand. Submitted Sales Order rows are used until the Sales Order has a current submitted Technical List revision; after that, the approved Technical List execution quantities are used.
- `Reserved Stock`: physically reserved stock.
- `Incoming`: ordered quantity expected into stock.

Click an item row to open its quantity, warehouse breakdown, recent movement, and permitted valuation detail.

Warehouse cards show `Stocked Item Coverage`, calculated as the percentage of Bin records in that warehouse with a positive quantity. It is not physical warehouse capacity.

## Read-only history

- `Stock Ledger (Moves)` opens the custom movement-history dialog.
- `Stock Entries` opens the custom read-only Stock Entry history dialog.
- The dialogs support date, warehouse, type/status, direction, and text filters.
- These dialogs do not create, edit, submit, cancel, or delete documents.

## Valuation visibility

Quantity and movement data follow normal stock and warehouse permissions. Valuation rates and stock values are returned only when `can_manage_stock_rates()` permits them. Restricted responses omit valuation fields server-side.

## Confirmed Order Stock Planning

The planning card shows company-scoped `Stock Demand Plan` rows generated from effective confirmed demand. Submitted Sales Order rows are used until a current submitted Technical List revision exists, then the approved Technical List execution rows replace the Sales Order quantities. Incoming Purchase Order quantity is allocated once by delivery priority, and protection actions create Pick Lists. The planner does not create Stock Reservation Entries directly.

Status colors are green for covered/reserved, blue for incoming coverage, gray for not due, orange for due/partial risk, and red for late or uncovered demand. Stock Managers can open `/app/stock-planning-settings-control` or run recalculation from the dashboard.
