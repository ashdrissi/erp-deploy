# Access Command Center Menu And Company Access

Orderlift uses one active Desk navigation entry point: `Main Dashboard`.

## Default Roles

Orderlift seeds seven business roles:

- `Orderlift Admin`: all business menus, still company-scoped unless also superadmin.
- `Sales User`: CRM, customers, sales, B2B, and sales-facing project links.
- `Pricing Manager`: pricing sheets, pricing dashboard, policies, segmentation, and B2B pricing setup.
- `Logistics User`: purchasing, warehouse, stock, logistics, and manufacturing operations.
- `Finance User`: finance dashboards, invoices, reports, and payments.
- `Installation User`: project execution and SIG menus.
- `Service User`: SAV service menus.

Superadmin roles stay unrestricted and outside this simplified model: `Administrator`, `System Manager`, and `Developer`.

## Admin Workflow

1. Open `Access Command Center` from `Main Dashboard > Administration`.
2. Create or edit business roles from the `Roles` tab.
3. Open `Menu Access`, select a role, and check the menu items that role should see.
4. Open `Permissions Matrix` to define DocType permissions for the same role.
5. Open a user from the `Users` tab and assign roles.
6. In the same user panel, set `Company Access` by checking allowed companies.
7. Use `How Access Works` when an operator needs to understand why a user can or cannot see a record.
8. Open `Menu Editor` from `Main Dashboard > Administration` to rename or reorder existing Main Dashboard items only.

## How Access Works

Access is a chain of yes/no gates. The user must pass every active gate.

Fast rule: no role, no record. No company, no record. No concerned link, no record when concerned-only is enabled.

Visibility gates:

- Role: the role must allow the document family and action, such as view, edit, create, export, print, or approval.
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
- Purchase user: sees purchase documents in allowed companies and, if concerned-only is enabled, only owned, assigned, or linked purchase documents.
- Stock user: stock entries must pass company scope, warehouse scope, and concerned links when concerned-only is enabled.

When troubleshooting a hidden record, check role permission, company, business type, business owner/assignment/source links, warehouse access, and price-list access.

## Rules

- Users get access through roles only. There are no per-user menu exceptions.
- Permission Matrix does not expose native `if_owner`; do not use Frappe owner-only permissions for Orderlift-managed business doctypes.
- Permission Matrix forces native `share` off for Orderlift-managed business doctypes; use roles, company/business-type scope, Person in Charge, and assignment ToDos instead of `DocShare`.
- Role Profiles are not part of the Orderlift access workflow; assign roles directly to users.
- New custom access patterns should be created as additional roles only when the seven default roles are not enough.
- Menu visibility is controlled by `Orderlift Menu Access Rule` records as the final visibility filter only. It cannot grant access to a Page, DocType, or Report when the user's backing permissions do not already allow it.
- If the user has the backing permission, Menu Access can still hide that related menu item for the user's role.
- Menu Editor can change only labels and menu order. It cannot create links or edit link targets.
- Company access is stored as global `User Permission` records on `Company`.
- Non-admin users without assigned companies have no access to the configured company-scoped DocTypes.
- Existing Company user permissions scoped to a single `Applicable For` DocType are left untouched by the Company Access panel.
- `Orderlift Admin` can use Access Command Center for business users, business roles, business menu access, and business role permissions only.
- Superadmin users (`Administrator`, `System Manager`, and `Developer`) can also use Access Command Center and are the only users who can see or manage superadmin roles and superadmin permissions.
- Backend finance structure permissions (`Account`, `Cost Center`, and accounting dimensions) are hidden from business roles in the Permissions Matrix; only superadmin roles can manage them.
- `Administrator`, `System Manager`, and `Developer` bypass menu and company restrictions.
- Direct Administration menu links stay limited to control entry points. User, role, permission, workflow, and assignment setup is managed from Access Command Center instead of separate Desk list links.
- Sidebar visibility is UX control. Custom page APIs should still validate role and company access server-side before returning data.
- `Pricing Sheet` and `Customer Segmentation Engine` are company-scoped through their `custom_company` fields.
- Frappe `DocShare` is blocked for Orderlift-managed business doctypes because it can re-grant records after central role/company/concerned-only checks deny them; migrations also normalize managed `share` flags back to `0`.

## Runtime Notes

- `Main Dashboard` is rebuilt from `orderlift.menu_registry` after migration.
- Section-specific sidebars such as `Sales`, `CRM & Customers`, and `Logistics` are no longer navigation sources.
- Direct access to registered custom Desk pages is blocked when the user lacks menu/page access.
- Static Workspace shortcut blocks are not generated for Main Dashboard because those blocks cannot be safely role-filtered per user.
