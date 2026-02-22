# Pricing Changelog

## 2026-02-22

- Replaced legacy hardcoded pricing blocks with sequential custom expense engine.
- Added expense `sequence` and `scope` model (`Per Unit`, `Per Line`, `Per Sheet`).
- Added projection guardrails: minimum margin and strict mode.
- Added dashboard analytics with expense impact and row breakdown modal.
- Added async recalc endpoint with queue support.
- Added quotation preview before generation.
- Added quotation audit metadata (scenario and override tracking).
- Added migration patch for legacy pricing scenarios.

## Known Limitations

- Percentage scope is intentionally limited to `Per Unit`.
- Grouped quotation line requires existing configured item.
- Server-side benchmark status uses current benchmark list snapshot.
- Full end-to-end tests with Frappe DB fixtures are not yet included.
