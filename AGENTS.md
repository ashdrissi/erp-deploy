# AGENTS.md

## Purpose
- This repository is a Dockerized Frappe/ERPNext bench deployment with custom apps under `apps/`.
- Main active apps: `apps/orderlift`, `apps/custom_desk_theme`, and `apps/infintrix_theme`.
- Treat the repo root as deployment orchestration; most app code changes happen inside app directories.
- Prefer minimal, targeted edits. The worktree may contain unrelated user changes.

## Rule Sources
- No repo-level Cursor rules were found in `.cursor/rules/`.
- No `.cursorrules` file was found.
- No Copilot instructions were found in `.github/copilot-instructions.md`.
- If any of those files are added later, treat them as higher-priority repository guidance.

## Repository Map
- `docker-compose.yml`: production-ish stack for app, backend, websocket, workers, scheduler, MariaDB, and Redis.
- `docker-compose.dev.yml`: development stack with bind-mounted apps for fast iteration.
- `scripts/dev.sh`: quick helper for rebuild, migrate, restart, shell, and logs.
- `scripts/create-site.sh`: site bootstrap, app install, asset build, and cache clear logic.
- `scripts/prepare_erpnext_imports.py`: generates ERPNext import CSVs from the pricing workbooks under `docs/data/`.
- `apps/orderlift/orderlift/scripts/import_generated_catalog.py`: imports generated catalog CSVs into ERPNext in master-data order.
- `apps/orderlift/orderlift/scripts/import_item_packaging_profiles.py`: imports packaging profiles from `logistique_export.csv`, creates missing UOMs, and updates item HS codes.
- `apps/orderlift/orderlift/scripts/setup_workbook_pricing_policies.py`: seeds workbook-derived customs, scenario, and passive benchmark policy records and can verify parity against imported price lists.
- `apps/orderlift/orderlift/scripts/import_workbook_dimensioning_set.py`: parses the pricing workbook formulas and upserts the dynamic Ascenseur Complet Dimensioning Set.
- `apps/orderlift/orderlift/orderlift_crm/page/opportunity_pipeline`: custom Opportunity kanban using native `Opportunity.sales_stage` as the main editable status.
- `apps/orderlift/orderlift/orderlift_crm/page/project_pipeline`: custom Project kanban using `Project.custom_project_status` as the main editable status.
- `apps/orderlift/orderlift/orderlift_crm/page/sales_order_pipeline`: custom Sales Order kanban using `Sales Order.custom_orderlift_order_status` as the main editable status.
- `apps/orderlift/orderlift/orderlift_crm/page/status_control`: editable status control page for Opportunity, Project, Sales Order, and Forecast Load Plan workflow statuses.
- `apps/orderlift/orderlift/orderlift_crm/page/campaign_editor` and `campaign_manager`: Partner Campaign builder/manager. `campaign_action_type` contains peer values (`Email`, `WhatsApp`, `Call`, `Visit`, `Other`); native `default_channel` stays channel-only (`Email`, `WhatsApp`, `Call`, or blank). The Content tab shows only the selected campaign action type. Email uses ERPNext/Frappe Email Queue, WhatsApp supports manual click-to-chat plus Twilio/custom webhook automated templates, Visit creates target ToDos, and Other is notes-only.
- `apps/orderlift/orderlift/orderlift_sales/page/pricing_sheet_manager`: independent custom Pricing Sheet landing page for opening/creating sheets without the native ERPNext list/form UI.
- `apps/orderlift/orderlift/orderlift_sales/page/pricing_sheet_builder`: independent custom Pricing Sheet builder page for setup, line building, dimensioning insertion, bundle import, recalculation, and quotation generation.
- `apps/orderlift/orderlift/orderlift_finance/account_governance.py`: minimal backend account defaults, Account edit restriction, and invoice/payment account defaulting/protection. Native finance documents stay visible; backend account fields are superadmin-only.
- `apps/orderlift/orderlift/orderlift_logistics/page/logistics_pipeline`: container-first Forecast Load Plan pipeline using logistics lifecycle statuses.
- `apps/orderlift`: main business logic app; Python-heavy with `unittest` coverage.
- `apps/custom_desk_theme`: small Frappe desk theme app with vanilla JS assets.
- `apps/infintrix_theme`: Frappe theme app with Ruff, pre-commit, and a React/Vite sidebar package.
- `docs/`: operational and pricing guides; update when behavior or rollout steps change.

## Working Context
- On the host, this repo lives at `/root/erp-deploy`.
- In containers, the bench lives at `/home/frappe/frappe-bench`.
- Bench commands usually need to run inside the app container, not on the host.
- App source is bind-mounted in dev for `orderlift` and `custom_desk_theme`; theme frontend assets may still require rebuilds.

## Runtime Targets
- Confirm the target host before running operational commands.
- Production host is `erp.ecomepivot.com` and is routed by the production `backend` service from `docker-compose.yml`.
- Dev host is `erp-dev.ecomepivot.com` and is routed by the dev `backend` service from `docker-compose.dev.yml`.
- Do not assume the first `app-*` container is the right one when both stacks are running.
- Identify the correct backend container with:
  `docker inspect <backend-container> --format '{{json .Config.Labels}}'`
- Match the Traefik host rule:
  `traefik.http.routers.erp-https.rule=Host(\`erp.ecomepivot.com\`)` for production.
- Once the backend container is identified, use the matching `app` container from the same Compose project for `bench` commands.
- In this environment, the production pair is currently named like `backend-cs08...` and `app-cs08...`.

## Preferred Command Entry Points
- Start by choosing the narrowest command that proves your change.
- For Frappe app changes, prefer `docker exec <app-container> bash -lc "cd /home/frappe/frappe-bench && ..."`.
- For frontend work in `infintrix_theme/public/js/sidebar_menu`, run Node commands from that package directory.
- Use `./scripts/dev.sh` for common local workflows when it matches the task.
- For pricing workbook import prep, use `python3 scripts/prepare_erpnext_imports.py --dry-run` to verify counts, then rerun without `--dry-run` to write CSVs under `docs/data/generated`.
- To load the generated catalog into the live site, copy `docs/data/generated` into the app container and run `bench --site <site> execute orderlift.scripts.import_generated_catalog.run --kwargs '{"import_dir": "/tmp/orderlift-import"}'`.
- To load packaging profiles from `logistique_export.csv` into the live site, copy the CSV into the app container and run `bench --site <site> execute orderlift.scripts.import_item_packaging_profiles.run --kwargs '{"import_file": "/tmp/logistique_export.csv", "dry_run": 1}'`, then rerun with `"dry_run": 0` after reviewing the summary.
- To seed workbook-derived pricing policy records, run `bench --site <site> execute orderlift.scripts.setup_workbook_pricing_policies.run` and verify with `bench --site <site> execute orderlift.scripts.setup_workbook_pricing_policies.verify`.
- To update `Item.custom_customs_material` from a materials workbook with columns `ITEM CATEGORY`, `ITEM GROUP`, `ITEM NAME FR`, and `DOUANE MATERIAL`, copy the workbook into the app container and run dry-run first: `bench --site <site> execute orderlift.scripts.sync_customs_material_values.sync_item_customs_materials --kwargs '{"workbook_path":"/tmp/materials.xlsx","sheet_name":"Database","dry_run":1}'`, then rerun with `"dry_run":0` after reviewing unmatched, ambiguous, and conflict samples.
- To stamp existing selling Price Lists/Item Prices with Pricing Builder source and max-discount metadata, run dry-run first: `bench --site <site> execute orderlift.scripts.backfill_pricing_builder_selling_list_stamps.run --kwargs '{"price_list":"<Selling Price List>","dry_run":1}'`, then rerun with `"dry_run":0`; use `"update_prices":1` only when the current selling rates should be recalculated from the builder.
- To import the dynamic workbook-derived Ascenseur Complet Dimensioning Set, copy the `.xlsm` into the app container and run `bench --site <site> execute orderlift.scripts.import_workbook_dimensioning_set.run --kwargs '{"workbook_path":"/tmp/Pricing & Edition Devis_V01.2026 (1).xlsm","target_name":"DSET-00038","dry_run":1}'`, then rerun with `"dry_run":0` after reviewing counts.
- To seed SIG demo projects and QC data, run `bench --site <site> execute orderlift.orderlift_sig.utils.demo_seed.seed_demo_data`.
- To seed live logistics demo flows (inbound, domestic, outbound customer-managed, outbound Orderlift-managed), run `bench --site <site> execute orderlift.scripts.seed_logistics_demo_flows.run --kwargs '{"company":"Orderlift","batch_key":"DEMO-LOG-YYYYMMDD"}'` and use `scenarios` to limit reruns, e.g. `{"company":"Orderlift","batch_key":"DEMO-LOG-YYYYMMDD","scenarios":"outbound_customer,outbound_orderlift"}`.
- To import B2C opportunity workbook rows from `Suivi Projets B2C (1).xlsx`, copy the workbook into the app container and run dry-run first: `bench --site <site> execute orderlift.scripts.import_b2c_opportunities.run --kwargs '{"workbook_path":"/tmp/Suivi Projets B2C (1).xlsx","dry_run":1}'`, then rerun with `"dry_run":0` after reviewing counts and warnings.

## Build Commands
- Dev stack: `docker compose -f docker-compose.dev.yml up -d`
- Full stack: `docker compose up -d`
- Rebuild all bench assets in container: `bench build`
- Rebuild one Frappe app: `bench build --app orderlift`
- Rebuild theme app assets quickly: `./scripts/dev.sh build-theme`
- Rebuild all app assets quickly: `./scripts/dev.sh build-all`
- Restart app container after Python-only changes: `./scripts/dev.sh restart`
- Run migrations after schema or fixture changes: `./scripts/dev.sh migrate`
- Open shell in running app container: `./scripts/dev.sh shell`

## Build Vs Restart Vs Migrate
- Python-only logic changes in `apps/orderlift` usually need an app container restart, not a migration.
- `hooks.py` changes are not schema changes, but they often require cache clearing and an app restart before Frappe reloads hook metadata.
- DocType JSON, fixtures, custom fields, property setters, patches, or `after_migrate` changes require `bench --site <site> migrate`.
- Direct `orderlift/public/js/*.js` and `orderlift/public/css/*.css` edits are served as static app assets and often do not need `bench build`.
- `custom_desk_theme` asset changes usually need `bench build --app custom_desk_theme`.
- `infintrix_theme` sidebar changes need `npm run build` in `apps/infintrix_theme/infintrix_theme/public/js/sidebar_menu`.
- If a workflow depends on `app_include_js`, `doctype_js`, or `app_include_css`, treat it as a hook-cache problem first, not a migration problem.
- Production images expose the base image's nvm-managed `node`, `npm`, and `yarn` through `/usr/local/bin`; if `bench migrate` or `bench build` reports missing `node`, verify those symlinks first.

## Live Apply Decision Table
- In this deployment, app code under `/root/erp-deploy/apps/...` is usually mounted into the live Coolify containers.
- That means you normally do **not** need to specify individual files when applying local changes.
- Edit the local files first, then run the narrowest bench/cache/restart action that matches the type of change.

| Changed | Run | Notes |
|---|---|---|
| Python logic only (`*.py`) | Clear cache + restart `app/backend/websocket` | No `migrate` needed unless schema or fixtures changed |
| `hooks.py`, `doctype_js`, page wiring | Clear cache + clear hook cache + restart `app/backend/websocket` | Full Desk reload afterward |
| Existing `orderlift/public/js/*` or `orderlift/public/css/*` | Clear cache first; restart if still stale | Usually no `bench build` needed |
| DocType JSON, fixtures, custom fields, property setters, patches | `bench --site <site> migrate` | If migrate reports missing `node`, verify `/usr/local/bin/node` points to the nvm Node binary |
| `setup.py` / `after_migrate` logic | `bench --site <site> migrate` or explicit `bench execute ...after_migrate` | Then clear cache + restart |
| New workspace/sidebar setup logic | Run the setup hook explicitly | Example: `bench --site <site> execute orderlift.scripts.setup_main_dashboard_sidebar.run --kwargs '{"workspace_name":"Main Dashboard"}'` |
| New static file not picked up publicly | Verify public asset URL directly with `curl` | Only use direct file copy/patching if mounted source is not enough |

### CRM Status Model
- `Opportunity.sales_stage` is the single main editable opportunity status for custom CRM pages.
- `Opportunity.status`, `Project.status`, and `Sales Order.status` remain visible ERP legacy statuses; do not overload them with custom workflow labels.
- Project workflow status now lives in `Project.custom_project_status` linked to the `Project Status` setup doctype.
- Sales Order workflow status now lives in `Sales Order.custom_orderlift_order_status` linked to the `Orderlift Order Status` setup doctype.
- Logistics pipeline status uses `Forecast Load Plan.status` with metadata from `Logistics Pipeline Status`; keep lifecycle labels aligned with `forecast_planning.advance_status`.
- Pipeline-assignment ToDos use Eisenhower priority labels: `Important Urgent`, `Important Non Urgent`, `Non Important Urgent`, `Non Important Non Urgent`.
- The `installation-pipeline` route now redirects to `opportunity-pipeline`; use the new route and naming in future changes.

### CRM Classification Model
- CRM classification uses `CRM Business Type` (`Distribution`, `Installation`) and `CRM Segment` (`Grossiste`, `Revendeur`, `Installateur`, `Promoteur`, `Individu`).
- `Lead`, `Prospect`, and `Customer` can have multiple CRM segments through the `custom_crm_segments` child table (`CRM Segment Assignment`).
- `Opportunity` uses one focused flow via `custom_crm_business_type` and `custom_crm_segment`.
- ERPNext `Customer Group` is a hidden technical fallback only; default it to `All Customer Groups` and do not use it for Orderlift business logic, targeting, portal access, pricing, campaigns, segmentation, or logistics decisions.
- Use `CRM Business Type` and `CRM Segment` as the active classification source for customer targeting, portal policies, pricing context, campaigns, segmentation, and pipeline filters.
- Party-level campaign fields (`custom_partner_campaign`, `custom_partner_campaign_target`) are legacy/hidden; campaign history is derived from `Partner Campaign Target` rows.

### Typical Live Apply Flow
1. Edit local files under `/root/erp-deploy/apps/orderlift/...`
2. If schema/fixtures changed: run `bench --site <site> migrate`
3. Clear site cache
4. If hooks changed: clear hook cache
5. Restart `app`, `backend`, and `websocket`
6. Verify route, asset, or DB record

## Lint And Format Commands
- Python lint/format rules are defined only for `apps/infintrix_theme` via Ruff and pre-commit.
- Run pre-commit for that app: `cd apps/infintrix_theme && pre-commit run --all-files`
- Run Ruff lint manually: `cd apps/infintrix_theme && ruff check .`
- Run Ruff import sorting only: `cd apps/infintrix_theme && ruff check . --select I --fix`
- Run Ruff format: `cd apps/infintrix_theme && ruff format .`
- Sidebar package lint: `cd apps/infintrix_theme/infintrix_theme/public/js/sidebar_menu && npm run lint`
- Sidebar package build: `cd apps/infintrix_theme/infintrix_theme/public/js/sidebar_menu && npm run build`
- Sidebar package dev server: `cd apps/infintrix_theme/infintrix_theme/public/js/sidebar_menu && npm run dev`

## Test Commands
- `orderlift` tests are plain `unittest` modules, not pytest.
- Run all discovered `orderlift` tests from app root:
  `cd apps/orderlift && python -m unittest discover -s orderlift/tests -p 'test_*.py'`
- Run one `orderlift` test file:
  `cd apps/orderlift && python -m unittest orderlift.tests.test_pricing_projection`
- Run one `orderlift` test class:
  `cd apps/orderlift && python -m unittest orderlift.tests.test_pricing_projection.TestPricingProjection`
- Run one `orderlift` test method:
  `cd apps/orderlift && python -m unittest orderlift.tests.test_pricing_projection.TestPricingProjection.test_percentage_and_fixed_sequence`
- There is also one standalone module-level test file:
  `cd apps/orderlift && python -m unittest orderlift.test_consolidation`
- Run the SIG unit tests:
  `cd apps/orderlift && python -m unittest orderlift.tests.test_sig_qc orderlift.tests.test_sig_sidebar_setup`
- `infintrix_theme` uses Frappe's test framework for doctype tests.
- Run all tests for that app inside the bench container:
  `bench --site $SITE_NAME run-tests --app infintrix_theme`
- Run a single Frappe test module:
  `bench --site $SITE_NAME run-tests --module infintrix_theme.infintrix_theme.doctype.theme_settings.test_theme_settings`
- After DB-backed changes, also consider `bench --site $SITE_NAME migrate` before running tests.

## When To Run What
- Python business-logic helper change in `orderlift.sales.utils`: run the narrowest `python -m unittest ...` target that covers it.
- Frappe DocType/model/hook change: run the nearest unit test plus a bench migration if schema or fixtures changed.
- `orderlift/public/js/*` or `orderlift/public/css/*` change: clear cache first; only escalate to restart or asset URL bump if the browser still serves stale code.
- `custom_desk_theme` Desk asset change: rebuild that app with `bench build --app custom_desk_theme`.
- React sidebar change in `infintrix_theme`: run `npm run lint` and `npm run build` in the sidebar package.
- Deployment or compose change: validate with the relevant `docker compose` file and note restart/migrate impact.

## Desk Asset And Cache Runbook
- For `apps/orderlift/orderlift/public/js/*` and `apps/orderlift/orderlift/public/css/*`, start by assuming the files are served directly from `/sites/assets/orderlift/...`.
- After changing existing `orderlift` static files, clear site cache before attempting restarts:
  `docker exec <app-container> bash -lc "cd /home/frappe/frappe-bench && bench --site <site> clear-cache && bench --site <site> clear-website-cache"`
- If the change touched `hooks.py` entries like `doctype_js`, `app_include_js`, or `app_include_css`, also clear the Frappe hook cache explicitly:
  `docker exec <app-container> bash -lc "cd /home/frappe/frappe-bench && bench --site <site> console <<'PY'`
  `import frappe`
  `frappe.cache.delete_value('app_hooks')`
  `frappe.clear_cache()`
  `print(frappe.get_hooks('doctype_js').get('Pricing Sheet'))`
  `PY"`
- After hook-cache clearing, restart both the matching `app` and `backend` containers for the target stack.
- For production, prefer restarting the matching `app-cs08...` and `backend-cs08...` pair once cache has been cleared.
- If a browser still shows stale Desk UI after hook and site cache clearing, do a full hard reload of the Desk shell.
- `app_include_js` changes require a full Desk reload, not just navigating between routes inside ERPNext.
- If static assets are still stale by filename, force a new asset URL by introducing a new filename or a new boot wrapper file rather than relying only on query-string changes.
- Before assuming the code is not loading, verify the live asset directly from the public host:
  `curl -s https://erp.ecomepivot.com/assets/orderlift/js/<file>.js`
- If the public host serves the new file but the UI does not change, suspect Frappe hook cache or a full-shell browser cache before suspecting the source edit.

## Python Style Guidelines
- Follow existing Frappe conventions and preserve surrounding style in touched files.
- Use module-level imports at the top unless the file already relies on deferred/local imports.
- Keep imports grouped: stdlib, third-party/Frappe, then local app imports.
- In `apps/infintrix_theme`, Ruff enforces import sorting, double quotes, and a 110-char line length.
- `infintrix_theme` Ruff format uses tabs for indentation; do not normalize those files to spaces.
- In `orderlift`, existing Python files use 4-space indentation; keep that style there.
- Prefer explicit helper names like `resolve_benchmark_margin` over abbreviated names.
- Use `snake_case` for functions, variables, and module names.
- Use `PascalCase` for classes and Frappe `Document` subclasses.
- Keep constants uppercase, e.g. `STATIC_MODE`, `MISSING_BUY_PRICE_MSG`.
- Add type hints when they clarify interfaces; follow existing usage rather than forcing full typing everywhere.
- Use `from __future__ import annotations` only when the file already benefits from it or new types warrant it.
- Prefer small helper functions over deeply nested logic.
- Favor guard clauses and early returns for invalid or empty input.
- Preserve translation wrappers with `from frappe import _` for user-facing strings.
- Use `frappe.throw(...)` for user-facing validation errors, not bare exceptions.
- Include contextual row/item information in raised errors when available.
- Normalize numeric values with Frappe helpers like `flt` and `cint` when reading document fields.
- Normalize optional text with `(value or "").strip()` when behavior depends on clean strings.
- Avoid hidden side effects in utility functions unless the file's pattern already expects mutation.

## JavaScript And TypeScript Style Guidelines
- Match the style of the file you touch; this repo contains both legacy JS and newer TS/React code.
- In the React sidebar package, TypeScript is strict; do not introduce `any` unless unavoidable.
- Prefer `import type` for type-only imports in TS/TSX.
- Use `camelCase` for variables/functions and `PascalCase` for React components/types.
- Keep React components functional and hook-based.
- Compute derived data with hooks like `useMemo` only when it improves clarity or avoids repeat work.
- Handle async calls with explicit `try/catch` and log actionable errors.
- In Frappe form scripts, keep handlers small and move reusable logic into named helper functions.
- Preserve Frappe globals patterns such as `frappe.ui.form.on(...)`, `frappe.call(...)`, and `__()`.
- Do not edit generated bundles like `public/dist/...` or `build/sidebar.js` by hand unless the task explicitly targets built output.
- Rebuild generated assets from source instead.

## Naming And Data Conventions
- Frappe custom fields use the `custom_` prefix; keep that convention for new exported custom fields.
- Many business rules are sequence-driven; preserve `sequence` and `idx` ordering semantics.
- Prefer descriptive names tied to ERP concepts: `pricing_scenario`, `benchmark_policy`, `transport_calc`.
- Keep API payload keys stable once exposed to client-side code.
- When returning dicts to the frontend, use consistent key names and default empty strings/lists where current code does.

## Error Handling And Safety
- Fail loudly on invalid domain input, but keep user-facing messages concise and actionable.
- Aggregate non-fatal warnings into return payloads when the existing API already exposes `warnings`.
- Do not swallow exceptions silently; if caught, log or convert them into explicit warnings/errors.
- Avoid destructive git operations and never revert unrelated user changes.
- Be careful around deployment files, site bootstrap scripts, and anything that can alter the live bench.

## Change Discipline For Agents
- Read nearby files before editing; patterns differ across apps.
- Keep diffs focused and avoid opportunistic refactors.
- Update docs or runbooks when changing operator-facing workflows.
- If you touch schema, fixtures, or hooks, mention migration/rebuild requirements in your handoff.
- If you add a new command or workflow, update this `AGENTS.md` so future agents inherit it.
- Operator-facing SAV/SIG delivery notes now live in `docs/sav_sig_delivery_runbook.md`.
- Operator-facing campaign workflow notes now live in `docs/campaign_workflows.md`.
- Operator-facing role/menu/company access notes now live in `docs/access_command_center_menu_company_access.md`.
- Operator-facing finance account and Cost Center governance notes now live in `docs/finance_account_governance.md`.
