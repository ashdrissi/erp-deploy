# Sales Order Auto-Close and Invoice Source Guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close a Sales Order automatically once every execution-relevant line of its approved Technical List revision is fully delivered, and refuse to raise a Sales Invoice from a Delivery Note that carries technical lineage.

**Architecture:** A new focused module owns closure, because it is a lifecycle concern rather than an adapter concern and it reads the delivery pool that already exists. The invoice guard joins the existing lineage validators in `technical_procurement.py`, since it is the same family of check. A hidden flag on the Sales Order records that a close was automatic, so a reopen never overrides a human decision.

**Tech Stack:** Frappe/ERPNext v15 app (`orderlift`), Python 3, plain `unittest` with `frappe` stubbed at import (no database).

**Spec:** `docs/superpowers/specs/2026-08-17-delivery-from-technical-list-design.md` — rules 10, 18 and 19 govern this plan. Rules 1-9 and 11-17 are already implemented and deployed.

**Branch:** create `feat/closure-and-invoicing` in a worktree. **Do not work in `/root/erp-deploy`** — it is bind-mounted into the live production containers.

---

## Preflight

- [ ] **Step 1: Create the worktree and confirm the baseline**

```bash
cd /root/erp-deploy
git worktree add -b feat/closure-and-invoicing /root/erp-deploy-wt/closure main
cd /root/erp-deploy-wt/closure/apps/orderlift
```

Use `python3`, not `python`. Test modules stub `sys.modules`, so **one module per command** — combined runs give bogus results.

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_sales_invoice_hooks 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_sales_order_technical_list 2>&1 | tail -3
```

Expected: 70 OK, 7 OK, and record whatever the other two report.

These 14 modules already fail on `main` and are **not** your concern at any point:
`test_access_command_center`, `test_admin_permissions_setup`, `test_business_type_access`, `test_e2e_pricing_chain`, `test_forecast_single_document_mode`, `test_material_request_no_price_list`, `test_partner_campaign_schema`, `test_pricing_builder_metadata`, `test_pricing_simulator_retirement`, `test_purchase_agent_rules`, `test_quotation_commission_assignment`, `test_sig_sidebar_setup`, `test_simplified_access_model`, `test_update_article_buying_prices`.

---

## Verified facts — read before starting

Confirmed against the installed ERPNext and the current tree, not assumed.

- **`Sales Order.update_status(status)`** calls `check_modified_date()` first, which throws
  *"Sales Order X has been modified. Please refresh."* if the in-memory doc is stale. Always
  `frappe.get_doc` immediately before calling it. It then calls `set_status(update=True, ...)`,
  `update_reserved_qty()`, `update_subcontracting_order_status()` and `notify_update()`.
- **Reopen is `update_status("Draft")`** on a submitted Sales Order. `set_status` recomputes the
  real status from `per_delivered` / `per_billed`; "Draft" is the reset signal, not a literal
  target status. For `docstatus == 1` it also re-runs `check_credit_limit()`.
- **A Closed Sales Order cannot be cancelled** — `sales_order.py:537` throws *"Closed order
  cannot be cancelled. Unclose to cancel."* So auto-closing blocks cancellation until reopened.
  This is native behaviour for any closed order, but it is a new consequence for these Sales
  Orders and must be documented.
- **`Sales Invoice Item` has both `delivery_note` and `dn_detail`.** Either can carry the link,
  so check both.
- **An existing assertion must flip.** `tests/test_technical_list_integration.py` contains
  `assertNotIn("technical_procurement", json.dumps(hooks.doc_events.get("Sales Invoice", {})))`.
  Its intent was "this feature stays out of invoicing"; rule 18 deliberately guards invoicing.
  Replace it with a positive assertion naming *only* the new guard, so the boundary is still
  asserted — do not simply delete it.
- **Allocation helpers are public** in `orderlift_logistics/technical_allocation.py`:
  `budget_by_key`, `delivered_stock_qty`, `allocation_key`, `line_stock_qty`, `revision_lines`.
  Import them; do not reimplement.
- **Do not shadow an imported helper with a local variable.** This has already caused one
  `UnboundLocalError` on every technical Delivery Note validation in this codebase. Pick
  distinct local names.
- **Test doubles:** use the existing `revision_stub(**values)` helper for revision doubles —
  `AttrDict` subclasses `dict`, so `.items` resolves to `dict.items` rather than the child
  table. `AttrDict` is fine for line and row doubles.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `orderlift/orderlift_logistics/technical_closure.py` | decide and apply auto-close / reopen | create |
| `orderlift/orderlift_logistics/technical_procurement.py` | add the Sales Invoice source guard | modify |
| `orderlift/orderlift_sig/technical_list.py` | install the auto-close flag field | modify |
| `orderlift/hooks.py` | wire Delivery Note, Revision and Sales Invoice events | modify |
| `orderlift/tests/test_technical_closure.py` | closure unit tests | create |
| `orderlift/tests/test_technical_procurement.py` | invoice guard tests | modify |
| `orderlift/tests/test_technical_list_integration.py` | hook wiring | modify |
| `docs/sales_order_technical_lists.md` | documentation | modify |

Closure goes in its own module rather than into `technical_procurement.py` (~1450 lines): it is
a lifecycle concern, not an adapter, and it only needs the public allocation helpers.

---

## Task 1: Install the auto-close flag

Rule 19. Without this, a reopen cannot tell an automatic close from one a person made
deliberately, and would silently override the person.

**Files:**
- Modify: `orderlift/orderlift_sig/technical_list.py` (its `after_migrate` already installs the
  Sales Order and Company technical fields — follow that existing pattern exactly)
- Test: `orderlift/tests/test_technical_list_integration.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_auto_close_flag_is_installed_on_the_sales_order(self):
        """Rule 19: only a close this feature owns may be reopened, otherwise an
        auto-reopen overrides a decision a person made for their own reasons."""
        core = (APP_ROOT / "orderlift_sig" / "technical_list.py").read_text()
        self.assertIn("custom_technical_auto_closed", core)
        # Never operator-editable: it records what the system did.
        block = core.split("custom_technical_auto_closed", 1)[1][:400]
        self.assertIn('"read_only": 1', block)
        self.assertIn('"hidden": 1', block)
        self.assertIn('"fieldtype": "Check"', block)
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/closure/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -12
```

Expected: FAIL, `'custom_technical_auto_closed' not found`.

- [ ] **Step 3: Add the field**

Read how `technical_list.py`'s `after_migrate` declares its existing Sales Order custom fields
and add one in the same shape:

```python
            {
                "fieldname": "custom_technical_auto_closed",
                "label": "Technical Auto Closed",
                "fieldtype": "Check",
                "insert_after": <the last existing Sales Order technical field>,
                "read_only": 1,
                "hidden": 1,
                "no_copy": 1,
            },
```

`no_copy` matters: an amended Sales Order must not inherit a close it did not earn.

- [ ] **Step 4: Run and confirm pass, then commit**

```bash
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_sales_order_technical_list 2>&1 | tail -3
```

```bash
cd /root/erp-deploy-wt/closure
git add apps/orderlift/orderlift/orderlift_sig/technical_list.py \
        apps/orderlift/orderlift/tests/test_technical_list_integration.py
git commit -m "feat(technical-list): install the auto-close ownership flag

Records that a Sales Order close was performed by the technical-list feature, so the
reopen required by rule 10 never overrides a close a person made deliberately.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Decide whether execution is fully delivered

Pure decision logic, no side effects — so it is fully unit-testable without a database.

**Files:**
- Create: `orderlift/orderlift_logistics/technical_closure.py`
- Create: `orderlift/tests/test_technical_closure.py`

- [ ] **Step 1: Write the failing tests**

Create `orderlift/tests/test_technical_closure.py`. Copy the stub preamble from
`tests/test_technical_procurement.py` (the `frappe` / `frappe.utils` / `frappe.model.document`
module stubs, `AttrDict`, and `revision_stub`) — that pattern is required for these
database-free tests to import at all.

```python
    def test_execution_is_complete_only_when_every_key_is_fully_delivered(self):
        revision = revision_stub(
            name="TLR-1",
            technical_list="TL-1",
            items=[
                AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                         execution_stock_qty=10, execution_relevant=1),
                AttrDict(name="R2", sales_order_item="", item_code="I-2",
                         execution_stock_qty=4, execution_relevant=1),
                AttrDict(name="R3", sales_order_item="SOI-3", item_code="I-3",
                         execution_stock_qty=7, execution_relevant=0),
            ],
        )
        with patch.object(technical_closure, "delivered_stock_qty",
                          return_value={"SOI-1": 10, "item::I-2": 4}):
            self.assertTrue(technical_closure.execution_fully_delivered(revision))
        # One unit short on the addition is still short.
        with patch.object(technical_closure, "delivered_stock_qty",
                          return_value={"SOI-1": 10, "item::I-2": 3}):
            self.assertFalse(technical_closure.execution_fully_delivered(revision))
        # An excluded line never holds the Sales Order open (rule 10).
        with patch.object(technical_closure, "delivered_stock_qty",
                          return_value={"SOI-1": 10, "item::I-2": 4, "SOI-3": 0}):
            self.assertTrue(technical_closure.execution_fully_delivered(revision))

    def test_a_revision_with_nothing_approved_is_not_complete(self):
        """Guards against closing a Sales Order whose revision has no execution-relevant
        lines at all, which would read as "delivered" under an all() over an empty set."""
        revision = revision_stub(name="TLR-2", technical_list="TL-2", items=[])
        with patch.object(technical_closure, "delivered_stock_qty", return_value={}):
            self.assertFalse(technical_closure.execution_fully_delivered(revision))

    def test_over_delivery_still_counts_as_complete(self):
        revision = revision_stub(
            name="TLR-3", technical_list="TL-3",
            items=[AttrDict(name="R1", sales_order_item="SOI-1", item_code="I-1",
                            execution_stock_qty=5, execution_relevant=1)],
        )
        with patch.object(technical_closure, "delivered_stock_qty",
                          return_value={"SOI-1": 6}):
            self.assertTrue(technical_closure.execution_fully_delivered(revision))
```

- [ ] **Step 2: Run and confirm failure**

```bash
cd /root/erp-deploy-wt/closure/apps/orderlift
python3 -m unittest orderlift.tests.test_technical_closure -v 2>&1 | tail -10
```

Expected: FAIL, no module `technical_closure`.

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

from orderlift.orderlift_logistics.technical_allocation import (
    budget_by_key,
    delivered_stock_qty,
)


AUTO_CLOSED_FIELD = "custom_technical_auto_closed"


def execution_fully_delivered(revision) -> bool:
    """True when every execution-relevant line of the revision has been delivered.

    Compared per allocation key rather than per line, because distinct lines can share
    one key (engineering additions collapse to "item::<item_code>") and the delivered
    pool is keyed the same way. Services and non-stock lines count: they reach delivery
    through the Delivery Note, which is why rule 11 puts them on it.

    A revision with nothing execution-relevant is deliberately *not* complete -- an
    all() over an empty budget would otherwise read as fully delivered and close a
    Sales Order that has delivered nothing.
    """
    budget = budget_by_key(revision)
    if not budget:
        return False
    delivered = delivered_stock_qty(revision.technical_list)
    return all(
        flt(delivered.get(key, 0)) + 1e-9 >= flt(total) for key, total in budget.items()
    )
```

- [ ] **Step 4: Run and confirm pass, then commit**

```bash
python3 -m unittest orderlift.tests.test_technical_closure 2>&1 | tail -3
```

```bash
cd /root/erp-deploy-wt/closure
git add apps/orderlift/orderlift/orderlift_logistics/technical_closure.py \
        apps/orderlift/orderlift/tests/test_technical_closure.py
git commit -m "feat(technical-closure): decide when execution is fully delivered

Compared per allocation key so shared buckets are handled, and an empty budget is
deliberately not complete so a Sales Order with nothing delivered never closes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Apply the close and the reopen

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_closure.py`
- Test: `orderlift/tests/test_technical_closure.py`

- [ ] **Step 1: Write the failing tests**

```python
    def test_closes_only_an_open_policy_sales_order_and_records_ownership(self):
        calls = []
        so = AttrDict(name="SO-1", doctype="Sales Order", docstatus=1, status="To Deliver",
                      custom_technical_auto_closed=0)
        so.update_status = lambda status: calls.append(status)
        so.db_set = lambda field, value, **kw: calls.append((field, value))
        with patch.object(technical_closure, "_policy_revision", return_value=("rev", so)), \
             patch.object(technical_closure, "execution_fully_delivered", return_value=True):
            technical_closure.apply_sales_order_closure("SO-1")
        self.assertIn("Closed", calls)
        self.assertIn((technical_closure.AUTO_CLOSED_FIELD, 1), calls)
        # The flag must be written only after the close succeeds.
        self.assertLess(calls.index("Closed"),
                        calls.index((technical_closure.AUTO_CLOSED_FIELD, 1)))

    def test_reopens_only_a_close_it_owns(self):
        """A Sales Order closed by a person must never be reopened by this feature."""
        for owned, expected in ((1, ["Draft"]), (0, [])):
            calls = []
            so = AttrDict(name="SO-1", doctype="Sales Order", docstatus=1, status="Closed",
                          custom_technical_auto_closed=owned)
            so.update_status = lambda status: calls.append(status)
            so.db_set = lambda field, value, **kw: None
            with patch.object(technical_closure, "_policy_revision", return_value=("rev", so)), \
                 patch.object(technical_closure, "execution_fully_delivered", return_value=False):
                technical_closure.apply_sales_order_closure("SO-1")
            self.assertEqual(calls, expected, f"auto_closed={owned}")

    def test_does_nothing_when_already_in_the_right_state(self):
        calls = []
        so = AttrDict(name="SO-1", doctype="Sales Order", docstatus=1, status="Closed",
                      custom_technical_auto_closed=1)
        so.update_status = lambda status: calls.append(status)
        so.db_set = lambda field, value, **kw: calls.append((field, value))
        with patch.object(technical_closure, "_policy_revision", return_value=("rev", so)), \
             patch.object(technical_closure, "execution_fully_delivered", return_value=True):
            technical_closure.apply_sales_order_closure("SO-1")
        self.assertEqual(calls, [])

    def test_skips_a_sales_order_with_no_approved_revision(self):
        calls = []
        with patch.object(technical_closure, "_policy_revision", return_value=(None, None)):
            technical_closure.apply_sales_order_closure("SO-1")
        self.assertEqual(calls, [])
```

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m unittest orderlift.tests.test_technical_closure -v 2>&1 | tail -10
```

Expected: FAIL, `has no attribute 'apply_sales_order_closure'`.

- [ ] **Step 3: Implement**

```python
def apply_sales_order_closure(sales_order: str) -> None:
    """Close or reopen a Sales Order to match its approved revision's delivery state.

    Fetched fresh every time: update_status calls check_modified_date, so a stale doc
    makes the close throw "has been modified" after any unrelated concurrent save.
    """
    revision, source = _policy_revision(sales_order)
    if not revision or not source:
        return
    if cint(source.get("docstatus")) != 1:
        return

    complete = execution_fully_delivered(revision)
    closed = source.get("status") == "Closed"
    owned = cint(source.get(AUTO_CLOSED_FIELD))

    if complete and not closed:
        source.update_status("Closed")
        # Written only after the close succeeds, so a failed close never leaves the
        # flag claiming ownership of a state that was not reached.
        source.db_set(AUTO_CLOSED_FIELD, 1, update_modified=False)
        return
    if not complete and closed and owned:
        source.update_status("Draft")
        source.db_set(AUTO_CLOSED_FIELD, 0, update_modified=False)
```

Also implement `_policy_revision(sales_order)`, returning `(revision_doc, sales_order_doc)` or
`(None, None)`. It must:
- `frappe.get_doc("Sales Order", sales_order)` — **fresh**, never a passed-in doc;
- return `(None, None)` unless `technical_procurement._technical_policy_applies(source)`;
- resolve the Technical List for that Sales Order and its `current_revision`, returning
  `(None, None)` when there is no submitted current revision.

Import `_technical_policy_applies` from `technical_procurement`. That direction is safe —
`technical_procurement` must **not** import `technical_closure`, or you create a cycle. Wire
the hooks to `technical_closure` directly instead.

- [ ] **Step 4: Add the hook entrypoints**

```python
def evaluate_on_delivery_note(doc, method=None) -> None:
    """Re-evaluate closure for every Sales Order a technical Delivery Note touches."""
    if not doc or doc.get("doctype") != "Delivery Note":
        return
    sales_orders = {
        (row.get("against_sales_order") or "").strip()
        for row in (doc.get("items") or [])
        if (row.get("custom_technical_revision") or "").strip()
    }
    sales_orders.discard("")
    if not sales_orders:
        # An additions-only delivery carries no Sales Order link on any row, so fall
        # back to the revision's own Sales Order.
        sales_orders = _sales_orders_from_lineage(doc)
    for name in sorted(sales_orders):
        apply_sales_order_closure(name)


def evaluate_on_revision(doc, method=None) -> None:
    """A new revision can raise a quantity, which must reopen a closed Sales Order."""
    if not doc or not (doc.get("sales_order") or "").strip():
        return
    apply_sales_order_closure(doc.get("sales_order"))
```

`_sales_orders_from_lineage(doc)` resolves the Sales Order via each row's
`custom_technical_revision` → revision → `sales_order`. This matters: an additions-only
delivery has no `against_sales_order` on any row by rule 3, so without it such a delivery
never triggers closure.

- [ ] **Step 5: Run and confirm pass, then commit**

```bash
python3 -m unittest orderlift.tests.test_technical_closure 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
```

```bash
cd /root/erp-deploy-wt/closure
git add apps/orderlift/orderlift/orderlift_logistics/technical_closure.py \
        apps/orderlift/orderlift/tests/test_technical_closure.py
git commit -m "feat(technical-closure): close and reopen the Sales Order on delivery state

Closes when every execution-relevant line of the approved revision is delivered, and
reopens only a close this feature owns. The Sales Order is always fetched fresh because
update_status calls check_modified_date.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Refuse a Sales Invoice raised from a technical Delivery Note

Rule 18. ERPNext's `make_sales_invoice` maps every Delivery Note row with no `so_detail`
condition, so invoicing from the delivery pulls engineering additions onto the invoice — and
billing must follow *sold* quantities, not delivered ones (rule 2).

The guard goes on Sales Invoice `before_validate` rather than only overriding
`make_sales_invoice`, so no path evades it — including a manually built invoice.

**Files:**
- Modify: `orderlift/orderlift_logistics/technical_procurement.py`
- Test: `orderlift/tests/test_technical_procurement.py`

- [ ] **Step 1: Write the failing test**

```python
    def test_sales_invoice_from_a_technical_delivery_note_is_refused(self):
        """Rule 18. ERPNext maps Delivery Note rows onto the invoice with no so_detail
        condition, so an engineering addition would be billed despite rule 3 -- and a
        short delivery would under-bill against rule 2."""
        row = AttrDict(idx=1, item_code="I-1", delivery_note="MAT-DN-1", dn_detail="DNI-1")
        doc = AttrDict(doctype="Sales Invoice", docstatus=0, is_return=0, items=[row])
        with patch.object(
            frappe_stub.db, "get_value", return_value="TLR-1"
        ), self.assertRaisesRegex(ValueError, "from the Sales Order"):
            technical_procurement.validate_sales_invoice_source(doc)

    def test_sales_invoice_from_a_plain_delivery_note_is_allowed(self):
        """A Delivery Note predating the feature carries no lineage and stays
        invoiceable -- historical documents are not retrofitted."""
        row = AttrDict(idx=1, item_code="I-1", delivery_note="MAT-DN-OLD", dn_detail="DNI-9")
        doc = AttrDict(doctype="Sales Invoice", docstatus=0, is_return=0, items=[row])
        with patch.object(frappe_stub.db, "get_value", return_value=None):
            technical_procurement.validate_sales_invoice_source(doc)

    def test_sales_invoice_raised_from_the_sales_order_is_allowed(self):
        row = AttrDict(idx=1, item_code="I-1", sales_order="SO-1", so_detail="SOI-1")
        doc = AttrDict(doctype="Sales Invoice", docstatus=0, is_return=0, items=[row])
        calls = []
        with patch.object(frappe_stub.db, "get_value",
                          side_effect=lambda *a, **k: calls.append(a)):
            technical_procurement.validate_sales_invoice_source(doc)
        # No Delivery Note reference, so no lookup should happen at all.
        self.assertEqual(calls, [])

    def test_credit_notes_are_not_blocked(self):
        """A return invoice against a delivered technical line is legitimate."""
        row = AttrDict(idx=1, item_code="I-1", delivery_note="MAT-DN-1", dn_detail="DNI-1")
        doc = AttrDict(doctype="Sales Invoice", docstatus=0, is_return=1, items=[row])
        with patch.object(frappe_stub.db, "get_value", return_value="TLR-1"):
            technical_procurement.validate_sales_invoice_source(doc)
```

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement -v 2>&1 | tail -12
```

Expected: FAIL, `has no attribute 'validate_sales_invoice_source'`.

- [ ] **Step 3: Implement**

Add beside the other validators in `technical_procurement.py`:

```python
def validate_sales_invoice_source(doc, method=None) -> None:
    """Refuse a Sales Invoice raised from a Delivery Note carrying technical lineage.

    Rule 18: the invoice follows the Sales Order. Billing must reflect *sold* quantities,
    because the client pays the full contract price even when execution delivers less
    (rule 2), and ERPNext's make_sales_invoice maps Delivery Note rows with no so_detail
    condition, so invoicing from the delivery would bill engineering additions that rule 3
    says are absorbed.

    Keyed on the lineage stamp, so a Delivery Note predating this feature stays
    invoiceable. Returns are allowed: crediting a delivered technical line is legitimate.
    """
    if not doc or _text(_get(doc, "doctype")) != "Sales Invoice":
        return
    if cint(_get(doc, "docstatus")) == 2 or cint(_get(doc, "is_return")):
        return
    meta = _meta("Delivery Note Item")
    if not meta or not meta.get_field("custom_technical_revision"):
        return
    for row in _get(doc, "items") or []:
        detail = _text(_get(row, "dn_detail"))
        if not detail:
            continue
        if not _text(
            frappe.db.get_value("Delivery Note Item", detail, "custom_technical_revision")
        ):
            continue
        frappe.throw(
            _(
                "Row {0}: this Delivery Note comes from an approved Technical List. "
                "Create the Sales Invoice from the Sales Order instead."
            ).format(_row_label(row))
        )
```

Note the check keys on `dn_detail` (the row-level link), because that is what identifies the
specific Delivery Note Item whose stamp we need. If a row carries `delivery_note` but no
`dn_detail`, there is no row to inspect and native ERPNext would not have mapped it.

- [ ] **Step 4: Run and confirm pass, then commit**

```bash
python3 -m unittest orderlift.tests.test_technical_procurement 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_sales_invoice_hooks 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_sales_invoice_modes 2>&1 | tail -3
```

```bash
cd /root/erp-deploy-wt/closure
git add apps/orderlift/orderlift/orderlift_logistics/technical_procurement.py \
        apps/orderlift/orderlift/tests/test_technical_procurement.py
git commit -m "feat(technical-procurement): refuse a Sales Invoice raised from a technical delivery

Rule 18. make_sales_invoice maps Delivery Note rows with no so_detail condition, so
invoicing from the delivery billed engineering additions that rule 3 says are absorbed,
and billed delivered rather than sold quantities against rule 2. Rule 3 was a
convention; this makes it a property. Returns and pre-feature deliveries are unaffected.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Wire the hooks

**Files:**
- Modify: `orderlift/hooks.py`
- Test: `orderlift/tests/test_technical_list_integration.py`

- [ ] **Step 1: Write the failing test**

Replace the `assertNotIn("technical_procurement", ... "Sales Invoice" ...)` assertion — its
intent has flipped — with a positive assertion that pins the boundary to exactly one function:

```python
    def test_sales_invoice_carries_only_the_source_guard(self):
        """The technical-list feature deliberately touches invoicing now (rule 18), but
        only to refuse a delivery-sourced invoice. Nothing else from the feature belongs
        in the invoicing path."""
        guard = "orderlift.orderlift_logistics.technical_procurement.validate_sales_invoice_source"
        invoice = hooks.doc_events["Sales Invoice"]
        self.assertIn(guard, invoice["before_validate"])
        serialised = json.dumps(invoice)
        self.assertEqual(serialised.count("technical_procurement"), 1)

    def test_closure_is_re_evaluated_on_delivery_and_on_revision(self):
        delivery = hooks.doc_events["Delivery Note"]
        closure = "orderlift.orderlift_logistics.technical_closure.evaluate_on_delivery_note"
        # Both directions: submitting delivers, cancelling un-delivers.
        self.assertIn(closure, delivery["on_submit"])
        self.assertIn(closure, delivery["on_cancel"])
        revision = hooks.doc_events["Sales Order Technical List Revision"]
        self.assertIn(
            "orderlift.orderlift_logistics.technical_closure.evaluate_on_revision",
            revision["on_submit"],
        )
```

- [ ] **Step 2: Run and confirm failure**

```bash
python3 -m unittest orderlift.tests.test_technical_list_integration -v 2>&1 | tail -12
```

Expected: both FAIL.

- [ ] **Step 3: Wire them**

In `hooks.py`:
- `"Sales Invoice"` → add `validate_sales_invoice_source` to `before_validate`. If Sales Invoice
  has no `before_validate` yet, add one; keep any existing entries.
- `"Delivery Note"` → append `technical_closure.evaluate_on_delivery_note` to both `on_submit`
  and `on_cancel`. Both are currently single strings, so convert to lists, preserving the
  existing entries.
- `"Sales Order Technical List Revision"` → append `technical_closure.evaluate_on_revision` to
  `on_submit`, after the existing `sync_technical_revision_demand_plans`.

Closure must run **after** delivery has been recorded, which is why it is `on_submit` and not
`before_validate`.

- [ ] **Step 4: Run and confirm pass, then commit**

```bash
python3 -m unittest orderlift.tests.test_technical_list_integration 2>&1 | tail -3
python3 -m unittest orderlift.tests.test_technical_closure 2>&1 | tail -3
```

```bash
cd /root/erp-deploy-wt/closure
git add apps/orderlift/orderlift/hooks.py apps/orderlift/orderlift/tests/test_technical_list_integration.py
git commit -m "feat(hooks): wire closure re-evaluation and the invoice source guard

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Document the behaviour

**Files:**
- Modify: `docs/sales_order_technical_lists.md`

- [ ] **Step 1: Extend the delivery section**

State, in the document's existing declarative tone:

- The Sales Order closes automatically once every execution-relevant line of the approved
  revision is fully delivered, services and non-stock included.
- Excluded lines do not hold it open.
- It reopens if a later revision raises a quantity — but only if the close was automatic; a
  close made by a person is never reversed by the system.
- The native `Closed` status is used. `delivery_status` is left to ERPNext, which derives it
  from sold quantities and will read `Partly Delivered` then `Closed` — that is expected,
  because rule 2 makes short delivery deliberate.
- **A closed Sales Order cannot be cancelled** until it is reopened (`Unclose to cancel`).
  This is native ERPNext behaviour but it is a new consequence for these Sales Orders.
- A Sales Invoice cannot be raised from a Delivery Note that came from a Technical List;
  raise it from the Sales Order. Credit notes and pre-feature Delivery Notes are unaffected.

- [ ] **Step 2: Commit**

```bash
cd /root/erp-deploy-wt/closure
git add docs/sales_order_technical_lists.md
git commit -m "docs: describe auto-close and the invoice source rule

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Full verification

- [ ] **Step 1: Run every module, one at a time**

```bash
cd /root/erp-deploy-wt/closure/apps/orderlift
for m in $(ls orderlift/tests/test_*.py | sed 's|.*/||;s|\.py||'); do
  r=$(python3 -m unittest orderlift.tests.$m 2>&1 | tail -1)
  case "$r" in OK*) ;; *) echo "$m :: $r";; esac
done
```

Expected: exactly the 14 pre-existing failures from Preflight. Any fifteenth is a regression
you introduced — fix it rather than explaining it.

- [ ] **Step 2: Report and stop**

Do **not** merge, migrate, restart containers, or deploy. Report the commit SHAs and the test
results. Deployment is a separate step requiring the user, because `/root/erp-deploy` is
bind-mounted into live production.

---

## Deploy notes (for the user, not the implementer)

Same sequence as before, and the container names carry per-deploy suffixes so resolve them with
`docker ps --format '{{.Names}}'` first:

1. Merge to `main` in `/root/erp-deploy`.
2. `bench --site erp.ecomepivot.com migrate` in `app-*` — **confirm the literal line
   ``Executing `after_migrate` hooks...`` appears**, then verify
   `custom_technical_auto_closed` exists on Sales Order. A migrate that stops early installs
   nothing while looking normal.
3. Flush **redis-cache only** (`hooks.py` changed, so a restart alone is not enough).
4. Restart `app-*` plus the queue and scheduler containers, and confirm `app-*`'s `StartedAt`
   is after the last edit — a 200 from curl proves nothing, nginx answers regardless.

**Manual acceptance — the cases no database-free test can cover:**

1. Deliver an approved revision in full; the Sales Order becomes `Closed`.
2. Confirm `custom_technical_auto_closed` is set on it.
3. Approve a new revision raising one line; the Sales Order reopens.
4. Manually close a different Sales Order, then deliver against it — it must **stay** closed
   and the flag must remain unset. This is rule 19 and the one most likely to be got wrong.
5. Try `Create > Sales Invoice` from a technical Delivery Note — refused, naming the Sales
   Order.
6. Raise a Sales Invoice from the Sales Order — succeeds.
7. Raise a credit note against a technical Delivery Note — succeeds.
8. Confirm a Delivery Note cancellation reopens a Sales Order the system closed.

---

## Follow-up

- **UOM divergence** between a revision line and its Sales Order Item still dies at insert with
  a native ERPNext message that never mentions Technical Lists. Worth an explicit pre-check for
  the error message alone.
- **`__default.buying_price_list = PRIX FOURNISSEUR MAD`** is still set globally and belongs to
  Orderlift Maroc Distribution — the same defect as the selling default already purged. A
  Purchase Order raised in Installation without an explicit list can still pick it up.
