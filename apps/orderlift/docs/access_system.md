# Orderlift Access System

## Overview

Access is a **5-gate chain**. A user must pass every gate to see or act on a record:

```
Gate 1 (Role)  →  Gate 2 (Company)  →  Gate 3 (Business Type)  →  Gate 4 (Special Scope)  →  Gate 5 (Concerned Link)
```

Each gate narrows what is visible. If any gate says no, the record is hidden. Related
records never bypass role permission — a visible Sale does not reveal a Customer unless
the role also grants Customer access.

---

## Layer 1 — Role Permissions (DocPerm)

**What it is:** Each DocType has a set of `DocPerm` (native) and `Custom DocPerm` (Orderlift)
rows that grant roles specific actions: read, write, create, delete, submit, cancel, amend,
report, import, export, print, email, share.

**How it works:**
- Roles are assigned to users via the native User form or the ACC Users tab.
- `DocPerm` rows live in the Frappe `tabDocPerm` table; Orderlift overrides live in `tabCustom DocPerm`.
- The ACC **Permissions Matrix** tab lets admins create/edit Custom DocPerm rows for any
  role on any doctype.

**Custom `has_permission` hooks in `hooks.py`:**
Some doctypes need per-record checks beyond DocPerm. These are registered in
`hooks.py` → `has_permission` dict and call `orderlift.company_access.has_company_permission`
or a custom guard in `orderlift.orderlift_guards`. Doctypes with custom hooks:

- All transaction doctypes: Opportunity, Quotation, Sales Order, Sales Invoice,
  Purchase Order, Purchase Receipt, Purchase Invoice, Delivery Note, Payment Entry,
  Stock Entry, Material Request, Request for Quotation, Project
- Party doctypes: Customer, Supplier, Lead, Prospect
- Pricing doctypes: Price List, Item Price, Pricing Sheet, Pricing Scenario,
  Pricing Benchmark Policy, Pricing Customs Policy, Customer Segmentation Engine,
  Partner Campaign, Portal Customer Group Policy, Portal Quote Request
- Guard-only (via `orderlift_guards`): Project Workflow Case, Orderlift Annex Document,
  Shipment Analysis, Pricing Builder History

**Who manages it:** ACC Roles tab (view/edit custom roles), ACC Permissions Matrix (DocPerm).

### Data Import dependency

The Business Permissions `Import` action is end-to-end. When a role has at least
one effective target DocType Import grant, the compiler also grants that role
`Data Import` read/write/create and `Data Import Log` read access. These are
runtime dependencies of the Import action and are not separate business
permissions. Removing the final Import target removes the managed supporting
flags.

**Operational transaction ownership:**

| Workflow area | Owner roles | Main responsibility |
|---------------|-------------|---------------------|
| Sales | Sales User, Sales Manager, Sales Distribution Manager, Sales Installation Manager, Commercial Agent roles, Quotation Creator | Create and submit quotations; managers can cancel/amend quotations and sales orders. |
| Purchasing | Purchase User, Purchase Manager | Create and submit Material Requests, RFQs, Supplier Quotations, and Purchase Orders. Purchase Managers can cancel/amend. |
| Logistics | Logistics User, Logistics Manager | Receive, deliver, pick, inspect, and move stock. Purchase Orders and suppliers are read-only for traceability. |
| Finance | Finance User, Finance Admin, Payment Validator | Create and submit invoices/payments. Finance Admin can cancel/amend finance transactions and manage commission payment state. |

The production migration hook uses a scoped role update on already-configured sites so
workflow permission fixes do not create unrelated legacy role rows during normal
`bench migrate`. A full startup seed is still available for fresh sites.

---

## Layer 2 — Company Scope

**What it is:** Records must belong to one of the user's allowed companies.

**Core files:**
- `orderlift/company_access.py` — `has_company_permission()` entry point
- `orderlift/company_scope.py` — `SCOPED_DOCTYPES` registry mapping doctype to company field
- `orderlift/menu_access.py` — `get_allowed_companies(user)`, `user_can_access_all_companies(user)`

**How it works:**
1. Each scoped doctype has a `company` or `custom_company` field (set via `company_scope.py` fixtures).
2. `get_allowed_companies(user)` resolves company access from User Permission records.
3. `_doc_company_allowed()` checks the record's company against the user's allowed set.
4. `_company_query()` generates SQL filters for list views.
5. The `permission_query_conditions` hook in `hooks.py` applies these filters at the
   database level for every registered doctype.

**Company-scoped doctypes (from `COMPANY_SCOPED_DOCTYPES`):**
Company, Opportunity, Quotation, Sales Order, Sales Invoice, Purchase Order,
Purchase Receipt, Purchase Invoice, Delivery Note, Payment Entry, Stock Entry,
Material Request, Request for Quotation, Project, Sales Commission, SAV Ticket,
Forecast Load Plan, Customer, Supplier, Price List, Prospect, Lead, Pricing Sheet,
Pricing Scenario, Pricing Benchmark Policy, Pricing Customs Policy,
Customer Segmentation Engine, Partner Campaign, Portal Customer Group Policy,
Portal Quote Request

**Price List special handling:**
- Shared price lists (mirrored across companies) are read-only in the target company
  and cannot be edited by non-admin users.
- `_price_list_shared_edit_allowed()` blocks write/delete on shared lists.

**Who manages it:** ACC User Panel → Company Access section.

---

## Layer 3 — Business Type Scope

**What it is:** Records are further narrowed by CRM business type (Distribution, Installation).

**Core files:**
- `orderlift/company_access.py` — `_doc_business_type_allowed()`
- `orderlift/company_scope.py` — business type field mapping in `SCOPED_DOCTYPES`
- `orderlift/orderlift_crm/company_business_type.py` — business type ↔ company validation

**How it works:**
- Some doctypes carry a single business type field (e.g., `Opportunity.custom_crm_business_type`).
- Others carry a `CRM Segment Assignment` child table with per-row business types.
- `_doc_business_type_allowed()` checks whether the record's business type is in the
  user's allowed set.
- Records with no business type set (blank) are visible to all business type scopes.

**Who manages it:** ACC User Panel → Business Type Access section.

---

## Layer 4 — Special Scope

### Warehouse Access

**What it is:** Stock-related records are scoped to the user's assigned warehouses.

**Core file:** `orderlift/warehouse_access.py`

**What it scopes:** Warehouse list views, Bin, Stock Ledger Entry, Item Reorder,
and Stock Entry (combined with company scope).

**Who manages it:** ACC User Panel → Warehouse Access section.

### Price List Visibility

**What it is:** Which price lists and item prices a user can see.

**Core file:** `orderlift/orderlift_sales/utils/price_list_scope.py`

**Roles and capabilities involved:**

| Role set | Constant | Effect |
|----------|----------|--------|
| `PRIVILEGED_PRICE_ROLES` | `privileged_pricing` capability | See all active-company price lists; bypass agent allocation |
| `PURCHASING_ROLES` | `purchasing_access` capability | See buying (cost) price lists |
| Agent allocation | N/A (via Agent Pricing Rules) | Static agents see only allocated selling/benchmark lists; dynamic agents see allocated buying lists |

**Key functions:**
- `get_visible_price_lists(kind, company, user)` — returns allowed price list names for a user
- `get_item_price_access(kind, company)` — resolves whether the Item form should show selling/buying grids
- `validate_visible_price_list(name, kind, company)` — throws if price list is not in the user's scope

**Agent Pricing Rules allocation:**
- **Static mode** (`Pick from Published Selling Price List`): agent sees only
  `allocated_price_lists` and `allocated_benchmark_price_lists`.
- **Dynamic mode** (`Dynamic Calculation Engine`): agent sees only
  `default_buying_price_list` plus any dynamic config rows.
- No allocation = all visible (privileged users).

**Who manages it:** Agent Pricing Rules doctype (admin/pricing roles).

---

## Layer 5 — Concerned-Link Scope (Owned-Only Mode)

**What it is:** When `custom_owned_documents_only = 1` is set on a user, records must
be owned by, assigned to, or linked through a visible source document.

**Core file:** `orderlift/company_access.py` — `_doc_owned_scope_allowed()`, per-doctype user clauses

**How it works:**
- The user is checked against document owner, sales person fields, ToDo assignments,
  and upstream document chains.
- Each doctype has a custom user clause function (e.g., `_opportunity_user_clause`,
  `_project_user_clause`, `_sales_order_user_clause`) that builds the appropriate SQL.
- Document chains are walked: a Purchase Order is visible if linked to a visible
  Material Request, which is visible if linked to a visible Sales Order or Project.

**Document chain examples:**
| Flow | Chain |
|------|-------|
| Sales | Opportunity → Quotation → Sales Order → Sales Invoice / Delivery Note |
| Purchasing | Sales Order / Project → Material Request → Purchase Order → Purchase Receipt / Purchase Invoice |
| Campaigns | Campaign owner or target linked to visible Lead, Prospect, Customer, Opportunity, Quotation, SO |
| SAV | Assigned technician or linked Customer, Sales Order, Delivery Note, Sales Invoice, Purchase Receipt, Project |
| Pricing | Pricing Sheet owner, sales person, linked Opportunity, or visible Lead/Prospect/Customer |

**Who manages it:** ACC User Panel → "Owned / assigned CRM documents only" toggle.

---

## Menu Access

**What it is:** Controls which sidebar links appear in the Main Dashboard for each role.

**Core file:** `orderlift/menu_access.py`

**How it works:**
- Stored in `Orderlift Menu Access Rule` doctype with `allowed_roles_json` and `denied_roles_json`.
- Each rule also has `required_doctypes` — if the user lacks read permission on any
  required doctype, the menu link is hidden.
- Admin bypass: `Administrator`, `System Manager`, `Developer` see all menu items.
- The `sync_menu_access_rules()` function rebuilds the rule cache on migrate.

**Who manages it:** ACC Menu Access tab.

The Access Command Center stores the compiled business policy in
`Role.custom_orderlift_business_grants_json` as a version-2 feature snapshot. The
snapshot keeps menu visibility separate from the action grant. Native Page, Report,
menu, DocPerm, and Import-support rows are derived from that snapshot; registry defaults
are bootstrap metadata and must not overwrite an existing snapshot.

---

## Page & Report Access

**What it is:** Custom pages and reports use `Has Role` child table rows to control which
roles can access them.

**How it works:**
- `user_can_access_page(page_name)` checks the parent menu policy, required DocTypes, and
  the page's `Has Role` rows. Supporting builder/detail routes inherit their registered
  parent menu key, while unknown Orderlift custom Pages fail closed.
- If a page has `required_doctypes` declared in its menu registry entry, those are also checked.
- Reports work the same way via `Has Role` on the Report doctype.
- Legacy `operations-pipeline`, `finance-dashboard`, and `orderlift-home` routes redirect
  to their current replacements and their old data APIs are denied.

**Who manages it:** ACC Business Permissions is authoritative. Native Page/Report role
rows and menu rules are compiler outputs; direct writers for managed targets must not be
used to bypass the snapshot compiler.

---

## Capabilities — Role-Level Privilege Overrides

Capabilities are role flags that bypass specific access gates. Unlike DocPerm
("can you see this doctype?"), capabilities answer "can you override pricing rules?"
Pipeline Page access and pipeline assignment are intentionally separate: viewing a
pipeline does not grant its assignment capability.

### How capabilities work

The capability system lives in `orderlift/role_capabilities.py`. Each capability:
1. Has a constant key (e.g., `"quotation_override"`) and a human label.
2. Is stored as a newline-separated string in the `custom_orderlift_capabilities`
   field on the native `Role` doctype.
3. Is normalized explicitly with `orderlift.role_capabilities.normalize_managed_role_capabilities`.
4. Is checked at enforcement points through `role_capability_decision()`.

### Authoritative mode

Role capabilities are authoritative at every migrated enforcement point. Legacy
role-name sets and the old `orderlift_use_role_capabilities` shadow switch no
longer decide access.

### Hardcoded bypass roles

These roles **always** pass capability checks regardless of the capability field value,
even after capabilities are enabled:

| Role | Hardcoded | Notes |
|------|-----------|-------|
| `Administrator` | Always | Checks at the top of every function |
| `System Manager` | Yes (`HARDCODED_CAPABILITY_ROLES`) | Platform Superadmin |

`Orderlift Admin` is not a hardcoded bypass. Its business capabilities are stored
visibly on the Role and can be audited in Access Command Center.

### Capability: `privileged_pricing`

**Label:** Privileged Pricing

**Effect:** User sees all active-company price lists (no agent allocation cap).
Also bypasses item price restriction checks for non-selling price lists.

**Enforced at:**
| File | Line | Function |
|------|------|----------|
| `price_list_scope.py` | 202 | `get_visible_price_lists()` |
| `price_list_usage_guard.py` | 377 | `_can_bypass_item_price_restriction()` |

**Default roles:** Orderlift Admin, Pricing Configuration, System Manager

### Capability: `quotation_override`

**Label:** Pricing Override

**Effect:** Bypasses all pricing floors, discount caps, and auto-repricing on
quotations and pricing sheets. Also allows direct/manual Sales Order pricing;
users without this capability must create Sales Orders from submitted Quotations
and cannot change inherited pricing. Effectively unrestricted pricing.

**Enforced at:**
| File | Line | Bypassed gate |
|------|------|---------------|
| `quotation_hooks.py` | 42 | Discount cap validation on quotation |
| `price_list_usage_guard.py` | 26 | Transaction item price validation |
| `price_list_usage_guard.py` | 35 | Auto-repricing from selected price lists |
| `sales_order_pricing_hooks.py` | n/a | Sales Order source lock and inherited price lock |
| `pricing_sheet.py` | 2112 | Manual price floor validation on pricing sheet |
| `pricing_sheet.py` | 2056 | Max discount cap on pricing sheet |

**Default roles:** Orderlift Admin, Sales Manager, System Manager

### Capability: `purchasing_access`

**Label:** Purchasing Access

**Effect:** User can view buying (cost/supplier) price lists and item cost data.

**Enforced at:**
| File | Line | Function |
|------|------|----------|
| `price_list_scope.py` | 210 | `get_visible_price_lists()` — buying kind |
| `price_list_scope.py` | 248 | `get_item_price_access()` — buying kind |

**Default roles:** Orderlift Admin, Pricing Configuration, Purchase Manager,
Purchase User, System Manager

Stock-rate approval is separate through `stock_rate_management`; purchasing access
does not unlock Purchase Receipt or Stock Entry valuation controls.

Additional authoritative capabilities:

- `stock_rate_management`: Orderlift Admin and Stock Manager.
- `commission_assignment_management`: Orderlift Admin and Sales Manager.
- `commission_payout_management`: Orderlift Admin and Finance Admin.
- `pipeline_assignment_management`: Orderlift Admin and Sales Manager.
- `saved_other_charge_management`: Orderlift Admin and Pricing Configuration.
- `todo_all_access`: Orderlift Admin.

---

## Access Command Center

The ACC (`access-command-center` page) is the all-in-one management cockpit gated
behind `_require_access_manager()` (Orderlift Admin or superadmin only).

### Tabs and what they manage

| Tab | Manages | Maps to layer |
|-----|---------|---------------|
| Users | Create/edit/delete users, assign roles, companies, warehouses, business types, concerned-only mode | Gates 2–5 |
| Roles | View/create/edit/delete custom roles, capability assignment, user counts | Gate 1, Capabilities |
| Policy | Plain-language how-access-works guide (this content) | Documentation |
| Menu Access | Control which sidebar links each role can see | Menu Access |
| Permissions Matrix | Custom DocPerm overrides per role per doctype | Gate 1 |
| Audit Log | Track access-related changes | Auditing |

### Managing capabilities in ACC

The **Roles** tab shows capability badges on each role card. Click **Edit** on a
custom role to open a dialog with a "Capabilities" multi-check field. Saved
capabilities are authoritative after role and boot caches are cleared.

### Sales Order Pricing Governance

Sales Order document permissions and pricing authority are separate. A role can
have Sales Order create/write permissions but still be quotation-only for pricing.

| User capability | Sales Order creation | Pricing edits |
|-----------------|----------------------|---------------|
| No Pricing Override | Submitted Quotation only | Locked to inherited Quotation pricing |
| Pricing Override | Direct or from Quotation | Manual changes allowed |
| Orderlift Admin / Sales Manager / System Manager | Direct or from Quotation | Manual changes allowed |

When troubleshooting Sales Order save errors, check both the Permissions Matrix
for Sales Order document access and the role capability badges for Pricing
Override.

---

## Adding a New Capability

1. **Define the constant** in `orderlift/role_capabilities.py`:
   ```python
   CAPABILITY_NEW_FEATURE = "new_feature"
   ROLE_CAPABILITIES[CAPABILITY_NEW_FEATURE] = "New Feature"
   ```

2. **Add default assignments** in `DEFAULT_ROLE_CAPABILITIES`.

3. **Do not add ordinary business roles to hardcoded bypasses.** Only System Manager is the platform capability bypass.

4. **Call at enforcement point**:
   ```python
    from orderlift.role_capabilities import CAPABILITY_NEW_FEATURE, user_has_capability
    # ...
    if not user_has_capability(CAPABILITY_NEW_FEATURE):
        frappe.throw("Not allowed")
   ```

5. **Deploy:** if the `Role` custom field is unchanged, just clear cache + restart.
   If the field definition changed, run `bench migrate`.

6. **ACC UI update:** not required — the Roles tab auto-discovers capabilities
   from the `role_capabilities` key in the data API payload.

---

## Reference: Key Files

| File | Purpose |
|------|---------|
| `orderlift/role_capabilities.py` | Capability constants, defaults, and authoritative checks |
| `orderlift/company_access.py` | `has_company_permission`, all query conditions, owned-only clauses |
| `orderlift/company_scope.py` | `SCOPED_DOCTYPES` registry, company field mappings, `after_migrate` |
| `orderlift/menu_access.py` | User companies, business types, page access, menu rule evaluation |
| `orderlift/warehouse_access.py` | Warehouse/Bin/Stock scoping queries |
| `orderlift/orderlift_guards.py` | Custom `has_permission` guards for Annex, Shipment, Builder History |
| `orderlift/hooks.py` | `has_permission`, `permission_query_conditions` registrations |
| `orderlift/orderlift_sales/utils/price_list_scope.py` | Price list visibility, `can_override_quotation_pricing` |
| `orderlift/orderlift_sales/utils/price_list_usage_guard.py` | Quotation price validation, auto-repricing, item price guards |
| `orderlift/orderlift_sales/quotation_hooks.py` | Quotation discount cap validation |
| `orderlift/orderlift_sales/doctype/pricing_sheet/pricing_sheet.py` | Pricing sheet floor/discount override |
| `orderlift/sales/utils/pricing_setup.py` | Custom field creation, default seeding, `after_migrate` |
| `orderlift/startup_roles.py` | Startup role constants (QUOTATION_CAPABLE, RESTRICTED) |
| `orderlift/orderlift/page/access_command_center/access_command_center.py` | ACC API — role management, DocPerm, audit |
| `orderlift/orderlift/page/access_command_center/access_command_center.js` | ACC UI — all tabs, policy markup |
