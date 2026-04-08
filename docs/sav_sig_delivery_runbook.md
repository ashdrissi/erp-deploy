# SAV / SIG Delivery Runbook

## Scope Source

Reference document: `docs/cahier des charges/Phase_4_SAV_SIG.docx`

High-level scope captured there:

- SAV
  - anomaly declaration
  - ticket creation
  - assignment
  - mandatory closure
- SIG
  - geolocation
  - project status tracking
  - quality-control forms

## Delivered Interpretation

### SAV

Delivered in this phase:

- `SAV Ticket` doctype for anomaly declaration and ticket lifecycle
- status workflow: `Open -> Assigned -> In Progress -> Resolved -> Closed`
- mandatory resolution report before resolution/closure
- technician assignment flow and notification
- rejection flow from `Resolved` back to `In Progress`
- `reported_via` channel classification: `Appel`, `Portail`, `Email`, `WhatsApp`
- `SAV Dashboard` desk page

Clarified scope interpretation:

- The wording "appel ou application" is implemented in this phase as Desk-based ticket capture plus channel tracking via `reported_via`.
- A separate customer-facing/mobile SAV intake application is not part of the delivered Phase 4 source unless explicitly added later.

### SIG

Delivered in this phase:

- Project custom fields for site/install context and QC checklisting
- QC template doctypes and template duplication
- geolocation fields and desk map page
- project QC status tracking and completion guard
- Sales Order to installation Project linkage
- `SIG Dashboard`, `Project Map`, and `Mobile QC` desk pages
- Main Dashboard sidebar/workspace registration

## Production Pages

- `/app/sav-dashboard`
- `/app/sig-dashboard`
- `/app/project-map`
- `/app/sig-qc`

## Deployment Runbook

### Normal deployment path

Use the standard Coolify redeploy/bootstrap path so migrations and asset-related steps run in the deployment image.

Required after source changes that touch doctypes, fixtures, hooks, or pages:

```bash
bench --site <site> migrate
```

Then clear cache / restart the desk services if needed.

### Important environment note

The production `app` container may not have `node` available for manual `bench build` or some migrate-time asset operations triggered by other apps/themes.

Implications:

- prefer the normal deploy/bootstrap container for full redeploys
- do not rely on ad-hoc `bench build` inside the long-running production `app` container
- `orderlift/public/js/*` and `orderlift/public/css/*` changes are static assets and normally do not require a dedicated `bench build`

### Post-deploy checks

1. Verify desk pages load:
   - `/app/sig-dashboard`
   - `/app/project-map`
   - `/app/sig-qc`
   - `/app/sav-dashboard`
2. Verify `Main Dashboard` sidebar links route correctly.
3. Verify `Project` form shows:
   - `SIG - Site & Installation` tab
   - `QC Checklist` tab
4. Verify map tiles and markers render.
5. Verify Mobile QC saves remarks and verification state.

## Acceptance Checklist

### SAV

1. Create a new `SAV Ticket`.
2. Set `reported_via`.
3. Assign a technician.
4. Move to `In Progress`.
5. Attempt resolution without `resolution_report` and confirm it is blocked.
6. Add report, resolve, then close.
7. Reject closure from `Resolved` and confirm it returns to `In Progress`.

### SIG

1. Open a submitted Sales Order and create an installation Project.
2. Open the linked Project and apply a QC template.
3. Confirm `Project` tabs render correctly.
4. Toggle checklist items and confirm `custom_qc_status` recalculates.
5. Attempt to complete a Project with incomplete QC and confirm it is blocked.
6. Open `/app/project-map` and verify project markers render.
7. Open `/app/sig-dashboard` and verify KPI/cards/tables load.
8. Open `/app/sig-qc`, edit remarks, save, and confirm the remarks persist after reload.

## Demo Data

Demo data can be seeded with:

```bash
bench --site <site> execute orderlift.orderlift_sig.utils.demo_seed.seed_demo_data
```

This creates:

- one demo QC template
- four demo Projects covering `Not Started`, `In Progress`, `Blocked`, and `Complete`

## Automated Verification Targets

Run from `apps/orderlift`:

```bash
python -m unittest orderlift.tests.test_sig_qc
python -m unittest orderlift.tests.test_sig_sidebar_setup
```

Recommended broader run:

```bash
python -m unittest discover -s orderlift/tests -p 'test_*.py'
```
