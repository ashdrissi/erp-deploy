# Pricing Sales Guide

## Daily Workflow

1. Open or create a `Pricing Scenario`.
2. Add expenses in business order (sequence).
3. Create `Pricing Sheet`, select customer + scenario.
4. Add lines manually or through `Add from Bundle`.
5. Use `Recalculate` or `Queue Recalculate`.
6. Review warnings and line breakdown details.
7. Use `Generate Quotation` and confirm in preview.

## Practical Tips

- Sales quotations must be priced from an allowed Selling Price List or from a Pricing Sheet policy snapshot.
- A manual item rate cannot go below the allowed net price after the item's max-discount policy.
- When multiple Selling Price Lists are selected on a Quotation, use `Selling Price List Used` on the item row to choose which selected list supplies that item's price.
- If selected Selling Price Lists change, the Quotation rows are repriced from the remaining selected lists; stale net prices below the remaining list floor must be recalculated before saving.
- Use print format `Orderlift Quotation PU HT` when item unit prices are HT and totals should show HT, taxes, then TTC.
- Use print format `Orderlift Quotation PU TTC` when item unit prices should display TTC; totals show TTC, taxes from the selected tax template, then HT. Without a tax template, PU TTC equals PU HT.
- The company default `Sales Taxes Template` is applied automatically to new Pricing Sheets and Quotations. If the company has several active templates, for example VAT 10%, VAT 14%, and VAT 20%, select the needed one from `Sales Taxes Template`; the detailed ERPNext tax table is system-filled from that template.
- Use the read-only `Stock by Warehouse` section on Pricing Sheet and Quotation to review current stock in allowed warehouses for the document company.
- The item-row stock column shows the total stock across those allowed warehouses.
- Keep manual overrides only for exceptions.
- Watch `Expense Impact` to identify major drivers.
- Use grouped output for summarized quotations.
- Use detailed output for technical offers.

## Troubleshooting

- Missing base prices: run `Refresh Base Prices` and verify Item Price setup.
- Strict guard blocks save: adjust margin rules or override logic.
- Grouped quote fails: configure `Pricing Group Line Item` in Selling Settings.
