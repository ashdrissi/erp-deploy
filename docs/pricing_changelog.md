# Pricing Changelog

## 2026-06-02

- Added company-tabbed `Customer Segmentation Engine` page under Policies & Configs.
- Moved global tier and territory modifiers out of active Benchmark Policy editing and into company segmentation engines.
- Pricing Sheet static and dynamic modes now resolve tier/territory modifiers from the Customer Segmentation Engine.
- Static Pricing Sheet mode supports ordered selling Price List selections; the first selected list containing the Item wins.
- Migration creates missing company segmentation engines and copies legacy Benchmark Policy modifier rows without deleting the old rows.

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
