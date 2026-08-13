# Canonical Sales Pricing

## Commercial Fields

Orderlift uses one final effective unit price throughout the selling flow.

| Label | Meaning |
|---|---|
| PU List HT | Selling-list reference used to calculate discount |
| PU HT | Final effective unit rate used by ERPNext accounting |
| Remise disponible % | Maximum discount allowed by the pricing policy |
| Remise % | Discount used relative to PU List HT |
| Remise PU HT | Discount amount per unit |
| PT HT | PU HT multiplied by quantity |
| PU TTC | Calculated tax-inclusive unit price |
| PT TTC | Calculated tax-inclusive line total |
| Commission % | Rate from the assigned salesperson's Agent Pricing Rule |
| Commission | Calculated line commission |

Pricing Sheet stores the effective values in `sell_unit_price` and `sell_total`.
Quotation, Sales Order, Delivery Note, and Sales Invoice use native ERPNext
`rate` and `amount`.

The former gross/manual/net fields are removed from active metadata. Migration
backfills the canonical fields before removing legacy Custom Field records.

## Editing Rules

Pricing Sheet and draft Quotation permit editing `PU HT`, `Remise %`, or
`Remise PU HT`. The last edited value drives the other two values.

```text
if PU HT >= PU List HT:
    Remise % = 0
    Remise PU HT = 0
else:
    Remise PU HT = PU List HT - PU HT
    Remise % = Remise PU HT / PU List HT * 100

PT HT = PU HT * Qty
```

Discounts above the policy allowance are rejected unless the user has the
quotation-pricing override capability. Sales Order prices are frozen from the
submitted Quotation. PU TTC and PT TTC are always calculated and read-only.

## Commission

```text
Unused Discount % = max(Remise disponible % - Remise %, 0)

Commission = PU HT * Qty
             * Unused Discount % / 100
             * Agent Commission % / 100
```

There is no separate above-list uplift commission. A PU HT at or above PU List
HT has zero used discount and uses the full available-discount percentage in
the commission formula.

## Precision

- Pricing calculations and database fields use up to nine decimal places.
- Values are never rounded to cents before persistence or document mapping.
- Custom grids display two decimals while unfocused.
- Editable controls expose the raw high-precision value.
- Print formats display two decimals without changing stored values.
- Payment allocation and statutory settlement rounding remain separate from
  source unit-price calculations.

MariaDB transaction rates use `DECIMAL(21,9)`. Values saved before this change
may already have lost precision and cannot be reconstructed.

## Role Visibility

Normal users see commercial fields, discounts, tax-inclusive totals, and
commission snapshots. Privileged pricing users additionally see buying cost,
loaded cost, target margin, and actual margin. Policy provenance, benchmark,
customs, transport, and margin-basis diagnostics remain available as advanced
or reporting fields instead of default grid columns.
