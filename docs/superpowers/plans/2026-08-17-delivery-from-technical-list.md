# Delivery Note from the Approved Technical List — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Delivery Note in policy-covered companies come from the approved Technical List revision instead of the commercial Sales Order, capped at approved execution quantities.

**Architecture:** Add a third safe adapter (`revision_to_delivery_note`) alongside the existing Material Request and Purchase Order adapters, reusing the existing lineage-stamping and route machinery. Delivery gets its own allocation pool, separate from procurement, anchored on the stable Technical List rather than the revision so that quantities already delivered survive a new revision. Native Delivery-Note-from-Sales-Order is hard blocked under policy.

**Tech Stack:** Frappe/ERPNext v15 app (`orderlift`), Python 3, plain `unittest` with `frappe` stubbed at import (no database in tests), vanilla JS for Desk form scripts.

**Spec:** `docs/superpowers/specs/2026-08-17-delivery-from-technical-list-design.md`

**Scope:** This is plan 1 of 4. It implements spec rules 1-9 and 11-12 for the **Delivery Note only**. Pick List revision-awareness (rule 1 for picking) and Sales Order auto-close (rule 10) are separate plans that build on the foundation laid here.

---

## Preflight

- [ ] **Step 1: Confirm the test baseline is green before touching anything**

These test modules stub `sys.modules`, so a combined run is polluted and gives bogus
results. Always run per-module.

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v
python -m unittest orderlift.tests.test_technical_list_integration -v
```

Expected: both `OK`. If either already fails, stop and report — do not build on a red baseline.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `orderlift/orderlift_logistics/technical_procurement.py` | adapters, registries, validation, allocation | modify |
| `orderlift/orderlift_logistics/doctype/technical_procurement_action/technical_procurement_action.py` | action-doc validation registry | modify |
| `orderlift/orderlift_logistics/doctype/technical_procurement_action/technical_procurement_action.json` | Select options | modify |
| `orderlift/hooks.py` | Delivery Note `before_validate` wiring | modify |
| `orderlift/public/js/sales_order_technical_list_20260815f.js` | Sales Order page actions + native Create guard | modify |
| `orderlift/orderlift_sig/doctype/sales_order_technical_list_revision/sales_order_technical_list_revision.js` | revision form actions | modify |
| `orderlift/tests/test_technical_procurement.py` | unit tests | modify |
| `orderlift/tests/test_technical_list_integration.py` | hook wiring tests | modify |
| `docs/sales_order_technical_lists.md` | user-facing documentation | modify |

`technical_procurement.py` is already 1268 lines. This plan adds roughly 120. It is
cohesive (one feature area, one registry) and the existing tests assert against its
source text, so splitting it is out of scope here — but if it passes ~1500 lines,
extracting the allocation helpers into
`orderlift_logistics/technical_allocation.py` is the natural seam.

---

## Task 1: Disentangle the doctype registries

`ROOT_TARGET_ITEM_DOCTYPES` is read by four call sites for three different purposes:
allocation (`_allocated_stock_qty`), lineage-schema readiness
(`_lineage_schema_ready`), previous-action lookup (`_previous_action_satisfied`), and
target row meta (`_build_target`). Delivery Note must be absent from the allocation
purpose but present in the other three. Leaving the dict triple-purposed is what
would make the whole feature silently disappear from the UI.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py:38-41, 767, 828, 1081, 1171`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

Add to `TestTechnicalProcurement` in `orderlift/tests/test_technical_procurement.py`:

```python
    def test_allocation_registry_is_separate_from_lineage_registry(self):
        """Delivery Note carries lineage but must never enter the procurement
        allocation pool: _allocated_stock_qty joins on child.sales_order, a column
        Delivery Note Item does not have, and deliveries are not procurement."""
        self.assertEqual(
            technical_procurement.ALLOCATION_ITEM_DOCTYPES,
            {
                "Material Request": "Material Request Item",
                "Purchase Order": "Purchase Order Item",
            },
        )
        self.assertNotIn("Delivery Note", technical_procurement.ALLOCATION_ITEM_DOCTYPES)
        self.assertFalse(hasattr(technical_procurement, "ROOT_TARGET_ITEM_DOCTYPES"))

    def test_lineage_lookups_use_the_lineage_registry_not_the_allocation_registry(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        # These three read a child doctype for lineage purposes and must resolve
        # Delivery Note, so they cannot read the allocation registry.
        self.assertIn("PROCUREMENT_ITEM_DOCTYPES.get(target_doctype)", source)
        self.assertIn("ALLOCATION_ITEM_DOCTYPES.items()", source)
        # Only the allocation pool may be keyed off the allocation registry.
        self.assertEqual(source.count("ALLOCATION_ITEM_DOCTYPES"), 2)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -20
```

Expected: FAIL with `AttributeError: module ... has no attribute 'ALLOCATION_ITEM_DOCTYPES'`.

- [ ] **Step 3: Rename the registry and add the child-table map**

In `technical_procurement.py`, replace the `ROOT_TARGET_ITEM_DOCTYPES` block at
lines 38-41:

```python
# Only Material Requests and direct Purchase Orders consume procurement allowance.
# Read by _allocated_stock_qty and nothing else: it joins on child.sales_order,
# which only these two child doctypes have. Deliveries have their own pool.
ALLOCATION_ITEM_DOCTYPES = {
    "Material Request": "Material Request Item",
    "Purchase Order": "Purchase Order Item",
}
# Parent doctype -> child table fieldname. Pick List uses "locations", not "items".
TARGET_CHILD_TABLES = {
    "Material Request": "items",
    "Purchase Order": "items",
    "Delivery Note": "items",
}
```

- [ ] **Step 4: Repoint the three lineage call sites**

`_previous_action_satisfied` (line 767) — a missing mapping must not silently
return False, which would make a gated step permanently unsatisfiable:

```python
    child_doctype = PROCUREMENT_ITEM_DOCTYPES.get(target_doctype)
    if not child_doctype:
        return False
```

`_build_target` (line 828):

```python
    item_meta = _meta(PROCUREMENT_ITEM_DOCTYPES.get(target_doctype))
```

`_lineage_schema_ready` (line 1171):

```python
    meta = _meta(PROCUREMENT_ITEM_DOCTYPES.get(target_doctype))
```

`_allocated_stock_qty` (line 1081) keeps the allocation registry:

```python
    for parent_doctype, child_doctype in ALLOCATION_ITEM_DOCTYPES.items():
```

- [ ] **Step 5: Verify no stale references remain**

```bash
cd /root/erp-deploy/apps/orderlift
grep -rn "ROOT_TARGET_ITEM_DOCTYPES" orderlift/ || echo "CLEAN"
```

Expected: `CLEAN`.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -20
```

Expected: `OK`. This is a pure refactor — no behaviour change, so every pre-existing test must still pass.

- [ ] **Step 7: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "refactor(technical-procurement): split allocation registry from lineage registry

ROOT_TARGET_ITEM_DOCTYPES served three unrelated purposes: the procurement
allocation pool, lineage-schema readiness, and target row meta. Adding a doctype
that needs lineage but not allocation was impossible without breaking one of them.

Renamed to ALLOCATION_ITEM_DOCTYPES, now read only by _allocated_stock_qty, and
repointed the lineage lookups at PROCUREMENT_ITEM_DOCTYPES. No behaviour change.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Add the delivery allocation pool

Delivery is capped by approved execution qty, counted across the whole Technical
List and **never** per revision — spec rule 6. The anchor is
`custom_technical_list`, not `against_sales_order`, because engineering additions
(spec rule 3) deliberately carry no Sales Order link and would otherwise be
invisible to the cap and deliverable without limit.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py` (after `_allocated_stock_qty`)
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_delivery_remaining_survives_a_new_revision(self):
        """Counting delivered per revision would reset the total to zero whenever a
        revision is approved, making the hard cap bypassable by the very mechanism
        that is supposed to raise it. Delivered totals are keyed per Sales Order
        line across the whole Technical List."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        delivered = source.split("def _delivered_stock_qty", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("child.custom_technical_list = %s", delivered)
        self.assertNotIn("custom_technical_revision = %s", delivered)
        self.assertIn("parent_doc.docstatus < 2", delivered)

    def test_delivery_remaining_subtracts_delivered_from_execution_qty(self):
        revision = AttrDict(
            name="TLR-2",
            technical_list="TL-1",
            items=[
                AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                         execution_stock_qty=12, execution_relevant=1),
                AttrDict(name="R2", sales_order_item="", item_code="I-2",
                         execution_stock_qty=5, execution_relevant=1),
                AttrDict(name="R3", sales_order_item="SOI-3", item_code="I-3",
                         execution_stock_qty=9, execution_relevant=0),
            ],
        )
        with patch.object(
            technical_procurement,
            "_delivered_stock_qty",
            return_value={"SOI-1": 8, "item::I-2": 5},
        ):
            remaining = technical_procurement._delivery_remaining_by_line(revision)

        self.assertEqual(remaining["R1"], 4)      # 12 approved - 8 delivered
        self.assertEqual(remaining["R2"], 0)      # added line, fully delivered
        self.assertNotIn("R3", remaining)         # not execution relevant

    def test_delivery_remaining_never_goes_negative(self):
        """A revision that lowers execution qty below what already shipped must
        report zero remaining, not a negative that would read as credit."""
        revision = AttrDict(
            name="TLR-3",
            technical_list="TL-1",
            items=[AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                            execution_stock_qty=6, execution_relevant=1)],
        )
        with patch.object(
            technical_procurement, "_delivered_stock_qty", return_value={"SOI-1": 10}
        ):
            self.assertEqual(
                technical_procurement._delivery_remaining_by_line(revision)["R1"], 0
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -20
```

Expected: FAIL with `AttributeError: ... has no attribute '_delivered_stock_qty'`.

- [ ] **Step 3: Implement the delivery pool**

Insert immediately after `_allocated_stock_qty` in `technical_procurement.py`:

```python
def _delivered_stock_qty(technical_list, *, exclude_doctype="", exclude_name=""):
    """Stock qty already delivered per allocation key for a whole Technical List.

    Anchored on custom_technical_list rather than the revision: the Technical List
    is stable for the life of the Sales Order while revisions are immutable
    snapshots, so counting per revision would reset delivered totals to zero every
    time engineering approves a new one. It is also anchored on the Technical List
    rather than against_sales_order because engineering additions carry no Sales
    Order link and would otherwise escape the cap entirely.
    """
    totals = defaultdict(float)
    meta = _meta("Delivery Note Item")
    if not meta or not meta.get_field("custom_technical_list"):
        return totals
    conditions = []
    parameters = [technical_list]
    if exclude_doctype == "Delivery Note" and exclude_name:
        conditions.append("parent_doc.name != %s")
        parameters.append(exclude_name)
    extra = "".join(f" AND {condition}" for condition in conditions)
    rows = frappe.db.sql(
        f"""
        SELECT child.so_detail AS sales_order_item,
               child.item_code,
               child.qty,
               child.stock_qty,
               child.conversion_factor
          FROM `tabDelivery Note Item` child
          INNER JOIN `tabDelivery Note` parent_doc ON parent_doc.name = child.parent
         WHERE parent_doc.docstatus < 2
           AND child.custom_technical_list = %s{extra}
        """,
        tuple(parameters),
        as_dict=True,
    )
    for row in rows:
        totals[_allocation_key(row)] += _row_stock_qty(row)
    return totals


def _delivery_remaining_by_line(revision):
    """Remaining deliverable stock qty per execution-relevant revision line."""
    delivered = _delivered_stock_qty(revision.technical_list)
    result = {}
    for line in revision.items or []:
        if not cint(line.execution_relevant):
            continue
        result[line.name] = max(
            _line_stock_qty(line) - delivered.get(_allocation_key(line), 0), 0
        )
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -20
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): add delivery allocation pool

Delivery gets its own remaining-quantity pool, separate from procurement
allowance, anchored on the stable Technical List so that quantities already
delivered survive approval of a new revision, and so engineering additions
(which carry no Sales Order link) are still subject to the cap.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Register the delivery adapter

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py:17-36, 152-170`
- Modify: `orderlift/orderlift_logistics/doctype/technical_procurement_action/technical_procurement_action.py:9-13`
- Modify: `orderlift/orderlift_logistics/doctype/technical_procurement_action/technical_procurement_action.json`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

Replace the existing `test_exact_core_doctypes_and_safe_adapters` assertion on
`SAFE_ADAPTERS` (it asserts exact equality on a two-entry dict and will otherwise
fail) and add coverage:

```python
    def test_exact_core_doctypes_and_safe_adapters(self):
        self.assertEqual(
            technical_procurement.REVISION_DOCTYPE,
            "Sales Order Technical List Revision",
        )
        self.assertEqual(
            technical_procurement.TECHNICAL_LIST_DOCTYPE,
            "Sales Order Technical List",
        )
        self.assertEqual(
            technical_procurement.SAFE_ADAPTERS,
            {
                "revision_to_material_request": "Material Request",
                "revision_to_purchase_order": "Purchase Order",
                "revision_to_delivery_note": "Delivery Note",
            },
        )
        self.assertTrue(all("." not in key for key in technical_procurement.SAFE_ADAPTERS))

    def test_delivery_note_carries_lineage_and_row_validation(self):
        self.assertEqual(
            technical_procurement.PROCUREMENT_ITEM_DOCTYPES["Delivery Note"],
            "Delivery Note Item",
        )
        self.assertIn("Delivery Note", technical_procurement.SUPPORTED_PROCUREMENT_DOCTYPES)
        self.assertEqual(technical_procurement.TARGET_CHILD_TABLES["Delivery Note"], "items")

    def test_action_doctype_registry_matches_the_adapter_registry(self):
        from orderlift.orderlift_logistics.doctype.technical_procurement_action import (
            technical_procurement_action,
        )

        self.assertEqual(
            technical_procurement_action.SAFE_ADAPTERS,
            technical_procurement.SAFE_ADAPTERS,
        )
        action = json.loads(
            (
                DOCTYPE_ROOT
                / "technical_procurement_action"
                / "technical_procurement_action.json"
            ).read_text()
        )
        fields = {field["fieldname"]: field for field in action["fields"]}
        self.assertIn("revision_to_delivery_note", fields["adapter_key"]["options"])
        self.assertIn("Delivery Note", fields["target_doctype"]["options"])
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: FAIL on the `SAFE_ADAPTERS` equality — the delivery key is missing.

- [ ] **Step 3: Extend the registries**

In `technical_procurement.py`, lines 17-36:

```python
SAFE_ADAPTERS = {
    "revision_to_material_request": "Material Request",
    "revision_to_purchase_order": "Purchase Order",
    "revision_to_delivery_note": "Delivery Note",
}
SUPPORTED_REFERENCES = {
    "Sales Order",
    TECHNICAL_LIST_DOCTYPE,
    REVISION_DOCTYPE,
}
SUPPORTED_PROCUREMENT_DOCTYPES = (
    "Material Request",
    "Request for Quotation",
    "Supplier Quotation",
    "Purchase Order",
    "Delivery Note",
)
PROCUREMENT_ITEM_DOCTYPES = {
    "Material Request": "Material Request Item",
    "Request for Quotation": "Request for Quotation Item",
    "Supplier Quotation": "Supplier Quotation Item",
    "Purchase Order": "Purchase Order Item",
    "Delivery Note": "Delivery Note Item",
}
```

Adding `Delivery Note` to `PROCUREMENT_ITEM_DOCTYPES` makes `after_migrate`
(line 66) install the seven `custom_technical_*` lineage fields on Delivery Note
Item automatically — it already loops that dict's values. The anchor lookup at
line 69 tries `sales_order_item`, then `material_request_item`, then `item_code`;
Delivery Note Item has `material_request_item`, so the section lands there.

- [ ] **Step 4: Add the seed label**

In `_ensure_safe_actions` (line 153):

```python
    labels = {
        "revision_to_material_request": _("Create Material Request"),
        "revision_to_purchase_order": _("Create Purchase Order"),
        "revision_to_delivery_note": _("Create Delivery Note"),
    }
```

- [ ] **Step 5: Mirror the registry in the action controller**

In `technical_procurement_action.py`, lines 9-13:

```python
SAFE_ADAPTERS = {
    "revision_to_material_request": "Material Request",
    "revision_to_purchase_order": "Purchase Order",
    "revision_to_delivery_note": "Delivery Note",
}
```

- [ ] **Step 6: Extend the Select options**

In `technical_procurement_action.json`, set `adapter_key`'s `options` to:

```
revision_to_material_request
revision_to_purchase_order
revision_to_delivery_note
```

and `target_doctype`'s `options` to:

```
Material Request
Purchase Order
Delivery Note
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/orderlift_logistics/doctype/technical_procurement_action/ \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): register the revision_to_delivery_note adapter

Registers the delivery adapter in SAFE_ADAPTERS, the lineage and row-validation
registries, and the action doctype Select options. after_migrate now installs the
custom_technical_* lineage fields on Delivery Note Item automatically.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Build the Delivery Note target

`_build_target` currently hardcodes Material-Request/Purchase-Order parent fields
and appends to `items`. The Delivery Note needs `customer` and `posting_date`, and
its rows use `against_sales_order` / `so_detail` rather than
`sales_order` / `sales_order_item`.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py:794-856`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_delivery_note_rows_use_against_sales_order_and_so_detail(self):
        """Delivery Note Item has no sales_order/sales_order_item columns. Native
        delivered-qty tracking hangs off so_detail, and an engineering addition has
        no Sales Order line so both fields must stay empty for it."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        branch = source.split('if target_doctype == "Delivery Note":', 1)[1].split(
            "    _set_known_fields", 1
        )[0]
        self.assertIn("customer", branch)
        self.assertIn("posting_date", branch)

        rows = source.split("def _delivery_row_values", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("against_sales_order", rows)
        self.assertIn("so_detail", rows)
        self.assertNotIn('"sales_order_item": line.sales_order_item', rows)

    def test_delivery_row_values_omit_sales_order_link_for_added_lines(self):
        sold = AttrDict(item_code="I-1", item_name="One", description="d",
                        sales_order_item="SOI-1", uom="Nos", conversion_factor=1,
                        stock_uom="Nos", warehouse="WH - O", required_date=None)
        added = AttrDict(item_code="I-2", item_name="Two", description="d",
                         sales_order_item="", uom="Nos", conversion_factor=1,
                         stock_uom="Nos", warehouse="WH - O", required_date=None)
        revision = AttrDict(sales_order="SO-1", project="PROJ-1")

        sold_values = technical_procurement._delivery_row_values(revision, sold, 4)
        added_values = technical_procurement._delivery_row_values(revision, added, 3)

        self.assertEqual(sold_values["against_sales_order"], "SO-1")
        self.assertEqual(sold_values["so_detail"], "SOI-1")
        self.assertEqual(sold_values["qty"], 4)
        # Added lines were never sold, so they must not link to the Sales Order:
        # that link is what would pull them into an invoice.
        self.assertEqual(added_values["against_sales_order"], "")
        self.assertEqual(added_values["so_detail"], "")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: FAIL with `AttributeError: ... has no attribute '_delivery_row_values'`.

- [ ] **Step 3: Add the Delivery Note parent branch**

In `_build_target`, immediately after the `if target_doctype == "Purchase Order":`
block and before `_set_known_fields(target, values)`:

```python
    if target_doctype == "Delivery Note":
        customer = _text(_get(sales_order, "customer"))
        if not customer:
            frappe.throw(_("The Sales Order has no Customer."))
        values["customer"] = customer
        values["posting_date"] = nowdate()
```

- [ ] **Step 4: Extract the row builder and add the delivery variant**

Replace the row loop body in `_build_target` so it dispatches on target doctype.
Change the loop to:

```python
    item_meta = _meta(PROCUREMENT_ITEM_DOCTYPES.get(target_doctype))
    for line, stock_qty, route, action in prepared:
        lineage = {
            "technical_list": technical_list.name,
            "revision": revision.name,
            "revision_item": line.name,
            "line_key": line.line_key,
            "approval_hash": revision.approval_hash,
            "route": route.name,
            "action": action.name,
        }
        if target_doctype == "Delivery Note":
            row_values = _delivery_row_values(revision, line, stock_qty)
        else:
            row_values = _procurement_row_values(revision, line, stock_qty, schedule_date)
        row_values.update(_lineage_values(item_meta, lineage))
        target.append(TARGET_CHILD_TABLES[target_doctype], _filter_fields(item_meta, row_values))
    return target


def _procurement_row_values(revision, line, stock_qty, schedule_date):
    factor = flt(line.conversion_factor)
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
        "schedule_date": _safe_schedule_date(line.required_date or schedule_date),
        "project": revision.project,
        "sales_order": revision.sales_order,
        "sales_order_item": line.sales_order_item,
    }


def _delivery_row_values(revision, line, stock_qty):
    """Delivery Note Item row for one revision line.

    against_sales_order/so_detail are the Delivery Note's equivalents of
    sales_order/sales_order_item and are what native delivered-qty tracking reads.
    Engineering additions have no Sales Order line, so both stay empty and the row
    can never reach an invoice.
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
        "project": revision.project,
        "against_sales_order": _text(revision.sales_order) if sales_order_item else "",
        "so_detail": sales_order_item,
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): build Delivery Note targets from a revision

Adds the Delivery Note parent branch (customer, posting_date) and splits row
construction so delivery rows use against_sales_order/so_detail. Engineering
additions carry no Sales Order link, which is what keeps them off invoices.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Select the delivery remaining pool and expose the entrypoint

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py:296-320, 429-460`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_create_from_revision_picks_the_pool_matching_the_adapter(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def _create_from_revision", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_delivery_remaining_by_line(revision)", body)
        self.assertIn("_remaining_by_line(revision)", body)
        self.assertIn('adapter_key == "revision_to_delivery_note"', body)

    def test_create_delivery_note_is_whitelisted_and_takes_no_supplier(self):
        import inspect

        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn(
            '@frappe.whitelist()\ndef create_delivery_note(', source
        )
        signature = inspect.signature(technical_procurement.create_delivery_note)
        self.assertEqual(
            list(signature.parameters),
            ["revision", "selected_row_ids", "quantities"],
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: FAIL with `AttributeError: ... has no attribute 'create_delivery_note'`.

- [ ] **Step 3: Switch the remaining pool by adapter**

In `_create_from_revision`, replace `remaining = _remaining_by_line(revision)`
(line 452) with:

```python
    # Delivery consumes its own pool: a line can be fully procured and still
    # undelivered, and vice versa when stock was already on hand.
    remaining = (
        _delivery_remaining_by_line(revision)
        if adapter_key == "revision_to_delivery_note"
        else _remaining_by_line(revision)
    )
```

- [ ] **Step 4: Add the whitelisted entrypoint**

After `create_purchase_order` (line 319):

```python
@frappe.whitelist()
def create_delivery_note(revision, selected_row_ids=None, quantities=None) -> dict:
    return _create_from_revision(
        "revision_to_delivery_note",
        revision,
        selected_row_ids,
        quantities,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): add create_delivery_note entrypoint

_create_from_revision now selects the delivery remaining pool for the delivery
adapter, so procurement allowance and delivery allowance stay independent.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Validate Delivery Note rows and block native creation

Adding Delivery Note to `SUPPORTED_PROCUREMENT_DOCTYPES` in Task 3 already routes
it through `validate_procurement_document`. Three things need adjusting:

1. `_target_sales_order` must resolve Delivery Note rows so the native block can
   find the source Sales Order.
2. `_validate_target_row`'s project check rejects rows whose doctype has no usable
   project value.
3. The cumulative cap must use the delivery pool, not the procurement pool.
   `_is_root_allocation` already returns False for Delivery Note, so the existing
   procurement cross-document check correctly skips delivery rows.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py:321-413, 1000-1020`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_target_sales_order_resolves_delivery_note_rows(self):
        """Delivery Note Item stores the link as against_sales_order/so_detail.
        Without this the native block cannot find the source Sales Order and every
        Opportunity-origin Delivery Note would pass unchecked."""
        with patch.object(
            frappe_stub.db, "get_value", return_value="SO-1"
        ):
            self.assertEqual(
                technical_procurement._target_sales_order({"so_detail": "SOI-1"}),
                "SO-1",
            )
        self.assertEqual(
            technical_procurement._target_sales_order(
                {"against_sales_order": "SO-2", "so_detail": ""}
            ),
            "SO-2",
        )

    def test_delivery_cumulative_cap_uses_the_delivery_pool(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_delivered_stock_qty(", body)
        self.assertIn("exceeds the remaining delivery quantity", body)

    def test_native_delivery_note_from_sales_order_is_blocked(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn(
            "create {1} from the approved Technical List instead of directly from the Sales Order.",
            body,
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: FAIL — `_target_sales_order` returns `""` for a `so_detail`-only row, and
the delivery cap assertions find nothing.

- [ ] **Step 3: Resolve the Sales Order for Delivery Note rows**

In `_target_sales_order` (line 1000), replace the first three lines:

```python
def _target_sales_order(row):
    # Delivery Note Item uses against_sales_order/so_detail; the procurement
    # doctypes use sales_order/sales_order_item. _operational_sales_order already
    # normalises both, so delegate rather than duplicating the fallbacks.
    sales_order = _operational_sales_order(row)
    if sales_order:
        return sales_order
    material_request_item = _text(_get(row, "material_request_item"))
```

Delete the now-dead `sales_order`/`sales_order_item` lookup lines that preceded
`material_request_item`, and the `if not sales_order and material_request_item:`
guard becomes `if material_request_item:`. Keep the rest of the function unchanged.

- [ ] **Step 4: Make the project check tolerate doctypes without a project**

In `_validate_target_row`, replace the project check:

```python
    project = _target_project(doc, row)
    # Only enforce when the target actually carries a project value: some stock
    # doctypes have no project field at all, and an absent value is not a mismatch.
    if revision.project and project and project != revision.project:
        frappe.throw(_("Row {0}: Project does not match the technical revision.").format(_row_label(row)))
```

- [ ] **Step 5: Add the delivery cumulative cap**

In `validate_procurement_document`, replace the final `allocated_by_revision` block
with a branch on doctype:

```python
    if doctype == "Delivery Note":
        delivered_by_list = {}
        for revision_name, revision_item in line_totals:
            revision = revisions[revision_name]
            technical_list = _text(revision.technical_list)
            if technical_list not in delivered_by_list:
                delivered_by_list[technical_list] = _delivered_stock_qty(
                    technical_list,
                    exclude_doctype=doctype,
                    exclude_name=_text(_get(doc, "name")),
                )
            source_line = _revision_lines(revision)[revision_item]
            key = _allocation_key(source_line)
            existing = delivered_by_list[technical_list].get(key, 0)
            if existing + line_totals[(revision_name, revision_item)] > _line_stock_qty(source_line) + 1e-9:
                frappe.throw(
                    _("Row {0}: quantity exceeds the remaining delivery quantity.").format(
                        _row_label(source_line)
                    )
                )
        return

    allocated_by_revision = {}
    for revision_name, revision_item in root_totals:
        if revision_name not in allocated_by_revision:
            allocated_by_revision[revision_name] = _allocated_stock_qty(
                revision_name,
                exclude_doctype=doctype,
                exclude_name=_text(_get(doc, "name")),
            )
        source_qty = _line_stock_qty(_revision_lines(revisions[revision_name])[revision_item])
        existing = allocated_by_revision[revision_name].get(revision_item, 0)
        if existing + root_totals[(revision_name, revision_item)] > source_qty + 1e-9:
            frappe.throw(
                _("Technical procurement quantity exceeds the revision item's remaining quantity.")
            )
```

- [ ] **Step 6: Do not deadlock the Pick List delivery route**

This step is what makes this plan safe to deploy on its own, and it must not be
skipped. `delivery_note_reservation_guard` **forces** the Pick List route whenever a
Sales Order row has reserved stock. Pick Lists are still built from the Sales Order
until Plan 2 lands, so their rows carry no technical lineage — and the block added
in Step 5 would refuse those Delivery Notes with no way through. Reserved-stock
deliveries would be completely blocked.

The Pick List itself is already gated by `validate_operational_document`, which
requires an approved revision to exist, so enforcement is not lost by allowing these
rows through.

Add the skip to the no-lineage branch in `validate_procurement_document`, replacing
the `source = _procurement_source(doc, row)` block:

```python
        # Rows sourced from a Pick List are allowed through without lineage until
        # Pick Lists become revision-aware (Plan 2). The Pick List is already gated
        # by validate_operational_document, and delivery_note_reservation_guard
        # forces this route for reserved stock, so blocking here would make
        # reserved-stock deliveries impossible. Remove this skip in Plan 2.
        if doctype == "Delivery Note" and _text(_get(row, "pick_list_item")):
            continue

        source = _procurement_source(doc, row)
```

Add the test:

```python
    def test_pick_list_sourced_delivery_rows_are_not_blocked_yet(self):
        """delivery_note_reservation_guard forces the Pick List route for reserved
        stock, and Pick Lists carry no lineage until Plan 2, so blocking these rows
        would make reserved-stock delivery impossible."""
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        body = source.split("def validate_procurement_document", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('_text(_get(row, "pick_list_item"))', body)
        self.assertIn("Remove this skip in Plan 2.", body)
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -25
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): validate Delivery Note lineage and cap deliveries

Delivery Notes now go through row-lineage validation: rows carrying lineage are
checked against the approved revision and capped by the delivery pool, and rows
with no lineage under a policy-covered Sales Order are refused with a pointer to
the Technical List. _target_sales_order delegates to _operational_sales_order so
against_sales_order/so_detail resolve, and the project check no longer treats an
absent project value as a mismatch.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Wire the hook

**Files:**
- Modify: `orderlift/hooks.py:449-455`
- Test: `orderlift/tests/test_technical_list_integration.py`

- [ ] **Step 1: Write the failing test**

In `test_technical_list_integration.py`, extend
`test_hooks_wire_lifecycle_procurement_and_assets`:

```python
        guard = "orderlift.orderlift_logistics.technical_procurement.validate_procurement_document"
        for doctype in ("Material Request", "Request for Quotation", "Purchase Order"):
            self.assertIn(guard, hooks.doc_events[doctype]["before_validate"])
        # Delivery Note now carries row-level lineage validation, not just the
        # "an approved revision must exist" gate.
        delivery = hooks.doc_events["Delivery Note"]["before_validate"]
        self.assertIn(guard, delivery)
        operational_guard = "orderlift.orderlift_logistics.technical_procurement.validate_operational_document"
        self.assertIn(operational_guard, delivery)
        # Row validation must run before company scoping rewrites the company.
        self.assertLess(delivery.index(guard), delivery.index("orderlift.company_scope.apply_transaction_company_scope"))
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -20
```

Expected: FAIL with `AssertionError: '...validate_procurement_document' not found in [...]`.

- [ ] **Step 3: Add the hook**

In `hooks.py`, the `"Delivery Note"` `before_validate` list (line 451):

```python
        "before_validate": [
            "orderlift.orderlift_logistics.technical_procurement.validate_procurement_document",
            "orderlift.orderlift_logistics.technical_procurement.validate_operational_document",
            "orderlift.company_scope.apply_transaction_company_scope",
            "orderlift.orderlift_crm.party_propagation.sync_downstream_sales_party_context",
            "orderlift.orderlift_sales.utils.commercial_presentation.inherit_commercial_presentation",
        ],
```

`validate_operational_document` is kept deliberately: it enforces "an approved
revision must exist" for a policy-covered Sales Order even when no row resolves to
a revision line, which the row-level guard alone would not catch.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -20
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/hooks.py \
        apps/orderlift/orderlift/tests/test_technical_list_integration.py
git commit -m "feat(hooks): validate Delivery Note technical lineage on before_validate

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: Seed the delivery route step

`get_available_actions` only surfaces actions reachable from an enabled route, so
without a route step the button never appears. The step ships ungated
(`required_previous_action` empty) per spec rule 7.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py:61-70` and after `_ensure_internal_material_request_route`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_delivery_route_step_is_seeded_ungated(self):
        source = (APP_ROOT / "orderlift_logistics" / "technical_procurement.py").read_text()
        self.assertIn("_ensure_delivery_route_step()", source)
        body = source.split("def _ensure_delivery_route_step", 1)[1].split("\ndef ", 1)[0]
        # Spec rule 7: delivery is not gated on procurement.
        self.assertIn('"required_previous_action": ""', body)
        self.assertIn('"enabled": 1', body)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -20
```

Expected: FAIL — `_ensure_delivery_route_step()` is not in the source.

- [ ] **Step 3: Implement the seeding**

Add after `_ensure_internal_material_request_route`:

```python
def _ensure_delivery_route_step() -> None:
    """Append the delivery action to every enabled route that lacks it.

    Ungated by design (spec rule 7): stock may already be on hand, so delivery
    must not wait on a purchase. A company can set required_previous_action on its
    own route later if it wants procurement-first delivery.
    """
    action = frappe.db.get_value(
        "Technical Procurement Action",
        {"adapter_key": "revision_to_delivery_note"},
        "name",
    )
    if not action:
        return
    routes = frappe.get_all(
        "Technical Procurement Route", filters={"enabled": 1}, pluck="name"
    )
    for route_name in routes:
        route = frappe.get_doc("Technical Procurement Route", route_name)
        if any(_text(step.action) == action for step in route.steps or []):
            continue
        sequence = max([cint(step.sequence) for step in route.steps or []] or [0]) + 10
        route.append(
            "steps",
            {"action": action, "sequence": sequence, "required_previous_action": ""},
        )
        route.save(ignore_permissions=True)
```

- [ ] **Step 4: Call it from `after_migrate`**

At the end of `after_migrate` (line 69), after `_ensure_internal_material_request_route()`:

```python
    _ensure_delivery_route_step()
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -20
```

Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): seed an ungated delivery route step on migrate

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Wire the UI actions

Both JS entrypoints branch two ways today (Purchase Order versus "else Material
Request"), so a delivery action would wrongly call `create_material_request`.

**Files:**
- Modify: `orderlift/public/js/sales_order_technical_list_20260815f.js:103-165`
- Modify: `orderlift/orderlift_sig/doctype/sales_order_technical_list_revision/sales_order_technical_list_revision.js:101`
- Test: `orderlift/tests/test_technical_list_integration.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_ui_dispatches_all_three_adapters(self):
        page = (APP_ROOT / "public" / "js" / "sales_order_technical_list_20260815f.js").read_text()
        form = (
            APP_ROOT
            / "orderlift_sig"
            / "doctype"
            / "sales_order_technical_list_revision"
            / "sales_order_technical_list_revision.js"
        ).read_text()
        for source in (page, form):
            self.assertIn("revision_to_delivery_note", source)
            self.assertIn(
                "orderlift.orderlift_logistics.technical_procurement.create_delivery_note",
                source,
            )
```

Add it to `TestTechnicalListIntegration`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /root/erp-deploy/apps/orderlift
python -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -20
```

Expected: FAIL with `'revision_to_delivery_note' not found`.

- [ ] **Step 3: Add the adapter method map to the page JS**

In `public/js/sales_order_technical_list_20260815f.js`, add above
`runProcurementAction` (line 103). `PROCUREMENT` is the existing module-path
constant in this file:

```javascript
    const ADAPTER_METHODS = {
        revision_to_material_request: `${PROCUREMENT}.create_material_request`,
        revision_to_purchase_order: `${PROCUREMENT}.create_purchase_order`,
        revision_to_delivery_note: `${PROCUREMENT}.create_delivery_note`,
    };
```

- [ ] **Step 4: Dispatch three ways in the page JS**

Replace the `method` assignment inside `runProcurementAction` (lines 112-114).
Current code falls back to `create_material_request` for anything that is not a
Purchase Order, so a delivery action would create a Material Request:

```javascript
        const method = ADAPTER_METHODS[action.adapter_key];
        if (!method) {
            frappe.msgprint(__("Unsupported technical procurement action."));
            return;
        }
        const response = await frappe.call({ method, args, freeze: true, freeze_message: __("Creating document...") });
```

- [ ] **Step 5: Intercept the native Delivery Note entry**

In `installNativeCreateGuard`, the `labels` array already includes
`"Delivery Note"` and the not-approved path already blocks it. But when a revision
**is** approved, `Delivery Note` currently falls through every branch and native
creation proceeds — that is the reported bug. Insert this immediately before the
final `if (["Purchase Order", "Request for Quotation"].includes(label))` block:

```javascript
            if (label === "Delivery Note") {
                event.preventDefault();
                event.stopImmediatePropagation();
                const action = (payload.actions || []).find((row) => row.adapter_key === "revision_to_delivery_note");
                if (action) runProcurementAction(action, payload);
                else frappe.msgprint(__("The approved Technical List has no remaining quantity for a Delivery Note."));
                return;
            }
```

Leave the `Pick List` label alone: it is handled in Plan 2, and until then the
not-approved guard plus `validate_operational_document` remain its only gates.

- [ ] **Step 6: Dispatch three ways in the revision form JS**

In `orderlift_sig/doctype/sales_order_technical_list_revision/sales_order_technical_list_revision.js`,
replace the `method` ternary (lines 105-107):

```javascript
            const METHODS = {
                revision_to_material_request: "orderlift.orderlift_logistics.technical_procurement.create_material_request",
                revision_to_purchase_order: "orderlift.orderlift_logistics.technical_procurement.create_purchase_order",
                revision_to_delivery_note: "orderlift.orderlift_logistics.technical_procurement.create_delivery_note",
            };
            const method = METHODS[action.adapter_key];
            if (!method) {
                frappe.msgprint(__("Unsupported technical procurement action."));
                return;
            }
```

The button label already comes from `action.label`, so the seeded
`Create Delivery Note` label appears with no further change. The supplier prompt is
already gated on `revision_to_purchase_order` in both files and needs no edit — the
delivery adapter takes no supplier.

- [ ] **Step 7: Run the test to verify it passes**

```bash
python -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -20
```

Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
cd /root/erp-deploy
git add apps/orderlift/orderlift/public/js/sales_order_technical_list_20260815f.js \
        apps/orderlift/orderlift/orderlift_sig/doctype/sales_order_technical_list_revision/sales_order_technical_list_revision.js \
        apps/orderlift/orderlift/tests/test_technical_list_integration.py
git commit -m "feat(ui): dispatch the delivery adapter and guard native Delivery Note creation

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Document the behaviour

**Files:**
- Modify: `docs/sales_order_technical_lists.md`

- [ ] **Step 1: Add a "Delivery from the Technical List" section**

Cover, in prose matching the existing document's tone: that delivery follows the
approved revision; that the delivery pool is separate from procurement allowance
and anchored on the Technical List so a new revision does not reset delivered
quantities; that approved execution qty is a hard cap raised only by a new
revision; that engineering additions deliver without a Sales Order link and
therefore never reach an invoice; that billing stays on the Sales Order at full
contract price; that partial deliveries work per line; that native
Delivery-Note-from-Sales-Order is blocked under policy; that the route step is
ungated and can be gated per route; and that commercial presentation
(`With details` / `Without details`) still governs what the customer sees.

- [ ] **Step 2: Update the Purpose paragraph**

The opening currently scopes Technical Lists to procurement
("the approved execution definition used for procurement"). Change it to cover
procurement **and delivery**, otherwise the document contradicts the feature.

- [ ] **Step 3: Commit**

```bash
cd /root/erp-deploy
git add docs/sales_order_technical_lists.md
git commit -m "docs: describe delivery from the approved Technical List

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 11: Full verification

- [ ] **Step 1: Run every affected module separately**

These modules stub `sys.modules`, so a combined run is meaningless. One command per
module:

```bash
cd /root/erp-deploy/apps/orderlift
for m in test_technical_procurement test_technical_list_integration \
         test_sales_order_technical_list test_menu_access test_company_scope \
         test_boot test_price_list_scope; do
  echo "=== $m"
  python -m unittest orderlift.tests.$m 2>&1 | tail -3
done
```

Expected: `OK` for every module. `test_access_command_center` has two failures that
predate this work — do not treat them as regressions and do not fix them here.

- [ ] **Step 2: Deploy**

`apps/orderlift` is bind-mounted, so the files are already in place, but gunicorn
caches imported modules and the merged hook registry lives in Redis. A restart
alone is **not** sufficient for the `hooks.py` change.

```bash
docker exec app-cs08owwk4wcw4k000kw0kg44-083312225264 \
  bench --site erp.ecomepivot.com migrate
docker exec redis-cache-cs08owwk4wcw4k000kw0kg44-083312244763 redis-cli FLUSHALL
docker restart app-cs08owwk4wcw4k000kw0kg44-083312225264 \
               queue-default-cs08owwk4wcw4k000kw0kg44 \
               queue-short-cs08owwk4wcw4k000kw0kg44 \
               queue-long-cs08owwk4wcw4k000kw0kg44 \
               scheduler-cs08owwk4wcw4k000kw0kg44
```

Resolve the exact container names first with `docker ps --format '{{.Names}}'` —
they carry per-deploy suffixes. Flush **redis-cache only**; never `redis-queue`
(live jobs) or `redis-socketio`. Run `bench` in `app-*`, never `backend-*` (nginx,
read-only sites volume).

- [ ] **Step 3: Confirm the restart actually took**

A 200 from curl proves nothing — nginx answers even when gunicorn is stale.

```bash
docker inspect app-cs08owwk4wcw4k000kw0kg44-083312225264 --format '{{.State.StartedAt}}'
```

Expected: a timestamp **after** the last edit.

- [ ] **Step 4: Verify the lineage fields installed**

```bash
docker exec app-cs08owwk4wcw4k000kw0kg44-083312225264 \
  bench --site erp.ecomepivot.com execute frappe.client.get_count \
  --kwargs '{"doctype":"Custom Field","filters":{"dt":"Delivery Note Item","fieldname":["like","custom_technical%"]}}'
```

Expected: `7`.

- [ ] **Step 5: Manual acceptance in the Desk**

1. Open a submitted Sales Order in a policy-covered company with an approved
   revision. Confirm **Create Delivery Note** appears.
2. Create one with a partial quantity on one line. Confirm the Delivery Note is a
   draft, rows carry the `custom_technical_*` lineage, and sold-linked rows have
   `against_sales_order` / `so_detail` set while an added row has neither.
3. Repeat and confirm the second Delivery Note offers only the remaining quantity.
4. Attempt native `Create > Delivery Note` from the Sales Order and confirm the
   block message names the Technical List.
5. Approve a new revision raising one line's `execution_qty`, then confirm the
   newly available quantity is the **increase only** — not the full quantity again.
   This is the regression that matters most; a database-free unit test cannot cover it.

- [ ] **Step 6: Document the before-state for the original report**

Compare the items of existing Delivery Notes linked to
`SAL-ORD-2026-00103~BENFRAIH80` and `SAL-ORD-2026-00135~115GRV` against their
revision lines, and record that new Delivery Notes now carry only revision items.
Existing documents are not retrofitted (spec "Out of scope").

---

## Follow-up plans

- **Plan 2 — Pick List from the Technical List.** Needs `TARGET_CHILD_TABLES["Pick List"] = "locations"`, `PROCUREMENT_ITEM_DOCTYPES["Pick List"] = "Pick List Item"`, and a stock-only row filter: Pick List Item has no `is_stock_item` and no `project`, and services cannot be picked. Must also reconcile `pick_list_override.validate_sales_order`, which caps picking at the Sales Order's open qty (`qty - delivered_qty`) and would therefore block a revision that raised execution qty above the sold qty.
- **Plan 3 — Sales Order auto-close.** Close when every execution-relevant line of the approved revision is fully delivered, services included; reopen when a later revision raises a quantity. Uses the native `Closed` status and does not touch `delivery_status`.
- **Plan 4 — Retire the orphaned shared price lists** (unrelated, carried over from the earlier session): three Installation lists with `custom_is_shared_from` set, no `Price List Sharing` rows, 1,289 Item Prices, and 3 stale Purchase Agent Rules rows.
