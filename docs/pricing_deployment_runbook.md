# Pricing Deployment Runbook

## Pre-Deploy

- Backup site database and files.
- Confirm `GROUP_LINE` (or configured grouped item) exists.
- Ensure Selling Settings contains optional grouped line configuration.

## Staging Validation

1. Run `bench --site <staging-site> migrate`.
2. Run `bench --site <staging-site> clear-cache`.
3. Open one legacy and one new Pricing Scenario.
4. Validate migration created `expenses` rows for old records.
5. Validate Pricing Sheet recalc, queue recalc, and quotation preview.

## UAT Checklist

- Create scenario with mixed expense scopes (unit/line/sheet).
- Create sheet and verify totals and warnings.
- Trigger strict guard and confirm save blocking.
- Generate both detailed and grouped quotations.
- Confirm source metadata fields in quotation lines.

## Production Rollout

1. Put system in low-traffic window.
2. Run `bench --site <prod-site> migrate`.
3. Run `bench --site <prod-site> clear-cache` and `clear-website-cache`.
4. Validate one smoke workflow end-to-end.

## Rollback

- Restore DB backup.
- Run `bench --site <site> migrate` to sync schema after restore.
- Re-validate previous pricing flow.
