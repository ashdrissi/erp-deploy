# Stock Rate Review

Warehouse users continue to receive stock through native ERPNext `Purchase Receipt` and `Stock Entry` forms. `Purchase Receipt` is quantity-only for every user: buying prices remain internal and come from the submitted Purchase Order when linked. `Stock Entry` keeps its existing capability-based rate visibility for valuation exceptions.

## Rate Resolution

- Purchase Receipt linked to a Purchase Order: use the submitted PO row rate and mark it approved.
- Buying rates are not edited or displayed on the Purchase Receipt form; use the Purchase Order for commercial pricing and Stock Rate Review for exceptional internal corrections.
- Otherwise: use the latest active Buying Item Price and mark it provisional.
- If no Buying Item Price exists: use the last submitted purchase rate and mark it provisional.
- If no positive rate exists: save the document as `Missing Rate`; submission is blocked without preventing warehouse quantity capture.
- `Allow Zero Valuation Rate` is disabled for incoming rows covered by this workflow.

## Bulk Review

Open `Warehouse & Stock > Stock Rate Review`.

- `Save selected rates` writes positive manual rates to draft documents and records the reviewer.
- `Approve current rates` confirms existing positive provisional values. On submitted documents this confirms the posted rate only; it does not rewrite accounting or stock ledger entries.
- `Submit ready documents` submits selected valued drafts only when the user also has native submit permission.
- To change a submitted rate, use the normal ERPNext correction flow such as Purchase Invoice variance handling or cancel/amend where appropriate.
