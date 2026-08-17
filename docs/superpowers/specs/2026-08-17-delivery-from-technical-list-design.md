# Delivery and Picking from the Approved Technical List

Status: business rules agreed 2026-08-17. No technical design in this document.

## Problem

Native `Create > Delivery Note` from a Sales Order copies the commercial,
Opportunity-origin Sales Order items. It ignores the approved Technical List
revision entirely.

The only existing guard is `validate_operational_document`
(`orderlift_logistics/technical_procurement.py:415`). It requires that an approved
revision *exists*; it never matches Delivery Note rows against revision items or
quantities. Delivery Note is not in `SUPPORTED_PROCUREMENT_DOCTYPES`, so the
row-lineage validation that governs Material Requests and Purchase Orders does not
apply to it.

The same gap exists upstream: the Pick List is built from the Sales Order, so a
picker is shown commercial quantities, and `reserve_submitted_pick_list` then
commits stock reservations against them.

Reported by Bilal. Confirmed as a design gap, not a data problem.

## What the Technical List is

Not a BOM explosion. Each revision line links back to a `sales_order_item` and
carries `sales_order_qty` against `execution_qty` with a `variance_qty`, an
`execution_relevant` flag, and `is_stock_item`. Lines with no `sales_order_item`
are engineering additions.

It is a **variance document against the sale**, largely 1:1 with the Sales Order.
So delivering from it diverges from what was sold in exactly three ways:

| Case | Sold | Execution says |
|---|---|---|
| Reduced | 10 | deliver 8 |
| Excluded (`execution_relevant = 0`) | 5 | deliver 0 |
| Added (no `sales_order_item`) | 0 | deliver 3 |

`docs/sales_order_technical_lists.md` scopes the Technical List to *procurement*.
Procurement is internal — nobody outside the company sees a Material Request. A
Delivery Note is the *bon de livraison* the client signs at site and it drives
`delivered_qty`. The procurement rules therefore cannot be copied across
unexamined; the three divergences above are commercial questions.

## Separation of concerns

| Document | Is the truth about | Governs |
|---|---|---|
| Sales Order | what was sold | invoicing — full contract price |
| Technical List revision | what engineering approved | procurement **and** delivery |
| Delivery Note / Pick List | what physically moved | stock, `delivered_qty` tracking |

The Sales Invoice is raised from the **Sales Order**, never from the Delivery Note.

## Rules

1. **Delivery and picking follow the approved revision, not the Sales Order.**
   Both the Pick List and the Delivery Note are built from the current approved
   revision's execution-relevant lines. Creating either natively from the Sales
   Order is blocked in policy-covered companies.

2. **Reduced or excluded lines** deliver what engineering approved — 8 of 10, or
   nothing at all. The client still pays the full contract price. Sales Order lines
   stay short-delivered by design.

3. **Added lines** deliver, and carry no Sales Order link, so they never reach an
   invoice. Absorbed as an engineering correction. This is the accepted cost of the
   model: an unbilled delivery is invisible in receivables, and only the revision's
   `variance_qty` and `change_reason` record that it happened.

4. **Approved execution qty is a hard ceiling** on cumulative delivery per line.

5. **To deliver more, engineering issues a new revision** raising `execution_qty`
   with a `change_reason`. No Delivery Note is cancelled and the Sales Order is not
   amended — billing follows the Sales Order, so raising execution qty does not
   change what the client pays. It is an engineering decision, not a commercial one.

6. **Delivered totals are counted per Sales Order line / item across the whole
   Sales Order, never per revision.** This is what makes rule 4 hold: counting per
   revision would reset delivered quantities to zero each time a revision is
   approved, making the hard cap bypassable by the very mechanism rule 5 blesses.
   The existing procurement code already does this — `_allocated_stock_qty`
   (line 1078) filters on `child.sales_order` (line 1104) with no revision filter
   and keys totals by `_allocation_key`.

   Consequence: `_allocation_key` falls back to `item::<item_code>` when there is
   no `sales_order_item`, which is what gives *added* lines continuity across
   revisions (they get a fresh row name in every revision). The trade-off is that
   two distinct added lines for the same item share one pool. Accepted.

7. **Delivery is not gated on procurement.** Whenever execution qty remains,
   delivery is allowed — the stock may already be on hand. The delivery route step
   ships ungated; a company may gate it per route later.

8. **Both delivery routes stay open.** Direct delivery and the Pick List route are
   both valid. `delivery_note_reservation_guard` continues to force the Pick List
   route when a Sales Order row has reserved stock. Because both routes exist,
   each enforces rule 1 independently — the Pick List cannot be the single gate.

9. **Partial deliveries are governed per line**, each with its own remaining
   quantity.

10. **The Sales Order closes automatically when every execution-relevant line of
    the approved revision is fully delivered** — service and non-stock lines
    included, so they must appear on a Delivery Note for the close to trigger (see
    rule 11). Excluded lines are not execution-relevant and do not hold it open.
    Reversible: if a later revision raises a quantity, the Sales Order reopens.

    This uses the **native** Sales Order `status` of `Closed`. We do not write or
    override the native `delivery_status` field. Native ERPNext derives it from
    `per_delivered` = `delivered_qty / qty` against the *sold* quantity, which under
    rule 2 is deliberately short (8 of 10), so it will read `Partly Delivered` and
    then `Closed`. Forcing it to `Fully Delivered` would mean re-asserting the value
    after every native recalculation on Delivery Note submit and cancel — fighting
    ERPNext on a field it owns. Rejected as not worth the fragility; `Closed` is a
    sufficient signal that execution is complete.

11. **What the client sees is a separate, already-solved concern.**
    `custom_presentation_mode` (`With details` / `Without details`) with
    `custom_commercial_designation` governs printing, and the Delivery Note already
    inherits it from the Sales Order via `so_detail`
    (`commercial_presentation.py:157`). Installation prints the commercial
    designation; Distribution prints details. Delivery Note item rows are therefore
    the internal execution record, so **all** execution-relevant rows go on it,
    services and non-stock included. Non-stock rows create no stock ledger entries.
    Rule 10 depends on this: a service line that never reaches a Delivery Note would
    hold the Sales Order open forever.

12. **Non-policy companies and pre-effective-date Sales Orders are untouched.**

## Picking rules

Agreed 2026-08-17, after the Delivery Note work landed. These extend rule 1 to the
Pick List.

13. **Picking follows the approved revision.** A Pick List is built from the current
    approved revision's execution-relevant lines, and creating one natively from the
    Sales Order is blocked in policy-covered companies. Without this, Bilal's report
    is only half closed: the warehouse would still be shown commercial quantities,
    and `reserve_submitted_pick_list` would commit stock reservations against them.

14. **A Pick List carries stock rows only.** Services and non-stock lines cannot be
    picked — there is nothing to take off a shelf, and `Pick List Item` has no
    `is_stock_item` field. They reach delivery through the Delivery Note instead,
    which is what rule 10's auto-close depends on.

15. **Picking is capped by the approved execution qty, counted across Pick Lists
    only.** Picking and delivery keep separate pools: a pick that later becomes its
    own Delivery Note would otherwise consume the budget twice and make shipping the
    full approved quantity impossible. This mirrors how the procurement and delivery
    pools are already independent.

16. **For policy-covered Sales Orders the technical cap replaces the Sales Order
    cap.** `pick_list_override.validate_sales_order` currently caps picking at the
    Sales Order's open quantity (`qty - delivered_qty`). That contradicts rule 4 the
    moment engineering raises a quantity above what was sold, and rule 5 makes that
    an engineering decision needing no commercial step — so the override must defer
    to the technical cap for these Sales Orders. Non-policy companies keep today's
    behaviour exactly.

17. **The interim Pick List allowance is removed.** The Delivery Note validator
    currently lets rows carrying `pick_list_item` through without lineage, because
    Pick Lists had none. Once rule 13 holds, that skip goes, closing the interim gap
    where Pick List deliveries did not count toward the delivery cap (spec rule 8
    requires each route to enforce rule 1 independently).

## Rule 16 extends to procurement

Agreed 2026-08-17, after a live Material Request was refused.

20. **A Material Request row carrying technical lineage is exempt from ERPNext's
    Sales-Order-qty overflow guard.** The native guard caps a Material Request row at its
    linked `Sales Order Item.stock_qty` (`status_updater`, joining on `sales_order_item`).
    Rule 16 already made the approved execution qty the cap for policy-covered Sales
    Orders, and rule 5 makes raising it an engineering decision that does *not* amend the
    Sales Order — so without this exemption rule 5 is unusable for procurement: a revision
    that raises a quantity above the sold quantity cannot be requested at all.

    Observed live: `SAL-ORD-2026-00139~TESTOPP` item `ECL-00001` sold 4, revision
    `TLR-11397` approved 7, and `MAT-MR-2026-00042~TESTOPP` was refused on submit as "over
    limit by Stock Qty 3.0".

    These rows are not uncapped. `validate_procurement_document` holds them to the approved
    execution qty through the procurement pool before the native guard ever runs — the cap
    moves to the correct document rather than disappearing. Rows with no lineage stamp keep
    the native guard exactly, and non-policy companies are untouched.

    **Applies to Purchase Order as well as Material Request.**

    *Corrected 2026-08-18.* This originally claimed Purchase Order needed no equivalent
    change, on the grounds that its `status_updater` links only to `Material Request Item`.
    That was wrong: `PurchaseOrder.__init__` lists only that entry, but
    `update_status_updater()` **appends** a `Purchase Order Item → Sales Order Item` entry
    at runtime (`purchase_order.py`, `join_field: "sales_order_item"`). Reading only
    `__init__` is how it was missed, and `PUR-ORD-2026-00061~TESTOPP` was refused for the
    same item and quantity as the Material Request that prompted this rule.

    The lesson generalises: an ERPNext `status_updater` list is not fully knowable from
    `__init__`. Check for runtime appends before concluding a doctype is unaffected.

## Invoicing and closure rules

Agreed 2026-08-17, after the Pick List work landed.

18. **The Sales Invoice is raised from the Sales Order, never from a Delivery Note
    that carries technical lineage.** Enforced server-side, not merely by convention.

    Two reasons, both already decided. Rule 2 says the client pays the full contract
    price, so the invoice has to follow *sold* quantities — invoicing a short delivery
    would under-bill. Rule 3 says engineering additions are never billed, and ERPNext's
    `make_sales_invoice` maps every Delivery Note row with no `so_detail` condition, so
    invoicing from the Delivery Note pulls additions straight onto the invoice. Rule 3
    was therefore only ever a convention; this makes it a property.

    Keyed on the lineage stamp, not on company membership: a Delivery Note predating
    this feature carries no stamp and stays invoiceable, matching "Out of scope" below.

19. **An auto-close records that it was automatic.** Rule 10 requires the close to
    reverse when a later revision raises a quantity, but a Sales Order can also be
    closed by a person for reasons this feature knows nothing about. A hidden read-only
    flag on the Sales Order marks a close performed by this feature; only a close it
    owns is ever reopened. Without it, an auto-reopen would silently override a human
    decision.

    Closing and reopening both go through the native `Sales Order.update_status`, which
    calls `check_modified_date` — so the document must be re-fetched immediately before,
    or an unrelated concurrent save makes the close throw "has been modified".

## Out of scope

Delivery Notes and Pick Lists created before this change keep their
Opportunity-origin items. They are historical documents and are not retrofitted.

## Corrections to the earlier draft plan

Recorded so they are not reintroduced.

- **`ROOT_TARGET_ITEM_DOCTYPES` is triple-purposed.** The draft correctly kept
  Delivery Note out of it for allocation reasons, but that dict is also read by
  `_lineage_schema_ready` (line 1171) and `_previous_action_satisfied` (line 767),
  and subscripted in `_build_target` (line 828). Excluding Delivery Note silently
  drops the delivery action from every route via `_route_actions` (line 722) — the
  feature would never appear in the UI and would fail as "the effective route does
  not enable this action" — and raises `KeyError` in `_build_target`.
- **Delivered totals must not be keyed by revision.** See rule 6.
- **The draft's `stamp_delivery_lineage` workaround is unnecessary** now that Pick
  List is revision-aware in the same change. It existed only to recover lineage for
  Delivery Notes derived from SO-based Pick Lists.

  **Corrected 2026-08-17, after implementation.** The reasoning above was wrong. A
  revision-aware Pick List does *not* pass its lineage to the Delivery Note for sold
  lines: ERPNext's `map_pl_locations` sets `source_doc = sales_order_item or location`
  (`pick_list.py`), so a location with a `sales_order_item` is mapped from the Sales
  Order Item — which carries no `custom_technical_*` fields. Only engineering
  additions, whose locations have no `sales_order_item`, inherit lineage through the
  mapper. Without a copy step, every ordinary Pick-List-route delivery is rejected for
  missing lineage.

  What was rightly rejected was the *heuristic*: the draft recovered lineage by
  matching a row's `sales_order_item` against the current approved revision, which can
  select the wrong line and fails on substitutions and partials. The implemented
  `stamp_pick_list_lineage` is a deterministic copy instead — `pick_list_item` names
  the exact Pick List row, whose lineage was already validated when the Pick List was
  saved. It runs on Delivery Note `before_validate` ahead of
  `validate_procurement_document`, skips rows that already carry lineage, and skips
  returns.
- **`_validate_target_row` (lines 932-937) requires `custom_technical_procurement_route`
  and `custom_technical_procurement_action`** to be non-empty on any row carrying
  lineage. Any row-stamping path must set them, not just the revision fields.
- **`_target_sales_order` should delegate to `_operational_sales_order`**
  (line 1022), which already resolves `against_sales_order` / `so_detail`, rather
  than growing a fourth fallback branch.
- **`validate_operational_document` is already on Delivery Note `before_validate`**
  (`hooks.py:452`). Removing it in favour of the new validation loosens today's
  behaviour and must be a deliberate choice, not an oversight.

## Open questions

None. Rules 1-12 are agreed.
