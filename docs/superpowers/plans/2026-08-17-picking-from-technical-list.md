# Pick List from the Approved Technical List — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Pick List in policy-covered companies come from the approved Technical List revision instead of the commercial Sales Order, so the warehouse picks and reserves what engineering approved.

**Architecture:** Add a fourth safe adapter (`revision_to_pick_list`) reusing the lineage and route machinery built for the Delivery Note. Picking gets its own allocation pool, separate from both procurement and delivery, so a pick that later becomes its own Delivery Note does not consume the approved quantity twice. The technical cap replaces `pick_list_override`'s Sales Order cap for policy-covered Sales Orders, and the interim allowance that let Pick-List-sourced Delivery Note rows through without lineage is removed.

**Tech Stack:** Frappe/ERPNext v15 app (`orderlift`), Python 3, plain `unittest` with `frappe` stubbed at import (no database), vanilla JS for Desk form scripts.

**Spec:** `docs/superpowers/specs/2026-08-17-delivery-from-technical-list-design.md` — rules 13-17 govern this plan; rules 1-12 are already implemented.

**Branch:** continue on `feat/delivery-from-technical-list` in the worktree `/root/erp-deploy-wt/delivery-tl`. Plan 1 is committed there but **not deployed**.

---

## Preflight

- [ ] **Step 1: Confirm the baseline**

Test modules stub `sys.modules`, so a combined run is polluted. Always one module per command. Use `python3`, not `python`.

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_price_list_usage_guard 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_stock_reservation_delivery_flow 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_logistics_quantity_only 2>&1 | tail -3
```

Expected: 42 OK, 6 OK, 43 OK, 9 OK, and whatever `test_logistics_quantity_only` reports — record it.

These 14 modules already fail on `main` and are **not** your concern at any point:
`test_access_command_center`, `test_admin_permissions_setup`, `test_business_type_access`, `test_e2e_pricing_chain`, `test_forecast_single_document_mode`, `test_material_request_no_price_list`, `test_partner_campaign_schema`, `test_pricing_builder_metadata`, `test_pricing_simulator_retirement`, `test_purchase_agent_rules`, `test_quotation_commission_assignment`, `test_sig_sidebar_setup`, `test_simplified_access_model`, `test_update_article_buying_prices`.

---

## Verified facts about Pick List — read before starting

Confirmed against the installed ERPNext, not assumed. Several differ from every doctype the adapter machinery has handled so far, and each one breaks something if missed.

- **The child table is `locations`, not `items`.** `TARGET_CHILD_TABLES` already exists for exactly this reason.
- **`Pick List` has no `project` field**, and neither does `Pick List Item`. Plan 1's `_target_has_project_field` already skips the project check for a target genuinely lacking the field — verify it does, do not re-add a blanket tolerance.
- **`Pick List Item` has no `is_stock_item` field.** Pickability must be resolved from the `Item` master, not the row.
- **`Pick List Item` fields available:** `item_code`, `item_name`, `description`, `qty`, `picked_qty`, `delivered_qty`, `stock_qty`, `uom`, `conversion_factor`, `stock_uom`, `warehouse`, `sales_order`, `sales_order_item`, `material_request`, `material_request_item`, `stock_reserved_qty`. It uses `sales_order`/`sales_order_item` (like the procurement doctypes), **not** `against_sales_order`/`so_detail`.
- **`Pick List` parent fields:** `company`, `customer`, `purpose`, `parent_warehouse`, `locations`. `purpose` must be `"Delivery"` — `pick_list_reservation` and `pick_list_override` both early-return on any other purpose.
- **`pick_list_override.py` is 58 lines total.** `OrderliftPickListMixin.validate_sales_order` caps each `sales_order_item` at `(qty - delivered_qty) * conversion_factor` summed across all other Pick Lists. It only counts rows that HAVE a `sales_order_item`, so engineering additions already pass it untouched.
- **`delivery_note_reservation_guard.py` line 42 requires BOTH `against_sales_order` and `so_detail`** for any row on the Pick List route that `_requires_stock_reservation`. Engineering additions have neither by spec rule 3, so once Pick Lists carry additions, delivering them through the reserved route is rejected at `before_submit`. Task 7 fixes this.
- **The existing hook test asserts equality, not membership:** `test_technical_list_integration` contains `self.assertEqual(hooks.doc_events["Pick List"]["before_validate"], operational_guard)`. Pick List's `before_validate` is currently a bare string. Turning it into a list breaks that assertion — update it in Task 8, do not work around it.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `orderlift/orderlift_logistics/technical_procurement.py` | adapters, registries, pools, validation | modify |
| `orderlift/orderlift_logistics/pick_list_override.py` | Pick List over-pick cap | modify |
| `orderlift/orderlift_logistics/utils/delivery_note_reservation_guard.py` | reserved-stock delivery guard | modify |
| `.../doctype/technical_procurement_action/technical_procurement_action.py` + `.json` | action registry | modify |
| `orderlift/hooks.py` | Pick List `before_validate` | modify |
| `orderlift/public/js/sales_order_technical_list_20260815f.js` | page actions + native Create guard | modify |
| `.../sales_order_technical_list_revision/sales_order_technical_list_revision.js` | revision form actions | modify |
| `orderlift/tests/test_technical_procurement.py` | unit tests | modify |
| `orderlift/tests/test_technical_list_integration.py` | hook wiring tests | modify |
| `docs/sales_order_technical_lists.md` | documentation | modify |

`technical_procurement.py` will pass ~1500 lines with this plan. Task 2 extracts the
allocation and pool helpers into `orderlift/orderlift_logistics/technical_allocation.py`
so the growth lands in a focused module instead. That extraction is the one structural
change here; everything else follows existing patterns.

---

## Task 1: Collapse the per-adapter pool selection into one helper

Plan 1 left the pool choice expressed twice — a lazy closure in `get_available_actions` and a conditional in `_create_from_revision`. Adding a third adapter to both is how the two drift apart, and a mismatch means the UI offers a quantity the adapter then refuses. One helper, two call sites.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py` (`get_available_actions`, `_create_from_revision`)
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_pool_selection_is_expressed_once_for_every_adapter(self):
        """The UI payload and the adapter must agree on remaining quantity. Two
        separate expressions of the same choice is how they drift, and a mismatch
        offers the user a quantity the adapter then refuses."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn("def _remaining_for_adapter(", source)
        # Exactly one definition and two call sites.
        self.assertEqual(source.count("_remaining_for_adapter("), 3)

    def test_remaining_for_adapter_maps_each_adapter_to_its_pool(self):
        calls = []
        with patch.object(
            technical_procurement, "_remaining_by_line",
            side_effect=lambda r: calls.append("procurement") or {"R1": 1},
        ), patch.object(
            technical_procurement, "_delivery_remaining_by_line",
            side_effect=lambda r: calls.append("delivery") or {"R1": 2},
        ):
            revision = revision_stub(name="TLR-1", technical_list="TL-1", items=[])
            cache = {}
            self.assertEqual(
                technical_procurement._remaining_for_adapter(
                    "revision_to_delivery_note", revision, cache
                ),
                {"R1": 2},
            )
            self.assertEqual(
                technical_procurement._remaining_for_adapter(
                    "revision_to_material_request", revision, cache
                ),
                {"R1": 1},
            )
            # Cached: a second lookup must not re-run the SQL-backed pool.
            technical_procurement._remaining_for_adapter(
                "revision_to_delivery_note", revision, cache
            )
        self.assertEqual(calls, ["delivery", "procurement"])
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -15
```

Expected: FAIL, `has no attribute '_remaining_for_adapter'`.

- [ ] **Step 3: Implement the helper**

Add near the other pool helpers:

```python
ADAPTER_POOLS = {
    "revision_to_material_request": "procurement",
    "revision_to_purchase_order": "procurement",
    "revision_to_delivery_note": "delivery",
}


def _remaining_for_adapter(adapter_key, revision, cache):
    """Remaining qty per revision line for the pool the adapter consumes.

    Each pool runs SQL, so results are memoised in the caller's cache dict. An
    unknown adapter falls back to the procurement pool, matching the pre-existing
    default.
    """
    pool = ADAPTER_POOLS.get(adapter_key, "procurement")
    if pool not in cache:
        if pool == "delivery":
            cache[pool] = _delivery_remaining_by_line(revision)
        else:
            cache[pool] = _remaining_by_line(revision)
    return cache[pool]
```

- [ ] **Step 4: Use it in both call sites**

In `get_available_actions`, delete the `pools` dict and the `remaining_for` closure, keep a plain `pools = {}`, and change the filter inside the `_route_actions` loop to:

```python
            if _remaining_for_adapter(action.adapter_key, revision, pools).get(line.name, 0) <= 0:
                continue
```

In `_create_from_revision`, replace the delivery/procurement conditional with:

```python
    remaining = _remaining_for_adapter(adapter_key, revision, {})
```

- [ ] **Step 5: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
```

Expected: both OK. All 42 pre-existing tests must still pass — this is a refactor.

- [ ] **Step 6: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "refactor(technical-procurement): express per-adapter pool selection once

The UI payload and the adapter each chose the remaining-quantity pool separately.
A third adapter would have to be added to both, and any mismatch offers the user a
quantity the adapter then refuses.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Extract the allocation helpers into their own module

`technical_procurement.py` is ~1400 lines and this plan adds ~150 more. The allocation
and pool helpers are a self-contained cluster with one clear responsibility — "how much
of a revision line remains, per pool" — and they are what the next two tasks grow.

**Files:**
- Create: `orderlift/orderlift_logistics/technical_allocation.py`
- Modify: `orderlift/orderlift_logistics/technical_procurement.py`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_allocation_helpers_live_in_their_own_module(self):
        from orderlift.orderlift_logistics import technical_allocation

        for name in (
            "ALLOCATION_ITEM_DOCTYPES",
            "ADAPTER_POOLS",
            "allocation_key",
            "line_stock_qty",
            "row_stock_qty",
            "allocated_stock_qty",
            "delivered_stock_qty",
            "delivery_budget_by_key",
            "delivery_remaining_by_line",
            "remaining_by_line",
            "remaining_for_adapter",
        ):
            self.assertTrue(hasattr(technical_allocation, name), name)
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -10
```

Expected: FAIL, `No module named 'orderlift.orderlift_logistics.technical_allocation'`.

- [ ] **Step 3: Move the helpers**

Move these from `technical_procurement.py` into the new module, dropping the leading
underscore since they are now a public interface between two modules:
`ALLOCATION_ITEM_DOCTYPES`, `ADAPTER_POOLS`, `_allocation_key`, `_line_stock_qty`,
`_row_stock_qty`, `_is_root_allocation`, `_allocated_stock_qty`, `_delivered_stock_qty`,
`_delivery_budget_by_key`, `_delivery_remaining_by_line`, `_remaining_by_line`,
`_remaining_for_adapter`, and `_revision_lines`.

They depend on `frappe`, `defaultdict`, `cint`, `flt`, `REVISION_DOCTYPE`, `_meta` and
`_text`. Import `REVISION_DOCTYPE` from a shared place or re-declare the literal — do
**not** create a circular import between the two modules. `_meta` and `_text` are tiny;
duplicate them in the new module rather than importing back.

In `technical_procurement.py`, import what it still needs:

```python
from orderlift.orderlift_logistics.technical_allocation import (
    ALLOCATION_ITEM_DOCTYPES,
    allocated_stock_qty,
    allocation_key,
    delivered_stock_qty,
    delivery_budget_by_key,
    line_stock_qty,
    remaining_for_adapter,
    revision_lines,
    row_stock_qty,
)
```

Then update every call site. **Several existing tests assert against the source text of
`technical_procurement.py`** and will break — for example the assertions on
`AND child.sales_order = %s{extra}` and `def _allocation_key`. Move those assertions to
read `technical_allocation.py` instead. Do not delete a test to make it pass; if an
assertion no longer makes sense in its new home, say so in your report.

- [ ] **Step 4: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_price_list_usage_guard 2>&1 | tail -3
```

Expected: all OK, with the same test counts as the baseline plus the one new test.

- [ ] **Step 5: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/technical_allocation.py \
        apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "refactor(technical-procurement): extract allocation helpers

The pool helpers are a self-contained cluster answering one question -- how much of a
revision line remains, per pool -- and are what the picking work grows. Moving them
out keeps technical_procurement.py from passing 1500 lines.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Register the Pick List adapter

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py`, `technical_allocation.py`
- Modify: `.../technical_procurement_action/technical_procurement_action.py` and `.json`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

Update the existing `test_exact_core_doctypes_and_safe_adapters` (it asserts exact dict
equality and will fail) and add:

```python
    def test_pick_list_is_registered_with_its_own_pool_and_child_table(self):
        self.assertEqual(
            technical_procurement.SAFE_ADAPTERS["revision_to_pick_list"], "Pick List"
        )
        self.assertEqual(
            technical_procurement.PROCUREMENT_ITEM_DOCTYPES["Pick List"], "Pick List Item"
        )
        self.assertIn("Pick List", technical_procurement.SUPPORTED_PROCUREMENT_DOCTYPES)
        # Pick List stores rows in "locations", not "items".
        self.assertEqual(technical_procurement.TARGET_CHILD_TABLES["Pick List"], "locations")
        # Picking has its own pool: a pick that becomes its own Delivery Note must not
        # consume the approved quantity twice.
        from orderlift.orderlift_logistics import technical_allocation

        self.assertEqual(
            technical_allocation.ADAPTER_POOLS["revision_to_pick_list"], "picking"
        )
        # Pick List must never enter the procurement allocation pool.
        self.assertNotIn("Pick List", technical_allocation.ALLOCATION_ITEM_DOCTYPES)
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -15
```

Expected: FAIL on `SAFE_ADAPTERS` exact equality and `KeyError: 'revision_to_pick_list'`.

- [ ] **Step 3: Extend the registries**

In `technical_procurement.py`:

```python
SAFE_ADAPTERS = {
    "revision_to_material_request": "Material Request",
    "revision_to_purchase_order": "Purchase Order",
    "revision_to_delivery_note": "Delivery Note",
    "revision_to_pick_list": "Pick List",
}
```

Add `"Pick List"` to `SUPPORTED_PROCUREMENT_DOCTYPES`, `PROCUREMENT_ITEM_DOCTYPES["Pick List"] = "Pick List Item"`, and `TARGET_CHILD_TABLES["Pick List"] = "locations"`.

In `_ensure_safe_actions`, add `"revision_to_pick_list": _("Create Pick List")`.

In `technical_allocation.py`, add `"revision_to_pick_list": "picking"` to `ADAPTER_POOLS`.

Mirror `SAFE_ADAPTERS` in `technical_procurement_action.py`, and extend both Select
option lists in `technical_procurement_action.json` (`adapter_key` gains
`revision_to_pick_list`, `target_doctype` gains `Pick List`).

Adding Pick List to `PROCUREMENT_ITEM_DOCTYPES` makes `after_migrate` install the seven
lineage custom fields on `Pick List Item` automatically. Its anchor lookup tries
`sales_order_item` first, which Pick List Item has.

- [ ] **Step 4: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/ apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): register the revision_to_pick_list adapter

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Add the picking allocation pool

Spec rule 15: picking is capped by approved execution qty, counted across Pick Lists
only. Same anchoring rules as delivery — `custom_technical_list`, never the revision
(rule 6) — and the same shared-key apportionment as `delivery_remaining_by_line`.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_allocation.py`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_picked_pool_is_anchored_on_the_technical_list_not_the_revision(self):
        """Rule 6 applies to picking exactly as it does to delivery: counting per
        revision would reset picked totals whenever engineering approves a new one."""
        source = (
            APP_ROOT / "orderlift_logistics" / "technical_allocation.py"
        ).read_text()
        body = source.split("def picked_stock_qty", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("child.custom_technical_list = %s", body)
        self.assertNotIn("custom_technical_revision = %s", body)
        self.assertIn("parent_doc.docstatus < 2", body)
        self.assertIn("tabPick List Item", body)

    def test_picking_remaining_is_independent_of_delivery(self):
        """A pick that later becomes its own Delivery Note must not consume the
        approved quantity twice, so the two pools never see each other."""
        from orderlift.orderlift_logistics import technical_allocation

        revision = revision_stub(
            name="TLR-1",
            technical_list="TL-1",
            items=[
                AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                         execution_stock_qty=10, execution_relevant=1),
            ],
        )
        with patch.object(
            technical_allocation, "picked_stock_qty", return_value={"SOI-1": 4}
        ), patch.object(
            technical_allocation, "delivered_stock_qty", return_value={"SOI-1": 10}
        ):
            picking = technical_allocation.picking_remaining_by_line(revision)
            delivery = technical_allocation.delivery_remaining_by_line(revision)
        # 4 picked of 10 approved leaves 6 pickable, regardless of what was delivered.
        self.assertEqual(picking["R1"], 6)
        self.assertEqual(delivery["R1"], 0)
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -15
```

Expected: FAIL, `has no attribute 'picked_stock_qty'`.

- [ ] **Step 3: Implement**

In `technical_allocation.py`, add `picked_stock_qty` as a near-copy of
`delivered_stock_qty` but over `tabPick List Item` / `tabPick List`, selecting
`sales_order_item` directly (Pick List Item has that column, so no `so_detail` aliasing),
and `picking_remaining_by_line` sharing the apportionment logic with
`delivery_remaining_by_line`.

The two remaining functions now differ only in which pool they subtract, so factor the
shared apportionment out rather than copying it:

```python
def _remaining_against(revision, consumed):
    """Apportion each key's unconsumed budget across the lines that share it.

    Distinct lines can share an allocation key -- engineering additions collapse to
    "item::<item_code>" -- so the remainder is walked in revision order, each line
    taking up to its own line_stock_qty. Deterministic, and never double-subtracts a
    shared bucket from every line.
    """
    budget = delivery_budget_by_key(revision)
    available = {
        key: max(total - consumed.get(key, 0), 0) for key, total in budget.items()
    }
    result = {}
    for line in revision.items or []:
        if not cint(line.execution_relevant):
            continue
        key = allocation_key(line)
        share = min(line_stock_qty(line), available.get(key, 0))
        available[key] = available.get(key, 0) - share
        result[line.name] = share
    return result


def delivery_remaining_by_line(revision):
    """Remaining deliverable stock qty per execution-relevant revision line."""
    return _remaining_against(revision, delivered_stock_qty(revision.technical_list))


def picking_remaining_by_line(revision):
    """Remaining pickable stock qty per execution-relevant revision line.

    Independent of the delivery pool: a pick that later becomes its own Delivery Note
    would otherwise consume the approved quantity twice (spec rule 15).
    """
    return _remaining_against(revision, picked_stock_qty(revision.technical_list))
```

**Rename `delivery_budget_by_key` to `budget_by_key`** — it is no longer
delivery-specific. Update every call site and every test that names it, including the one
in `validate_procurement_document`. Do not leave both names in the tree.

Add `"picking"` handling to `remaining_for_adapter`, calling `picking_remaining_by_line`.

- [ ] **Step 4: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
```

Expected: both OK.

- [ ] **Step 5: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/technical_allocation.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-allocation): add the picking pool

Picking is capped by approved execution qty across Pick Lists only, kept independent
of the delivery pool so a pick that becomes its own Delivery Note does not consume
the approved quantity twice. Apportionment of shared allocation keys is now factored
out and used by both pools.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Build the Pick List target, stock rows only

Spec rule 14: a Pick List carries stock rows only. Non-stock and service lines cannot be
picked and must be **skipped**, not rejected — a revision legitimately mixes both, and
throwing would make Create Pick List unusable on any realistic revision.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_pick_list_rows_use_locations_and_the_sales_order_fieldnames(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        rows = source.split("def _pick_list_row_values", 1)[1].split("\ndef ", 1)[0]
        # Pick List Item uses sales_order/sales_order_item, not against_sales_order.
        self.assertIn('"sales_order"', rows)
        self.assertIn('"sales_order_item"', rows)
        self.assertNotIn("against_sales_order", rows)
        # It has no project field, so do not invent one.
        self.assertNotIn('"project"', rows)

    def test_pick_list_parent_is_a_delivery_purpose_pick_list(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        branch = source.split('if target_doctype == "Pick List":', 1)[1].split(
            "    _set_known_fields", 1
        )[0]
        self.assertIn('"purpose"', branch)
        self.assertIn('"Delivery"', branch)
        self.assertIn("customer", branch)

    def test_non_stock_lines_are_skipped_for_picking_not_rejected(self):
        """A revision legitimately mixes stock and service lines. Throwing on a
        service line would make Create Pick List unusable; services reach delivery
        through the Delivery Note instead (spec rule 14)."""
        stock = AttrDict(name="R1", item_code="I-1", is_stock_item=1)
        service = AttrDict(name="R2", item_code="I-2", is_stock_item=0)
        self.assertTrue(technical_procurement._is_pickable_line(stock))
        self.assertFalse(technical_procurement._is_pickable_line(service))
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -15
```

Expected: FAIL, `has no attribute '_is_pickable_line'`.

- [ ] **Step 3: Implement pickability**

`Sales Order Technical List Item` has an `is_stock_item` field (read-only, synced from
the Item). Prefer it, and fall back to the Item master when it is unset:

```python
def _is_pickable_line(line):
    """Only stock items can be picked (spec rule 14).

    Pick List Item has no is_stock_item field, so pickability comes from the revision
    line, falling back to the Item master when the cached flag is unset.
    """
    value = _get(line, "is_stock_item")
    if value is not None and value != "":
        return bool(cint(value))
    return bool(cint(frappe.db.get_value("Item", _text(line.item_code), "is_stock_item")))
```

- [ ] **Step 4: Add the parent branch and row builder**

In `_build_target`, after the Delivery Note branch:

```python
    if target_doctype == "Pick List":
        customer = _text(_get(sales_order, "customer"))
        if not customer:
            frappe.throw(_("The Sales Order has no Customer."))
        values["customer"] = customer
        # pick_list_reservation and pick_list_override both early-return on any
        # other purpose, so a technical Pick List must be a Delivery one.
        values["purpose"] = "Delivery"
```

And the row builder:

```python
def _pick_list_row_values(revision, line, stock_qty):
    """Pick List Item row for one revision line.

    Pick List Item uses sales_order/sales_order_item like the procurement doctypes,
    and has no project field. Engineering additions carry no Sales Order line, so
    both stay empty -- pick_list_override only caps rows that have one, which is
    what lets an addition be picked at all.
    """
    factor = flt(line.conversion_factor)
    sales_order_item = _text(line.sales_order_item)
    return {
        "item_code": line.item_code,
        "item_name": line.item_name,
        "description": line.description,
        "qty": stock_qty / factor,
        "stock_qty": stock_qty,
        "uom": line.uom,
        "conversion_factor": factor,
        "stock_uom": line.stock_uom,
        "warehouse": line.warehouse,
        "sales_order": _text(revision.sales_order) if sales_order_item else "",
        "sales_order_item": sales_order_item,
    }
```

Wire it into the row dispatch alongside the Delivery Note branch.

- [ ] **Step 5: Filter non-stock lines out of the picking flow**

Two places, both required:
- `get_available_actions`: skip a line for the pick adapter when `not _is_pickable_line(line)`, so a services-only revision offers no Create Pick List button.
- `_create_from_revision`: when `adapter_key == "revision_to_pick_list"`, drop non-pickable lines from `selected_lines` before validation. If that leaves nothing, `frappe.throw(_("None of the selected rows can be picked: only stock items are pickable."))`.

- [ ] **Step 6: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
```

Expected: OK.

- [ ] **Step 7: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): build Pick List targets from a revision

Rows go to locations with sales_order/sales_order_item, the parent is a Delivery
purpose Pick List, and non-stock lines are skipped rather than rejected so a mixed
revision stays pickable.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Validate Pick List rows and expose the entrypoint

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_validation_reads_the_right_child_table_per_doctype(self):
        """Pick List stores rows in locations. Reading doc.items for a Pick List
        would silently validate nothing at all -- the worst possible failure, since
        it looks like the guard is working."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("TARGET_CHILD_TABLES", body)
        self.assertNotIn('rows = _get(doc, "items") or []', body)

    def test_create_pick_list_is_whitelisted_and_takes_no_supplier(self):
        import inspect

        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn("@frappe.whitelist()\ndef create_pick_list(", source)
        self.assertEqual(
            list(inspect.signature(technical_procurement.create_pick_list).parameters),
            ["revision", "selected_row_ids", "quantities"],
        )

    def test_picking_cap_uses_the_picking_pool(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("picked_stock_qty(", body)
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -15
```

Expected: FAIL, `has no attribute 'create_pick_list'`.

- [ ] **Step 3: Read the correct child table**

In `validate_procurement_document`, replace the hardcoded `_get(doc, "items")` with a
lookup so Pick List reads `locations`:

```python
    rows = _get(doc, TARGET_CHILD_TABLES.get(doctype, "items")) or []
```

Check every other `doc.items` read in that function and in `_validate_target_row`, and
fix any that would see an empty list for a Pick List. Getting this wrong means the guard
silently validates nothing.

- [ ] **Step 4: Generalise the cumulative cap**

The existing Delivery Note branch and the new Pick List branch differ only in which pool
they consult and what the error says. Fold them into one branch. Add a module-level map in
`technical_procurement.py` (note this is keyed by **doctype**, distinct from
`technical_allocation.ADAPTER_POOLS` which is keyed by adapter):

```python
# Doctype -> (consumed-pool function, over-cap message). Both consume the approved
# execution qty but from independent pools, so a pick and its own Delivery Note do
# not double-consume (spec rule 15).
CONSUMED_POOL_BY_DOCTYPE = {
    "Delivery Note": (delivered_stock_qty, "Row {0}: quantity exceeds the remaining delivery quantity."),
    "Pick List": (picked_stock_qty, "Row {0}: quantity exceeds the remaining pickable quantity."),
}
```

Then replace the `if doctype == "Delivery Note":` branch with:

```python
    pool = CONSUMED_POOL_BY_DOCTYPE.get(doctype)
    if pool:
        consumed_for, message = pool
        consumed_by_list = {}
        budget_by_revision = {}
        requested = defaultdict(float)
        labels = {}
        for (revision_name, revision_item), total in line_totals.items():
            revision = revisions[revision_name]
            technical_list = _text(revision.technical_list)
            if technical_list not in consumed_by_list:
                consumed_by_list[technical_list] = consumed_for(
                    technical_list,
                    exclude_doctype=doctype,
                    exclude_name=_text(_get(doc, "name")),
                )
            if revision_name not in budget_by_revision:
                budget_by_revision[revision_name] = budget_by_key(revision)
            source_line = revision_lines(revision)[revision_item]
            key = (technical_list, revision_name, allocation_key(source_line))
            requested[key] += total
            labels.setdefault(key, _row_label(source_line))
        for key, total in requested.items():
            technical_list, revision_name, alloc_key = key
            existing = consumed_by_list[technical_list].get(alloc_key, 0)
            allowed = budget_by_revision[revision_name].get(alloc_key, 0)
            if existing + total > allowed + 1e-9:
                frappe.throw(_(message).format(labels[key]))
        return
```

The budget comes from `budget_by_key(revision)` — the **whole revision** — never
accumulated from this document's rows. Plan 1 shipped that bug and it was fixed in
`c72f0ee`; do not reintroduce it.

- [ ] **Step 5: Add the entrypoint**

```python
@frappe.whitelist()
def create_pick_list(revision, selected_row_ids=None, quantities=None) -> dict:
    return _create_from_revision(
        "revision_to_pick_list",
        revision,
        selected_row_ids,
        quantities,
    )
```

- [ ] **Step 6: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_stock_reservation_delivery_flow 2>&1 | tail -3
```

Expected: both OK.

- [ ] **Step 7: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): validate Pick List lineage and cap picking

Validation now reads each doctype's own child table, so Pick List locations are
actually inspected, and the cumulative cap is keyed on the pool a doctype consumes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Reconcile the two stock guards

Two pre-existing guards contradict the agreed rules once Pick Lists carry lineage. Both
changes must be scoped to policy-covered Sales Orders so non-policy companies are
untouched (spec rule 12).

**Files:**
- Modify: `orderlift/orderlift_logistics/pick_list_override.py`
- Modify: `orderlift/orderlift_logistics/utils/delivery_note_reservation_guard.py`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_pick_list_override_defers_to_the_technical_cap(self):
        """Rule 16: when engineering raises a quantity above what was sold, the
        Sales Order's open qty must not block the pick. Rule 5 makes raising a
        quantity an engineering decision needing no commercial step."""
        source = (APP_ROOT / "orderlift_logistics" / "pick_list_override.py").read_text()
        self.assertIn("custom_technical_revision", source)
        self.assertIn("continue", source)

    def test_reservation_guard_accepts_a_lineage_stamped_addition(self):
        """delivery_note_reservation_guard requires against_sales_order and
        so_detail on the Pick List route, but an engineering addition has neither
        by rule 3, so delivering a picked addition would be rejected at submit."""
        source = (
            APP_ROOT / "orderlift_logistics" / "utils" / "delivery_note_reservation_guard.py"
        ).read_text()
        self.assertIn("custom_technical_revision", source)
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -12
```

Expected: FAIL, `'custom_technical_revision' not found`.

- [ ] **Step 3: Make the override defer to the technical cap**

In `OrderliftPickListMixin.validate_sales_order`, skip rows carrying
`custom_technical_revision` when accumulating `current`. Those rows are already capped by
the picking pool against the approved execution qty, which is the authority for
policy-covered Sales Orders (rule 16). Rows without a stamp keep today's Sales Order cap
exactly. Add a comment naming rule 16 and explaining why the caps disagree.

Do **not** remove the over-pick protection for unstamped rows, and do not widen the skip
to rows that merely belong to a policy company — the stamp is the signal, because only a
stamped row has passed `validate_procurement_document`.

- [ ] **Step 4: Let the reservation guard accept picked additions**

In `validate_delivery_note_pick_list_reservation`, the check
`if not row.get("against_sales_order") or not row.get("so_detail")` must tolerate a row
that carries `custom_technical_revision` and has no `so_detail` — that is a deliberate
engineering addition, not a missing reference. Everything else about the Pick List route
validation (both references present, Pick List submitted, picked and reserved qty
sufficient) must still apply to it.

- [ ] **Step 5: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_stock_reservation_delivery_flow 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_logistics_quantity_only 2>&1 | tail -3
```

Expected: all OK.

- [ ] **Step 6: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/pick_list_override.py \
        apps/orderlift/orderlift/orderlift_logistics/utils/delivery_note_reservation_guard.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "fix(logistics): reconcile the stock guards with the technical cap

pick_list_override capped picking at the Sales Order's open qty, which blocked a pick
the approved revision permits once engineering raised a quantity. The reservation
guard required a Sales Order reference on the Pick List route, which every engineering
addition lacks by design. Both now recognise a technical revision stamp.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: Remove the interim allowance and wire the hook

Spec rule 17. This is the step that actually closes the gap where Pick List deliveries
escaped the delivery cap.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py`
- Modify: `orderlift/hooks.py`
- Test: `orderlift/tests/test_technical_procurement.py`, `test_technical_list_integration.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_the_interim_pick_list_allowance_is_gone(self):
        """Rule 17: Pick Lists now carry lineage, so a Delivery Note row sourced
        from one has no excuse for missing it. Leaving the skip in place would keep
        the gap where Pick List deliveries escaped the delivery cap."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertNotIn('_text(_get(row, "pick_list_item"))', source)
        self.assertNotIn("Remove this skip in Plan 2.", source)
```

In `test_technical_list_integration.py`, replace the equality assertion on Pick List's
`before_validate` (it is currently a bare string) with:

```python
        pick_list = hooks.doc_events["Pick List"]["before_validate"]
        self.assertIn(guard, pick_list)
        self.assertIn(operational_guard, pick_list)
        self.assertLess(pick_list.index(guard), pick_list.index(operational_guard))
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -8
python3 -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -8
```

Expected: both FAIL.

- [ ] **Step 3: Delete the skip**

Remove the whole `if doctype == "Delivery Note" and _text(_get(row, "pick_list_item")):`
block and its comment from `validate_procurement_document`.

- [ ] **Step 4: Wire the Pick List hook**

In `hooks.py`, change Pick List's `before_validate` from a bare string to a list:

```python
        "before_validate": [
            "orderlift.orderlift_logistics.technical_procurement.validate_procurement_document",
            "orderlift.orderlift_logistics.technical_procurement.validate_operational_document",
        ],
```

- [ ] **Step 5: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_stock_reservation_delivery_flow 2>&1 | tail -3
```

Expected: all OK.

- [ ] **Step 6: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/hooks.py \
        apps/orderlift/orderlift/tests/
git commit -m "feat(technical-procurement): gate Pick Lists and drop the interim allowance

Pick Lists now carry lineage, so Delivery Note rows sourced from one are held to it
like any other. This closes the gap where a Pick List delivery consumed no delivery
allowance, letting the approved quantity be shipped twice.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Seed the route step, wire the UI, and document

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py` (`_ensure_delivery_route_step`)
- Modify: both JS files
- Modify: `docs/sales_order_technical_lists.md`
- Test: `orderlift/tests/test_technical_list_integration.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_ui_dispatches_the_pick_list_adapter(self):
        page = (APP_ROOT / "public" / "js" / "sales_order_technical_list_20260815f.js").read_text()
        form = (
            APP_ROOT / "orderlift_sig" / "doctype"
            / "sales_order_technical_list_revision"
            / "sales_order_technical_list_revision.js"
        ).read_text()
        for source in (page, form):
            self.assertIn("revision_to_pick_list", source)
            self.assertIn(
                "orderlift.orderlift_logistics.technical_procurement.create_pick_list",
                source,
            )
        # The native Pick List entry must now be intercepted, not left to fall through.
        self.assertIn('label === "Pick List"', page)
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -8
```

Expected: FAIL, `'revision_to_pick_list' not found`.

- [ ] **Step 3: Generalise the route seeding**

`_ensure_delivery_route_step` currently seeds one adapter. Rename it
`_ensure_ungated_route_steps` and have it seed both `revision_to_delivery_note` and
`revision_to_pick_list`, each with `required_previous_action` empty. Update the
`after_migrate` call and the test that names the old function. Use `route.save()`, not
`ignore_permissions=True` — an existing test forbids that string anywhere in the file.

- [ ] **Step 4: Add the adapter to both JS maps**

Add to `ADAPTER_METHODS` in the page JS and `METHODS` in the revision form JS:

```javascript
        revision_to_pick_list: "orderlift.orderlift_logistics.technical_procurement.create_pick_list",
```

Use full literal strings, not template literals — the tests assert the literal method
path appears in the source text.

- [ ] **Step 5: Intercept the native Pick List entry**

In `installNativeCreateGuard`, alongside the Delivery Note block:

```javascript
            if (label === "Pick List") {
                event.preventDefault();
                event.stopImmediatePropagation();
                const action = (payload.actions || []).find((row) => row.adapter_key === "revision_to_pick_list");
                if (action) runProcurementAction(action, payload);
                else frappe.msgprint(__("The approved Technical List has no remaining stock quantity for a Pick List."));
                return;
            }
```

- [ ] **Step 6: Update the documentation**

In `docs/sales_order_technical_lists.md`, add picking to the delivery section: picking
follows the approved revision; stock rows only, with services reaching delivery via the
Delivery Note; the picking pool is separate from delivery so a pick and its Delivery Note
do not double-consume; the technical cap replaces the Sales Order cap for policy-covered
Sales Orders; native Pick-List-from-Sales-Order is blocked. **Remove the known-limitation
note about Pick List deliveries escaping the delivery cap** — this plan closes it.

- [ ] **Step 7: Run and confirm pass**

```bash
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
node --check orderlift/public/js/sales_order_technical_list_20260815f.js
node --check orderlift/orderlift_sig/doctype/sales_order_technical_list_revision/sales_order_technical_list_revision.js
```

Expected: OK, OK, and no output from either `node --check`.

- [ ] **Step 8: Commit**

```bash
cd /root/erp-deploy-wt/delivery-tl
git add apps/orderlift/orderlift/ docs/sales_order_technical_lists.md
git commit -m "feat(picking): seed the pick route step, wire the UI, document the behaviour

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Full verification

- [ ] **Step 1: Run every module, one at a time**

```bash
cd /root/erp-deploy-wt/delivery-tl/apps/orderlift
for m in $(ls orderlift/tests/test_*.py | sed 's|.*/||;s|\.py||'); do
  r=$(python3 -m unittest orderlift.tests.$m 2>&1 | tail -1)
  case "$r" in OK*) ;; *) echo "$m :: $r";; esac
done
```

Expected: **exactly** the 14 pre-existing failures listed in Preflight. Any fifteenth is a regression you introduced — fix it, do not explain it away.

- [ ] **Step 2: Confirm the interim gap is closed**

```bash
grep -rn "pick_list_item" orderlift/orderlift_logistics/technical_procurement.py || echo "SKIP REMOVED"
```

Expected: `SKIP REMOVED`.

- [ ] **Step 3: Deploy — requires the user, do not run unattended**

Same sequence as Plan 1. Resolve container names with `docker ps --format '{{.Names}}'`
first; they carry per-deploy suffixes. `bench` runs in `app-*`, never `backend-*` (nginx,
read-only sites volume). Flush **redis-cache only** — never `redis-queue` or
`redis-socketio`. A restart alone does not reload `hooks.py`; the merged registry is
cached in Redis.

Verify the deploy by checking `app-*` started **after** the last edit
(`docker inspect ... --format '{{.State.StartedAt}}'`). A 200 from curl proves nothing —
nginx answers even when gunicorn is stale.

Confirm the lineage fields installed on the new child doctype:

```bash
docker exec <app-container> bench --site erp.ecomepivot.com execute frappe.client.get_count \
  --kwargs '{"doctype":"Custom Field","filters":{"dt":"Pick List Item","fieldname":["like","custom_technical%"]}}'
```

Expected: `7`.

- [ ] **Step 4: Manual acceptance — the cases no database-free test can cover**

1. **Create Pick List** appears on a submitted revision and on its Sales Order.
2. A revision mixing stock and service lines produces a Pick List containing **only** the stock lines, with no error.
3. Native `Create > Pick List` from the Sales Order is blocked with a message naming the Technical List.
4. Submit the Pick List, confirm stock reservations are created, then create the Delivery Note from it and confirm it carries lineage and submits.
5. **Pick an engineering addition** (a revision line with no `sales_order_item`), submit the Pick List, then deliver it. This exercises both guards changed in Task 7 and is the single most likely thing to fail in production.
6. Approve a revision raising a line's `execution_qty` **above the sold qty**, then confirm the warehouse can pick the raised amount — this is rule 16, and it fails against the unmodified `pick_list_override`.
7. Confirm picking and delivering the same line does not consume the approved quantity twice: pick 10 of 10, deliver 10, and confirm no cap error.
8. Confirm a Sales Return against a technical Delivery Note still saves.

Cases 5, 6 and 7 are the acceptance tests for this plan. If any fails, the plan is not done.

---

## Follow-up

- **Plan 3 — Sales Order auto-close.** Close when every execution-relevant line of the approved revision is fully delivered, services included; reopen when a later revision raises a quantity. Native `Closed` status; do not touch `delivery_status`.
- **Sales Invoice from a technical Delivery Note** still maps engineering additions onto the invoice, because ERPNext's `make_sales_invoice` has no `so_detail` condition. Spec rule 3 says additions are never billed, so either block Sales Invoice creation from a lineage-carrying Delivery Note or soften the rule's wording. Decide before the first month-end.
- **UOM divergence** between a revision line and its Sales Order Item dies at insert with a native ERPNext message that never mentions Technical Lists. Worth an explicit pre-check for the error message alone.
