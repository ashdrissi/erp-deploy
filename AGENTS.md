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
- `apps/orderlift`: main business logic app; Python-heavy with `unittest` coverage.
- `apps/custom_desk_theme`: small Frappe desk theme app with vanilla JS assets.
- `apps/infintrix_theme`: Frappe theme app with Ruff, pre-commit, and a React/Vite sidebar package.
- `docs/`: operational and pricing guides; update when behavior or rollout steps change.

## Working Context
- On the host, this repo lives at `/root/erp-deploy`.
- In containers, the bench lives at `/home/frappe/frappe-bench`.
- Bench commands usually need to run inside the app container, not on the host.
- App source is bind-mounted in dev for `orderlift` and `custom_desk_theme`; theme frontend assets may still require rebuilds.

## Preferred Command Entry Points
- Start by choosing the narrowest command that proves your change.
- For Frappe app changes, prefer `docker exec <app-container> bash -lc "cd /home/frappe/frappe-bench && ..."`.
- For frontend work in `infintrix_theme/public/js/sidebar_menu`, run Node commands from that package directory.
- Use `./scripts/dev.sh` for common local workflows when it matches the task.

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
- `infintrix_theme` uses Frappe's test framework for doctype tests.
- Run all tests for that app inside the bench container:
  `bench --site $SITE_NAME run-tests --app infintrix_theme`
- Run a single Frappe test module:
  `bench --site $SITE_NAME run-tests --module infintrix_theme.infintrix_theme.doctype.theme_settings.test_theme_settings`
- After DB-backed changes, also consider `bench --site $SITE_NAME migrate` before running tests.

## When To Run What
- Python business-logic helper change in `orderlift.sales.utils`: run the narrowest `python -m unittest ...` target that covers it.
- Frappe DocType/model/hook change: run the nearest unit test plus a bench migration if schema or fixtures changed.
- Desk JS/CSS change in `orderlift` or `custom_desk_theme`: rebuild the touched app with `bench build --app <app>`.
- React sidebar change in `infintrix_theme`: run `npm run lint` and `npm run build` in the sidebar package.
- Deployment or compose change: validate with the relevant `docker compose` file and note restart/migrate impact.

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
