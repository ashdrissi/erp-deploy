# Item Modeling Summary

Conservative phase-2 modeling guidance generated from the item catalog.

## Counts

- plain_item: `133`
- bundle_candidate: `27`
- bom_review_candidate: `11`

## Guidance

- `plain_item`: import as a normal Item and use directly in pricing/transactions.
- `bundle_candidate`: import as a normal Item first, then review as a possible ERPNext Product Bundle after child items are validated.
- `bom_review_candidate`: import as a normal Item first, then review whether the business wants an assembly/BOM model instead of a simple bundle.

## Important

- These are conservative suggestions only; no bundle or BOM structures were auto-created from the spreadsheet because the files do not provide explicit child-item compositions.

## Image Extraction

- mapped item images: `23`
- unmatched image anchors: `19`
- duplicate image anchors skipped: `3`