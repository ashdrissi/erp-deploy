# Workspace Split Implementation Checklist

## Goal

Turn these `Main Dashboard` sections into dedicated workspaces with their own
sidebar/content instead of keeping everything inside one large shell:

- My Work
- Administration
- CRM & Customers
- Sales
- Policies & Configs
- SAV
- Items & Price Lists
- Finance
- Purchasing
- HR
- Manufacturing
- Gestion de Projets
- Warehouse & Stock
- Logistics
- B2B Portal
- SIG

## Current Architecture

There are three active layers that affect navigation and workspace behavior:

1. `Workspace Sidebar = Main Dashboard`
   - Managed partially by `apps/orderlift/orderlift/scripts/setup_main_dashboard_sidebar.py`
   - This script injects curated section links and rebuilds `Workspace Shortcut`
     and `Workspace.content` blocks for `Main Dashboard`

2. Desk shell behavior in `apps/orderlift/orderlift/public/js/orderlift_bundle_20260422.js`
   - Still contains restricted route logic for `Orderlift Admin`
   - Blocks native workspace/module routes like `selling`, `stock`, `workspaces`
   - Filters workspace dropdown/search behavior for restricted users

3. User defaults / backend redirects
   - `admin_access.py`, `setup_restricted_user.py`, `restricted_user_guard.py`
   - These still route restricted users to `/desk/home-page`
   - They no longer force `?sidebar=Main+Dashboard`, but they still preserve the
     `Main Dashboard` shell model conceptually

## Live Workspace Inventory

### Existing Workspaces Worth Reusing

- `CRM`
- `Selling`
- `Buying`
- `Stock`
- `Projects`
- `Invoicing`
- `Manufacturing`

### Existing Workspaces That Are Fragments, Not Final Section Targets

- `HR Setup`
- `Recruitment`
- `Performance`
- `Shift & Attendance`
- `Leaves`
- `Payroll`
- `Tax & Benefits`
- `Users`
- `ERPNext Settings`
- `Support`

### Existing Custom / Hub Workspaces

- `Main Dashboard`
- `Orderlift Ops`
- `CRM-Orderlift` (custom workspace created from `Main Dashboard` CRM section)

## Reuse vs Create Decision Matrix

### Reuse Native Workspaces Directly

- `CRM & Customers` -> `CRM`
- `Purchasing` -> `Buying`
- `Warehouse & Stock` -> `Stock`
- `Manufacturing` -> `Manufacturing`
- `Gestion de Projets` -> `Projects`

### Reuse Native Workspaces as a Base, But Extend or Curate

- `Sales` -> start from `Selling`
- `Finance` -> start from `Invoicing`
- `HR` -> combine HR fragments into a new `HR-Orderlift`
- `Administration` -> combine `Users`, `Companies`, `ERPNext Settings`

### Create New Custom Workspaces

- `My Work`
- `Administration`
- `Sales`
- `Policies & Configs`
- `SAV`
- `Items & Price Lists`
- `Finance`
- `HR`
- `Logistics`
- `B2B Portal`
- `SIG`

## Recommended Target Model

Use `Main Dashboard` as the landing hub only.

`Main Dashboard` should:

- show top-level section entries only
- stop acting as the long-lived catch-all shell for all business navigation
- open the target workspace for each domain

Target workspaces:

- `My Work`
- `Administration`
- `CRM`
- `Sales-Orderlift`
- `Policies-Orderlift`
- `SAV-Orderlift`
- `Catalog-Orderlift`
- `Finance-Orderlift`
- `Buying`
- `HR-Orderlift`
- `Manufacturing`
- `Projects`
- `Stock`
- `Logistics-Orderlift`
- `B2B-Portal-Orderlift`
- `SIG-Orderlift`

## Constraints and Known Gotchas

### 1. `Main Dashboard` sync can overwrite manual edits

File:

- `apps/orderlift/orderlift/scripts/setup_main_dashboard_sidebar.py`

Implication:

- any manual edits to `Main Dashboard` links/shortcuts/content can be lost after
  `after_migrate` or explicit sync runs
- the final workspace split must be encoded in scripts, not done only manually

### 2. Restricted shell route guards still block native workspaces

File:

- `apps/orderlift/orderlift/public/js/orderlift_bundle_20260422.js`

Current blockers:

- `stock`
- `selling`
- `workspaces`
- many finance/accounting routes

Implication:

- even if native workspaces exist, users can still be forced back to home page
- workspace split requires relaxing this logic

### 3. Page breadcrumbs for custom dashboards need page-level handling

Example:

- `apps/orderlift/orderlift/orderlift_crm/page/crm_dashboard/crm_dashboard.js`

Implication:

- custom dashboards do not automatically behave like native doctype routes
- each custom dashboard may need explicit breadcrumb/title handling

### 4. Sidebar item type matters

For workspace sidebar rows:

- use `link_type = Workspace` when opening another workspace directly
- use `link_type = Page` only for custom pages
- use `route_options` when the page needs a specific sidebar context
- avoid raw URL links unless no native type supports the route correctly

## Implementation Order

### Phase 1. Freeze the Model

- [ ] Finalize workspace names
- [ ] Finalize which native workspaces are reused as-is
- [ ] Finalize which new custom workspaces must be created
- [ ] Decide if native names stay visible (`CRM`, `Buying`, `Stock`) or get aliased

### Phase 2. Workspace Sync Foundation

- [ ] Create a generic workspace-sync script for custom section workspaces
- [ ] Input should support:
  - workspace name
  - source sidebar section
  - optional template workspace
  - optional icon/module/title
- [ ] Reuse logic from:
  - `sync_sidebar_section_workspace.py`
  - `sync_crm_workspace_sidebar.py`
- [ ] Make scripts idempotent

### Phase 3. Reuse Native Workspace Targets

- [ ] Wire `CRM & Customers` -> `CRM`
- [ ] Wire `Purchasing` -> `Buying`
- [ ] Wire `Warehouse & Stock` -> `Stock`
- [ ] Wire `Manufacturing` -> `Manufacturing`
- [ ] Wire `Gestion de Projets` -> `Projects`

### Phase 4. Create First Custom Workspaces

- [ ] Create `Sales-Orderlift`
- [ ] Create `Finance-Orderlift`
- [ ] Create `Logistics-Orderlift`
- [ ] Create `Policies-Orderlift`

For each workspace:

- [ ] Create/update `Workspace`
- [ ] Create/update `Workspace Shortcut`
- [ ] Build `content` blocks
- [ ] Add sidebar navigation entry
- [ ] Verify route opens under correct sidebar context

### Phase 5. Create Remaining Custom Workspaces

- [ ] `My Work`
- [ ] `Administration`
- [ ] `SAV-Orderlift`
- [ ] `Catalog-Orderlift` (`Items & Price Lists`)
- [ ] `HR-Orderlift`
- [ ] `B2B-Portal-Orderlift`
- [ ] `SIG-Orderlift`

### Phase 6. Simplify Main Dashboard

- [ ] Replace long child link lists with workspace links only
- [ ] Keep `Main Dashboard` as landing hub
- [ ] Remove duplicated detail links once workspaces own them
- [ ] Keep a small number of cross-domain shortcuts only if necessary

### Phase 7. Relax Shell Restrictions

- [ ] Update `orderlift_bundle_20260422.js` route guards to allow target workspaces
- [ ] Decide whether restricted users can access native ERPNext workspaces directly
- [ ] Update workspace dropdown filtering to show approved workspaces
- [ ] Update search filtering to keep approved workspace hits visible

### Phase 8. User Defaults and Redirects

- [ ] Decide whether restricted users still land on `Main Dashboard`
- [ ] If yes, keep `/desk/home-page` landing but make workspace navigation free
- [ ] If no, define role-based default workspace strategy
- [ ] Review:
  - `admin_access.py`
  - `setup_restricted_user.py`
  - `restricted_user_guard.py`

## Per-Workspace Build Checklist

Use this for every section/workspace:

- [ ] Confirm target name
- [ ] Confirm icon/module/title
- [ ] Confirm whether it reuses native workspace or custom one
- [ ] Define shortcut list
- [ ] Define section headers/cards/content blocks
- [ ] Define sidebar link type (`Workspace`, `Page`, `DocType`, `Report`)
- [ ] Add/verify breadcrumbs on custom pages
- [ ] Verify route opens in the correct sidebar context
- [ ] Verify no duplicate link remains in `Main Dashboard`

## Verification Checklist

### Functional

- [ ] `Main Dashboard` loads cleanly
- [ ] Each workspace target opens from the hub
- [ ] `CRM` opens from `Main Dashboard` and keeps CRM sidebar context
- [ ] `Buying` opens from `Main Dashboard`
- [ ] `Stock` opens from `Main Dashboard`
- [ ] `Projects` opens from `Main Dashboard`
- [ ] custom workspaces open without fallback to home page

### Shell / Access

- [ ] Restricted user can open approved workspaces
- [ ] Restricted user is still blocked from undesired admin/build areas
- [ ] Workspace dropdown shows only approved targets
- [ ] Desk search returns approved workspaces only

### UI

- [ ] Breadcrumbs are correct for custom dashboards
- [ ] Sidebar highlights correct active item
- [ ] No orphan/duplicated shortcuts in `Main Dashboard`
- [ ] No `Install Frappe CRM` promo remains where unwanted

### Regression

- [ ] `setup_main_dashboard_sidebar.run` remains idempotent
- [ ] Existing custom dashboards still load
- [ ] No forced `?sidebar=Main+Dashboard` URL injection remains
- [ ] Native desk/home/login still work normally

## Recommended First Execution Slice

Implement in this order:

1. Convert `Main Dashboard` section entries into workspace links for existing native workspaces:
   - `CRM`
   - `Buying`
   - `Stock`
   - `Projects`
   - `Manufacturing`
2. Relax restricted shell guards so those workspaces can actually open
3. Create `Sales-Orderlift`
4. Create `Finance-Orderlift`
5. Create `Logistics-Orderlift`
6. Simplify `Main Dashboard`

This gives the biggest structural improvement early, with the least custom workspace surface area.

## Open Decisions

- [ ] Keep native names (`CRM`, `Buying`, `Stock`) or alias them to branded names?
- [ ] Should `Administration` be one workspace or remain multiple admin links?
- [ ] Should `HR` be one workspace or keep separate HR workspaces plus one hub?
- [ ] Should `Main Dashboard` still show detailed shortcuts after the split, or only top-level workspace entry points?
