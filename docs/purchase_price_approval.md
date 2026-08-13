# Purchase Price Approval

Purchase Order prices that differ from the loaded supplier `Item Price` are treated as negotiated prices. A positive direct PO rate may also enter approval as a new buying price, but only when no valid supplier/UOM price exists in any Buying Price List permitted to the purchasing user. Removing a list from the PO source table never converts its existing prices into new-price requests.

## PO Form

The `Pricing Alerts & Approvals` section uses responsive review cards showing the loaded rate, PO rate, and review state. Existing-price updates show their difference from the loaded reference. New prices have no reference variance; after the reviewer selects a target Buying Price List, the card previews the exact converted `Item Price` that will be stored in that list's currency. A draft PO cannot be submitted while a negotiated or new-price row is `Pending`.

The Purchase Order `Currency` is the supplier transaction currency. Each selected buying list keeps its own source currency and a source-to-PO exchange rate. Item rows preserve the original source rate and currency, while `Loaded Buying Rate`, `PU HT`, taxes, and totals remain in the PO currency. When source and PO currencies match, the source-to-PO rate is always `1`.

Changing the PO currency leaves ERPNext responsible for converting the current PO item rate exactly once. Orderlift then refreshes each loaded reference in the new currency and clears stale price approvals; it does not apply a second conversion to negotiated or direct rates.

Automatic exchange rates use the PO transaction date. Purchase Managers, Orderlift Admins, System Managers, and users with privileged pricing capability may override a selected-list exchange rate. Lists with the same source currency must use the same rate. Missing cross-currency rates block price loading instead of silently defaulting to `1`.

Only users with the `privileged_pricing` capability can approve or skip a row. Approval requires an attestation that the PO rate may create or update an `Item Price` on submission. Skipping preserves the PO rate without changing the price list.

For a new price, the created `Item Price` uses the target Price List currency and the Purchase Order supplier. If the PO currency differs, the PO unit rate is divided by the validated target-list-to-PO exchange rate so the stored price is in the target list currency. Missing exchange rates block approval/publication.

## Batch Review

Privileged users can open `Buying Price Review` from Purchasing to review negotiated and new-price rows across draft Purchase Orders. The page supports filtering by status, supplier, buying price list, and item, target-list selection for new prices, and multi-row approval or skip actions.

## History

On Purchase Order submission, approved rows convert the negotiated PO rate back to the source-list currency exactly once before updating the source `Item Price`. Approved and skipped rows create immutable `Buying Price Change Log` records with separate PO-currency and source-currency values, the exchange rate, reviewer, and review timestamp.

## Material Requests

From the Material Request list, select one or more submitted Purchase-type requests and use `Create Purchase Order`. The dialog requires one supplier and creates one unsaved PO containing every remaining item quantity. Each PO row preserves its `material_request` and `material_request_item` links. Material Requests remain quantity-only; supplier price loading and missing-price approval start on the resulting PO.
