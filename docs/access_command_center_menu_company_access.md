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
7. Open `Menu Editor` from `Main Dashboard > Administration` to rename or reorder existing Main Dashboard items only.

## Rules

- Users get access through roles only. There are no per-user menu exceptions.
- Role Profiles are not part of the Orderlift access workflow; assign roles directly to users.
- New custom access patterns should be created as additional roles only when the seven default roles are not enough.
- Menu visibility is controlled by `Orderlift Menu Access Rule` records.
- Menu Editor can change only labels and menu order. It cannot create links or edit link targets.
- Company access is stored as global Frappe `User Permission` records on `Company`.
- Non-admin users without assigned companies have no access to the configured company-scoped DocTypes.
- Existing Company user permissions scoped to a single `Applicable For` DocType are left untouched by the Company Access panel.
- `Orderlift Admin` can use Access Command Center for business users, business roles, business menu access, and business role permissions only.
- Superadmin users (`Administrator`, `System Manager`, and `Developer`) can also use Access Command Center and are the only users who can see or manage superadmin roles and superadmin permissions.
- Backend finance structure permissions (`Account`, `Cost Center`, and accounting dimensions) are hidden from business roles in the Permissions Matrix; only superadmin roles can manage them.
- `Administrator`, `System Manager`, and `Developer` bypass menu and company restrictions.
- Direct Administration menu links stay limited to control entry points. User, role, permission, workflow, and assignment setup is managed from Access Command Center instead of separate Desk list links.
- Sidebar visibility is UX control. Custom page APIs should still validate role and company access server-side before returning data.
- `Pricing Sheet` and `Customer Segmentation Engine` are company-scoped through their `custom_company` fields.

## Runtime Notes

- `Main Dashboard` is rebuilt from `orderlift.menu_registry` after migration.
- Section-specific sidebars such as `Sales`, `CRM & Customers`, and `Logistics` are no longer navigation sources.
- Direct access to registered custom Desk pages is blocked when the user lacks menu/page access.
- Static Workspace shortcut blocks are not generated for Main Dashboard because those blocks cannot be safely role-filtered per user.
