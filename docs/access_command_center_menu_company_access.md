# Access Command Center Menu And Company Access

Orderlift uses one active Desk navigation entry point: `Main Dashboard`.

## Default Roles

Orderlift seeds these active business roles:

- `Orderlift Admin`: full business access across all companies, business types, and warehouses; platform configuration remains superadmin-only.
- `Sales User`: CRM, customers, sales, B2B, and sales-facing project links.
- `Sales Manager`: self-contained sales manager access without pricing configuration.
- `Purchase User` and `Purchase Manager`: purchasing transactions and supplier management at manager level.
- `Purchase Agent Rules` access is capability-driven: `purchase_agent_rules_management` manages policies, while non-privileged users can use only Buying Price Lists explicitly allowed for their User and active company.
- `Stock User` and `Stock Manager`: stock operations and manager-only stock-rate/settings control.
- `Pricing Configuration`: price lists, Item Price, pricing builders, dimensioning, and pricing policies.
- `Logistics User`: shipment planning, warehouse, stock, and logistics operations.
- `Finance User` and `Finance Admin`: invoices, payments, reporting, and manager-only commission payout control.
- `Installation User`: project execution and SIG menus.
- `Service User`: SAV service menus.

`System Manager` is the platform superadmin role. `Orderlift Admin` is a business administrator and has no protected platform DocPerm access.

Optional specialist roles may remain installed, but they are not part of the canonical assignment baseline.

## Admin Workflow

1. Open `Access Command Center` from `Main Dashboard > Administration`.
2. Create or edit business roles from the `Roles` tab.
3. Open `Business Permissions`, select a role, and choose business actions such as Use in Fields, View, Create/Edit, Approve/Cancel, Delete, Import, and Export.
4. Open `Menu Access` and choose which Main Dashboard links that role should see. Menu visibility remains separate from business permission.
5. Open a user from the `Users` tab with `User Settings` and edit identity, password, roles, companies, warehouses, and business types in the modal.
6. Click `Save All User Settings` once to apply the complete configuration. Password fields clear after saving for security; the new password remains active.
7. Select `User Type` explicitly, then assign compatible roles. `System User` requires at least one Desk Access role; `Website User` cannot have Desk Access roles.
8. Use `How Access Works` when an operator needs to understand why a user can or cannot see a record.
9. Open `Menu Editor` from `Main Dashboard > Administration` to rename or reorder existing Main Dashboard items only.

## How Access Works

Access is a chain of yes/no gates. The user must pass every active gate.

Fast rule: no role, no record. No company, no record. No concerned link, no record when concerned-only is enabled.

Visibility gates:

- Role: the role must allow the document family and action, such as view, edit, create, export, print, or approval.
- Use in Fields: native `select` permission allows a record in Link fields without granting form, list, report, or configuration access.
- Custom workflows use the shared `orderlift.reference_access` service to enforce `select`, native row scope, and active/enabled policy separately from configuration `read`. This applies to active Dimensioning Sets, Price Lists, CRM classifications, Pricing Tiers, installation stages, and pipeline statuses.
- Commercial users can select, load, preview, apply, map, and save active Dimensioning Sets on Opportunity, Quotation, Pricing Sheet, and Pricing Sheet Builder. The Dimensioning Set list, form, manager, builder, and mutations remain unavailable without configuration access.
- Sales Order payment terms are template-driven for normal commercial users. Agent Pricing Rules define the allowed `Payment Terms Template` rows and the default; the payment schedule table is read-only and regenerated from the selected allowed template. `Orderlift Admin`, `System Manager`, and roles with the editable `Pricing Override` capability can override payment terms and edit the schedule.
- Sales Users can submit, cancel, and amend Sales Orders. Order status setup remains select-only for Sales Users; the status link displays the status document name directly to avoid Frappe's read-gated title lookup.
- Company: the record must belong to one of the user's selected companies.
- Business type: Distribution and Installation narrow records inside the selected companies. Blank business type stays visible.
- Special scopes: warehouse and price-list rules apply only where those controls are relevant.
- Concerned-only: when `Owned / assigned CRM documents only` is enabled, the user must be the doctype-specific business owner, assigned, responsible, or connected through a visible source document.
- Related permission: related records never bypass role permission. A visible Sales Order does not reveal invoices unless the role also grants invoice access.
- Native Frappe `if_owner` is not used for Orderlift-managed business access. The access model uses explicit business-owner fields, assignment `ToDo`s, and linked source documents instead.

Concerned-only business-owner anchors:

- `Opportunity`: `opportunity_owner` or an open assignment `ToDo`; native technical `owner` does not drive Opportunity business visibility.
- `Customer`: account manager, Sales Team, open assignment `ToDo`, or a visible linked Opportunity when the role also grants Customer access.
- `Lead` and `Prospect`: owner field, open assignment `ToDo`, or a visible linked Opportunity when the role also grants the party doctype.
- `Project`: project owner, open assignment `ToDo`, or a visible source Opportunity.
- `Pricing Sheet`: sheet owner, sales person, linked Opportunity, or visible party.
- Pipeline assignment uses Orderlift pipeline `ToDo`s. `DocShare` is not the normal assignment visibility mechanism.

Document chains covered by concerned-only:

- Sales: `Opportunity -> Quotation -> Sales Order -> Sales Invoice / Delivery Note`.
- Purchasing: `Sales Order / Project -> Material Request -> Purchase Order -> Purchase Receipt / Purchase Invoice`.
- Payments: payment entries are visible through their referenced invoices, orders, receipts, or ownership/assignment.
- Campaigns: `Person in Charge` (`campaign_owner`) or an open campaign-level `ToDo`; target rows and visible target customers do not grant campaign management access.
- SAV: assigned technician or linked `Customer`, `Sales Order`, `Delivery Note`, `Sales Invoice`, `Purchase Receipt`, or `Project`.
- Pricing sheets: sheet owner, assigned sales person, linked Opportunity, or visible party.
- Portal quote requests: request owner, portal user, visible Customer, or linked visible Quotation.

Practical examples:

- Sales agent: sees owned or assigned Opportunities, linked Quotations, Sales Orders, invoices, deliveries, campaigns, and SAV tickets only when the role also allows those document families.
- Commissions: a sales agent sees only commission rows for their own Sales Person. Managers can see broader team data.
- Catalogue items: a restricted static agent sees an item only when it has an Item Price in one of the selected allowed selling price lists.
- Price lists: `Price List` and `Item Price` rows are limited to allowed selling, buying, or benchmark lists.
- Buying Price Lists: `privileged_pricing` bypasses purchase allowances; every other purchasing user needs an enabled Purchase Agent Rule for the active company and sees only its active Buying lists.
- Sales Orders: document create/write permission is not pricing authority. Users without `Pricing Override` must create Sales Orders from submitted Quotations and inherited prices stay locked.
- Purchase user: sees purchase documents in allowed companies and, if concerned-only is enabled, only owned, assigned, or linked purchase documents.
- Stock user: stock entries must pass company scope, warehouse scope, and concerned links when concerned-only is enabled.

When troubleshooting a hidden record, check role permission, company, business type, business owner/assignment/source links, warehouse access, and price-list access.

## Rules

- Users get access through roles only. There are no per-user menu exceptions.
- Business Permissions does not expose technical Frappe records, child tables, permission levels, native `if_owner`, or `share`.
- Business actions synchronize the required native document, page, and report permissions. For example, Stock Ledger View synchronizes both report access and Stock Ledger Entry read/report access.
- Native `share` remains forced off for Orderlift-managed business documents; use roles, company/business-type scope, Person in Charge, and assignment ToDos instead of `DocShare`.
- Role Profiles are not part of the Orderlift access workflow; assign roles directly to users.
- New custom business roles can be created in Access Command Center when the default roles are not enough.
- Menu visibility is controlled by `Orderlift Menu Access Rule` records as the final visibility filter only. It cannot grant access to a Page, DocType, or Report when the user's backing permissions do not already allow it.
- If the user has the backing permission, Menu Access can still hide that related menu item for the user's role.
- Menu Editor can change only labels and menu order. It cannot create links or edit link targets.
- Company access is stored as global `User Permission` records on `Company`.
- The preferred startup company is stored in the `orderlift_preferred_company` user default. The legacy `Company` default is retained for ERPNext compatibility but is not the active browser context.
- The active company is stored per authenticated browser session in Redis. Tabs sharing one browser session use one active company; another browser or device using the same user has an independent active company.
- Company switching never changes Company User Permissions and does not accept a company through the URL. Use the Orderlift sidebar company switcher.
- Non-admin users without assigned companies have no access to configured company-scoped business records. `Orderlift Admin` is the full-business exception.
- Existing Company user permissions scoped to a single `Applicable For` DocType are left untouched by the Company Access panel.
- `Orderlift Admin` can use Access Command Center for business users, business roles, business menu access, and business role permissions only.
- The `Access Command Center` Business Permissions row is available only for high-access roles. Open/View grants the Page and native `User` read/select access; Create/Edit adds `User` write/create; Delete adds `User` delete; Export adds `User` export. The Menu toggle controls its Main Dashboard link.
- This permission bundle does not broaden the Access Command Center server-side ceiling: only `Orderlift Admin`, `Administrator`, and `System Manager` can call its APIs.
- Superadmin users (`Administrator` and `System Manager`) can also use Access Command Center and are the only users who can see or manage superadmin roles and superadmin permissions.
- Backend finance structure permissions (`Account`, `Cost Center`, and accounting dimensions) remain outside Business Permissions; only superadmin roles can manage them.
- `Administrator` and `System Manager` bypass menu and company restrictions.
- Direct Administration menu links stay limited to control entry points. User, role, permission, workflow, and assignment setup is managed from Access Command Center instead of separate Desk list links.
- Sidebar visibility is UX control. Custom page APIs should still validate role and company access server-side before returning data.
- `Pricing Sheet` and `Customer Segmentation Engine` are company-scoped through their `custom_company` fields.
- `Pricing Override` in Access Command Center role capabilities controls direct/manual Sales Order pricing. Without it, Sales Order pricing must come from a submitted Quotation even if the role can create or write Sales Orders.
- Frappe `DocShare` is blocked for Orderlift-managed business doctypes because it can re-grant records after central role/company/concerned-only checks deny them; migrations also normalize managed `share` flags back to `0`.

## Runtime Notes

- `Main Dashboard` is rebuilt from `orderlift.menu_registry` after migration.
- The native Frappe `Company` Session Default is removed during migration so it cannot overwrite the shared user default. Other configured Session Defaults are preserved.
- Interactive Desk list/report queries focus on the active session company. Background jobs, API-token calls, and console operations without a browser SID use the full allowed-company scope.
- Switching company reloads clean tabs in the same browser. Dirty forms and custom pages show a reload warning so unsaved work is not silently discarded.
- Section-specific sidebars such as `Sales`, `CRM & Customers`, and `Logistics` are no longer navigation sources.
- Direct access to registered custom Desk pages is blocked when the user lacks menu/page access.
- Static Workspace shortcut blocks are not generated for Main Dashboard because those blocks cannot be safely role-filtered per user.
- Every canonical business role has read-only `Notification Log` access so the standard Desk notification dropdown can load without granting notification configuration access.
- Every canonical business role has an explicit shared Desk baseline for attachments (`File`), personal work (`ToDo`), calendar events, tags, Email Template lookup, and common reference values such as Gender and Salutation. Record visibility and ToDo scope still follow the existing document and capability guards.
- `User` selection and Letter Head lookup remain native `Desk User` permissions. Timeline comments remain source-document-scoped through Frappe APIs instead of receiving broad `Comment` DocPerm access.
- `Orderlift Admin` and `Pricing Configuration` can manage native Data Import records and read their inline Data Import Log results. The target selector lists only parent DocTypes for which the current user has native import permission.
- `Error Log` remains superadmin-only because it can expose raw tracebacks, paths, queries, and sensitive request data. Data Import suppresses Frappe's Error Log lookup for users without that permission and continues to show row-level Data Import Log messages.
- Access Command Center login-email changes must use the queued Frappe `User` rename path. Do not manually update user email fields in SQL; rename updates linked assignments, rules, ToDos, and ownership fields across the site and can take several minutes on large tables.
- When an email and password change is saved, the requested email is activated immediately as a native login alias and the new password is committed in the same fast transaction. The old login remains valid temporarily while the canonical User ID and linked records migrate.
- While an email rename is queued or running, the Users list shows the new active login plus an `Updating linked records` state and refreshes automatically. User Settings are read-only for that row until the rename completes. A failed background rename remains visible with its error instead of silently leaving the old email.

## Explicit Normalization Commands

All normalization commands are dry-run by default and are not migration hooks:

```bash
bench --site <site> execute orderlift.scripts.setup_startup_roles.run --kwargs '{"dry_run":1,"exact_normalization":1}'
bench --site <site> execute orderlift.role_capabilities.normalize_managed_role_capabilities --kwargs '{"dry_run":1}'
bench --site <site> execute orderlift.scripts.normalize_simplified_user_roles.run
```

After reviewing output, pass `"dry_run":0`. User role normalization clears role profiles for the named users only, does not alter User Permission scopes, and reports missing Sales Person mappings without creating them. If a login email is renamed, update this named-user list before rerunning normalization.

Approved named-user assignments:

- `ashdrissi@gmail.com`: `System Manager` only.
- `orderlift.admin@ecomepivot.com`, `taha@orderlift.net`, `sara@orderlift.net`, and `imad@orderlift.net`: `Orderlift Admin` only.
- `haitem@orderlift.net`, `yassine@orderlift.net`, and `ahmed.orderlift@gmail.com`: `Sales User` only.
- `bilalorderlift@gmail.com`: `Sales User`, `Purchase User`, and `Stock User`.
- `ashdrissi1@gmail.com`: enabled without a business/admin role.
